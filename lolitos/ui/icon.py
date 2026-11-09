"""Ícone do app desenhado em código (losango dourado com 'L')."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap, QPolygonF


def pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size
    poly = QPolygonF([QPointF(s / 2, s * 0.04), QPointF(s * 0.96, s / 2), QPointF(s / 2, s * 0.96),
                      QPointF(s * 0.04, s / 2)])
    g = QLinearGradient(0, 0, s, s)
    g.setColorAt(0, QColor("#5cc8ff"))
    g.setColorAt(1, QColor("#0a6cff"))
    p.setBrush(g)
    p.setPen(Qt.NoPen)
    p.drawPolygon(poly)
    inner = QPolygonF([QPointF(s / 2, s * 0.15), QPointF(s * 0.85, s / 2), QPointF(s / 2, s * 0.85),
                       QPointF(s * 0.15, s / 2)])
    p.setBrush(QColor("#050b16"))
    p.drawPolygon(inner)
    f = QFont("Segoe UI", int(s * 0.30))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#5cc8ff"))
    p.drawText(pm.rect(), Qt.AlignCenter, "L")
    p.end()
    return pm


def icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(pixmap(s))
    return ic
