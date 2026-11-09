"""Componentes de interface reutilizáveis e execução em segundo plano."""
from __future__ import annotations

import inspect
import traceback

from PySide6.QtCore import QObject, QRectF, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractButton, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from lolitos.i18n import tr, translate_tree
from lolitos.ui.theme import C


# ===================================================================== segundo plano
class _Sig(QObject):
    progress = Signal(object)
    done = Signal(object)
    error = Signal(str)


class _Job(QRunnable):
    def __init__(self, fn, args, kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.sig = _Sig()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            kw = dict(self.kwargs)
            try:
                if "progress" in inspect.signature(self.fn).parameters:
                    kw["progress"] = self.sig.progress.emit
            except (TypeError, ValueError):
                pass
            result = self.fn(*self.args, **kw)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            try:
                self.sig.error.emit(f"{type(e).__name__}: {e}")
            except RuntimeError:      # janela já fechada
                pass
            return
        try:
            self.sig.done.emit(result)
        except RuntimeError:          # o app fechou enquanto a tarefa rodava
            pass


_JOBS: set = set()


class _Invoker(QObject):
    """Executa uma função na thread da interface, chamada de qualquer thread (sinal em fila)."""
    call = Signal(object)


_INVOKER: _Invoker | None = None


def init_ui_thread() -> None:
    """Chamar uma vez na thread principal (antes de qualquer ui_call)."""
    global _INVOKER
    if _INVOKER is None:
        _INVOKER = _Invoker()
        _INVOKER.call.connect(lambda fn: fn())


def ui_call(fn) -> None:
    """Agenda `fn()` na thread da interface. Seguro a partir de threads Python comuns."""
    if _INVOKER is None:
        fn()
    else:
        _INVOKER.call.emit(fn)


_STATUS_POOL: QThreadPool | None = None


def status_pool() -> QThreadPool:
    """Pool pequeno para leituras de estado (registro, powercfg, PowerShell): poucas ao mesmo tempo,
    para não disputar CPU e o GIL com a interface."""
    global _STATUS_POOL
    if _STATUS_POOL is None:
        _STATUS_POOL = QThreadPool()
        _STATUS_POOL.setMaxThreadCount(2)
    return _STATUS_POOL


def run_async(fn, *args, on_done=None, on_error=None, on_progress=None, _pool=None, **kwargs):
    job = _Job(fn, args, kwargs)
    _JOBS.add(job.sig)
    if on_done:
        job.sig.done.connect(on_done)
    if on_error:
        job.sig.error.connect(on_error)
    if on_progress:
        job.sig.progress.connect(on_progress)
    job.sig.done.connect(lambda *_: _JOBS.discard(job.sig))
    job.sig.error.connect(lambda *_: _JOBS.discard(job.sig))
    (_pool or QThreadPool.globalInstance()).start(job)
    return job.sig


class TaskDialog(QDialog):
    """Janela de tarefa: mostra cada passo e só libera 'Fechar' no fim."""

    def __init__(self, parent, title: str, fn, *args, intro: str = "", on_done=None, **kwargs):
        super().__init__(parent)
        title, intro = tr(title), tr(intro)
        self.setWindowTitle(title)
        self.resize(640, 420)
        self.result_value = None
        lay = QVBoxLayout(self)
        h = QLabel(title)
        h.setObjectName("h2")
        lay.addWidget(h)
        if intro:
            i = QLabel(intro)
            i.setWordWrap(True)
            i.setObjectName("muted")
            lay.addWidget(i)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        lay.addWidget(self.bar)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log, 1)
        row = QHBoxLayout()
        row.addStretch()
        self.btn = QPushButton(tr("Fechar"))
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.accept)
        row.addWidget(self.btn)
        lay.addLayout(row)
        self._on_done = on_done
        run_async(fn, *args, on_done=self._done, on_error=self._err, on_progress=self.add, **kwargs)

    def add(self, s):
        self.log.appendPlainText(tr(str(s)))

    def _done(self, res):
        self.result_value = res
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        if isinstance(res, str) and res:
            self.add("\n" + res)
        self.add("\n" + tr("Concluído. Clique em Fechar."))
        self.btn.setEnabled(True)
        if self._on_done:
            self._on_done(res)

    def _err(self, msg):
        self.bar.setRange(0, 1)
        self.add("\n" + tr("Erro: {}").replace("{}", str(msg)))
        self.btn.setEnabled(True)

    def reject(self):
        if self.btn.isEnabled():
            super().reject()


# ===================================================================== blocos visuais
def label(text: str = "", obj: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    lb = QLabel(tr(text))
    if obj:
        lb.setObjectName(obj)
    lb.setWordWrap(wrap)
    if rich:
        lb.setTextFormat(Qt.RichText)
    return lb


def button(text: str, kind: str = "", on_click=None, tip: str = "") -> QPushButton:
    b = QPushButton(tr(text))
    if kind:
        b.setObjectName(kind)
    b.setCursor(Qt.PointingHandCursor)
    if on_click:
        b.clicked.connect(on_click)
    if tip:
        b.setToolTip(tip)
    return b


class Card(QFrame):
    def __init__(self, hero: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("hero" if hero else "card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(16, 14, 16, 14)
        self.lay.setSpacing(8)


class Badge(QLabel):
    STYLES = {
        "on": ("ATIVO", "ok"), "off": ("PENDENTE", "muted"), "partial": ("PARCIAL", "warn"),
        "na": ("NÃO SE APLICA", "muted"), "unknown": ("—", "muted"), "blocked": ("BLOQUEADO", "bad"),
        "ok": ("OK", "ok"), "atencao": ("ATENÇÃO", "warn"), "corrigir": ("CORRIGIR", "bad"),
        "loading": ("…", "muted"),
    }

    def __init__(self, state: str = "loading"):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(96)
        self.set(state)

    def set(self, state: str, text: str = ""):
        t, color = self.STYLES.get(state, (state.upper(), "muted"))
        col = C.get(color, C["muted"])
        self.setText(text or t)
        self.setStyleSheet(f"color:{col}; border:1px solid {col}; border-radius:9px; padding:2px 8px;"
                           f"font-size:8.5pt; font-weight:700;")


class IconTile(QFrame):
    """Quadrado arredondado com um ícone de linha (cabeçalho das telas e dos cartões)."""

    def __init__(self, name: str, size: int = 50, pt: float = 17, color: str = ""):
        super().__init__()
        from lolitos.ui import glyphs
        self.setObjectName("icontile")
        self.setFixedSize(size, size)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(glyphs.glyph(name, pt, color or C["accent2"]))


class Toggle(QAbstractButton):
    """Chave liga/desliga (no lugar de caixa de marcar onde é uma configuração)."""

    def __init__(self, checked: bool = False, on_toggle=None):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 24)
        if on_toggle:
            self.toggled.connect(on_toggle)

    def paintEvent(self, _):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["accent"] if on else C["border2"]))
        if not self.isEnabled():
            p.setOpacity(0.45)
        p.drawRoundedRect(QRectF(0, 0, 44, 24), 12, 12)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(23 if on else 3, 3, 18, 18))


class StatTile(QFrame):
    """Bloco de número: rótulo pequeno em cima, valor grande, unidade embaixo."""

    def __init__(self, caption: str, value: str = "—", unit: str = "", icon: str = "", align=Qt.AlignCenter):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(6)
        if icon:
            from lolitos.ui import glyphs
            top.addWidget(glyphs.glyph(icon, 10, C["accent2"]))
        cap = label(caption.upper(), "statcap", wrap=False)
        top.addWidget(cap)
        if align == Qt.AlignCenter:
            top.insertStretch(0)
        top.addStretch()
        lay.addLayout(top)
        self.value = label(value, "statval", wrap=False)
        self.value.setAlignment(align)
        lay.addWidget(self.value)
        self.unit = label(unit, "statunit", wrap=False)
        self.unit.setAlignment(align)
        lay.addWidget(self.unit)

    def set(self, value: str, unit: str | None = None):
        self.value.setText(value)
        if unit is not None:
            self.unit.setText(unit)


def card_header(icon: str, title: str, right: QWidget | None = None) -> QHBoxLayout:
    """Linha de título de cartão: ícone + título em negrito + algo à direita (selo, contador, chave)."""
    from lolitos.ui import glyphs
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(glyphs.glyph(icon, 13, C["accent2"]))
    row.addWidget(label(f"<b>{tr(title)}</b>", "h3", rich=True, wrap=False))
    row.addStretch()
    if right is not None:
        row.addWidget(right)
    return row


def pill(text: str, color: str = "") -> QLabel:
    lb = label(text, "pill", wrap=False)
    if color:
        lb.setStyleSheet(f"color:{color}; border-color:{color};")
    return lb


class Page(QWidget):
    """Página com cabeçalho (ícone, título, subtítulo, ações à direita) e área rolável."""
    title = ""
    subtitle = ""
    icon = ""

    def __init__(self, main=None):
        super().__init__()
        self.main = main
        self.setObjectName("page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        inner = QWidget()
        inner.setObjectName("page")
        scroll.setWidget(inner)
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(28, 22, 28, 28)
        self.body.setSpacing(14)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        if self.title:
            head = QHBoxLayout()
            head.setSpacing(16)
            if self.icon:
                head.addWidget(IconTile(self.icon), 0, Qt.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(label(self.title, "h1"))
            if self.subtitle:
                col.addWidget(label(self.subtitle, "muted"))
            head.addLayout(col, 1)
            head.addLayout(self.actions)
            self.body.addLayout(head)
        elif self.subtitle:
            self.body.addWidget(label(self.subtitle, "muted"))
        self._built = False

    def ensure_built(self):
        """Monta o conteúdo uma vez, sem desenhar pela metade."""
        if self._built:
            return
        self._built = True
        self.setUpdatesEnabled(False)
        try:
            self.build()
            self.body.addStretch()
            translate_tree(self)
        finally:
            self.setUpdatesEnabled(True)

    def showEvent(self, e):
        self.ensure_built()
        super().showEvent(e)
        self.on_show()

    def build(self):
        pass

    def on_show(self):
        pass


def hrow(*widgets, stretch_first=False, spacing=8) -> QHBoxLayout:
    r = QHBoxLayout()
    r.setSpacing(spacing)
    for i, w in enumerate(widgets):
        if w is None:
            r.addStretch()
        elif isinstance(w, QHBoxLayout):
            r.addLayout(w)
        else:
            r.addWidget(w, 1 if (stretch_first and i == 0) else 0)
    return r


def confirm(parent, title: str, text: str, yes: str = "Sim", no: str = "Cancelar") -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(tr(title))
    box.setText(tr(text))
    box.setTextFormat(Qt.RichText)
    y = box.addButton(tr(yes), QMessageBox.AcceptRole)
    box.addButton(tr(no), QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is y


def info(parent, title: str, text: str):
    QMessageBox.information(parent, tr(title), tr(text))


# ===================================================================== linha de ajuste
class TweakRow(QFrame):
    """Um ajuste: seleção, título, descrição, prós/contras, estado e botão aplicar/desfazer."""

    def __init__(self, tweak, on_toggle, selectable: bool = True):
        super().__init__()
        self.t = tweak
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.chk = QCheckBox(self)
        lay.addWidget(self.chk, 0, Qt.AlignTop)
        self.chk.setVisible(selectable)      # só depois de ter pai: antes disso viraria uma janela solta
        col = QVBoxLayout()
        col.setSpacing(3)
        tags = []
        if tweak.level == "essencial":
            tags.append(f"<span style='color:{C['ok']}'>● essencial</span>")
        elif tweak.level == "recomendado":
            tags.append(f"<span style='color:{C['info']}'>● recomendado</span>")
        else:
            tags.append(f"<span style='color:{C['warn']}'>● avançado</span>")
        if tweak.restart:
            tags.append(f"<span style='color:{C['muted']}'>reinicie para valer</span>")
        if not tweak.reversible:
            tags.append(f"<span style='color:{C['bad']}'>sem desfazer</span>")
        tags = [tr(t) for t in tags]
        title = label(f"<b>{tr(tweak.title)}</b> &nbsp; <span style='font-size:8.5pt'>{' · '.join(tags)}</span>",
                      rich=True)
        col.addWidget(title)
        col.addWidget(label(tweak.desc, "muted"))
        extra = []
        if tweak.gain:
            extra.append(f"<span style='color:{C['ok']}'>+ {tr(tweak.gain)}</span>")
        if tweak.loss:
            extra.append(f"<span style='color:{C['warn']}'>− {tr(tweak.loss)}</span>")
        if extra:
            col.addWidget(label("<br>".join(extra), rich=True))
        lay.addLayout(col, 1)
        right = QVBoxLayout()
        self.badge = Badge("loading")
        right.addWidget(self.badge, 0, Qt.AlignRight)
        self.btn = button("Aplicar", on_click=lambda: on_toggle(self))
        right.addWidget(self.btn, 0, Qt.AlignRight)
        right.addStretch()
        lay.addLayout(right)
        self.state = "loading"
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def set_state(self, st: str, blocked: bool = False):
        self.state = st
        self.badge.set("blocked" if blocked else st)
        if st == "on":
            self.btn.setText("Desfazer")
            self.chk.setEnabled(False)
            self.chk.setChecked(False)
        elif st == "na":
            self.btn.setText("—")
            self.btn.setEnabled(False)
            self.chk.setEnabled(False)
        else:
            self.btn.setText("Aplicar")
            self.btn.setEnabled(True)
            self.chk.setEnabled(True)
