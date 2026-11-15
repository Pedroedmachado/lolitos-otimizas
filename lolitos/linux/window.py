"""Janela principal da versão Linux: a mesma barra lateral, temas e efeitos do app do Windows."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from lolitos import APP_NAME, VERSION
from lolitos.core import settings
from lolitos.ui import theme
from lolitos.ui.icon import icon
from lolitos.ui.widgets import label


def _pages():
    from lolitos.linux import pages as p
    return [
        ("PRINCIPAL", [("painel", "home", "Painel", p.Dashboard), ("desempenho", "speed", "Desempenho", p.PerformancePage),
                       ("meupc", "pc", "Meu PC", p.MyPcPage)]),
        ("OTIMIZAR", [("ajustes", "bolt", "Ajustes", p.TweaksPage), ("jogos", "games", "Jogos", p.GamesPage),
                      ("mangohud", "overlay", "MangoHud", p.MangoHudPage)]),
        ("SISTEMA", [("restauracao", "history", "Restauração", p.RestorePage),
                     ("config", "settings", "Configurações", p.SettingsPage)]),
    ]


class LinuxWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from lolitos.ui.nav import Brand, NavButton
        from lolitos.ui.widgets import init_ui_thread
        init_ui_thread()
        self.setWindowTitle(f"{APP_NAME} {VERSION} · Linux")
        self.setWindowIcon(icon())
        self.resize(1180, 800)
        self.setMinimumSize(800, 600)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(256)
        self.side = side
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 18, 10, 12)
        sl.setSpacing(4)
        sl.addWidget(Brand())
        sl.addSpacing(8)
        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        self.index: dict[str, int] = {}
        self.nav_buttons: list = []
        scroll = QScrollArea()
        scroll.setObjectName("navscroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav = QWidget()
        nav.setObjectName("navlist")
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(0, 0, 6, 0)
        nl.setSpacing(2)
        i = 0
        for section, items in _pages():
            nl.addSpacing(8 if i else 2)
            nl.addWidget(label(section, "navsec"))
            for key, ico, text, cls in items:
                b = NavButton(ico, text)
                b.clicked.connect(lambda _=False, k=key: self.go(k))
                self.group.addButton(b, i)
                self.nav_buttons.append(b)
                nl.addWidget(b)
                if not cls.icon:
                    cls.icon = ico
                self.stack.addWidget(cls(self))
                self.index[key] = i
                i += 1
        nl.addStretch()
        scroll.setWidget(nav)
        sl.addWidget(scroll, 1)
        lay.addWidget(side)
        lay.addWidget(self.stack, 1)
        self.go("painel")

    def go(self, key: str, bring: bool = False):
        i = self.index.get(key, 0)
        page = self.stack.widget(i)
        page.ensure_built()
        changed = self.stack.currentIndex() != i
        fx_on = changed and self.isVisible() and theme.effects()
        if fx_on:
            from lolitos.ui.anim import blur_out
            blur_out(self.stack, self.stack.currentWidget())
        self.stack.setCurrentIndex(i)
        self.group.button(i).setChecked(True)
        if fx_on:
            from lolitos.ui.anim import fade_in, type_text
            fade_in(page)
            type_text(getattr(page, "title_lbl", None))

    def changed(self):
        pass

    def apply_theme(self):
        from lolitos.ui.fx import current_from_settings
        theme.use(settings.get("theme"), current_from_settings())
        app = QApplication.instance()
        app.setStyleSheet(theme.qss())
        for w in app.allWidgets():
            w.update()

    def set_effects(self, lv: int):
        settings.set("effects_level", int(lv))
        settings.set("visual_effects", lv > 0)
        self.apply_theme()

    def set_theme(self, key: str):
        settings.set("theme", key)
        self.apply_theme()
