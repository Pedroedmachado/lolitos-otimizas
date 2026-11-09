"""Configurações do app, antivírus e sobre."""
import os

from PySide6.QtWidgets import QCheckBox

from lolitos import APP_NAME, VERSION
from lolitos.core import settings
from lolitos.core.system import data_dir, resource_path
from lolitos.modules import antivirus, startup
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, button, hrow, info, label, run_async


class SettingsPage(Page):
    title = "Configurações"

    def build(self):
        c = Card()
        c.lay.addWidget(label("Aplicativo", "h2"))
        dark = QCheckBox("Tema escuro")
        dark.setChecked(settings.get("theme") == "dark")
        dark.toggled.connect(lambda v: (settings.set("theme", "dark" if v else "light"), self.main.apply_theme()))
        tray = QCheckBox("Ao fechar a janela, continuar na bandeja (o overlay e a tecla continuam funcionando)")
        tray.setChecked(settings.get("tray_on_close"))
        tray.toggled.connect(lambda v: settings.set("tray_on_close", v))
        rp = QCheckBox("Criar ponto de restauração antes de aplicar em lote (reaproveita o das últimas 24 h)")
        rp.setChecked(settings.get("restore_point_before"))
        rp.toggled.connect(lambda v: settings.set("restore_point_before", v))
        auto = QCheckBox("Iniciar com o Windows (minimizado na bandeja, já como administrador)")
        run_async(startup.self_autostart_enabled, on_done=auto.setChecked)
        auto.toggled.connect(startup.self_autostart)
        free = QCheckBox("'Preparar e jogar': liberar RAM antes de abrir o jogo")
        free.setChecked(settings.get("play_free_ram"))
        free.toggled.connect(lambda v: settings.set("play_free_ram", v))
        plan = QCheckBox("'Preparar e jogar': trocar o plano de energia só durante a partida")
        plan.setChecked(settings.get("play_power_plan"))
        plan.toggled.connect(lambda v: settings.set("play_power_plan", v))
        upd = QCheckBox("Procurar atualização no GitHub ao abrir o app")
        upd.setChecked(settings.get("check_updates", True))
        upd.toggled.connect(lambda v: settings.set("check_updates", v))
        for w in (dark, tray, rp, auto, free, plan, upd):
            c.lay.addWidget(w)
        c.lay.addLayout(hrow(button("Abrir pasta de dados", on_click=lambda: os.startfile(str(data_dir()))), None))
        self.body.addWidget(c)

        av = Card()
        av.lay.addWidget(label("Antivírus", "h2"))
        av.lay.addWidget(label("Antivírus costumam bloquear mudanças no registro, serviços e tarefas, mesmo com o app "
                               "como administrador. O app nunca desliga nem contorna a proteção: no máximo marca a "
                               "si mesmo como confiável.", "muted"))
        self.av_lbl = label("Lendo o antivírus…", rich=True)
        av.lay.addWidget(self.av_lbl)
        av.lay.addLayout(hrow(button("Liberar este app no Microsoft Defender", on_click=self._def_add),
                              button("Remover a liberação", on_click=self._def_rm), None))
        self.body.addWidget(av)
        run_async(antivirus.products, on_done=self._av)

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

    def _av(self, prods):
        if not prods:
            self.av_lbl.setText("Nenhum antivírus registrado na Central de Segurança do Windows.")
            return
        lines = []
        for p in prods:
            st = (f"<span style='color:{C['ok']}'>proteção em tempo real ligada</span>" if p["realtime"]
                  else f"<span style='color:{C['warn']}'>tempo real desligado</span>")
            g = "" if "defender" in p["name"].lower() else f"<br><span style='color:{C['muted']}'>Como liberar: " \
                                                           f"{antivirus.guide_for(p['name'])}</span>"
            lines.append(f"<b>{p['name']}</b> · {st}{g}")
        lines.append(f"<span style='color:{C['muted']}'>Pasta do app: {antivirus.app_folder()}</span>")
        self.av_lbl.setText("<br>".join(lines))

    def _def_add(self):
        ok, msg = antivirus.defender_add_app()
        info(self, "Defender", "O Defender agora confia neste app." if ok else msg or "Não foi possível.")

    def _def_rm(self):
        ok, msg = antivirus.defender_remove_app()
        info(self, "Defender", "Liberação removida." if ok else msg or "Não foi possível.")
