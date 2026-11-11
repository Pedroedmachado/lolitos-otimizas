"""Efeitos visuais da interface, em três níveis (Configurações › Efeitos visuais):

0 Desligados  — nada animado, sem vidro (o mais leve para PC fraco).
1 Básicos     — vidro, telas que aparecem esmaecendo, chaves que deslizam, brilho ao passar o mouse nos botões,
                velocímetro que sobe até o valor.
2 Completos   — tudo do básico + onda ao clicar, reflexo que atravessa os botões principais, cartões que levantam
                com sombra, telas que entram deslizando e pulso de luz no clique.

Tudo é feito com um filtro de eventos na aplicação: vale para qualquer botão, mesmo os criados direto com
QPushButton. Os efeitos só existem enquanto o mouse está em cima (nada fica pesando no desenho depois)."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QRadialGradient
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QFrame, QGraphicsDropShadowEffect,
                               QPushButton, QRadioButton, QWidget)

from lolitos.ui import theme
from lolitos.ui.theme import C

OFF, BASIC, FULL = 0, 1, 2
LEVELS = [(OFF, "Desligados"), (BASIC, "Básicos"), (FULL, "Completos")]
_LIVE: set = set()          # segura as animações até o fim


def level() -> int:
    return theme.level()


def current_from_settings() -> int:
    from lolitos.core import settings
    if not settings.get("visual_effects", True):
        return OFF
    try:
        return max(OFF, min(FULL, int(settings.get("effects_level", FULL))))
    except (TypeError, ValueError):
        return FULL


def _anim(owner: QObject, start, end, ms: int, on_value, done=None, curve=QEasingCurve.OutCubic):
    a = QVariantAnimation(owner)
    a.setDuration(ms)
    a.setStartValue(start)
    a.setEndValue(end)
    a.setEasingCurve(curve)
    a.valueChanged.connect(on_value)

    def fin():
        _LIVE.discard(a)
        if done:
            done()
    a.finished.connect(fin)
    _LIVE.add(a)
    a.start()
    return a


def _round_clip(p: QPainter, w: QWidget, radius: float = 8):
    path = QPainterPath()
    path.addRoundedRect(QRectF(w.rect()), radius, radius)
    p.setClipPath(path)


# ---------------------------------------------------------------- camadas desenhadas por cima do botão
class _Ripple(QWidget):
    """Onda que sai do ponto do clique e some (nível Completo)."""

    def __init__(self, host: QWidget, pos: QPointF):
        super().__init__(host)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(host.rect())
        self.c, self.t = pos, 0.0
        r = (host.width() ** 2 + host.height() ** 2) ** 0.5
        self.rmax = max(24.0, r)
        self.show()
        _anim(self, 0.0, 1.0, 520, self._step, self.deleteLater)

    def _step(self, v):
        self.t = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        _round_clip(p, self, 8)
        col = QColor("#ffffff")
        col.setAlphaF(0.28 * (1.0 - self.t))
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        r = self.rmax * (0.15 + 0.85 * self.t)
        p.drawEllipse(self.c, r, r)


class _Shine(QWidget):
    """Reflexo diagonal que atravessa o botão uma vez ao passar o mouse (botões principais, nível Completo)."""

    def __init__(self, host: QWidget):
        super().__init__(host)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(host.rect())
        self.x = -0.4
        self.show()
        _anim(self, -0.4, 1.4, 650, self._step, self.deleteLater, QEasingCurve.InOutQuad)

    def _step(self, v):
        self.x = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        _round_clip(p, self, 8)
        w = self.width()
        cx = self.x * w
        g = QLinearGradient(QPointF(cx - 40, 0), QPointF(cx + 40, self.height()))
        clear, white = QColor(255, 255, 255, 0), QColor(255, 255, 255, 70)
        g.setColorAt(0.0, clear)
        g.setColorAt(0.5, white)
        g.setColorAt(1.0, clear)
        p.fillRect(self.rect(), g)


class _Spot(QWidget):
    """Luz suave que segue o mouse dentro do botão (nível Completo)."""

    def __init__(self, host: QWidget):
        super().__init__(host)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(host.rect())
        self.pos_ = QPointF(host.width() / 2, host.height() / 2)
        self.show()

    def move_to(self, pos: QPointF):
        self.pos_ = pos
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        _round_clip(p, self, 8)
        g = QRadialGradient(self.pos_, max(40.0, self.width() * 0.6))
        col = QColor(C.get("accent2", "#6ab8ff"))
        col.setAlpha(46)
        g.setColorAt(0.0, col)
        col.setAlpha(0)
        g.setColorAt(1.0, col)
        p.fillRect(self.rect(), g)


class _CardShadow(QWidget):
    """Sombra macia atrás de um cartão (irmão dele no mesmo pai, logo abaixo na pilha)."""

    PAD = 18

    def __init__(self, card: QWidget):
        super().__init__(card.parentWidget())
        self.card = card
        self.t = 0.0
        self.anim = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._place()
        self.stackUnder(card)
        self.show()

    def _place(self):
        g = self.card.geometry()
        self.setGeometry(g.adjusted(-self.PAD, -self.PAD // 2, self.PAD, self.PAD + 6))

    def go(self, end: float):
        if self.anim is not None:
            self.anim.stop()
        self._place()
        self.stackUnder(self.card)

        def step(v):
            self.t = float(v)
            self.update()

        def done():
            if end == 0.0:
                self.card._fx_shadow = None
                self.deleteLater()
        self.anim = _anim(self, self.t, end, 200 if end else 260, step, done)

    def paintEvent(self, _):
        if self.t <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        base = 0.035 if theme.is_light() else 0.08
        r = QRectF(self.PAD, self.PAD // 2 + 6 * self.t, self.card.width(), self.card.height())
        for i in range(8, 0, -1):            # camadas cada vez maiores e mais fracas = sombra borrada
            col = QColor(0, 0, 0)
            col.setAlphaF(min(1.0, base * self.t * (1.0 / i)))
            p.setBrush(col)
            k = i * 2.2
            p.drawRoundedRect(r.adjusted(-k, -k * 0.6, k, k), 12 + k, 12 + k)


# ---------------------------------------------------------------- filtro de eventos
class FxFilter(QObject):
    """Liga os efeitos em todos os botões e cartões da aplicação."""

    def _glow(self, w: QWidget, on: bool, strong: bool = False):
        if on:                                       # efeitos não podem ficar aninhados (ex.: tela esmaecendo)
            p = w.parentWidget()
            while p is not None:
                if p.graphicsEffect() is not None:
                    return
                p = p.parentWidget()
        eff = w.graphicsEffect()
        if eff is not None and not getattr(eff, "_fx", False):
            return                                   # o widget já usa outro efeito: não mexe
        if on:
            if eff is None:
                eff = QGraphicsDropShadowEffect(w)
                eff._fx = True
                eff.setOffset(0, 0)
                eff.setBlurRadius(0)
                col = QColor(C.get("accent", "#2d8cff"))
                col.setAlpha(0)
                eff.setColor(col)
                w.setGraphicsEffect(eff)
            target_blur, target_a = (30, 230) if strong else (20, 150)
        else:
            if eff is None:
                return
            target_blur, target_a = 0, 0
        old = getattr(w, "_fx_anim", None)
        if old is not None:
            old.stop()
        b0, a0 = eff.blurRadius(), eff.color().alpha()

        def step(t, e=eff):
            try:
                e.setBlurRadius(b0 + (target_blur - b0) * t)
                c = e.color()
                c.setAlpha(int(a0 + (target_a - a0) * t))
                e.setColor(c)
            except RuntimeError:
                pass

        def done(wid=w, e=eff, off=not on):
            if off:
                try:
                    if wid.graphicsEffect() is e:
                        wid.setGraphicsEffect(None)
                except RuntimeError:
                    pass
        w._fx_anim = _anim(w, 0.0, 1.0, 180 if on else 240, step, done)

    def _lift(self, w: QWidget, on: bool):
        """Cartão que 'levanta': uma sombra desenhada atrás dele (sem QGraphicsEffect, que não pode ficar
        aninhado com o brilho dos botões de dentro)."""
        sh = getattr(w, "_fx_shadow", None)
        if on:
            if sh is None and w.parentWidget() is not None:
                sh = _CardShadow(w)
                w._fx_shadow = sh
            if sh is not None:
                sh.go(1.0)
        elif sh is not None:
            sh.go(0.0)
    @staticmethod
    def _is_card(w) -> bool:
        return isinstance(w, QFrame) and w.objectName() in ("card", "tcard", "tcardrec") and w.height() < 420

    def eventFilter(self, obj, ev):
        lvl = theme.level()
        if lvl == OFF:
            return False
        t = ev.type()
        if t not in (QEvent.Enter, QEvent.Leave, QEvent.MouseButtonPress, QEvent.MouseMove):
            return False
        try:
            if isinstance(obj, QAbstractButton) and not isinstance(obj, (QCheckBox, QRadioButton)):
                if not obj.isEnabled():
                    return False
                primary = isinstance(obj, QPushButton) and obj.objectName() in ("primary", "outline")
                if t == QEvent.Enter:
                    self._glow(obj, True)
                    if lvl >= FULL and isinstance(obj, QPushButton):
                        if primary:
                            _Shine(obj)
                        elif obj.objectName() not in ("nav", "navgold", "link") and obj.width() > 40:
                            obj._fx_spot = _Spot(obj)
                elif t == QEvent.Leave:
                    self._glow(obj, False)
                    spot = getattr(obj, "_fx_spot", None)
                    if spot is not None:
                        spot.deleteLater()
                        obj._fx_spot = None
                elif t == QEvent.MouseMove and lvl >= FULL:
                    spot = getattr(obj, "_fx_spot", None)
                    if spot is not None:
                        spot.move_to(ev.position())
                elif t == QEvent.MouseButtonPress and lvl >= FULL and isinstance(obj, QPushButton):
                    _Ripple(obj, ev.position())
                    self._glow(obj, True, strong=True)
            elif lvl >= FULL and t in (QEvent.Enter, QEvent.Leave) and self._is_card(obj):
                self._lift(obj, t == QEvent.Enter)
        except RuntimeError:
            pass
        return False


_FILTER: FxFilter | None = None


def install(app: QApplication | None = None) -> None:
    global _FILTER
    app = app or QApplication.instance()
    if app is None or _FILTER is not None:
        return
    _FILTER = FxFilter(app)
    app.installEventFilter(_FILTER)
