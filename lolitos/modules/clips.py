"""Clipes: guarda os últimos segundos do jogo (Alt+Home) ou grava enquanto você quiser (Alt+End).

Como funciona:
- O ffmpeg captura a tela pela Duplicação de Área de Trabalho do Windows (ddagrab) e a placa de vídeo codifica
  (NVENC na NVIDIA, AMF na AMD, Quick Sync na Intel; sem nenhum deles, o processador).
- O áudio vem só do jogo (WASAPI por processo; no Windows mais antigo, o som do PC).
- Enquanto um jogo está em primeiro plano, o vídeo fica num buffer circular de pedaços de 1 s no disco. Salvar
  junta os últimos pedaços num .mp4 sem recodificar, então o arquivo sai na hora.
- O ffmpeg só é instalado quando você ativa os Clipes (pelo winget, com o hash conferido pelo próprio winget).
Nada é injetado no jogo."""
from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

from lolitos import APP_NAME
from lolitos.core import settings
from lolitos.core.system import IS_WIN, data_dir, run

log = logging.getLogger("lolitos")
SEG = 1                          # segundos por pedaço do buffer
WINGET_ID = "Gyan.FFmpeg.Essentials"
NO_WINDOW = 0x08000000
ENCODERS = [  # (nome do ffmpeg, rótulo, filtro sem redimensionar, argumentos do codificador)
    ("h264_nvenc", "NVIDIA NVENC", "", ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "{q}",
                                        "-b:v", "{br}", "-maxrate", "{max}", "-bufsize", "{max}"]),
    ("h264_amf", "AMD AMF", "", ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "vbr_peak", "-b:v", "{br}",
                                 "-maxrate", "{max}"]),
    ("h264_qsv", "Intel Quick Sync", "hwmap=derive_device=qsv,format=qsv",
     ["-c:v", "h264_qsv", "-preset", "fast", "-b:v", "{br}", "-maxrate", "{max}"]),
    ("libx264", "processador (x264)", "hwdownload,format=bgra,format=yuv420p",
     ["-c:v", "libx264", "-preset", "veryfast", "-crf", "{q}", "-maxrate", "{max}", "-bufsize", "{max}"]),
]
# qualidade: (cq/crf, Mb/s em 1080p). O bitrate acompanha o tamanho do vídeo.
QUALITY = {"leve": (27, 6), "media": (23, 12), "alta": (19, 20)}
QUALITY_NAMES = [("leve", "Leve"), ("media", "Equilibrada"), ("alta", "Alta")]
BUFFER_CHOICES = [15, 30, 60, 120, 180, 300]
RES_CHOICES = [(720, "720p"), (1080, "1080p"), (1440, "1440p"), (0, "Original")]
CAPTURE = "ddagrab=output_idx={mon}:framerate={fps}{crop}"     # fonte de vídeo (troca só nos testes)
AUDIO_KBPS = 192
NOT_GAMES = {"explorer.exe", "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe", "discord.exe",
             "spotify.exe", "vlc.exe", "mpc-hc64.exe", "obs64.exe", "applicationframehost.exe",
             "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe", "taskmgr.exe",
             "chinesecontrol.exe", "python.exe", "pythonw.exe", "code.exe", "steamwebhelper.exe"}


# ====================================================================== ffmpeg
def tools_dir() -> Path:
    d = data_dir() / "tools"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_ffmpeg() -> Path | None:
    # primeiro a instalação para todos os usuários (Arquivos de Programas: só administradores alteram)
    cands = [Path(os.path.expandvars(r"%ProgramFiles%\WinGet\Links\ffmpeg.exe"))]
    pkgs = os.path.expandvars(r"%ProgramFiles%\WinGet\Packages")
    cands += [Path(p) for p in glob.glob(pkgs + r"\Gyan.FFmpeg*\*\bin\ffmpeg.exe")]
    cands += [tools_dir() / "ffmpeg.exe",
              Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe"))]
    pkgs = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    cands += [Path(p) for p in glob.glob(pkgs + r"\Gyan.FFmpeg*\*\bin\ffmpeg.exe")]
    w = shutil.which("ffmpeg")
    if w:
        cands.append(Path(w))
    for c in cands:
        if c.exists():
            return c
    return None


def has_ddagrab(exe: Path) -> bool:
    r = run([str(exe), "-hide_banner", "-filters"], timeout=20)
    return r.ok and "ddagrab" in r.out


def install_ffmpeg(progress=None) -> Path:
    """Instala o ffmpeg (build oficial do Gyan) pelo winget, só para o usuário atual."""
    say = progress or (lambda s: None)
    exe = find_ffmpeg()
    if exe and has_ddagrab(exe):
        return exe
    if not shutil.which("winget"):
        raise RuntimeError("O winget (Instalador de Aplicativo da Microsoft Store) não está disponível neste "
                           "Windows. Instale-o pela Microsoft Store e tente de novo.")
    say("Baixando o gravador (ffmpeg, ~90 MB) pelo winget…")
    from lolitos.core.system import is_admin
    exe = None
    for scope in (("machine", "user") if is_admin() else ("user",)):   # de preferência em Arquivos de Programas
        r = run(["winget", "install", "--id", WINGET_ID, "-e", "--silent", "--scope", scope,
                 "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"],
                timeout=900)
        exe = find_ffmpeg()
        if exe:
            break
    if not exe:
        raise RuntimeError("O winget não conseguiu instalar o ffmpeg: " + (r.err or r.out).strip()[-300:])
    if not has_ddagrab(exe):
        raise RuntimeError("O ffmpeg encontrado é antigo demais (falta a captura ddagrab). Atualize-o pelo winget.")
    say(f"Gravador pronto: {exe}")
    return exe


def pick_encoder(exe: Path, progress=None) -> str:
    """Testa os codificadores da placa de vídeo e fica com o primeiro que funciona neste PC."""
    say = progress or (lambda s: None)
    for name, label, _f, _args in ENCODERS:
        say(f"Testando {label}…")
        args = video_args(name, "media")
        cmd = [str(exe), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
               "ddagrab=output_idx=0:framerate=30", "-t", "1", *args, "-f", "null", "-"]
        r = run(cmd, timeout=40)
        if r.ok:
            say(f"   usando {label}")
            return name
    raise RuntimeError("Nenhum codificador de vídeo funcionou (a captura de tela pode estar bloqueada).")


def bitrate_mbps(quality: str, height: int) -> float:
    """Bitrate de vídeo para a qualidade e a altura do vídeo (proporcional à área, com base no 1080p)."""
    base = QUALITY.get(quality, QUALITY["media"])[1]
    h = height or 1080
    return round(base * max(0.35, min(4.0, (h / 1080) ** 2)), 1)


def out_height(src_h: int, res: int) -> int:
    """Altura final: a escolhida, sem aumentar quem já é menor ('Original' = a da captura)."""
    if not res or not src_h:
        return src_h
    return min(src_h, res)


def video_args(encoder: str, quality: str, src_h: int = 0, res: int = 0) -> list[str]:
    """Filtro + codificador. Sem redimensionar, a imagem vai direto da placa de vídeo para o codificador.
    Para diminuir (ex.: 1440p → 1080p), a imagem é reduzida antes de codificar."""
    ent = next((e for e in ENCODERS if e[0] == encoder), None) or ENCODERS[-1]
    name, _label, base_filter, args = ent
    h = out_height(src_h, res)
    q = QUALITY.get(quality, QUALITY["media"])[0]
    br = bitrate_mbps(quality, h or src_h)
    vals = {"q": q, "br": f"{br:g}M", "max": f"{round(br * 1.7, 1):g}M"}
    out = []
    if src_h and h and h < src_h:
        fmt = "yuv420p" if name == "libx264" else "nv12"
        out += ["-vf", f"hwdownload,format=bgra,scale=-2:{h}:flags=bicubic,format={fmt}"]
    elif base_filter:
        out += ["-vf", base_filter]
    return out + [a.format(**vals) for a in args]


def buffer_mb(seconds: int, quality: str, height: int) -> int:
    """Quanto o buffer ocupa no disco (aproximado)."""
    return int((bitrate_mbps(quality, height) + AUDIO_KBPS / 1000) * seconds / 8) + 1


def encoder_label(name: str) -> str:
    return next((e[1] for e in ENCODERS if e[0] == name), name)


def clips_dir() -> Path:
    base = settings.get("clips_dir") or ""
    if not base:
        vids = Path(os.path.expandvars(r"%USERPROFILE%\Videos")) if IS_WIN else Path.home() / "Videos"
        base = str(vids / f"{APP_NAME} Clipes")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ====================================================================== jogo em primeiro plano
@dataclass
class GameWin:
    pid: int
    exe: str
    hwnd: int = 0


@dataclass
class Monitor:
    idx: int
    left: int
    top: int
    width: int
    height: int
    primary: bool


def monitors() -> list[Monitor]:
    """Monitores na ordem da captura do Windows (o principal primeiro, depois da esquerda para a direita)."""
    if not IS_WIN:
        return [Monitor(0, 0, 0, 1920, 1080, True)]
    import ctypes
    from ctypes import wintypes

    class MI(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                              wintypes.LPARAM)

    def cb(hmon, _hdc, _rc, _lp):
        mi = MI()
        mi.cbSize = ctypes.sizeof(MI)
        if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            found.append((not (mi.dwFlags & 1), r.left, r.top, r.right - r.left, r.bottom - r.top))
        return 1
    ctypes.windll.user32.EnumDisplayMonitors(None, None, proc(cb), 0)
    found.sort()
    return [Monitor(i, l, t, w, h, not np) for i, (np, l, t, w, h) in enumerate(found)] or \
        [Monitor(0, 0, 0, 1920, 1080, True)]


def client_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Área de desenho da janela (sem bordas e barra de título), em pixels da tela."""
    if not IS_WIN or not hwnd:
        return None
    import ctypes
    from ctypes import wintypes
    r = wintypes.RECT()
    if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(r)):
        return None
    pt = wintypes.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, pt.x + r.right, pt.y + r.bottom


def region(target: str, game: "GameWin | None", mons: list[Monitor], rect=None, mon_choice: int = 0):
    """(índice do monitor, recorte para o ddagrab, altura capturada).

    'window': só a janela do jogo (recortada do monitor onde ela está); 'screen': o monitor inteiro."""
    rect = rect if rect is not None else (client_rect(game.hwnd) if game else None)
    if rect:
        cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        mon = next((m for m in mons if m.left <= cx < m.left + m.width and m.top <= cy < m.top + m.height),
                   mons[0])
    else:
        mon = mons[mon_choice] if 0 <= mon_choice < len(mons) else mons[0]
    if target != "window" or not rect:
        return mon.idx, "", mon.height
    x = max(0, rect[0] - mon.left)
    y = max(0, rect[1] - mon.top)
    w = min(rect[2] - mon.left, mon.width) - x
    h = min(rect[3] - mon.top, mon.height) - y
    w, h = w - w % 2, h - h % 2
    if w < 160 or h < 120 or (w >= mon.width - 1 and h >= mon.height - 1):
        return mon.idx, "", mon.height
    return mon.idx, f":video_size={w}x{h}:offset_x={x}:offset_y={y}", h


def _known_exes() -> set[str]:
    from lolitos.modules import games
    out = {"blackdesert64.exe", "blackdesert32.exe"}
    try:
        for g in games.all_games(max_age=600):
            out |= {e.lower() for e in g.exes}
    except Exception:  # noqa: BLE001
        pass
    return out


def foreground_game() -> GameWin | None:
    """O jogo em primeiro plano: um executável conhecido (biblioteca de Jogos) ou uma janela em tela cheia."""
    if not IS_WIN:
        return None
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        return None
    pid = ctypes.c_ulong()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        name = psutil.Process(pid.value).name()
    except psutil.Error:
        return None
    low = name.lower()
    if low in NOT_GAMES:
        return None
    if low in _known_exes():
        return GameWin(pid.value, name, hwnd)
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    mon = u.MonitorFromWindow(hwnd, 2)

    class MI(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]
    mi = MI()
    mi.cbSize = ctypes.sizeof(MI)
    if not u.GetMonitorInfoW(mon, ctypes.byref(mi)):
        return None
    m = mi.rcMonitor
    full = r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom
    return GameWin(pid.value, name, hwnd) if full else None


# ====================================================================== buffer e gravação
def read_list(path: Path) -> list[tuple[str, float, float]]:
    """Lista de pedaços prontos que o próprio ffmpeg escreve (nome, início, fim), em ordem."""
    out = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.rsplit(",", 2)
            if len(parts) == 3:
                try:
                    out.append((parts[0], float(parts[1]), float(parts[2])))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def pick_last(rows: list[tuple[str, float, float]], seconds: int) -> list[str]:
    """Dos pedaços prontos, os que cobrem os últimos `seconds` (pelo tempo do vídeo, não do arquivo)."""
    if not rows:
        return []
    end = rows[-1][2]
    keep = [r for r in rows if r[1] >= end - seconds - 0.05] or rows[-1:]
    return [r[0] for r in keep]


def join_ts(parts: list[Path], dst: Path, append: bool = False) -> Path:
    """Junta os pedaços byte a byte. Eles vêm de um único fluxo MPEG-TS contínuo, então o resultado é o mesmo
    fluxo sem emendas (o concat 'por arquivo' do ffmpeg recalculava os horários a cada pedaço e deixava
    buraquinhos no áudio — o som pipocava a cada segundo)."""
    with open(dst, "ab" if append else "wb") as out:
        for p in parts:
            with open(p, "rb") as f:
                shutil.copyfileobj(f, out, 1024 * 1024)
    return dst


def remux(exe: Path, ts: Path, out: Path) -> Path:
    """MPEG-TS → MP4 sem recodificar (o arquivo sai na hora)."""
    r = run([str(exe), "-hide_banner", "-loglevel", "error", "-y", "-analyzeduration", "20M", "-probesize", "50M",
             "-fflags", "+genpts", "-i", str(ts), "-map", "0", "-c", "copy", "-bsf:a", "aac_adtstoasc",
             "-movflags", "+faststart", str(out)], timeout=600)
    if not r.ok or not out.exists():
        raise RuntimeError("não deu para montar o vídeo: " + (r.err or r.out).strip()[-300:])
    return out


def concat(exe: Path, parts: list[Path], out: Path) -> Path:
    ts = out.with_suffix(".ts")
    join_ts(parts, ts)
    try:
        return remux(exe, ts, out)
    finally:
        ts.unlink(missing_ok=True)


def safe_name(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in " -_()").strip() or "Clipe"


class Recorder:
    """Uma sessão de captura (buffer circular) enquanto o jogo está aberto."""

    def __init__(self, exe: Path, game: GameWin | None, on_event=None):
        self.exe, self.game = exe, game
        self.on_event = on_event or (lambda kind, msg: None)
        self.buf = data_dir() / "clips_buffer"
        self.proc: subprocess.Popen | None = None
        self.audio = None
        self.recording_since = 0.0
        self.rec_parts: list[Path] = []
        self._copied: set[tuple[str, float]] = set()
        self._before: set[tuple[str, float]] = set()
        self._lock = threading.Lock()
        self._watch: threading.Thread | None = None
        self._stop = threading.Event()

    # -------------------------------------------------------------- ciclo de vida
    def start(self):
        shutil.rmtree(self.buf, ignore_errors=True)
        self.buf.mkdir(parents=True, exist_ok=True)
        fps = int(settings.get("clips_fps") or 60)
        secs = int(settings.get("clips_seconds") or 30)
        wrap = secs // SEG + 4
        audio_mode = settings.get("clips_audio") or "game"      # game | pc | none
        if self.game is None and audio_mode == "game":
            audio_mode = "pc"                                      # sem jogo: o som do PC
        mon, crop, src_h = region(settings.get("clips_target") or "window", self.game, monitors(),
                                  mon_choice=int(settings.get("clips_monitor") or 0))
        self.region_key = (mon, crop)
        from lolitos.modules import procaudio
        cmd = [str(self.exe), "-hide_banner", "-loglevel", "warning", "-y"]
        if audio_mode != "none":
            self.audio = procaudio.AudioCapture(self._feed, self.game.pid if audio_mode == "game" else 0)
            # o formato do áudio só é conhecido depois de ativar o dispositivo
            self.audio.start()
            self.audio.ready.wait(5)
            if self.audio.error and not self.audio.is_alive():
                self.on_event("aviso", f"Sem áudio: {self.audio.error}")
                self.audio = None
        if self.audio:
            cmd += ["-thread_queue_size", "4096", *self.audio.ffmpeg_args, "-i", "pipe:0"]
        cmd += ["-f", "lavfi", "-i", CAPTURE.format(mon=mon, fps=fps, crop=crop)]
        vid_in = 1 if self.audio else 0
        cmd += ["-map", f"{vid_in}:v"]
        if self.audio:
            cmd += ["-map", "0:a", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
        cmd += [*video_args(settings.get("clips_encoder") or "libx264", settings.get("clips_quality") or "media",
                            src_h, int(settings.get("clips_res") if settings.get("clips_res") is not None else 1080)),
                "-g", str(fps * SEG), "-keyint_min", str(fps * SEG),
                "-f", "segment", "-segment_time", str(SEG), "-segment_format", "mpegts",
                "-segment_wrap", str(wrap), "-reset_timestamps", "0",
                "-segment_list", str(self.buf / "list.csv"), "-segment_list_type", "csv",
                "-segment_list_size", str(wrap - 2), str(self.buf / "seg_%03d.ts")]
        logf = open(data_dir() / "clips_ffmpeg.log", "w", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if self.audio else subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=logf,
                                     creationflags=NO_WINDOW if IS_WIN else 0)
        if self.audio:
            self.audio.reset_clock()
        self._watch = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch.start()
        mode = self.audio.mode if self.audio else "sem áudio"
        log.info("clipes: buffer iniciado (%s, %s%s, áudio %s)", self.name, mon, crop, mode)

    @property
    def name(self) -> str:
        return self.game.exe if self.game else "Tela"

    def _feed(self, data: bytes):
        p = self.proc
        if p is None or p.stdin is None:
            return
        try:
            p.stdin.write(data)
        except (OSError, ValueError):
            pass

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        self._stop.set()
        if self.audio:
            self.audio.stop()
        p = self.proc
        if p and p.poll() is None:
            try:
                if p.stdin:
                    p.stdin.close()
            except OSError:
                pass
            try:
                p.terminate()
                p.wait(5)
            except (OSError, subprocess.TimeoutExpired):
                p.kill()
        self.proc = None

    # -------------------------------------------------------------- pedaços
    def _segments(self) -> list[tuple[str, float, float]]:
        """Pedaços prontos (o ffmpeg só põe na lista depois de fechar o arquivo)."""
        return [(str(self.buf / Path(n).name), a, b) for n, a, b in read_list(self.buf / "list.csv")]

    def _collect(self):
        """Acrescenta ao arquivo da gravação os pedaços novos que saíram do buffer circular (uma vez cada, em
        ordem), formando um fluxo contínuo."""
        rec = data_dir() / "clips_rec"
        with self._lock:
            for f, a, _b in self._segments():
                key = (Path(f).name, a)
                if key in self._copied or key in self._before:
                    continue
                rec.mkdir(parents=True, exist_ok=True)
                dst = rec / "gravacao.ts"
                try:
                    join_ts([Path(f)], dst, append=True)
                except OSError:
                    continue
                self._copied.add(key)
                if dst not in self.rec_parts:
                    self.rec_parts.append(dst)

    def _watch_loop(self):
        while not self._stop.wait(0.4):
            if self.recording_since:
                self._collect()

    # -------------------------------------------------------------- ações
    def save_last(self, seconds: int) -> Path:
        time.sleep(SEG + 0.3)            # espera o pedaço atual fechar para incluir o momento do aperto
        parts = [Path(f) for f in pick_last(self._segments(), seconds)]
        if not parts:
            raise RuntimeError("o buffer ainda está vazio (espere alguns segundos de jogo)")
        tmp = data_dir() / "clips_tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        copies = []
        for i, p in enumerate(parts):    # copia antes que o buffer sobrescreva
            dst = tmp / f"{i:04d}.ts"
            shutil.copy2(p, dst)
            copies.append(dst)
        out = clips_dir() / f"{safe_name(Path(self.name).stem)} {time.strftime('%Y-%m-%d %H-%M-%S')}.mp4"
        concat(self.exe, copies, out)
        shutil.rmtree(tmp, ignore_errors=True)
        return out

    def start_recording(self):
        shutil.rmtree(data_dir() / "clips_rec", ignore_errors=True)
        self.rec_parts, self._copied = [], set()
        # tudo que já estava pronto antes do aperto fica de fora; o que fechar daqui em diante entra
        self._before = {(Path(f).name, a) for f, a, _b in self._segments()}
        self.recording_since = time.time()

    def stop_recording(self) -> Path:
        time.sleep(SEG + 0.6)            # o pedaço do momento do aperto fecha e entra na lista
        self.recording_since = 0.0
        self._collect()
        if not self.rec_parts:
            raise RuntimeError("a gravação ficou vazia")
        out = clips_dir() / (f"{safe_name(Path(self.name).stem)} {time.strftime('%Y-%m-%d %H-%M-%S')} "
                             "(gravação).mp4")
        remux(self.exe, self.rec_parts[0], out)
        shutil.rmtree(data_dir() / "clips_rec", ignore_errors=True)
        return out


class ClipsService(threading.Thread):
    """Controla a captura: ligada à mão ('Ligar captura') ou sozinha quando um jogo aparece na tela
    ('Ligar sozinho quando um jogo abrir'), e desligada 30 s depois que o jogo sai. Recebe os pedidos das teclas."""

    def __init__(self, on_event=None):
        super().__init__(daemon=True)
        self.on_event = on_event or (lambda kind, msg: None)
        self.rec: Recorder | None = None
        self.recording = False
        self.manual = False
        self.suppressed_pid = 0      # desligada à mão com um jogo aberto: não religa sozinha até esse jogo fechar
        self._stop = threading.Event()
        self._jobs: list[str] = []
        self._cv = threading.Condition()
        self._last_game = 0.0

    def stop(self):
        self._stop.set()
        with self._cv:
            self._cv.notify()

    def request(self, what: str):
        with self._cv:
            self._jobs.append(what)
            self._cv.notify()

    def set_capture(self, on: bool):
        self.manual = bool(on)
        if not on:
            g = self.rec.game if self.rec and self.rec.game else foreground_game()
            self.suppressed_pid = g.pid if g else 0
        else:
            self.suppressed_pid = 0
        self.request("tick")

    def capturing(self) -> bool:
        return bool(self.rec and self.rec.alive())

    def status(self) -> str:
        if self.recording:
            return "gravando"
        if self.capturing():
            return f"ligada · {self.rec.name}"
        return "desligada"

    def run(self):
        exe = find_ffmpeg()
        if not exe:
            self.on_event("erro", "O gravador não está instalado. Baixe o componente de gravação de novo.")
            return
        while not self._stop.is_set():
            with self._cv:
                self._cv.wait(2)
                jobs, self._jobs = self._jobs, []
            try:
                self._tick(exe)
                for j in jobs:
                    self._do(j)
            except Exception as e:  # noqa: BLE001
                log.exception("clipes")
                self.on_event("erro", str(e))
        if self.rec:
            self.rec.stop()

    def _start(self, exe, game):
        if self.rec:
            self.rec.stop()
        self.rec = Recorder(exe, game, self.on_event)
        self.rec.start()
        key = settings.get("clips_key_save") or "Alt+Home"
        self.on_event("buffer", f"Captura ligada em {self.rec.name} ({key} salva os últimos "
                                f"{settings.get('clips_seconds') or 30} s)")

    def _tick(self, exe):
        g = foreground_game()
        now = time.time()
        if g:
            self._last_game = now
        auto = settings.get("clips_auto", True)
        recent = g is not None or (self.rec is not None and self.rec.game is not None
                                   and now - self._last_game < 30)
        if self.suppressed_pid and not psutil.pid_exists(self.suppressed_pid):
            self.suppressed_pid = 0
        suppressed = bool(self.suppressed_pid) and (g is None or g.pid == self.suppressed_pid)
        want = self.manual or (auto and recent and not suppressed)
        if not want:
            if self.rec and not self.recording:
                self.rec.stop()
                self.rec = None
                self.on_event("estado", "")
            return
        if self.recording:                     # nunca troca no meio de uma gravação
            return
        if not self.capturing():
            self._start(exe, g or (self.rec.game if self.rec else None))
            return
        cur = self.rec.game
        if g and (cur is None or cur.pid != g.pid):
            self._start(exe, g)                # outro jogo na frente
            return
        if g and (settings.get("clips_target") or "window") == "window":
            mon, crop, _h = region("window", g, monitors(), mon_choice=int(settings.get("clips_monitor") or 0))
            if (mon, crop) != getattr(self.rec, "region_key", None):
                self._start(exe, g)            # a janela do jogo mudou de tamanho ou de lugar

    def _do(self, job):
        if job == "tick":
            self.on_event("estado", "")
            return
        if job == "save":
            if not self.capturing():
                self.on_event("aviso", "A captura está desligada: ligue em Clipes (ou abra um jogo com a captura "
                                       "automática ligada).")
                return
            out = self.rec.save_last(int(settings.get("clips_seconds") or 30))
            self.on_event("salvo", str(out))
        elif job == "record":
            if not self.recording:
                if not self.capturing():
                    self.on_event("aviso", "Ligue a captura (ou abra o jogo) antes de gravar.")
                    return
                self.rec.start_recording()
                self.recording = True
                key = settings.get("clips_key_record") or "Alt+End"
                self.on_event("gravando", f"Gravando… ({key} de novo para parar)")
            else:
                self.recording = False
                out = self.rec.stop_recording()
                self.on_event("salvo", str(out))
