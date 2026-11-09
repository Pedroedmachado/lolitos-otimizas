"""Inicialização: programas que abrem com o Windows."""
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QVBoxLayout

from lolitos.modules import startup
from lolitos.ui.widgets import Card, Page, button, hrow, label, run_async


class StartupPage(Page):
    title = "Inicialização"
    subtitle = ("Programas que abrem junto com o Windows. Desligar não desinstala nada e funciona como o "
                "Gerenciador de Tarefas: dá para religar quando quiser.")

    def build(self):
        self.count = label("", "muted")
        self.body.addLayout(hrow(button("Atualizar lista", on_click=self.reload), self.count, None))
        self.box = QVBoxLayout()
        self.box.setSpacing(8)
        self.body.addLayout(self.box)
        self.reload()

    def reload(self):
        run_async(startup.list_entries, on_done=self._show)

    def _show(self, entries):
        while self.box.count():
            it = self.box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        on = sum(1 for e in entries if e.enabled)
        self.count.setText(f"{on} de {len(entries)} abrem com o Windows. Limite sugerido: 12."
                           if entries else "Nenhum programa configurado para abrir com o Windows.")
        for e in entries:
            c = Card()
            row = QHBoxLayout()
            ck = QCheckBox(e.name)
            ck.setChecked(e.enabled)
            ck.toggled.connect(lambda v, ee=e: (startup.set_enabled(ee, v), self.reload()))
            row.addWidget(ck, 1)
            row.addWidget(label(e.source, "muted", wrap=False))
            c.lay.addLayout(row)
            c.lay.addWidget(label(e.command[:180], "muted"))
            self.box.addWidget(c)
