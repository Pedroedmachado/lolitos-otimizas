"""Overlay: janela transparente, sempre no topo e que deixa os cliques passarem (nada é injetado no jogo)."""
from __future__ import annotations

import ctypes

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from lolitos.core import settings
from lolitos.core.system import IS_WIN
from lolitos.modules import gpu, sensors

GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x80000, 0x20
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_TOPMOST = 0x80, 0x08000000, 0x8

LABELS = {"fps": "FPS", "cpu": "CPU", "cpu_temp": "CPU °C", "gpu": "GPU", "gpu_temp": "GPU °C", "vram": "VRAM",
          "ram": "RAM", "ping": "PING"}


class Overlay(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                         Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.lines: list[tuple[str, str, str]] = []
        self.fps_reader = None
        self.cpu_t = None
        self.ping = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.slow = QTimer(self)
        self.slow.timeout.connect(self.slow_tick)
        psutil.cpu_percent()

    # ---------------------------------------------------------------- janela
    def showEvent(self, e):
        super().showEvent(e)
        if IS_WIN:
            hwnd = int(self.winId())
            u = ctypes.windll.user32
            style = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
            u.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW |
                             WS_EX_NOACTIVATE | WS_EX_TOPMOST)
        self.timer.start(1000)
        self.slow.start(4000)
        self.tick()
        self.slow_tick()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()
        self.slow.stop()
        if self.fps_reader:
            self.fps_reader.stop()
            self.fps_reader = None

    def place(self):
        items = settings.get("overlay_items")
        h = 14 + 22 * max(1, len(items))
        w = 210
        scr = QApplication.primaryScreen().geometry()
        corner = settings.get("overlay_corner")
        x = scr.left() + 12 if "left" in corner else scr.right() - w - 12
        y = scr.top() + 12 if "top" in corner else scr.bottom() - h - 12
        self.setGeometry(x, y, w, h)

    # ---------------------------------------------------------------- dados
    def slow_tick(self):
        from lolitos.ui.widgets import run_async
        items = settings.get("overlay_items")
        if "cpu_temp" in items:
            run_async(lambda: sensors.cpu_temp(3)[0], on_done=lambda v: setattr(self, "cpu_t", v))
        if "ping" in items:
            run_async(self._measure_ping, on_done=lambda v: setattr(self, "ping", v))
        if "fps" in items and self.fps_reader is None:
            from lolitos.bdo.game import EXE, game_process
            from lolitos.modules.fps import FpsReader, find_presentmon
            if find_presentmon():
                name = EXE if game_process() else (self._running_game_exe() or self._foreground_exe())
                if name:
                    self.fps_reader = FpsReader(name)
                    self.fps_reader.start()

    @staticmethod
    def _running_game_exe() -> str:
        """Executável de um jogo detectado que esteja aberto agora."""
        from lolitos.modules import games
        wanted = {}
        for g in games.all_games(max_age=300):
            for e in g.exes:
                wanted[e.lower()] = e
        for p in psutil.process_iter(["name"]):
            n = (p.info["name"] or "").lower()
            if n in wanted:
                return p.info["name"]
        return ""

    @staticmethod
    def _foreground_exe() -> str:
        if not IS_WIN:
            return ""
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(ctypes.windll.user32.GetForegroundWindow(), ctypes.byref(pid))
        try:
            n = psutil.Process(pid.value).name()
            return "" if n.lower() in ("explorer.exe", "python.exe", "pythonw.exe") else n
        except psutil.Error:
            return ""

    @staticmethod
    def _measure_ping():
        from lolitos.bdo import game as bdo
        conns = bdo.server_connections()
        if conns:
            return bdo.tcp_ping(conns[0].ip, conns[0].port, timeout=1.5)
        from lolitos.modules import netdiag
        st, rtt, _ = netdiag.ping_once(settings.get("ping_target") or "1.1.1.1", 1000)
        return rtt if st == 0 else None

    def tick(self):
        items = settings.get("overlay_items")
        g = gpu.read()
        out = []
        for k in items:
            v, col = "—", "#f2f6fc"
            if k == "fps" and self.fps_reader:
                f, low = self.fps_reader.stats()
                if f:
                    v = f"{f:.0f}  (1% {low:.0f})"
                    col = "#4ade80" if f >= 60 else "#f5b82e" if f >= 40 else "#ff4d5e"
            elif k == "fps":
                v = "PresentMon?"
            elif k == "cpu":
                v = f"{psutil.cpu_percent():.0f}%"
            elif k == "cpu_temp" and self.cpu_t:
                v = f"{self.cpu_t:.0f} °C"
                col = "#ff4d5e" if self.cpu_t > 88 else "#f2f6fc"
            elif k == "gpu" and g.get("util") is not None:
                v = f"{g['util']}%"
            elif k == "gpu_temp" and g.get("temp") is not None:
                v = f"{g['temp']} °C"
                col = "#ff4d5e" if g["temp"] > 83 else "#f2f6fc"
            elif k == "vram" and g.get("vram_used"):
                v = f"{g['vram_used'] / 1024**3:.1f} / {g['vram_total'] / 1024**3:.0f} GB"
            elif k == "ram":
                v = f"{psutil.virtual_memory().percent:.0f}%"
            elif k == "ping" and self.ping:
                v = f"{self.ping:.0f} ms"
                col = "#4ade80" if self.ping < 60 else "#f5b82e" if self.ping < 120 else "#ff4d5e"
            out.append((LABELS[k], v, col))
        self.lines = out
        self.place()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QColor(5, 11, 22)
        bg.setAlphaF(float(settings.get("overlay_opacity")))
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 8, 8)
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        y = 24
        for name, v, col in self.lines:
            p.setPen(QColor("#5cc8ff"))
            p.drawText(10, y, name)
            p.setPen(QColor(col))
            p.drawText(84, y, v)
            y += 22


# ------------------------------------------------------------------ tecla global
MODS = {"ctrl": 0x2, "control": 0x2, "shift": 0x4, "alt": 0x1, "win": 0x8}
NAMED = {"insert": 0x2D, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "pause": 0x13,
         "scrolllock": 0x91}


def parse_hotkey(text: str) -> tuple[int, int] | None:
    parts = [p.strip().lower().replace(" ", "") for p in text.split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    for p in parts[:-1]:
        if p not in MODS:
            return None
        mods |= MODS[p]
    k = parts[-1]
    if k.startswith("f") and k[1:].isdigit() and 1 <= int(k[1:]) <= 24:
        vk = 0x6F + int(k[1:])
    elif len(k) == 1 and k.isalnum():
        vk = ord(k.upper())
    elif k in NAMED:
        vk = NAMED[k]
    else:
        return None
    return mods | 0x4000, vk   # MOD_NOREPEAT


class HotkeyThread:
    """RegisterHotKey numa thread com fila de mensagens própria.

    Evita sobrescrever nativeEvent da janela: isso faria o Python processar TODA mensagem do Windows
    (mouse, pintura...) e travaria a interface quando há trabalho em segundo plano."""

    WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

    def __init__(self, mods: int, vk: int, callback):
        import threading
        self.mods, self.vk, self.callback = mods, vk, callback
        self.ok = False
        self.tid = 0
        self._ready = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def start(self, timeout: float = 1.0) -> bool:
        self._t.start()
        self._ready.wait(timeout)
        return self.ok

    def _run(self):
        from ctypes import wintypes
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        self.tid = k.GetCurrentThreadId()
        self.ok = bool(u.RegisterHotKey(None, 1, self.mods, self.vk))
        self._ready.set()
        if not self.ok:
            return
        msg = wintypes.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == self.WM_HOTKEY:
                try:
                    self.callback()
                except Exception:  # noqa: BLE001
                    pass
        u.UnregisterHotKey(None, 1)

    def stop(self):
        if self.tid:
            ctypes.windll.user32.PostThreadMessageW(self.tid, self.WM_QUIT, 0, 0)
