"""Janela principal: barra lateral, páginas, bandeja e tecla global do overlay."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QMenu,
                               QPushButton, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget)

from lolitos import APP_NAME, VERSION
from lolitos.core import settings
from lolitos.core.system import IS_WIN, is_admin
from lolitos.ui import theme
from lolitos.ui.icon import icon
from lolitos.ui.overlay import Overlay, parse_hotkey
from lolitos.ui.widgets import label



def _pages():
    from lolitos.ui.pages.bdo_page import BdoPage
    from lolitos.ui.pages.cleanup_page import CleanupPage
    from lolitos.ui.pages.dashboard import Dashboard
    from lolitos.ui.pages.debloat_page import DebloatPage
    from lolitos.ui.pages.games_page import GamesPage
    from lolitos.ui.pages.hardware_page import HardwarePage
    from lolitos.ui.pages.network_page import NetworkPage
    from lolitos.ui.pages.overlay_page import OverlayPage
    from lolitos.ui.pages.profiles_page import ProfilesPage
    from lolitos.ui.pages.restore_page import RestorePage
    from lolitos.ui.pages.settings_page import SettingsPage
    from lolitos.ui.pages.tools_page import ToolsPage
    from lolitos.ui.pages.tweaks_page import TweaksPage
    return [
        ("painel", "⌂  Painel", Dashboard), ("jogos", "🎮  Jogos", GamesPage),
        ("bdo", "⚔  Black Desert", BdoPage), ("ajustes", "⚙  Ajustes", TweaksPage),
        ("debloat", "✂  Debloat", DebloatPage), ("perfis", "★  Perfis", ProfilesPage),
        ("limpeza", "🧹  Limpeza", CleanupPage), ("rede", "📶  Rede", NetworkPage),
        ("ferramentas", "🛠  Ferramentas", ToolsPage), ("hardware", "🖥  Hardware", HardwarePage),
        ("overlay", "◱  Overlay", OverlayPage), ("restauracao", "↺  Restauração", RestorePage),
        ("config", "☰  Configurações", SettingsPage),
    ]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from lolitos.ui.widgets import init_ui_thread
        init_ui_thread()
        self.setWindowTitle(f"{APP_NAME} {VERSION}" + ("" if is_admin() else "  (sem administrador)"))
        self.setWindowIcon(icon())
        self.resize(1240, 820)
        self.setMinimumSize(980, 640)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 18, 12, 14)
        sl.setSpacing(3)
        sl.addWidget(label("Lolitos Control", "brand"))
        sl.addWidget(label("Otimização para jogos", "brandsub"))
        sl.addSpacing(14)
        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        self.index = {}
        for i, (key, text, cls) in enumerate(_pages()):
            b = QPushButton(text)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.group.addButton(b, i)
            sl.addWidget(b)
            self.stack.addWidget(cls(self))
            self.index[key] = i
        sl.addStretch()
        sl.addWidget(label(f"v{VERSION}", "brandsub"))
        lay.addWidget(side)
        lay.addWidget(self.stack, 1)

        self.overlay = Overlay()
        self._overlay_auto = False
        self._tray()
        self.go("painel")
        self.register_hotkey()
        self.prebuild_pages()
        if not settings.get("seen_analysis"):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(900, self.first_run)

    # ---------------------------------------------------------------- navegação
    def go(self, key: str, bring: bool = False):
        """Troca de tela. Só traz a janela para frente quando pedido (bandeja/atalhos) — reativar a janela
        a cada clique fazia o Windows piscar."""
        i = self.index.get(key, 0)
        page = self.stack.widget(i)
        if hasattr(page, "ensure_built"):
            page.ensure_built()
        self.stack.setCurrentIndex(i)
        self.group.button(i).setChecked(True)
        if bring:
            if self.isMinimized():
                self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
            if not self.isVisible():
                self.show()
            self.raise_()
            self.activateWindow()

    def prebuild_pages(self):
        """Monta as outras telas aos poucos, com o app parado, para a primeira visita ser instantânea."""
        from PySide6.QtCore import QTimer
        pending = [self.stack.widget(i) for i in range(self.stack.count())]

        def step():
            while pending:
                pg = pending.pop(0)
                if hasattr(pg, "ensure_built") and not pg._built:
                    pg.ensure_built()
                    QTimer.singleShot(250, step)
                    return
        QTimer.singleShot(1500, step)

    def changed(self):
        settings.set("dirty", True)

    def apply_theme(self):
        theme.use(settings.get("theme"))
        QApplication.instance().setStyleSheet(theme.qss())

    def first_run(self):
        """Na primeira abertura: mostra a análise do PC e oferece o recomendado para ELE."""
        from lolitos.ui.pages.dashboard import boost, pc_analysis
        from lolitos.ui.theme import C
        from lolitos.ui.widgets import TaskDialog, confirm, run_async

        def show(r):
            settings.set("seen_analysis", True)
            p, adv, rec = r
            html = (f"<h3>Análise do seu PC: {p.tier_name}</h3><p>" + "<br>".join(p.summary()) + "</p>"
                    f"<p style='color:{C['muted']}'>{rec}</p>")
            html += "".join(f"<p><b>{t}</b><br>{txt}</p>" for t, txt in adv)
            html += ("<p>Aplicar agora os ajustes recomendados para este PC? Um ponto de restauração é criado antes "
                     "e tudo pode ser desfeito em Restauração.</p>")
            if confirm(self, "Bem-vindo ao Lolitos Control", html, yes="Aplicar o recomendado",
                       no="Agora não"):
                TaskDialog(self, "Otimizando para este PC", boost,
                           on_done=lambda _: self.changed()).exec()
        run_async(pc_analysis, on_done=show)

    # ---------------------------------------------------------------- bandeja
    def _tray(self):
        self.tray = QSystemTrayIcon(icon(), self)
        self.tray.setToolTip(APP_NAME)
        m = QMenu()
        m.addAction("Abrir", lambda: self.go("painel", bring=True))
        m.addAction("Jogos", lambda: self.go("jogos", bring=True))
        m.addAction("Black Desert", lambda: self.go("bdo", bring=True))
        m.addAction("Mostrar/ocultar overlay", self.overlay_toggle)
        m.addSeparator()
        m.addAction("Sair", self.quit)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda r: self.go("painel", bring=True) if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def closeEvent(self, e):
        if settings.get("tray_on_close") and self.tray.isVisible():
            e.ignore()
            self.hide()
            if not settings.get("tray_hint_shown"):
                settings.set("tray_hint_shown", True)
                self.tray.showMessage(APP_NAME, "Continuo na bandeja. O overlay abre com "
                                      f"{settings.get('overlay_hotkey')}. Para sair, clique com o botão direito "
                                      "neste ícone.")
            return
        self.quit()

    def quit(self):
        self.unregister_hotkey()
        self.overlay.hide()
        self.tray.hide()
        QApplication.instance().quit()

    # ---------------------------------------------------------------- overlay
    def overlay_toggle(self):
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.place()
            self.overlay.show()

    def overlay_reconfigure(self):
        if self.overlay.isVisible():
            self.overlay.tick()

    def overlay_auto_on(self):
        if settings.get("overlay_with_game") and not self.overlay.isVisible():
            self._overlay_auto = True
            self.overlay_toggle()

    def overlay_auto_off(self):
        if self._overlay_auto and self.overlay.isVisible():
            self.overlay.hide()
        self._overlay_auto = False

    def register_hotkey(self) -> bool:
        if not IS_WIN:
            return False
        self.unregister_hotkey()
        hk = parse_hotkey(settings.get("overlay_hotkey") or "")
        if not hk:
            return False
        from lolitos.ui.overlay import HotkeyThread
        from lolitos.ui.widgets import ui_call
        self._hotkey = HotkeyThread(hk[0], hk[1], lambda: ui_call(self.overlay_toggle))
        return self._hotkey.start()

    def unregister_hotkey(self):
        hk = getattr(self, "_hotkey", None)
        if hk:
            hk.stop()
            self._hotkey = None
