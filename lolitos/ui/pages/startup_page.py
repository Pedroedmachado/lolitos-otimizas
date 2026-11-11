"""Inicialização: programas que abrem com o Windows, numa lista com ícone, caminho, para quem vale e a chave."""
from PySide6.QtCore import QFileInfo, QSize, Qt
from PySide6.QtWidgets import QFileIconProvider, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from lolitos.i18n import tr
from lolitos.modules import startup
from lolitos.ui.widgets import Card, Page, Toggle, button, label, pill, run_async

_ICONS = QFileIconProvider()


def _icon(path: str):
    try:
        ic = _ICONS.icon(QFileInfo(path))
        return ic.pixmap(QSize(22, 22)) if not ic.isNull() else None
    except Exception:  # noqa: BLE001
        return None


class StartupPage(Page):
    title = "Inicialização"
    subtitle = ("Programas que abrem junto com o Windows. Desligar não desinstala nada e dá para religar quando "
                "quiser.")

    def build(self):
        self.count = label("", "counter", wrap=False)
        self.actions.addWidget(self.count)
        self.actions.addWidget(button("Atualizar", on_click=self.reload))
        self.card = Card()
        self.box = QVBoxLayout()
        self.box.setSpacing(0)
        self.card.lay.addLayout(self.box)
        self.body.addWidget(self.card)
        self.body.addWidget(label("Funciona como o Gerenciador de Tarefas: a entrada continua lá e só deixa de ser "
                                  "executada. Cada mudança fica no histórico.", "muted"))
        self.reload()

    def reload(self):
        run_async(startup.list_entries, on_done=self._show)

    def _show(self, entries):
        while self.box.count():
            it = self.box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        on = sum(1 for e in entries if e.enabled)
        self.count.setText(tr("{} ativos · {} desativado(s)").replace("{}", str(on), 1)
                           .replace("{}", str(len(entries) - on), 1) if entries else "")
        if not entries:
            self.box.addWidget(label("Nenhum programa configurado para abrir com o Windows.", "muted"))
            return
        for n, e in enumerate(entries):
            row = QFrame()
            row.setObjectName("listrow")
            h = QHBoxLayout(row)
            h.setContentsMargins(4, 8, 4, 8)
            h.setSpacing(12)
            ico = QLabel()
            ico.setFixedSize(24, 24)
            pix = _icon(startup.exe_path(e.command))
            if pix is not None:
                ico.setPixmap(pix)
            else:
                ico.setText("▣")
            h.addWidget(ico, 0, Qt.AlignVCenter)
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(label(f"<b>{e.name}</b>", rich=True, wrap=False))
            path = label(e.command[:200], "small")
            path.setToolTip(e.command)
            col.addWidget(path)
            h.addLayout(col, 1)
            h.addWidget(pill(tr("TODOS OS USUÁRIOS") if startup.all_users(e) else tr("USUÁRIO")), 0, Qt.AlignVCenter)
            sw = Toggle(e.enabled)
            sw.toggled.connect(lambda v, ee=e: run_async(startup.set_enabled, ee, v, on_done=lambda _: self.reload()))
            h.addWidget(sw, 0, Qt.AlignVCenter)
            self.box.addWidget(row)
