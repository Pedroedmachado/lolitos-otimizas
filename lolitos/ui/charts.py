"""Desenhos do Painel: velocímetro da pontuação, anel de uso, gráfico de linha e a arte de circuito do cabeçalho."""
from __future__ import annotations

import math
import random
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from lolitos.ui.icon import l_path
from lolitos.ui.theme import C


class Speedometer(QWidget):
    """Arco de 0 a 100 com degradê vermelho → amarelo → azul, marcações e ponteiro."""

    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setMinimumSize(300, 230)

    def set(self, v: float):
        self.value = max(0.0, min(100.0, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height() * 1.25)
        r = side * 0.42
        cx, cy = self.width() / 2, self.height() * 0.58
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        start, span = 225, -270           # graus Qt (anti-horário a partir das 3h)
        # fundo do arco
        p.setPen(QPen(QColor(C["panel2"]), r * 0.16, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(rect, start * 16, span * 16)
        # arco colorido
        g = QConicalGradient(QPointF(cx, cy), 225)
        # o degradê cônico corre no sentido anti-horário; o arco, no horário: posição = 1 - (fração × 270/360)
        for t, col in ((0.0, "#ff3b5c"), (0.22, "#ff8a3d"), (0.45, "#f5d13b"), (0.72, "#5cc8ff"), (1.0, "#1e9bff")):
            g.setColorAt(1 - t * 0.75, QColor(col))
        g.setColorAt(0.0, QColor("#ff3b5c"))
        pen = QPen(g, r * 0.16, Qt.SolidLine, Qt.FlatCap)
        p.setPen(pen)
        p.drawArc(rect, start * 16, int(span * 16 * self.value / 100))
        # marcações e números
        p.setFont(QFont("Segoe UI", max(7, int(r * 0.075)), QFont.Bold))
        for i in range(0, 101, 5):
            ang = math.radians(225 - 270 * i / 100)
            big = i % 20 == 0
            r1, r2 = r * 0.72, r * (0.62 if big else 0.67)
            p.setPen(QPen(QColor(C["text"] if big else C["muted"]), 2 if big else 1))
            p.drawLine(QPointF(cx + r1 * math.cos(ang), cy - r1 * math.sin(ang)),
                       QPointF(cx + r2 * math.cos(ang), cy - r2 * math.sin(ang)))
            if big:
                rt = r * 0.5
                p.setPen(QColor(C["text"]))
                p.drawText(QRectF(cx + rt * math.cos(ang) - 16, cy - rt * math.sin(ang) - 9, 32, 18),
                           Qt.AlignCenter, str(i))
        # ponteiro
        ang = math.radians(225 - 270 * self.value / 100)
        tip = QPointF(cx + r * 0.82 * math.cos(ang), cy - r * 0.82 * math.sin(ang))
        p.setPen(QPen(QColor("#ffffff"), max(3, r * 0.03), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx, cy), tip)
        p.setPen(QPen(QColor(C["accent2"]), 3))
        p.setBrush(QColor(C["panel"]))
        p.drawEllipse(QPointF(cx, cy), r * 0.1, r * 0.1)
        p.setBrush(QColor(C["accent2"]))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 0.045, r * 0.045)


class Ring(QWidget):
    """Anel de uso com o valor no centro."""

    def __init__(self, caption: str = ""):
        super().__init__()
        self.value, self.text, self.caption = 0.0, "—", caption
        self.setFixedSize(150, 150)

    def set(self, frac: float, text: str, caption: str | None = None):
        self.value = max(0.0, min(1.0, frac))
        self.text = text
        if caption is not None:
            self.caption = caption
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(12, 12, self.width() - 24, self.height() - 24)
        p.setPen(QPen(QColor(C["panel2"]), 12, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 0, 360 * 16)
        g = QConicalGradient(rect.center(), 90)
        g.setColorAt(0, QColor(C["accent2"]))
        g.setColorAt(1, QColor(C["deep"]))
        p.setPen(QPen(g, 12, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 225 * 16, int(-360 * 16 * self.value))
        p.setPen(QColor(C["text"]))
        p.setFont(QFont("Segoe UI", 22, QFont.Black))
        p.drawText(rect.adjusted(0, -10, 0, -10), Qt.AlignCenter, self.text)
        p.setPen(QColor(C["muted"]))
        p.setFont(QFont("Segoe UI", 7, QFont.Bold))
        p.drawText(rect.adjusted(0, 34, 0, 34), Qt.AlignCenter, self.caption)


class LineChart(QWidget):
    """Gráfico dos últimos 60 s, com grade em 25/50/75/100% e área preenchida."""

    def __init__(self, n: int = 60):
        super().__init__()
        self.data: deque[float] = deque(maxlen=n)
        self.n = n
        self.scale_max = 100.0
        self.fixed = True
        self.setMinimumHeight(150)

    def reset(self, fixed=True):
        self.data.clear()
        self.fixed = fixed
        self.scale_max = 100.0
        self.update()

    def push(self, v: float):
        self.data.append(max(0.0, v))
        if not self.fixed:
            self.scale_max = max(1.0, max(self.data) * 1.2)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left, bottom = 40, 20
        w, h = self.width() - left - 8, self.height() - bottom - 6
        p.setFont(QFont("Segoe UI", 7))
        for frac in (0, 0.25, 0.5, 0.75, 1):
            y = 6 + h * (1 - frac)
            p.setPen(QPen(QColor(C["border"]), 1, Qt.DashLine))
            p.drawLine(QPointF(left, y), QPointF(left + w, y))
            p.setPen(QColor(C["muted"]))
            lab = f"{frac * 100:.0f}%" if self.fixed else f"{self.scale_max * frac:.0f}"
            p.drawText(QRectF(0, y - 7, left - 6, 14), Qt.AlignRight | Qt.AlignVCenter, lab)
        for i, t in enumerate(("60 s", "45 s", "30 s", "15 s", "agora")):
            x = left + w * i / 4
            p.drawText(QRectF(x - 20, 6 + h + 3, 40, 14), Qt.AlignCenter, t)
        if len(self.data) < 2:
            return
        pts = []
        start = self.n - len(self.data)
        for i, v in enumerate(self.data):
            x = left + w * (start + i) / (self.n - 1)
            y = 6 + h * (1 - min(1.0, v / self.scale_max))
            pts.append(QPointF(x, y))
        path = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):
            mx = (a.x() + b.x()) / 2
            path.cubicTo(QPointF(mx, a.y()), QPointF(mx, b.y()), b)
        area = QPainterPath(path)
        area.lineTo(pts[-1].x(), 6 + h)
        area.lineTo(pts[0].x(), 6 + h)
        area.closeSubpath()
        g = QLinearGradient(0, 6, 0, 6 + h)
        c1 = QColor(C["accent"])
        c1.setAlpha(90)
        c2 = QColor(C["accent"])
        c2.setAlpha(0)
        g.setColorAt(0, c1)
        g.setColorAt(1, c2)
        p.fillPath(area, g)
        p.setPen(QPen(QColor(C["accent"]), 2.2))
        p.drawPath(path)
        p.setBrush(QColor(C["accent2"]))
        p.setPen(QPen(QColor("#ffffff"), 1.5))
        p.drawEllipse(pts[-1], 4, 4)


class CircuitArt(QWidget):
    """Arte do cabeçalho: trilhas de circuito saindo de um chip com o L do app (desenho próprio)."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(460, 170)
        rnd = random.Random(7)
        self.tracks = []
        for side in (-1, 1):
            for i in range(9):
                y = 0.18 + i * 0.08
                length = 0.18 + rnd.random() * 0.22
                bend = rnd.choice((-1, 0, 1)) * 0.04
                self.tracks.append((side, y, length, bend))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        chip = min(H * 0.62, 110)
        line = QColor(C["accent"])
        line.setAlpha(150)
        for side, y, length, bend in self.tracks:
            x0 = cx + side * chip * 0.62
            y0 = H * y
            x1 = x0 + side * W * length * 0.5
            path = QPainterPath(QPointF(x0, y0))
            mid = x0 + side * W * length * 0.18
            path.lineTo(mid, y0)
            path.lineTo(mid + side * 10, y0 + bend * H)
            path.lineTo(x1, y0 + bend * H)
            p.setPen(QPen(line, 1.3))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            p.setBrush(QColor(C["accent2"]))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x1, y0 + bend * H), 2.4, 2.4)
        # pinos do chip
        p.setPen(QPen(QColor(C["border2"]), 2))
        for i in range(9):
            x = cx - chip * 0.4 + i * chip * 0.1
            p.drawLine(QPointF(x, cy - chip * 0.62), QPointF(x, cy - chip * 0.5))
            p.drawLine(QPointF(x, cy + chip * 0.5), QPointF(x, cy + chip * 0.62))
        # brilho
        glow = QColor(C["accent"])
        glow.setAlpha(45)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawRoundedRect(QRectF(cx - chip * 0.62, cy - chip * 0.62, chip * 1.24, chip * 1.24), 18, 18)
        body = QRectF(cx - chip / 2, cy - chip / 2, chip, chip)
        g = QLinearGradient(body.topLeft(), body.bottomRight())
        g.setColorAt(0, QColor(C["panel2"]))
        g.setColorAt(1, QColor(C["bg"]))
        p.setBrush(g)
        p.setPen(QPen(QColor(C["accent"]), 2))
        p.drawRoundedRect(body, 14, 14)
        s = chip * 0.62
        p.translate(cx - s / 2, cy - s / 2)
        lg = QLinearGradient(0, 0, s, s)
        lg.setColorAt(0, QColor("#5cc8ff"))
        lg.setColorAt(1, QColor("#0a6cff"))
        p.fillPath(l_path(s), lg)
