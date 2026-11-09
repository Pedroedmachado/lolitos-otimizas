"""Ajustes do sistema separados por categoria (cada aba é montada só quando aberta)."""
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
        self.lists: dict[str, TweakList] = {}
        self.holders: dict[str, QVBoxLayout] = {}
        for cat in TABS:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 12, 0, 0)
            self.holders[cat] = lay
            self.tabs.addTab(w, CATS[cat])
        self.tabs.currentChanged.connect(self._ensure)
        self.body.addWidget(self.tabs)
        self._ensure(0)

    def _ensure(self, idx: int):
        cat = TABS[idx]
        if cat in self.lists:
            return
        tl = TweakList(by_cat(cat), self)
        self.lists[cat] = tl
        self.holders[cat].addWidget(tl)
        self.holders[cat].addStretch()

    def on_show(self):
        if self._built:
            cur = TABS[self.tabs.currentIndex()]
            if cur in self.lists:
                self.lists[cur].refresh()
