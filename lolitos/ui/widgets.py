"""Componentes de interface reutilizáveis e execução em segundo plano."""
from __future__ import annotations

import inspect
import traceback

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

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
            self.sig.done.emit(self.fn(*self.args, **kw))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.sig.error.emit(f"{type(e).__name__}: {e}")


_JOBS: set = set()


def run_async(fn, *args, on_done=None, on_error=None, on_progress=None, **kwargs):
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
    QThreadPool.globalInstance().start(job)
    return job.sig


class TaskDialog(QDialog):
    """Janela de tarefa: mostra cada passo e só libera 'Fechar' no fim."""

    def __init__(self, parent, title: str, fn, *args, intro: str = "", on_done=None, **kwargs):
        super().__init__(parent)
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
        self.btn = QPushButton("Fechar")
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.accept)
        row.addWidget(self.btn)
        lay.addLayout(row)
        self._on_done = on_done
        run_async(fn, *args, on_done=self._done, on_error=self._err, on_progress=self.add, **kwargs)

    def add(self, s):
        self.log.appendPlainText(str(s))

    def _done(self, res):
        self.result_value = res
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        if isinstance(res, str) and res:
            self.add("\n" + res)
        self.add("\nConcluído. Clique em Fechar.")
        self.btn.setEnabled(True)
        if self._on_done:
            self._on_done(res)

    def _err(self, msg):
        self.bar.setRange(0, 1)
        self.add(f"\nErro: {msg}")
        self.btn.setEnabled(True)

    def reject(self):
        if self.btn.isEnabled():
            super().reject()


# ===================================================================== blocos visuais
def label(text: str = "", obj: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    lb.setWordWrap(wrap)
    if rich:
        lb.setTextFormat(Qt.RichText)
    return lb


def button(text: str, kind: str = "", on_click=None, tip: str = "") -> QPushButton:
    b = QPushButton(text)
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


class Page(QWidget):
    """Página com título, subtítulo e área rolável."""
    title = ""
    subtitle = ""

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
        if self.title:
            self.body.addWidget(label(self.title, "h1"))
        if self.subtitle:
            self.body.addWidget(label(self.subtitle, "muted"))
        self._built = False

    def showEvent(self, e):
        super().showEvent(e)
        if not self._built:
            self._built = True
            self.build()
            self.body.addStretch()
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
    box.setWindowTitle(title)
    box.setText(text)
    box.setTextFormat(Qt.RichText)
    y = box.addButton(yes, QMessageBox.AcceptRole)
    box.addButton(no, QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is y


def info(parent, title: str, text: str):
    QMessageBox.information(parent, title, text)


# ===================================================================== linha de ajuste
class TweakRow(QFrame):
    """Um ajuste: seleção, título, descrição, prós/contras, estado e botão aplicar/desfazer."""

    def __init__(self, tweak, on_toggle, selectable: bool = True):
        super().__init__()
        self.t = tweak
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.chk = QCheckBox()
        self.chk.setVisible(selectable)
        lay.addWidget(self.chk, 0, Qt.AlignTop)
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
        title = label(f"<b>{tweak.title}</b> &nbsp; <span style='font-size:8.5pt'>{' · '.join(tags)}</span>",
                      rich=True)
        col.addWidget(title)
        col.addWidget(label(tweak.desc, "muted"))
        extra = []
        if tweak.gain:
            extra.append(f"<span style='color:{C['ok']}'>+ {tweak.gain}</span>")
        if tweak.loss:
            extra.append(f"<span style='color:{C['warn']}'>− {tweak.loss}</span>")
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
