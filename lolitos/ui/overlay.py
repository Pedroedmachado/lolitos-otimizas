"""Overlay: janela transparente, sempre no topo e que deixa os cliques passarem (nada é injetado no jogo)."""
from __future__ import annotations

import ctypes
import time

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

LABELS = {"fps": "FPS", "frametime": "FRAME", "low1": "1% LOW", "cpu": "CPU", "cpu_temp": "CPU °C",
          "cpu_freq": "CPU CLK", "gpu": "GPU", "gpu_temp": "GPU °C", "gpu_freq": "GPU CLK", "vram": "VRAM",
          "ram": "RAM", "ping": "PING", "game": "JOGO"}


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

    # ---------------------------------------------------------------- dados
    def slow_tick(self):
        from lolitos.ui.widgets import run_async
        items = settings.get("overlay_items")
        if "cpu_temp" in items:
            run_async(lambda: sensors.cpu_temp(3)[0], on_done=lambda v: setattr(self, "cpu_t", v))
        if "ping" in items:
            run_async(self._measure_ping, on_done=lambda v: setattr(self, "ping", v))
        if any(k in items for k in ("fps", "frametime", "low1", "game")):
            self._ensure_fps()

    def _ensure_fps(self):
        """Uma medição para todos os processos; se cair (PresentMon fechou, erro), tenta de novo a cada 20 s."""
        from lolitos.modules.fps import FpsReader, find_presentmon
        r = self.fps_reader
        if r is not None and r.is_alive():
            return
        if r is not None and time.time() - getattr(self, "_fps_started", 0) < 20:
            return
        if not find_presentmon():
            return
        self.fps_reader = FpsReader()
        self._fps_started = time.time()
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
        self.lines = compute_lines(self.fps_reader, self.cpu_t, self.ping)
        self.place()
        self.update()

    def place(self):
        sz = overlay_size(self.lines)
        scr = QApplication.primaryScreen().geometry()
        corner = settings.get("overlay_corner")
        x = scr.left() + 12 if "left" in corner else scr.right() - sz[0] - 12
        y = scr.top() + 12 if "top" in corner else scr.bottom() - sz[1] - 12
        self.setGeometry(x, y, *sz)

    def paintEvent(self, _):
        p = QPainter(self)
        paint_lines(p, self.lines)


# ------------------------------------------------------------------ conteúdo e desenho (overlay e prévia)
OK, MID, BAD, TXT, KEY = "#4ade80", "#f5b82e", "#ff4d5e", "#f2f6fc", "#8fb8de"


def compute_lines(fps_reader, cpu_t, ping) -> list[tuple[str, str, str]]:
    """(rótulo, valor, cor) na ordem escolhida em Configurações › Overlay."""
    items = settings.get("overlay_items")
    g = gpu.read() if any(k.startswith(("gpu", "vram")) for k in items) else {}
    f = low = None
    game = ""
    if fps_reader is not None:
        f, low, game = fps_reader.stats_named()
    out = []
    for k in items:
        v, col = "—", TXT
        if k == "fps":
            if f:
                v, col = f"{f:.0f}", (OK if f >= 60 else MID if f >= 40 else BAD)
            elif fps_reader is None:
                v = "sem PresentMon"
            elif fps_reader.error and not fps_reader.is_alive():
                v, col = "erro", BAD
        elif k == "frametime" and f:
            v = f"{1000 / f:.1f} ms"
        elif k == "low1" and low:
            v = f"{low:.0f}"
        elif k == "cpu":
            v = f"{psutil.cpu_percent():.0f}%"
        elif k == "cpu_temp" and cpu_t:
            v, col = f"{cpu_t:.0f}°C", (BAD if cpu_t > 88 else MID if cpu_t > 80 else OK)
        elif k == "cpu_freq":
            fr = psutil.cpu_freq()
            if fr and fr.current:
                v = f"{fr.current / 1000:.2f} GHz"
        elif k == "gpu" and g.get("util") is not None:
            v = f"{g['util']}%"
        elif k == "gpu_temp" and g.get("temp") is not None:
            v, col = f"{g['temp']}°C", (BAD if g["temp"] > 83 else MID if g["temp"] > 75 else OK)
        elif k == "gpu_freq" and g.get("clock") is not None:
            v = f"{g['clock']} MHz"
        elif k == "vram" and g.get("vram_used"):
            v = f"{g['vram_used'] / 1024**3:.1f}/{g['vram_total'] / 1024**3:.0f} GB"
        elif k == "ram":
            v = f"{psutil.virtual_memory().percent:.0f}%"
        elif k == "ping" and ping:
            v, col = f"{ping:.0f} ms", (OK if ping < 60 else MID if ping < 120 else BAD)
        elif k == "game":
            v = game.rsplit(".", 1)[0] if game else "—"
        if k in LABELS:
            out.append((LABELS[k], v, col))
    return out


def _metrics(lines) -> tuple[float, bool, QFont, QFont]:
    scale = float(settings.get("overlay_scale") or 1.0)
    horiz = settings.get("overlay_layout") == "horizontal"
    fk = QFont("Segoe UI", max(6, int(round(7.5 * scale))), QFont.DemiBold)
    fv = QFont("Segoe UI", max(7, int(round(11 * scale))), QFont.Bold)
    return scale, horiz, fk, fv


def overlay_size(lines) -> tuple[int, int]:
    from PySide6.QtGui import QFontMetrics
    scale, horiz, fk, fv = _metrics(lines)
    mk, mv = QFontMetrics(fk), QFontMetrics(fv)
    n = max(1, len(lines))
    if horiz:
        w = sum(mk.horizontalAdvance(k) + mv.horizontalAdvance(v) + int(22 * scale) for k, v, _ in lines) + 12
        return max(60, w), int(30 * scale)
    kw = max([mk.horizontalAdvance(k) for k, _, _ in lines] or [40])
    vw = max([mv.horizontalAdvance(v) for _, v, _ in lines] or [40])
    return int(kw + vw + 44 * scale), int(14 * scale + 24 * scale * n)


def paint_lines(p: QPainter, lines, rect=None):
    p.setRenderHint(QPainter.Antialiasing)
    scale, horiz, fk, fv = _metrics(lines)
    w, h = overlay_size(lines)
    if rect is not None:
        p.translate(rect.x(), rect.y())
    bg = QColor(5, 11, 22)
    bg.setAlphaF(float(settings.get("overlay_opacity")))
    p.setBrush(bg)
    p.setPen(QColor(30, 155, 255, 60))
    p.drawRoundedRect(0, 0, w - 1, h - 1, 8 * scale, 8 * scale)
    from PySide6.QtGui import QFontMetrics
    mk, mv = QFontMetrics(fk), QFontMetrics(fv)
    if horiz:
        x = 10
        base = int(h / 2 + mv.ascent() / 2 - 2)
        for name, v, col in lines:
            p.setFont(fk)
            p.setPen(QColor(KEY))
            p.drawText(x, base, name)
            x += mk.horizontalAdvance(name) + int(6 * scale)
            p.setFont(fv)
            p.setPen(QColor(col))
            p.drawText(x, base, v)
            x += mv.horizontalAdvance(v) + int(16 * scale)
        return
    y = int(7 * scale)
    row = 24 * scale
    for name, v, col in lines:
        base = int(y + row / 2 + mv.ascent() / 2 - 2)
        p.setFont(fk)
        p.setPen(QColor(KEY))
        p.drawText(int(12 * scale), base, name)
        p.setFont(fv)
        p.setPen(QColor(col))
        p.drawText(int(w - 12 * scale - mv.horizontalAdvance(v)), base, v)
        y += row


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
