"""Animações leves (só com 'Efeitos visuais' ligado): entrada das telas e o menu que cresce ao passar o mouse."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QVariantAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from lolitos.ui import theme

_RUNNING: set = set()      # segura as animações vivas até terminarem


def fade_in(w: QWidget, ms: int = 200) -> None:
    """A tela aparece com um esmaecer rápido. O efeito sai no fim (deixar o efeito ligado pesa no desenho)."""
    if not theme.effects() or w is None:
        return
    eff = QGraphicsOpacityEffect(w)
    eff.setOpacity(0.0)
    w.setGraphicsEffect(eff)
    full = theme.level() >= 2
    ms = int(ms * 1.3) if full else ms
    a = QPropertyAnimation(eff, b"opacity", w)
    a.setDuration(ms)
    a.setStartValue(0.0)
    a.setEndValue(1.0)
    a.setEasingCurve(QEasingCurve.OutCubic)
    slide = None
    if full:                       # nível Completo: a tela também entra deslizando de baixo
        x, y = w.x(), w.y()
        slide = QVariantAnimation(w)
        slide.setDuration(ms)
        slide.setStartValue(18)
        slide.setEndValue(0)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        slide.valueChanged.connect(lambda v: w.move(x, y + int(v)))
        _RUNNING.add(slide)
        slide.finished.connect(lambda: _RUNNING.discard(slide))
        slide.start()

    def end():
        _RUNNING.discard(a)
        try:
            w.setGraphicsEffect(None)
        except RuntimeError:
            pass
    a.finished.connect(end)
    _RUNNING.add(a)
    a.start()


def animate_width(w: QWidget, to: int, ms: int = 170, done=None) -> QVariantAnimation | None:
    """Muda a largura fixa de um widget suavemente (ou na hora, com os efeitos desligados)."""
    if not theme.effects():
        w.setFixedWidth(to)
        if done:
            done()
        return None
    old = getattr(w, "_width_anim", None)
    if old is not None:
        old.stop()
    a = QVariantAnimation(w)
    a.setDuration(ms)
    a.setStartValue(w.width())
    a.setEndValue(to)
    a.setEasingCurve(QEasingCurve.OutCubic)
    a.valueChanged.connect(lambda v: w.setFixedWidth(int(v)))

    def end():
        _RUNNING.discard(a)
        if done:
            done()
    a.finished.connect(end)
    w._width_anim = a
    _RUNNING.add(a)
    a.start()
    return a
