"""Configurações: seções em cartões (Aparência, Inicialização, Atualizações, Segurança, Jogo, Dados) e o Sobre.
Cada linha tem ícone, título, explicação curta e o controle à direita."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from lolitos import APP_NAME, VERSION
from lolitos.core import settings
from lolitos.core.system import data_dir, resource_path
from lolitos.i18n import tr
from lolitos.modules import startup
from lolitos.ui.widgets import Card, Page, Toggle, button, confirm, hrow, label, run_async


def _row(icon: str, title: str, text: str, control) -> QFrame:
    f = QFrame()
    f.setObjectName("setrow")
    h = QHBoxLayout(f)
    h.setContentsMargins(0, 12, 0, 12)
    h.setSpacing(14)
    ic = QLabel(icon)
    ic.setObjectName("seticon")
    ic.setFixedSize(36, 36)
    ic.setAlignment(Qt.AlignCenter)
    h.addWidget(ic, 0, Qt.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(2)
    col.addWidget(label(f"<b>{tr(title)}</b>", rich=True))
    if text:
        col.addWidget(label(text, "muted"))
    h.addLayout(col, 1)
    if control is not None:
        if isinstance(control, QHBoxLayout):
            h.addLayout(control)
        else:
            h.addWidget(control, 0, Qt.AlignVCenter)
    return f


def _section(title: str, sub: str = "") -> Card:
    c = Card()
    c.lay.setSpacing(0)
    c.lay.addWidget(label(title, "h2"))
    if sub:
        s = label(sub, "muted")
        s.setContentsMargins(0, 2, 0, 8)
        c.lay.addWidget(s)
    else:
        c.lay.addSpacing(8)
    return c


def _toggle(key: str, default=None) -> Toggle:
    t = Toggle(bool(settings.get(key, default)))
    t.toggled.connect(lambda v: settings.set(key, v))
    return t


class SettingsPage(Page):
    title = "Configurações"
    subtitle = "Aparência, inicialização, atualizações e segurança do Chinese Control."

    def build(self):
        from lolitos.i18n import LANGS, current
        from lolitos.ui import fx as _fx
        from lolitos.ui.theme import THEME_NAMES

        # ---------------------------------------------------------------- Aparência
        ap = _section("Aparência")
        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.theme_group = QButtonGroup(self)
        cur = settings.get("theme")
        for key, name in THEME_NAMES:
            b = QPushButton(tr(name))
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(key == cur)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.main.set_theme(k))
            self.theme_group.addButton(b)
            seg.addWidget(b)
        ap.lay.addWidget(_row("◐", "Tema", "Escuro, Claro ou Azul. Muda na hora, sem reiniciar.", seg))
        self.fx_cb = QComboBox()
        for lv, name in _fx.LEVELS:
            self.fx_cb.addItem(tr(name), lv)
        self.fx_cb.setCurrentIndex(_fx.current_from_settings())
        self.fx_cb.currentIndexChanged.connect(lambda _: self.main.set_effects(self.fx_cb.currentData()))
        ap.lay.addWidget(_row("✦", "Efeitos visuais",
                              "Básicos: vidro, telas esmaecendo e chaves deslizando. Completos: também desfoque na "
                              "troca de tela, título digitando, onda ao clicar e luz que segue o mouse. Em PC fraco, "
                              "use Desligados.", self.fx_cb))
        self.lang = QComboBox()
        for code, name in LANGS.items():
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(list(LANGS).index(current()))
        self.lang.currentIndexChanged.connect(self._lang)
        ap.lay.addWidget(_row("🌐", "Idioma / Language / Idioma", "Português, English ou Español.", self.lang))
        ap.lay.addWidget(_row("▶", "Apresentação do app", "Mostra de novo a volta guiada pelas telas principais.",
                              button("Rever a apresentação", on_click=lambda: self.main.show_tour())))
        self.body.addWidget(ap)

        # ---------------------------------------------------------------- Inicialização
        ini = _section("Inicialização")
        auto = Toggle(False)
        run_async(startup.self_autostart_enabled,
                  on_done=lambda v: (auto.blockSignals(True), auto.setChecked(bool(v)), auto.blockSignals(False)))
        auto.toggled.connect(lambda on: run_async(startup.self_autostart, on))
        ini.lay.addWidget(_row("⏻", "Iniciar com o Windows",
                               "Abre minimizado na bandeja, já como administrador, para o overlay e a tecla de "
                               "atalho estarem prontos.", auto))
        ini.lay.addWidget(_row("▾", "Fechar para a bandeja",
                               "Ao fechar a janela, o app continua na bandeja (o overlay e a tecla continuam "
                               "funcionando).", _toggle("tray_on_close")))
        self.body.addWidget(ini)

        # ---------------------------------------------------------------- Atualizações
        up = _section("Atualizações")
        up.lay.addWidget(_row("⟳", "Procurar atualizações automaticamente",
                              "Confere no GitHub ao abrir o app e a cada 6 horas.", _toggle("check_updates", True)))
        ver = label(VERSION, "pill", wrap=False)
        up.lay.addWidget(_row("ⓘ", "Versão instalada", f"{APP_NAME} {VERSION}", ver))
        up.lay.addWidget(_row("⬆", "Procurar atualização agora",
                              "Se houver versão nova, ela é baixada, conferida e instalada sem perder nada.",
                              button("Procurar agora", "outline", on_click=lambda: self.main.check_update(True))))
        self.body.addWidget(up)

        # ---------------------------------------------------------------- Segurança
        sec = _section("Segurança")
        sec.lay.addWidget(_row("⛨", "Ponto de restauração antes de aplicar",
                               "Cria um ponto de restauração do Windows antes de aplicar em lote (reaproveita o das "
                               "últimas 24 h).", _toggle("restore_point_before")))
        self.body.addWidget(sec)

        # ---------------------------------------------------------------- Jogo
        jg = _section("Preparar e jogar")
        jg.lay.addWidget(_row("▣", "Liberar RAM antes de abrir o jogo", "", _toggle("play_free_ram")))
        jg.lay.addWidget(_row("⚡", "Plano de energia só durante a partida",
                              "Troca para o plano de alto desempenho ao abrir o jogo e volta ao fechar.",
                              _toggle("play_power_plan")))
        self.body.addWidget(jg)

        # ---------------------------------------------------------------- Dados
        dd = _section("Dados do aplicativo")
        dd.lay.addWidget(_row("🗀", "Pasta de dados",
                              f"{data_dir()}  ·  " + tr("histórico, perfis, configurações e registros."),
                              button("Abrir pasta", on_click=lambda: os.startfile(str(data_dir())))))
        self.body.addWidget(dd)

        # ---------------------------------------------------------------- Sobre
        ab = Card()
        ab.lay.addWidget(label(f"{APP_NAME} {VERSION}", "h2"))
        ab.lay.addWidget(label("Manutenção e otimização do Windows para jogos, com as ferramentas do próprio sistema "
                               "e um módulo especial para Black Desert Online. Tudo roda localmente; o app só acessa a internet quando você pede "
                               "(instalar apps, teste de velocidade).", "muted"))
        lic = resource_path("WINUTIL_LICENSE.txt")
        ab.lay.addWidget(label("Catálogo de apps: projeto WinUtil de Chris Titus Tech (licença MIT). "
                               "FPS: PresentMon da Intel (licença MIT), opcional.", "muted"))
        if lic.exists():
            ab.lay.addLayout(hrow(button("Ver licença do WinUtil", on_click=lambda: os.startfile(str(lic))), None))
        self.body.addWidget(ab)

    def showEvent(self, e):
        super().showEvent(e)
        cur = settings.get("theme")          # o tema pode ter mudado pela barra lateral
        from lolitos.ui.theme import THEME_NAMES
        for b, (key, _n) in zip(self.theme_group.buttons(), THEME_NAMES):
            b.setChecked(key == cur)

    def _lang(self):
        code = self.lang.currentData()
        settings.set("lang", code)
        from lolitos.i18n import restart_text
        if confirm(self, "Idioma", restart_text(code), yes="OK", no="Depois"):
            from lolitos.core.system import relaunch_self
            relaunch_self()
            self.main.quit()
