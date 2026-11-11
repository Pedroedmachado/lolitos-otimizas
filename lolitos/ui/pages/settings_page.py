"""Configurações do app, idioma e sobre."""
import os

from PySide6.QtWidgets import QCheckBox, QComboBox

from lolitos import APP_NAME, VERSION
from lolitos.core import settings
from lolitos.core.system import data_dir, resource_path
from lolitos.modules import startup
from lolitos.ui.widgets import Card, Page, button, confirm, hrow, label, run_async


class SettingsPage(Page):
    title = "Configurações"

    def build(self):
        c = Card()
        c.lay.addWidget(label("Aplicativo", "h2"))
        from lolitos.i18n import LANGS, current
        self.lang = QComboBox()
        for code, name in LANGS.items():
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(list(LANGS).index(current()))
        self.lang.currentIndexChanged.connect(self._lang)
        c.lay.addLayout(hrow(label("Idioma / Language / Idioma", wrap=False), self.lang, None))
        from lolitos.ui.theme import THEME_NAMES
        self.theme_cb = QComboBox()
        for key, name in THEME_NAMES:
            self.theme_cb.addItem(name, key)
        keys = [k for k, _ in THEME_NAMES]
        self.theme_cb.setCurrentIndex(keys.index(settings.get("theme")) if settings.get("theme") in keys else 2)
        self.theme_cb.currentIndexChanged.connect(lambda _: self.main.set_theme(self.theme_cb.currentData()))
        c.lay.addLayout(hrow(label("Tema", wrap=False), self.theme_cb, None))
        from lolitos.ui import fx as _fx
        self.fx_cb = QComboBox()
        for lv, name in _fx.LEVELS:
            self.fx_cb.addItem(name, lv)
        self.fx_cb.setCurrentIndex(_fx.current_from_settings())
        self.fx_cb.currentIndexChanged.connect(lambda _: self.main.set_effects(self.fx_cb.currentData()))
        c.lay.addLayout(hrow(label("Efeitos visuais", wrap=False), self.fx_cb, None))
        c.lay.addWidget(label("Básicos: vidro, telas esmaecendo, chaves deslizando e brilho nos botões. Completos: "
                              "também onda ao clicar, reflexo nos botões principais, luz que segue o mouse, cartões "
                              "que levantam e telas que entram deslizando. Em PC fraco, use Desligados.", "muted"))
        tray = QCheckBox("Ao fechar a janela, continuar na bandeja (o overlay e a tecla continuam funcionando)")
        tray.setChecked(settings.get("tray_on_close"))
        tray.toggled.connect(lambda v: settings.set("tray_on_close", v))
        rp = QCheckBox("Criar ponto de restauração antes de aplicar em lote (reaproveita o das últimas 24 h)")
        rp.setChecked(settings.get("restore_point_before"))
        rp.toggled.connect(lambda v: settings.set("restore_point_before", v))
        auto = QCheckBox("Iniciar com o Windows (minimizado na bandeja, já como administrador)")
        run_async(startup.self_autostart_enabled,
                  on_done=lambda v: (auto.blockSignals(True), auto.setChecked(bool(v)), auto.blockSignals(False)))
        auto.toggled.connect(lambda on: run_async(startup.self_autostart, on))
        free = QCheckBox("'Preparar e jogar': liberar RAM antes de abrir o jogo")
        free.setChecked(settings.get("play_free_ram"))
        free.toggled.connect(lambda v: settings.set("play_free_ram", v))
        plan = QCheckBox("'Preparar e jogar': trocar o plano de energia só durante a partida")
        plan.setChecked(settings.get("play_power_plan"))
        plan.toggled.connect(lambda v: settings.set("play_power_plan", v))
        upd = QCheckBox("Procurar atualização no GitHub ao abrir o app")
        upd.setChecked(settings.get("check_updates", True))
        upd.toggled.connect(lambda v: settings.set("check_updates", v))
        for w in (tray, rp, auto, free, plan, upd):
            c.lay.addWidget(w)
        c.lay.addLayout(hrow(button("Abrir pasta de dados", on_click=lambda: os.startfile(str(data_dir()))), None))
        self.body.addWidget(c)

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

    def _lang(self):
        code = self.lang.currentData()
        settings.set("lang", code)
        from lolitos.i18n import restart_text
        if confirm(self, "Idioma", restart_text(code), yes="OK", no="Depois"):
            from lolitos.core.system import relaunch_self
            relaunch_self()
            self.main.quit()
