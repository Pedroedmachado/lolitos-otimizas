"""Janela principal: barra lateral, páginas, bandeja e tecla global do overlay."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QMenu,
                               QPushButton, QScrollArea, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget)

from lolitos import APP_NAME, VERSION
from lolitos.core import settings
from lolitos.core.system import IS_WIN, is_admin
from lolitos.ui import theme
from lolitos.ui.icon import icon
from lolitos.ui.overlay import Overlay, parse_hotkey
from lolitos.ui.widgets import label



def _pages():
    """Seções da barra lateral: (título da seção, [(chave, texto, classe)])."""
    from lolitos.ui.pages.apps_page import AppsPage
    from lolitos.ui.pages.bdo_page import BdoPage
    from lolitos.ui.pages.cleanup_page import CleanupPage
    from lolitos.ui.pages.dashboard import Dashboard
    from lolitos.ui.pages.debloat_page import DebloatPage
    from lolitos.ui.pages.games_page import GamesPage
    from lolitos.ui.pages.hardware_page import MyPcPage, PerformancePage
    from lolitos.ui.pages.maintenance_page import MaintenancePage
    from lolitos.ui.pages.fresh_page import FreshPage
    from lolitos.ui.pages.opt_pages import (DefenderAiPage, GpuComparePage, GpuPage, KeyboardPage, MousePage,
                                            WindowsPage)
    from lolitos.ui.pages.overlay_page import OverlayPage
    from lolitos.ui.pages.profiles_page import ProfilesPage
    from lolitos.ui.pages.restore_page import RestorePage
    from lolitos.ui.pages.settings_page import SettingsPage
    from lolitos.ui.pages.startup_page import StartupPage
    from lolitos.ui.pages.tools_pages import (CheckupPage, MonitorTestPage, MouseTestPage, PacketLossPage,
                                              SpeedTestPage)
    from lolitos.ui.pages.full_opt_page import FullOptPage
    from lolitos.ui.pages.hwmon_page import HwMonitorPage
    return [
        ("PRINCIPAL", [
            ("painel", "home", "Painel", Dashboard), ("manutencao", "repair", "Manutenção", MaintenancePage),
            ("desempenho", "speed", "Desempenho", PerformancePage), ("meupc", "pc", "Meu PC", MyPcPage),
            ("hwmon", "sensor", "Hardware Monitor", HwMonitorPage), ("bdo", "bdo", "Black Desert", BdoPage),
            ("completa", "bolt", "Otimização Completa", FullOptPage)]),
        ("OTIMIZAR", [
            ("formatacao", "fresh", "Formatação", FreshPage), ("debloat", "debloat", "Debloat", DebloatPage),
            ("windows", "windows", "Windows", WindowsPage), ("mouse", "mouse", "Mouse", MousePage),
            ("teclado", "keyboard", "Teclado", KeyboardPage), ("gpu", "gpu", "GPU", GpuPage),
            ("perfis", "profiles", "Perfis", ProfilesPage), ("jogos", "games", "Jogos", GamesPage),
            ("apps", "apps", "Instalar apps", AppsPage), ("limpeza", "clean", "Limpeza", CleanupPage),
            ("inicializacao", "power", "Inicialização", StartupPage)]),
        ("FERRAMENTAS", [
            ("overlay", "overlay", "Overlay de jogo", OverlayPage), ("teste_mouse", "mouse", "Teste do mouse", MouseTestPage),
            ("teste_monitor", "monitor", "Teste de monitor", MonitorTestPage),
            ("velocidade", "download", "Teste de velocidade", SpeedTestPage),
            ("perda", "network", "Perda de pacotes", PacketLossPage),
            ("comparar", "compare", "Comparar placas", GpuComparePage), ("defender", "shield", "Defender e IA", DefenderAiPage),
            ("checkup", "heart", "Check-up", CheckupPage)]),
        ("SISTEMA", [
            ("restauracao", "history", "Restauração", RestorePage), ("config", "settings", "Configurações", SettingsPage)]),
    ]


# nomes antigos (atalhos, bandeja, versões anteriores) → telas novas
ALIASES = {"ajustes": "windows", "hardware": "meupc", "ferramentas": "manutencao", "rede": "perda"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from lolitos.ui.widgets import init_ui_thread
        init_ui_thread()
        self.setWindowTitle(f"{APP_NAME} {VERSION}" + ("" if is_admin() else "  (sem administrador)"))
        self.setWindowIcon(icon())
        self.resize(1240, 820)
        self.setMinimumSize(800, 600)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        from lolitos.i18n import current
        from lolitos.ui.nav import Brand, Flag, NavButton
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(256)
        self.side = side
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 18, 10, 12)
        sl.setSpacing(4)
        self.brand = Brand()
        sl.addWidget(self.brand)
        self.flags = QWidget()
        fl = QHBoxLayout(self.flags)
        fl.setContentsMargins(8, 8, 0, 4)
        fl.setSpacing(8)
        for code in ("pt", "es", "en"):
            f = Flag(code, current() == code)
            f.clicked.connect(self.set_language)
            fl.addWidget(f)
        fl.addStretch()
        sl.addWidget(self.flags)
        self.collapse_btn = NavButton("menu", "Recolher menu")
        self.collapse_btn.setCheckable(False)
        self.collapse_btn.clicked.connect(self.toggle_collapse)
        sl.addWidget(self.collapse_btn)
        sl.addSpacing(4)
        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        self.index = {}
        self.nav_buttons: list[NavButton] = []
        self.nav_sections: list[QWidget] = []
        nav_scroll = QScrollArea()
        nav_scroll.setObjectName("navscroll")
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_w = QWidget()
        nav_w.setObjectName("navlist")
        nl = QVBoxLayout(nav_w)
        nl.setContentsMargins(0, 0, 6, 0)
        nl.setSpacing(2)
        i = 0
        for section, items in _pages():
            nl.addSpacing(8 if i else 2)
            sec = label(section, "navsec")
            self.nav_sections.append(sec)
            nl.addWidget(sec)
            for key, ico, text, cls in items:
                b = NavButton(ico, text, special=key == "completa", badge="NOVO" if key == "comparar" else "")
                b.clicked.connect(lambda _=False, k=key: self.go(k))
                self.group.addButton(b, i)
                self.nav_buttons.append(b)
                nl.addWidget(b)
                if not cls.icon:
                    cls.icon = ico          # o mesmo ícone no cabeçalho da tela
                self.stack.addWidget(cls(self))
                self.index[key] = i
                i += 1
        nl.addStretch()
        nav_scroll.setWidget(nav_w)
        sl.addWidget(nav_scroll, 1)
        self.update_btn = QPushButton("⟳  Procurar atualização")
        self.update_btn.setObjectName("update")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setToolTip("Confere no GitHub se há versão nova do Chinese Control")
        self.update_btn.clicked.connect(lambda: self.check_update(manual=True))
        sl.addWidget(self.update_btn)
        lay.addWidget(side)
        lay.addWidget(self.stack, 1)
        if settings.get("nav_collapsed"):
            self._set_collapsed(True)
            settings.set("nav_manual", True)

        from lolitos.i18n import translate_tree
        translate_tree(side)
        self.overlay = Overlay()
        self._overlay_auto = False
        self._tray()
        self.go("painel")
        self.register_hotkey()
        self.prebuild_pages()
        self._update_info = None
        if settings.get("check_updates", True):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(5000, lambda: self.check_update(manual=False))
        if not settings.get("seen_analysis"):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(900, self.first_run)

    # ---------------------------------------------------------------- barra lateral
    AUTO_COLLAPSE_W = 1100     # abaixo disso o menu recolhe sozinho (a menos que você tenha escolhido)

    def toggle_collapse(self):
        """Clique no 'Recolher menu': vira escolha manual, que vale também em janela estreita."""
        col = self.side.width() > 100
        self._set_collapsed(col)
        settings.set("nav_collapsed", col)
        settings.set("nav_manual", True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if settings.get("nav_manual") or not hasattr(self, "side"):
            return
        narrow = self.width() < self.AUTO_COLLAPSE_W
        if narrow != (self.side.width() <= 100):
            self._set_collapsed(narrow)

    def _set_collapsed(self, col: bool):
        self.side.setFixedWidth(68 if col else 256)
        self.brand.set_collapsed(col)
        self.flags.setVisible(not col)
        for sec in self.nav_sections:
            sec.setVisible(not col)
        for b in self.nav_buttons + [self.collapse_btn]:
            b.set_collapsed(col)
        self.update_btn.setText("⟳" if col else ("⟳  " + __import__("lolitos.i18n", fromlist=["tr"]).tr(
            "Procurar atualização")))

    def set_language(self, code: str):
        from lolitos.i18n import current, restart_text
        from lolitos.ui.widgets import confirm
        if code == current():
            return
        settings.set("lang", code)
        if confirm(self, "Idioma", restart_text(code), yes="OK", no="Depois"):
            from lolitos.core.system import relaunch_self
            relaunch_self()
            self.quit()

    # ---------------------------------------------------------------- navegação
    def go(self, key: str, bring: bool = False):
        """Troca de tela. Só traz a janela para frente quando pedido (bandeja/atalhos) — reativar a janela
        a cada clique fazia o Windows piscar."""
        i = self.index.get(ALIASES.get(key, key), 0)
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

    # ---------------------------------------------------------------- atualização
    def check_update(self, manual: bool = True):
        from lolitos.modules import updater
        from lolitos.ui.widgets import info, run_async

        def found(inf):
            self._update_info = inf
            if not inf:
                self.update_btn.setText("⟳  Procurar atualização")
                if manual:
                    info(self, "Atualização", f"Você já está na versão mais recente ({VERSION}).")
                return
            self.update_btn.setText(f"⬆  Atualizar para {inf['version']}")
            self.update_btn.setStyleSheet(f"color:{theme.C['accent2']}; font-weight:700;")
            if manual:
                self.do_update(inf)
            elif self.tray.isVisible():
                self.tray.showMessage(APP_NAME, f"Versão {inf['version']} disponível. Clique em 'Atualizar' na "
                                                "barra lateral.")

        def failed(err):
            self.update_btn.setText("⟳  Procurar atualização")
            if manual:
                info(self, "Atualização", f"Não foi possível consultar o GitHub agora.\n\n{err}")

        if manual and self._update_info:
            self.do_update(self._update_info)
            return
        if manual:
            self.update_btn.setText("⟳  Procurando…")
        run_async(updater.check, on_done=found, on_error=failed)

    def do_update(self, inf: dict):
        import webbrowser
        from lolitos.modules import updater
        from lolitos.ui.widgets import TaskDialog, confirm, info
        notes = inf["notes"][:1200].replace("\n", "<br>") if inf["notes"] else ""
        if not updater.can_self_update():
            if confirm(self, "Atualização", f"Versão <b>{inf['version']}</b> disponível.<br><br>Esta cópia roda "
                       "direto do código, então a atualização automática não se aplica. Abrir a página de "
                       "download?", yes="Abrir página"):
                webbrowser.open(inf["page"])
            return
        if not confirm(self, "Atualizar o Chinese Control",
                       f"<p>Versão <b>{inf['version']}</b> disponível (você tem a {VERSION}).</p>"
                       + (f"<p>{notes}</p>" if notes else "")
                       + "<p>O instalador é baixado do GitHub, conferido e executado sem janelas. O app fecha e "
                         "abre de novo sozinho em alguns segundos. Histórico, perfis e configurações são mantidos.</p>",
                       yes="Atualizar agora", no="Depois"):
            return

        def work(progress=None):
            last = [-1]

            def pct(p):
                if p // 10 != last[0]:
                    last[0] = p // 10
                    progress(f"Baixando… {p}%")
            progress(f"Baixando {inf['name']} do GitHub…")
            path = updater.download(inf, pct)
            progress("Download conferido (tamanho" + (" e SHA-256" if inf["sha256"] else "") + ").")
            return str(path)

        def done(path):
            if not path:
                return
            updater.install_and_restart(Path(path))
            self.quit()

        dlg = TaskDialog(self, "Atualizando o Chinese Control", work, on_done=done)
        dlg.exec()
        if dlg.result_value is None:
            info(self, "Atualização", "A atualização não foi concluída. Tente de novo mais tarde.")

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
            if confirm(self, "Bem-vindo ao Chinese Control", html, yes="Aplicar o recomendado",
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
