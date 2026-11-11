"""Animações leves (só com 'Efeitos visuais' ligado): entrada das telas e o menu que cresce ao passar o mouse."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QVariantAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from lolitos.ui import theme

_RUNNING: set = set()      # segura as animações vivas até terminarem


def fade_only(w: QWidget, ms: int = 220) -> None:
    """Só esmaece (sem deslizar): para itens dentro de um layout, que ainda não têm posição definida."""
    if not theme.effects() or w is None:
        return
    eff = QGraphicsOpacityEffect(w)
    eff.setOpacity(0.0)
    w.setGraphicsEffect(eff)
    a = QPropertyAnimation(eff, b"opacity", w)
    a.setDuration(ms)
    a.setStartValue(0.0)
    a.setEndValue(1.0)
    a.setEasingCurve(QEasingCurve.OutCubic)
    _RUNNING.add(a)

    def end():
        _RUNNING.discard(a)
        try:
            w.setGraphicsEffect(None)
        except RuntimeError:
            pass
    a.finished.connect(end)
    a.start()


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


# ---------------------------------------------------------------- troca de tela: a tela antiga desfoca e some
class BlurOut(QWidget):
    """Foto da tela que está saindo, por cima da nova: fica borrada e some enquanto a nova aparece por baixo.
    O desfoque é feito uma vez só (reduz e amplia a imagem), então não pesa durante a animação."""

    def __init__(self, host: QWidget, pix, ms: int = 360):
        from PySide6.QtCore import Qt
        super().__init__(host)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(0, 0, host.width(), host.height())
        self.sharp = pix
        w, h = max(1, pix.width()), max(1, pix.height())
        small = pix.scaled(max(1, w // 14), max(1, h // 14), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.blur = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.t = 0.0
        self.raise_()
        self.show()
        a = QVariantAnimation(self)
        a.setDuration(ms)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.valueChanged.connect(self._step)
        a.finished.connect(self._end)
        _RUNNING.add(a)
        self._a = a
        a.start()

    def _step(self, v):
        self.t = float(v)
        self.update()

    def _end(self):
        _RUNNING.discard(self._a)
        self.deleteLater()

    def paintEvent(self, _):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRect(0, 0, self.width(), self.height())
        p.setOpacity(max(0.0, 1.0 - self.t) * 0.95)       # a versão borrada some devagar
        p.drawPixmap(r, self.blur)
        p.setOpacity(max(0.0, 1.0 - self.t * 2.4))        # a nítida some rápido: parece que borra
        p.drawPixmap(r, self.sharp)


def blur_out(host: QWidget, old: QWidget | None) -> None:
    if not theme.effects() or old is None or not old.isVisible() or old.width() < 10:
        return
    try:
        pix = old.grab()
    except RuntimeError:
        return
    BlurOut(host, pix, 420 if theme.level() >= 2 else 300)


# ---------------------------------------------------------------- título digitado
def type_text(lbl, ms: int = 380) -> None:
    """O título da tela aparece sendo digitado (Manuten… → Manutenção)."""
    if not theme.effects() or lbl is None:
        return
    full = lbl.text()
    if not full or "<" in full:
        return
    old = getattr(lbl, "_type_anim", None)
    if old is not None:
        old.stop()
        lbl.setText(getattr(lbl, "_type_full", full))
        full = lbl.text()
    lbl._type_full = full
    lbl.setMinimumWidth(lbl.sizeHint().width())        # a largura não pula enquanto digita
    a = QVariantAnimation(lbl)
    a.setDuration(ms)
    a.setStartValue(0)
    a.setEndValue(len(full))
    a.valueChanged.connect(lambda n: lbl.setText(full[:int(n)]))

    def end():
        _RUNNING.discard(a)
        try:
            lbl.setText(full)
            lbl._type_anim = None
        except RuntimeError:
            pass
    a.finished.connect(end)
    lbl._type_anim = a
    _RUNNING.add(a)
    a.start()


# ---------------------------------------------------------------- destaque do menu que desliza
def slide_rect(w: QWidget, start, end, ms: int = 260, done=None) -> None:
    from PySide6.QtCore import QRect
    a = QVariantAnimation(w)
    a.setDuration(ms)
    a.setStartValue(QRect(start))
    a.setEndValue(QRect(end))
    a.setEasingCurve(QEasingCurve.OutCubic)
    a.valueChanged.connect(w.setGeometry)

    def fin():
        _RUNNING.discard(a)
        if done:
            done()
    a.finished.connect(fin)
    _RUNNING.add(a)
    a.start()
