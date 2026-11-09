"""FPS via PresentMon (Intel, MIT) — lê os eventos de apresentação de quadros que o próprio Windows publica (ETW).

Não injeta nada no jogo. Precisa do PresentMon (console) e de administrador.
Coloque o PresentMon.exe em %LOCALAPPDATA%\\LolitosControl\\tools\\ ou instale pelo winget."""
from __future__ import annotations

import csv
import io
import shutil
import statistics
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from lolitos.core.system import CREATE_NO_WINDOW, IS_WIN, data_dir

RELEASES = "https://github.com/GameTechDev/PresentMon/releases"


def find_presentmon() -> Path | None:
    tools = data_dir() / "tools"
    tools.mkdir(exist_ok=True)
    for p in sorted(tools.glob("PresentMon*.exe"), reverse=True):
        return p
    w = shutil.which("PresentMon") or shutil.which("PresentMon.exe")
    return Path(w) if w else None


class FpsReader(threading.Thread):
    """Mantém as últimas ~2 s de frametimes do processo e expõe fps / 1% low."""

    def __init__(self, process_name: str):
        super().__init__(daemon=True)
        self.process_name = process_name
        self.frames: deque[tuple[float, float]] = deque(maxlen=4000)  # (t, ms)
        self.proc: subprocess.Popen | None = None
        self.error = ""
        self._stop = threading.Event()

    def run(self):
        exe = find_presentmon()
        if not exe or not IS_WIN:
            self.error = "PresentMon não encontrado"
            return
        args = [str(exe), "--process_name", self.process_name, "--output_stdout", "--stop_existing_session",
                "--session_name", "LolitosFPS", "--no_console_stats", "--terminate_on_proc_exit"]
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         creationflags=CREATE_NO_WINDOW, text=True, bufsize=1)
        except OSError as e:
            self.error = str(e)
            return
        header = None
        col = None
        for line in self.proc.stdout:  # type: ignore[union-attr]
            if self._stop.is_set():
                break
            row = next(csv.reader(io.StringIO(line)), None)
            if not row:
                continue
            if header is None:
                header = row
                for name in ("MsBetweenPresents", "msBetweenPresents", "FrameTime", "MsBetweenDisplayChange"):
                    if name in header:
                        col = header.index(name)
                        break
                if col is None:
                    self.error = "formato do PresentMon não reconhecido"
                    break
                continue
            try:
                ms = float(row[col])
            except (ValueError, IndexError):
                continue
            if 0 < ms < 1000:
                self.frames.append((time.time(), ms))

    def stats(self, window: float = 2.0) -> tuple[float | None, float | None]:
        now = time.time()
        ms = [m for t, m in list(self.frames) if now - t <= window]
        if len(ms) < 3:
            return None, None
        fps = 1000 / statistics.mean(ms)
        worst = sorted(ms, reverse=True)[: max(1, len(ms) // 100)]
        low1 = 1000 / statistics.mean(worst)
        return fps, low1

    def stop(self):
        self._stop.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
