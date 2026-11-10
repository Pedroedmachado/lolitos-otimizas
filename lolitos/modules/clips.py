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
ENCODERS = [  # (nome do ffmpeg, rótulo, argumentos de vídeo)
    ("h264_nvenc", "NVIDIA NVENC", ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "{q}",
                                    "-b:v", "{br}", "-maxrate", "{max}"]),
    ("h264_amf", "AMD AMF", ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "vbr_peak", "-b:v", "{br}",
                             "-maxrate", "{max}"]),
    ("h264_qsv", "Intel Quick Sync", ["-vf", "hwmap=derive_device=qsv,format=qsv", "-c:v", "h264_qsv",
                                      "-preset", "fast", "-b:v", "{br}", "-maxrate", "{max}"]),
    ("libx264", "processador (x264)", ["-vf", "hwdownload,format=bgra,format=yuv420p", "-c:v", "libx264",
                                        "-preset", "veryfast", "-crf", "{q}", "-maxrate", "{max}",
                                        "-bufsize", "{max}"]),
]
QUALITY = {   # rótulo: (cq/crf, bitrate, máximo)
    "alta": (19, "20M", "35M"), "media": (23, "12M", "20M"), "leve": (27, "6M", "10M")}
BUFFER_CHOICES = [15, 30, 60, 120]
CAPTURE = "ddagrab=output_idx={mon}:framerate={fps}"     # fonte de vídeo (troca só nos testes)
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
    cands = [tools_dir() / "ffmpeg.exe",
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
    r = run(["winget", "install", "--id", WINGET_ID, "-e", "--silent", "--scope", "user",
             "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"], timeout=900)
    exe = find_ffmpeg()
    if not exe:
        raise RuntimeError("O winget não conseguiu instalar o ffmpeg: " + (r.err or r.out).strip()[-300:])
    if not has_ddagrab(exe):
        raise RuntimeError("O ffmpeg encontrado é antigo demais (falta a captura ddagrab). Atualize-o pelo winget.")
    say(f"Gravador pronto: {exe}")
    return exe


def pick_encoder(exe: Path, progress=None) -> str:
    """Testa os codificadores da placa de vídeo e fica com o primeiro que funciona neste PC."""
    say = progress or (lambda s: None)
    for name, label, _args in ENCODERS:
        say(f"Testando {label}…")
        args = video_args(name, "media")
        cmd = [str(exe), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
               "ddagrab=output_idx=0:framerate=30", "-t", "1", *args, "-f", "null", "-"]
        r = run(cmd, timeout=40)
        if r.ok:
            say(f"   usando {label}")
            return name
    raise RuntimeError("Nenhum codificador de vídeo funcionou (a captura de tela pode estar bloqueada).")


def video_args(encoder: str, quality: str) -> list[str]:
    q, br, mx = QUALITY.get(quality, QUALITY["media"])
    for name, _label, args in ENCODERS:
        if name == encoder:
            return [a.format(q=q, br=br, max=mx) for a in args]
    return video_args("libx264", quality)


def encoder_label(name: str) -> str:
    return next((label for n, label, _ in ENCODERS if n == name), name)


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
        return GameWin(pid.value, name)
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
    return GameWin(pid.value, name) if full else None


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


def concat(exe: Path, parts: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    r = run([str(exe), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
             "-c", "copy", "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart", str(out)], timeout=300)
    lst.unlink(missing_ok=True)
    if not r.ok or not out.exists():
        raise RuntimeError("não deu para montar o vídeo: " + (r.err or r.out).strip()[-300:])
    return out


def safe_name(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in " -_()").strip() or "Clipe"


class Recorder:
    """Uma sessão de captura (buffer circular) enquanto o jogo está aberto."""

    def __init__(self, exe: Path, game: GameWin, on_event=None):
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
        cmd += ["-f", "lavfi", "-i", CAPTURE.format(mon=int(settings.get("clips_monitor") or 0), fps=fps)]
        vid_in = 1 if self.audio else 0
        cmd += ["-map", f"{vid_in}:v"]
        if self.audio:
            cmd += ["-map", "0:a", "-c:a", "aac", "-b:a", "160k", "-ac", "2"]
        cmd += [*video_args(settings.get("clips_encoder") or "libx264", settings.get("clips_quality") or "media"),
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
        log.info("clipes: buffer iniciado (%s, áudio %s)", self.game.exe, mode)

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
        """Copia para fora do buffer circular os pedaços novos da gravação (uma vez cada)."""
        rec = data_dir() / "clips_rec"
        with self._lock:
            for f, a, _b in self._segments():
                key = (Path(f).name, a)
                if key in self._copied or key in self._before:
                    continue
                rec.mkdir(parents=True, exist_ok=True)
                dst = rec / f"{len(self.rec_parts):06d}.ts"
                try:
                    shutil.copy2(f, dst)
                except OSError:
                    continue
                self._copied.add(key)
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
        out = clips_dir() / f"{safe_name(Path(self.game.exe).stem)} {time.strftime('%Y-%m-%d %H-%M-%S')}.mp4"
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
        out = clips_dir() / (f"{safe_name(Path(self.game.exe).stem)} {time.strftime('%Y-%m-%d %H-%M-%S')} "
                             "(gravação).mp4")
        concat(self.exe, self.rec_parts, out)
        shutil.rmtree(data_dir() / "clips_rec", ignore_errors=True)
        return out


class ClipsService(threading.Thread):
    """Fica de olho no jogo em primeiro plano: liga o buffer quando um jogo aparece e desliga 30 s depois que
    ele sai. Recebe os pedidos das teclas (salvar / gravar)."""

    def __init__(self, on_event=None):
        super().__init__(daemon=True)
        self.on_event = on_event or (lambda kind, msg: None)
        self.rec: Recorder | None = None
        self.recording = False
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

    def status(self) -> str:
        if self.recording:
            return "gravando"
        if self.rec and self.rec.alive():
            return f"buffer ativo · {self.rec.game.exe}"
        return "esperando um jogo"

    def run(self):
        exe = find_ffmpeg()
        if not exe:
            self.on_event("erro", "O gravador não está instalado. Ative os Clipes de novo.")
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

    def _tick(self, exe):
        g = foreground_game()
        now = time.time()
        if g:
            self._last_game = now
            if self.rec and self.rec.alive() and self.rec.game.pid != g.pid and not self.recording:
                self.rec.stop()
                self.rec = None
            if not self.rec or not self.rec.alive():
                self.rec = Recorder(exe, g, self.on_event)
                self.rec.start()
                self.on_event("buffer", f"Clipes prontos em {g.exe} (Alt+Home salva os últimos "
                                        f"{settings.get('clips_seconds') or 30} s)")
        elif self.rec and not self.recording and now - self._last_game > 30:
            self.rec.stop()
            self.rec = None

    def _do(self, job):
        if job == "save":
            if not self.rec or not self.rec.alive():
                self.on_event("aviso", "Nenhum jogo em primeiro plano agora: o buffer está parado.")
                return
            out = self.rec.save_last(int(settings.get("clips_seconds") or 30))
            self.on_event("salvo", str(out))
        elif job == "record":
            if not self.recording:
                if not self.rec or not self.rec.alive():
                    self.on_event("aviso", "Abra o jogo antes de gravar.")
                    return
                self.rec.start_recording()
                self.recording = True
                self.on_event("gravando", "Gravando… (Alt+End de novo para parar)")
            else:
                self.recording = False
                out = self.rec.stop_recording()
                self.on_event("salvo", str(out))
