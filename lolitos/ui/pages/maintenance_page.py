"""Manutenção: ferramentas do próprio Windows para manter o sistema saudável."""
from PySide6.QtWidgets import QGridLayout

from lolitos.modules import repair
from lolitos.ui.widgets import Card, Page, TaskDialog, button, confirm, hrow, label

GROUP_TITLES = {"Saúde": "Saúde do Windows", "Rede": "Rede", "Windows": "Windows e dispositivos"}


class MaintenancePage(Page):
    title = "Manutenção"
    subtitle = ("Ferramentas do próprio Windows para manter o sistema saudável e corrigir problemas. "
                "O comando exato é mostrado antes de rodar.")

    def build(self):
        groups: dict[str, list] = {}
        for t in repair.TOOLS:
            groups.setdefault(t.group, []).append(t)
        for g, items in groups.items():
            self.body.addWidget(label(GROUP_TITLES.get(g, g), "h2"))
            grid = QGridLayout()
            grid.setSpacing(10)
            for i, t in enumerate(items):
                c = Card()
                c.lay.addWidget(label(f"<b>{t.name}</b>" + (f" · {t.minutes}" if t.minutes else ""), rich=True))
                c.lay.addWidget(label(t.desc, "muted"))
                c.lay.addLayout(hrow(button("Executar", on_click=lambda _=False, tt=t: self.run_tool(tt)), None))
                grid.addWidget(c, i // 2, i % 2)
            self.body.addLayout(grid)

    def run_tool(self, t):
        if not confirm(self, t.name, f"<p>{t.desc}</p><p><b>O que será executado:</b><br><code>{t.cmd}</code></p>",
                       yes="Executar"):
            return

        def work(progress=None):
            progress(f"> {t.cmd}")
            ok, out = repair.run_tool(t)
            return (out or "") + ("\n\nReinicie o PC para concluir." if t.restart else "") + \
                ("" if ok else "\n\nTerminou com avisos ou erros (veja acima).")
        TaskDialog(self, t.name, work).exec()
