"""Debloat: apps pré-instalados, recursos opcionais e OneDrive."""
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from lolitos.catalog.debloat import DEBLOAT_TWEAKS, ONEDRIVE
from lolitos.catalog.sem_ia import CAPABILITY_TWEAKS
from lolitos.core.actions import APPX
from lolitos.ui.tweaklist import TweakList
from lolitos.ui.widgets import Page, label


class DebloatPage(Page):
    title = "Debloat"
    subtitle = ("Remove o que vem com o Windows e quase ninguém usa. Os itens com aviso (avançado) começam "
                "desmarcados. Apps removidos não têm desfazer automático: voltam pela Microsoft Store.")

    def build(self):
        tabs = QTabWidget()
        for title, items, note in (
            ("Apps pré-instalados", DEBLOAT_TWEAKS, "Só aparecem como pendentes os apps instalados nesta conta."),
            ("Recursos do Windows", CAPABILITY_TWEAKS, "Desfazer reinstala pela internet (pode demorar)."),
            ("OneDrive", [ONEDRIVE], ""),
        ):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 12, 0, 0)
            if note:
                lay.addWidget(label(note, "muted"))
            tl = TweakList(items, self)
            lay.addWidget(tl)
            lay.addStretch()
            tabs.addTab(w, title)
        self.body.addWidget(tabs)

    def on_show(self):
        APPX.invalidate()
