"""Ajustes do sistema separados por categoria."""
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from lolitos.core.tweaks import CATS, by_cat
from lolitos.ui.tweaklist import TweakList
from lolitos.ui.widgets import Page

TABS = ["desempenho", "jogos", "entrada", "gpu", "rede", "privacidade", "ia", "interface", "atualizacoes",
        "seguranca", "apps"]


class TweaksPage(Page):
    title = "Ajustes"
    subtitle = ("Cada cartão diz o que muda, mostra o estado lido do seu Windows e pode ser desfeito a qualquer "
                "momento. Essencial é seguro em qualquer PC; Recomendado tem uma contrapartida pequena; Avançado "
                "pede confirmação.")

    def build(self):
        self.tabs = QTabWidget()
        self.lists = {}
        for cat in TABS:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 12, 0, 0)
            tl = TweakList(by_cat(cat), self)
            self.lists[cat] = tl
            lay.addWidget(tl)
            lay.addStretch()
            self.tabs.addTab(w, CATS[cat])
        self.body.addWidget(self.tabs)

    def on_show(self):
        if self._built:
            cur = TABS[self.tabs.currentIndex()]
            self.lists[cur].refresh()
