"""Barra lateral: marca com versão, bandeiras de idioma, 'Recolher menu' e botões com ícone de linha."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from lolitos import VERSION
from lolitos.i18n import tr
from lolitos.ui import glyphs
from lolitos.ui.icon import pixmap
from lolitos.ui.theme import C


class NavButton(QPushButton):
    """Botão da barra lateral: ícone de linha + texto. 'special' = destaque dourado (Otimização Completa)."""

    def __init__(self, icon: str, text: str, special: bool = False, badge: str = ""):
        super().__init__("")
        self.icon_name, self.label_text = icon, tr(text)
        self.special, self.badge = special, tr(badge) if badge else ""
        self.collapsed = False
        self.setObjectName("navgold" if special else "nav")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        self.setToolTip(self.label_text)

    def set_collapsed(self, v: bool):
        self.collapsed = v
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)          # fundo e borda vêm do tema (QSS)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        col = QColor(C["gold"]) if self.special else QColor(C["text"] if on else C["muted"])
        if self.underMouse() and not on and not self.special:
            col = QColor(C["text"])
        p.setPen(col)
        p.setFont(glyphs.font(11.5))
        x = 14
        p.drawText(QRectF(x, 0, 22, self.height()), Qt.AlignCenter, glyphs.char(self.icon_name))
        if self.collapsed:
            return
        f = QFont(self.font())
        f.setPointSizeF(10)
        f.setBold(on or self.special)
        p.setFont(f)
        right = self.width() - 10
        if self.badge:
            fm = p.fontMetrics()
            bw = fm.horizontalAdvance(self.badge) + 14
            r = QRectF(right - bw, (self.height() - 18) / 2, bw, 18)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["accent"]))
            p.drawRoundedRect(r, 9, 9)
            p.setPen(QColor("#ffffff"))
            bf = QFont(f)
            bf.setPointSizeF(7)
            bf.setBold(True)
            p.setFont(bf)
            p.drawText(r, Qt.AlignCenter, self.badge)
            right -= bw + 6
            p.setFont(f)
            p.setPen(col)
        txt = p.fontMetrics().elidedText(self.label_text, Qt.ElideRight, int(right - (x + 32)))
        p.drawText(QRectF(x + 32, 0, right - (x + 32), self.height()), Qt.AlignVCenter | Qt.AlignLeft, txt)


class Flag(QWidget):
    """Bandeira desenhada (Brasil, Espanha, EUA) — troca o idioma."""
    clicked = Signal(str)

    def __init__(self, code: str, active: bool):
        super().__init__()
        self.code, self.active = code, active
        self.setFixedSize(30, 20)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip({"pt": "Português", "es": "Español", "en": "English"}[code])

    def mouseReleaseEvent(self, e):
        self.clicked.emit(self.code)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = 28.0, 18.0
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w, h), 3, 3)
        p.setClipPath(clip)
        p.translate(1, 1)
        if self.code == "pt":
            p.fillRect(QRectF(0, 0, w, h), QColor("#169b3a"))
            p.setBrush(QColor("#f7d417"))
            p.setPen(Qt.NoPen)
            p.drawPolygon(QPolygonF([QPointF(w / 2, 2), QPointF(w - 3, h / 2), QPointF(w / 2, h - 2),
                                     QPointF(3, h / 2)]))
            p.setBrush(QColor("#1d3f9a"))
            p.drawEllipse(QRectF(w / 2 - 4.5, h / 2 - 4.5, 9, 9))
        elif self.code == "es":
            p.fillRect(QRectF(0, 0, w, h), QColor("#c60b1e"))
            p.fillRect(QRectF(0, h / 4, w, h / 2), QColor("#f6c400"))
        else:
            for i in range(7):
                p.fillRect(QRectF(0, i * h / 6.5, w, h / 13), QColor("#b22234"))
            p.fillRect(QRectF(0, 0, w * 0.45, h * 0.54), QColor("#3c3b6e"))
        p.setClipping(False)
        p.resetTransform()
        p.setBrush(Qt.NoBrush)
        p.setPen(QColor(C["accent2"]) if self.active else QColor(0, 0, 0, 0))
        p.drawRoundedRect(QRectF(0.5, 0.5, w + 1, h + 1), 3, 3)
        if not self.active:
            p.fillRect(QRectF(1, 1, w, h), QColor(0, 0, 0, 70))


class Brand(QWidget):
    """Logo C + 'CHINESE / CONTROL' + pílula da versão."""

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 0, 0)
        lay.setSpacing(10)
        self.logo = QLabel()
        self.logo.setPixmap(pixmap(40))
        self.logo.setFixedSize(40, 40)
        lay.addWidget(self.logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        t1 = QLabel("CHINESE")
        t1.setObjectName("brand1")
        t2 = QLabel("C O N T R O L")
        t2.setObjectName("brand2")
        col.addWidget(t1)
        col.addWidget(t2)
        self.words = QWidget()
        self.words.setLayout(col)
        lay.addWidget(self.words)
        lay.addStretch()
        self.ver = QLabel(f"v{VERSION}")
        self.ver.setObjectName("verpill")
        self.ver.setFixedHeight(20)
        lay.addWidget(self.ver, 0, Qt.AlignVCenter)

    def set_collapsed(self, v: bool):
        self.words.setVisible(not v)
        self.ver.setVisible(not v)
