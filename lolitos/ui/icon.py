"""Ícone do app: um L azul, desenhado como forma (nítido de 16 px a 256 px)."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap


def l_path(s: float) -> QPainterPath:
    """Contorno do L com cantos levemente arredondados."""
    bar = 0.26 * s          # espessura
    x0, y0 = 0.20 * s, 0.08 * s
    x1, y1 = 0.84 * s, 0.92 * s
    r = 0.06 * s
    vert = QPainterPath()
    vert.addRoundedRect(QRectF(x0, y0, bar, y1 - y0), r, r)
    horiz = QPainterPath()
    horiz.addRoundedRect(QRectF(x0, y1 - bar, x1 - x0, bar), r, r)
    return vert.united(horiz)


def pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    path = l_path(s)
    g = QLinearGradient(QPointF(0, 0), QPointF(s, s))
    g.setColorAt(0, QColor("#5cc8ff"))
    g.setColorAt(0.55, QColor("#1e9bff"))
    g.setColorAt(1, QColor("#0a6cff"))
    p.fillPath(path, g)
    if size >= 48:   # brilho sutil na borda superior nos tamanhos grandes
        p.setPen(QColor(255, 255, 255, 60))
        p.drawPath(path)
    p.end()
    return pm


def icon() -> QIcon:
    ic = QIcon()
    for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        ic.addPixmap(pixmap(s))
    return ic
