"""Ícone do app: um C grosso com um ponto aceso na abertura (desenho próprio,
feito como forma para ficar nítido de 16 px a 256 px)."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPainterPathStroker, QPen,
                           QPixmap)

GAP = 84          # abertura do C, em graus (centrada à direita)


def _geom(s: float, simple: bool):
    width = s * (0.21 if simple else 0.18)
    r = s * 0.5 - width / 2 - s * 0.04
    return width, r, s / 2 - s * 0.03, s / 2      # largura, raio, centro x (um pouco à esquerda), centro y


def ring_path(s: float, simple: bool = False) -> QPainterPath:
    """O C: arco grosso com pontas arredondadas."""
    width, r, cx, cy = _geom(s, simple)
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    arc = QPainterPath()
    arc.arcMoveTo(rect, GAP / 2)
    arc.arcTo(rect, GAP / 2, 360 - GAP)
    st = QPainterPathStroker()
    st.setWidth(width)
    st.setCapStyle(Qt.RoundCap)
    return st.createStroke(arc).simplified()


def dot_path(s: float, simple: bool = False) -> QPainterPath:
    """A luz de 'ligado' encaixada na abertura do C."""
    width, r, cx, cy = _geom(s, simple)
    dot = QPainterPath()
    dot.addEllipse(QPointF(cx + r, cy), width * 0.62, width * 0.62)
    return dot


def mark_path(s: float) -> QPainterPath:
    """Marca completa (C + ponto) como uma forma só; usada no ícone e na arte do Painel."""
    simple = s < 24
    return ring_path(s, simple).united(dot_path(s, simple)).simplified()


def _gradient(s: float) -> QLinearGradient:
    g = QLinearGradient(QPointF(0, 0), QPointF(s, s))
    g.setColorAt(0, QColor("#5cc8ff"))
    g.setColorAt(0.55, QColor("#1e9bff"))
    g.setColorAt(1, QColor("#0a6cff"))
    return g


def pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    path = mark_path(s)
    p.fillPath(path, _gradient(s))
    if size >= 48:   # brilho sutil na borda nos tamanhos grandes
        p.setPen(QPen(QColor(255, 255, 255, 55), max(1.0, s / 128)))
        p.drawPath(path)
    p.end()
    return pm


def icon() -> QIcon:
    ic = QIcon()
    for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        ic.addPixmap(pixmap(s))
    return ic

