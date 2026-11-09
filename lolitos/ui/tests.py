"""Teste de polling do mouse e testes de monitor em tela cheia (movimento/ghosting, cores, OLED e pixels)."""
from __future__ import annotations

import statistics
import time

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QFrame, QWidget

from lolitos.i18n import tr


# ===================================================================== mouse
class MousePad(QFrame):
    """Área de teste: mede o intervalo entre eventos de movimento (polling rate aproximado)."""

    def __init__(self, on_update=None):
        super().__init__()
        self.setMouseTracking(True)
        self.setMinimumSize(520, 420)
        self.ts: list[float] = []
        self.best = 0.0
        self.events = 0
        self.on_update = on_update
        self.title = tr("Faça círculos rápidos e contínuos aqui dentro")
        self.sub = tr("Uns 5 segundos sem parar. Movimento em linha reta mede o seu braço, não o mouse.")
        t = QTimer(self)
        t.timeout.connect(self._calc)
        t.start(250)

    def mouseMoveEvent(self, e):
        self.ts.append(time.perf_counter())
        self.events += 1
        if len(self.ts) > 4000:
            self.ts = self.ts[-4000:]

    def reset(self):
        self.ts, self.best, self.events = [], 0.0, 0
        if self.on_update:
            self.on_update(0.0, 0.0, 0)

    def _calc(self):
        now = time.perf_counter()
        recent = [t for t in self.ts if now - t < 0.6]
        hz = 0.0
        if len(recent) >= 20:
            gaps = [b - a for a, b in zip(recent, recent[1:]) if 0 < b - a < 0.05]
            if gaps:
                hz = 1 / statistics.median(gaps)
                self.best = max(self.best, hz)
        if self.on_update:
            self.on_update(hz, self.best, self.events)

    def paintEvent(self, _):
        from lolitos.ui.theme import C
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(QColor(C["panel"]))
        pen = p.pen()
        pen.setColor(QColor(C["border2"]))
        pen.setStyle(Qt.DashLine)
        pen.setWidthF(1.2)
        p.setPen(pen)
        p.drawRoundedRect(r, 14, 14)
        cx, cy = r.center().x(), r.center().y() - 30
        pen.setColor(QColor(C["accent"]))
        pen.setWidthF(2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 46, 46)
        p.setPen(QColor(C["accent2"]))
        p.setFont(QFont("Segoe UI", 18))
        p.drawText(QRectF(cx + 20, cy + 18, 30, 30), Qt.AlignCenter, "🖱")
        p.setPen(QColor(C["text"]))
        p.setFont(QFont("Segoe UI", 12, QFont.Bold))
        p.drawText(QRectF(r.left(), cy + 60, r.width(), 26), Qt.AlignCenter, self.title)
        p.setPen(QColor(C["muted"]))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(r.left(), cy + 88, r.width(), 22), Qt.AlignCenter, self.sub)


def mouse_verdict(best: float) -> tuple[str, str]:
    if best >= 900:
        return "ok", "Excelente: 1000 Hz ou mais, ideal para jogos competitivos."
    if best >= 450:
        return "atencao", "Bom: 500 Hz. Se o seu mouse suporta 1000 Hz, ajuste no software do fabricante."
    return "corrigir", "Baixo para jogos. Confira no software do mouse se dá para subir a taxa."


# ===================================================================== monitor
BACKGROUNDS = [
    ("Cinza claro com faixas pretas (recomendado)", "#b4b4b4", True),
    ("Cinza sobre cinza escuro (ghosting em LCD)", "#3c3c3c", False),
    ("Cinza escuro sobre preto (black smearing em VA)", "#000000", False),
    ("Branco e preto sobre cinza 50% (overshoot)", "#808080", False),
]
OBJECTS = ["Bloco", "Soldado (silhueta)", "Xadrez", "Listras verticais"]
OBJ_COLORS = [("Preto e branco", "#101010", "#f5f5f5"), ("Colorido", "#e11d48", "#22d3ee"),
              ("Cinza escuro", "#2a2a2a", "#6a6a6a")]
COLOR_SCREENS = [("Branco", "#ffffff"), ("Preto total (vazamento de luz, IPS glow, clouding)", "#000000"),
                 ("Vermelho", "#ff0000"), ("Verde", "#00ff00"), ("Azul", "#0000ff"), ("Ciano", "#00ffff"),
                 ("Magenta", "#ff00ff"), ("Amarelo", "#ffff00"), ("Cinza 50%", "#808080"), ("Cinza 18%", "#2e2e2e")]


class MonitorTest(QWidget):
    """mode: 'motion' (movimento/ghosting com faixas de 1, 1/2 e 1/4 dos quadros), 'colors' (cores sólidas,
    degradê e degraus de preto) ou 'oled' (preto total + retenção)."""

    def __init__(self, mode="motion", speed=960, obj=0, bg=0, col=0, count=1, bands=True, text=""):
        super().__init__()
        self.setWindowTitle(tr("Chinese Control — Teste de monitor"))
        self.mode = mode
        self.i = 0
        self.x = 0.0
        self.speed = float(speed)
        self.paused = False
        self.obj = obj
        self.bg = bg
        self.col = col
        self.count = count
        self.bands = bands
        self.text_color = text
        self.show_help = True
        self.timer = QElapsedTimer()
        self.timer.start()
        self.last = 0.0
        self.frames: list[float] = []
        self._help_t, self._help = -1.0, ""
        self.setCursor(Qt.BlankCursor)
        if mode == "motion":
            t = QTimer(self)
            t.setTimerType(Qt.PreciseTimer)
            t.timeout.connect(self.update)
            t.start(0)

    # ---------------------------------------------------------------- teclado/mouse
    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape:
            self.close()
        elif self.mode != "motion" and k in (Qt.Key_Right, Qt.Key_Space):
            self.i += 1
        elif self.mode != "motion" and k == Qt.Key_Left:
            self.i -= 1
        elif k == Qt.Key_H:
            self.show_help = not self.show_help
        elif self.mode == "motion":
            if k == Qt.Key_Up:
                self.speed = min(3840, self.speed + 240)
            elif k == Qt.Key_Down:
                self.speed = max(240, self.speed - 240)
            elif k == Qt.Key_Space:
                self.paused = not self.paused
            elif k == Qt.Key_O:
                self.obj = (self.obj + 1) % len(OBJECTS)
            elif k == Qt.Key_B:
                self.bg = (self.bg + 1) % len(BACKGROUNDS)
            elif k == Qt.Key_K:
                self.col = (self.col + 1) % len(OBJ_COLORS)
            elif k == Qt.Key_N:
                self.count = self.count % 3 + 1
            elif k == Qt.Key_R:
                self.speed, self.x, self.frames = 960.0, 0.0, []
        self._help_t = -1.0
        self.update()

    def mousePressEvent(self, e):
        if self.mode != "motion":
            self.i += -1 if e.button() == Qt.RightButton else 1
            self.update()

    def mouseDoubleClickEvent(self, e):
        self.close()

    # ---------------------------------------------------------------- desenho
    def _screens(self):
        if self.mode == "bleed":
            return [("Preto total: procure clarões nos cantos (backlight bleed), IPS glow e manchas (clouding).",
                     "#000000"),
                    ("Cinza muito escuro (5%): manchas e faixas ficam mais visíveis.", "#0d0d0d")]
        if self.mode == "oled":
            return [("Preto total: num OLED a tela inteira deve sumir. Pontos acesos = pixels travados.", "#000000"),
                    ("Cinza 18%: procure contornos da barra de tarefas e HUDs (retenção/burn-in).", "#2e2e2e"),
                    ("Cinza 50%: manchas e faixas (uniformidade).", "#808080"),
                    ("Branco: pontos pretos = pixels mortos.", "#ffffff")]
        return COLOR_SCREENS + [("Degradê de cinza: deve ser suave, sem faixas nem tons coloridos.", "gradient"),
                                ("Degraus de preto (0 a 20 de 255): bons painéis separam os primeiros degraus.",
                                 "steps")]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.mode != "motion":
            screens = self._screens()
            name, col = screens[self.i % len(screens)]
            if col == "gradient":
                g = QLinearGradient(0, 0, self.width(), 0)
                g.setColorAt(0, QColor("#000000"))
                g.setColorAt(1, QColor("#ffffff"))
                p.fillRect(self.rect(), g)
            elif col == "steps":
                w = self.width() / 21
                for v in range(21):
                    p.fillRect(QRectF(v * w, 0, w + 1, self.height()), QColor(v, v, v))
            else:
                p.fillRect(self.rect(), QColor(col))
            if self.show_help:
                p.setPen(QColor("#888888"))
                p.setFont(QFont("Segoe UI", 10))
                p.drawText(20, self.height() - 20, tr(name) + "  ·  " + tr("clique ou → próximo · ← anterior · H "
                                                                         "esconde o texto · Esc ou duplo clique sai"))
            return
        self._paint_motion(p)

    def _paint_object(self, p: QPainter, x: float, y: float, h: float):
        dark, light = QColor(OBJ_COLORS[self.col][1]), QColor(OBJ_COLORS[self.col][2])
        kind = OBJECTS[self.obj]
        w = h * 1.4
        if kind == "Bloco":
            p.fillRect(QRectF(x - w, y, w, h), dark)
            p.fillRect(QRectF(x - w * 0.8, y + h * 0.25, w * 0.25, h * 0.5), light)
        elif kind == "Soldado (silhueta)":
            path = QPainterPath()
            cx = x - w / 2
            path.addEllipse(QPointF(cx, y + h * 0.15), h * 0.12, h * 0.12)
            path.addRoundedRect(QRectF(cx - h * 0.16, y + h * 0.28, h * 0.32, h * 0.42), 6, 6)
            path.addRect(QRectF(cx - h * 0.14, y + h * 0.70, h * 0.10, h * 0.30))
            path.addRect(QRectF(cx + h * 0.04, y + h * 0.70, h * 0.10, h * 0.30))
            path.addRect(QRectF(cx + h * 0.10, y + h * 0.36, h * 0.45, h * 0.06))
            p.fillPath(path, dark)
        elif kind == "Xadrez":
            s = h / 4
            for r in range(4):
                for c in range(int(w / s)):
                    p.fillRect(QRectF(x - w + c * s, y + r * s, s, s), dark if (r + c) % 2 else light)
        else:
            s = w / 10
            for c in range(10):
                p.fillRect(QRectF(x - w + c * s, y, s, h), dark if c % 2 else light)

    def _paint_motion(self, p: QPainter):
        now = self.timer.nsecsElapsed() / 1e9
        dt = now - self.last if self.last else 0
        self.last = now
        if dt:
            self.frames.append(dt)
            self.frames = self.frames[-240:]
        if not self.paused:
            self.x = (self.x + self.speed * dt) % (self.width() + 300)
        name, bgc, bars = BACKGROUNDS[self.bg]
        p.fillRect(self.rect(), QColor(bgc))
        h = self.height()
        fracs = (1, 2, 4) if self.bands else (1,)
        band = h / len(fracs)
        fps = 1 / statistics.mean(self.frames) if self.frames else 0
        for row, frac in enumerate(fracs):
            y0 = row * band
            if bars:
                p.fillRect(QRectF(0, y0 + band - 6, self.width(), 6), QColor("#000000"))
            # 1/2 e 1/4: o objeto só anda a cada 2 ou 4 quadros (simula FPS menor)
            step = self.speed / max(fps, 1) * frac
            x = (self.x // step) * step if frac > 1 and step else self.x
            size = min(band * 0.45, h * 0.2)
            for k in range(self.count):
                self._paint_object(p, x - k * (size * 2.2), y0 + band * 0.22, size)
            p.setPen(QColor(self.text_color) if self.text_color else
                     QColor("#ffffff") if bgc in ("#000000", "#3c3c3c") else QColor("#101010"))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            p.drawText(12, int(y0 + 20), tr(["Quadros cheios", "Metade dos quadros (1/2)",
                                             "Um quarto dos quadros (1/4)"][row]))
        if self.show_help:
            p.setPen(QColor(self.text_color) if self.text_color else
                     QColor("#ffffff") if bgc in ("#000000", "#3c3c3c") else QColor("#101010"))
            p.setFont(QFont("Segoe UI", 10))
            if now - self._help_t > 0.25:     # traduz 4x por segundo, não a cada quadro
                self._help_t = now
                self._help = tr(f"{fps:.0f} quadros/s · {self.speed:.0f} px/s · {self.speed / max(fps, 1):.1f} px "
                                f"por quadro · objeto: {OBJECTS[self.obj]} · fundo: {name}"
                                ) + (tr("  · PAUSADO") if self.paused else "")
            p.drawText(12, h - 34, self._help)
            p.drawText(12, h - 14, tr("Esc sai · ↑/↓ velocidade · Espaço pausa · O objeto · K cores · B fundo · "
                                      "N quantidade · R zerar · H esconde"))
