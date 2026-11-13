"""FPS via PresentMon (Intel, MIT) — lê os eventos de apresentação de quadros que o próprio Windows publica (ETW).

Não injeta nada no jogo e não lê a memória dele: é o mesmo mecanismo que o Windows usa para as ferramentas de
desempenho. Precisa de administrador (o app já roda assim). O PresentMon vem junto no instalador ({app}\\tools);
se faltar, o app baixa a versão fixada abaixo e confere o SHA-256."""
from __future__ import annotations

import csv
import hashlib
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

from lolitos.core.system import CREATE_NO_WINDOW, IS_WIN, data_dir

RELEASES = "https://github.com/GameTechDev/PresentMon/releases"
PM_VERSION = "2.6.0"
PM_URL = f"https://github.com/GameTechDev/PresentMon/releases/download/v{PM_VERSION}/PresentMon-{PM_VERSION}-x64.exe"
PM_SHA256 = "b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af"

# processos que apresentam quadros mas não são jogos
IGNORE = {"dwm.exe", "explorer.exe", "lolitoscontrol.exe", "python.exe", "pythonw.exe", "searchhost.exe",
          "startmenuexperiencehost.exe", "shellexperiencehost.exe", "textinputhost.exe", "applicationframehost.exe",
          "systemsettings.exe", "lockapp.exe", "<unknown>", "<error>"}


def _trusted(p: Path) -> bool:
    """Fora da pasta do app, só roda o PresentMon que confere com o SHA-256 da versão fixada. Ele é aberto como
    administrador, e essas pastas (dados do app, PATH) podem ser alteradas por qualquer programa."""
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest() == PM_SHA256
    except OSError:
        return False


def find_presentmon() -> Path | None:
    """Ordem: o que veio no instalador, o que o app baixou, o que estiver no PATH (os dois últimos, conferidos)."""
    if getattr(sys, "frozen", False):
        for p in sorted((Path(sys.executable).parent / "tools").glob("PresentMon*.exe"), reverse=True):
            return p
    tools = data_dir() / "tools"
    tools.mkdir(exist_ok=True)
    cands = sorted(tools.glob("PresentMon*.exe"), reverse=True)
    w = shutil.which("PresentMon") or shutil.which("PresentMon.exe")
    if w:
        cands.append(Path(w))
    for p in cands:
        if _trusted(p):
            return p
    return None


def download_presentmon(dst: Path | None = None, progress=None) -> Path:
    """Baixa a versão fixada do PresentMon e confere o SHA-256 antes de usar."""
    dst = dst or (data_dir() / "tools" / "PresentMon.exe")
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".part")
    req = urllib.request.Request(PM_URL, headers={"User-Agent": "ChineseControl"})
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            h.update(chunk)
            f.write(chunk)
            if progress:
                progress(f.tell())
    if h.hexdigest() != PM_SHA256:
        tmp.unlink(missing_ok=True)
        raise ValueError("o arquivo baixado não confere (SHA-256 diferente); nada foi instalado")
    tmp.replace(dst)
    return dst


def foreground_pid() -> int:
    if not IS_WIN:
        return 0
    import ctypes
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(ctypes.windll.user32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value


class FpsReader(threading.Thread):
    """Uma sessão do PresentMon para todos os processos; guarda os últimos frametimes de cada um.

    stats() mostra o processo da janela em primeiro plano (o jogo, quando você está jogando) ou, se ele não estiver
    desenhando nada, o que mais apresentou quadros nos últimos segundos."""

    def __init__(self):
        super().__init__(daemon=True)
        self.frames: dict[int, deque] = defaultdict(lambda: deque(maxlen=3000))   # pid -> (t, ms)
        self.names: dict[int, str] = {}
        self.proc: subprocess.Popen | None = None
        self.error = ""
        self.last_line = 0.0
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.taps: list = []        # funções (pid, nome, t, ms) chamadas a cada quadro (ex.: medição antes/depois)

    def run(self):
        exe = find_presentmon()
        if not IS_WIN:
            self.error = "só no Windows"
            return
        if not exe:
            self.error = "PresentMon não encontrado"
            return
        args = [str(exe), "--output_stdout", "--no_console_stats", "--stop_existing_session",
                "--session_name", "ChineseControlFPS", "--no_track_gpu", "--no_track_display", "--no_track_input"]
        for name in ("dwm.exe", "explorer.exe", "ChineseControl.exe", "LolitosControl.exe"):
            args += ["--exclude", name]
        log = data_dir() / "tools" / "presentmon.log"
        try:
            self._err = open(log, "w", encoding="utf-8", errors="replace")
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=self._err,
                                         creationflags=CREATE_NO_WINDOW, text=True, encoding="utf-8",
                                         errors="replace", bufsize=1)
        except OSError as e:
            self.error = str(e)
            return
        header: list[str] | None = None
        c_app = c_pid = c_ms = None
        for row in csv.reader(self.proc.stdout):  # type: ignore[arg-type]
            if self._stop.is_set():
                break
            if not row:
                continue
            if header is None:
                if "Application" not in row:
                    continue          # avisos antes do cabeçalho
                header = row
                c_app, c_pid = header.index("Application"), header.index("ProcessID")
                for name in ("FrameTime", "MsBetweenPresents", "msBetweenPresents", "MsBetweenDisplayChange"):
                    if name in header:
                        c_ms = header.index(name)
                        break
                if c_ms is None:
                    self.error = "formato do PresentMon não reconhecido"
                    break
                continue
            try:
                pid, ms = int(row[c_pid]), float(row[c_ms])
            except (ValueError, IndexError):
                continue
            now = time.time()
            self.last_line = now
            if 0 < ms < 1000:
                with self._lock:
                    self.frames[pid].append((now, ms))
                    self.names[pid] = row[c_app]
                for tap in list(self.taps):
                    try:
                        tap(pid, row[c_app], now, ms)
                    except Exception:  # noqa: BLE001
                        pass
        if self.proc:
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        self._err.close()
        if self.proc and self.proc.poll() is not None and not self.error and not self._stop.is_set():
            try:
                err = log.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                err = ""
            lines = [x for x in err.splitlines() if x.lower().startswith("error")] or err.splitlines()
            self.error = lines[-1][:120] if lines else f"PresentMon fechou (código {self.proc.returncode})"

    def _pick(self, window: float) -> int | None:
        now = time.time()
        with self._lock:
            recent = {pid: sum(1 for t, _ in d if now - t <= window) for pid, d in self.frames.items()}
            names = dict(self.names)
        recent = {p: n for p, n in recent.items() if n >= 3 and names.get(p, "").lower() not in IGNORE}
        if not recent:
            return None
        fg = foreground_pid()
        if fg in recent:
            return fg
        return max(recent, key=recent.get)

    def stats(self, window: float = 2.0) -> tuple[float | None, float | None]:
        fps, low, _ = self.stats_named(window)
        return fps, low

    def stats_named(self, window: float = 2.0) -> tuple[float | None, float | None, str]:
        pid = self._pick(window)
        if pid is None:
            return None, None, ""
        now = time.time()
        with self._lock:
            ms = [m for t, m in self.frames[pid] if now - t <= window]
            name = self.names.get(pid, "")
            # descarta processos que pararam há muito tempo
            for p in [p for p, d in self.frames.items() if d and now - d[-1][0] > 30]:
                del self.frames[p]
                self.names.pop(p, None)
        if len(ms) < 3:
            return None, None, name
        fps = 1000 / statistics.mean(ms)
        worst = sorted(ms, reverse=True)[: max(1, len(ms) // 100)]
        low1 = 1000 / statistics.mean(worst)
        return fps, low1, name

    def stop(self):
        self._stop.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


# ---------------------------------------------------------------- leitor compartilhado
# O PresentMon só aceita uma sessão com o mesmo nome: overlay e medição usam o MESMO leitor. Ele liga quando o
# primeiro pede e desliga quando o último solta.
_SHARED: dict = {"reader": None, "users": set(), "started": 0.0}
_SHARED_LOCK = threading.Lock()


def acquire(user: str) -> FpsReader | None:
    """Leitor de FPS para `user`. Se o PresentMon caiu, tenta de novo (no máximo a cada 20 s).
    None = PresentMon não encontrado."""
    with _SHARED_LOCK:
        _SHARED["users"].add(user)
        r = _SHARED["reader"]
        if r is not None and (r.is_alive() or time.time() - _SHARED["started"] < 20):
            return r
        if not find_presentmon():
            return r
        new = FpsReader()
        if r is not None:
            new.taps = list(r.taps)          # quem estava gravando continua gravando no leitor novo
        _SHARED.update(reader=new, started=time.time())
        new.start()
        return new


def release(user: str) -> None:
    with _SHARED_LOCK:
        _SHARED["users"].discard(user)
        if not _SHARED["users"] and _SHARED["reader"] is not None:
            _SHARED["reader"].stop()
            _SHARED["reader"] = None
