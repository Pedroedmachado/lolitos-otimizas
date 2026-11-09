"""Formatação: Windows recém-instalado pronto de uma vez — programas, Boost completo e extras."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QVBoxLayout

from lolitos.core.tweaks import CATALOG
from lolitos.i18n import tr
from lolitos.modules import winget
from lolitos.modules.winget import App
from lolitos.ui.appgrid import AppGrid, chip_bar
from lolitos.ui.pages.opt_pages import FRESH_DEFAULT, FRESH_GROUPS, fresh_setup
from lolitos.ui.widgets import (Card, IconTile, Page, TaskDialog, button, confirm, info, label, pill, run_async,
                                status_pool)

# programas que não estão no catálogo do WinUtil (IDs conferidos no repositório oficial do winget)
EXTRA_LINKS = {
    "Opera.OperaGX": "https://www.opera.com/gx", "RiotGames.LeagueOfLegends.BR": "https://www.leagueoflegends.com",
    "RiotGames.Valorant.BR": "https://playvalorant.com", "Amazon.Games": "https://gaming.amazon.com",
    "Mojang.MinecraftLauncher": "https://www.minecraft.net", "ppy.osu": "https://osu.ppy.sh",
    "Logitech.GHUB": "https://www.logitechg.com", "SteelSeries.GG": "https://steelseries.com",
    "Corsair.iCUE.5": "https://www.corsair.com", "Elgato.StreamDeck": "https://www.elgato.com",
    "Streamlabs.Streamlabs": "https://streamlabs.com", "VB-Audio.Voicemeeter": "https://vb-audio.com",
    "VB-Audio.Voicemeeter.Banana": "https://vb-audio.com", "Deezer.Deezer": "https://www.deezer.com",
    "Malwarebytes.Malwarebytes": "https://www.malwarebytes.com", "Greenshot.Greenshot": "https://getgreenshot.org",
    "BleachBit.BleachBit": "https://www.bleachbit.org", "RevoUninstaller.RevoUninstaller": "https://www.revouninstaller.com",
    "Intel.IntelDriverAndSupportAssistant": "https://www.intel.com", "Nvidia.PhysX": "https://www.nvidia.com",
    "Oracle.JavaRuntimeEnvironment": "https://www.java.com", "Mega.MEGASync": "https://mega.io",
    "Google.GoogleDrive": "https://www.google.com/drive", "Overwolf.CurseForge": "https://www.curseforge.com",
    "Nvidia.GeForceNow": "https://www.nvidia.com", "Ookla.Speedtest.Desktop": "https://www.speedtest.net",
    "LocalSend.LocalSend": "https://localsend.org", "Proton.ProtonVPN": "https://protonvpn.com",
}
EXTRA_CAT = {"Hardware e monitoramento": "Hardware", "Lojas e launchers de jogos": "Games", "Navegadores": "Browsers",
             "Comunicação": "Communications", "Gravação e streaming": "Multimedia Tools",
             "Música e vídeo": "Multimedia Tools", "Utilitários": "Utilities", "Documentos e criação": "Document",
             "Programação": "Development"}


def full_catalog() -> list[App]:
    """Catálogo do WinUtil + 'Essenciais para jogos' + os programas extras da lista da Formatação."""
    base = winget.catalog()
    have = {a.winget.lower() for a in base}
    out = list(base)
    for title, _note, items in FRESH_GROUPS:
        cat = "Essentials" if title == "Essenciais para jogos" else EXTRA_CAT.get(title, "Utilities")
        for name, wid in items:
            if cat == "Essentials":
                out.append(App(wid, name, "Biblioteca que jogos usam (Microsoft/NVIDIA/Oracle).", cat, wid,
                               EXTRA_LINKS.get(wid, ""), False))
            elif wid.lower() not in have:
                out.append(App(wid, name, "", cat, wid, EXTRA_LINKS.get(wid, ""), False))
                have.add(wid.lower())
    return out


class FreshPage(Page):
    title = "Formatação"
    subtitle = ("Configure um Windows recém-formatado de uma vez só: marque os apps abaixo, deixe o Boost completo "
                "ligado e clique em Iniciar configuração. No fim, o app pergunta se pode reiniciar.")

    def build(self):
        self.count = pill(tr("0 selecionado(s)"))
        self.actions.addWidget(self.count, 0, Qt.AlignTop)
        hero = Card(hero=True)
        hero.lay.addWidget(label("ESCOLHA OS APPS QUE DESEJA INSTALAR", "bigtitle"))
        hero.lay.addWidget(label("Clique nos apps para marcar. Eles são instalados junto com o Boost quando você clicar "
                                 "em Iniciar configuração, no fim da página.", "muted"))
        self.body.addWidget(hero)
        top = QHBoxLayout()
        self.q = QLineEdit()
        self.q.setPlaceholderText("Buscar apps…")
        top.addWidget(self.q, 1)
        top.addWidget(button("Só os essenciais", on_click=lambda: self.grid.set_selected(FRESH_DEFAULT)))
        top.addWidget(button("Limpar seleção", on_click=lambda: self.grid.set_selected([])))
        self.body.addLayout(top)
        self.grid = AppGrid(full_catalog(), FRESH_DEFAULT)
        self.grid.changed.connect(self._count)
        self.q.textChanged.connect(lambda t: self.grid.set_filter(text=t))
        self.body.addWidget(chip_bar(self.grid))
        self.status = label("Verificando o que já está instalado…", "muted")
        self.body.addWidget(self.status)
        self.body.addWidget(self.grid)
        self.body.addWidget(label("Catálogo de apps: projeto WinUtil (licença MIT) e programas conferidos no "
                                  "repositório oficial do winget. Clique direito em um app abre o site oficial.",
                                  "muted"))

        boost = Card()
        r = QHBoxLayout()
        r.setSpacing(14)
        r.addWidget(IconTile("bolt", 44, 15), 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.addWidget(label("<b>Boost completo</b>", "h3", rich=True))
        col.addWidget(label("Os mesmos ajustes do botão 'Boost agora' do Painel (desempenho, jogos, GPU, rede e "
                            "privacidade recomendados para este PC), a remoção dos apps pré-instalados recomendados e a "
                            "limpeza dos temporários.", "muted"))
        self.ck_boost = QCheckBox("Aplicar o Boost completo")
        self.ck_boost.setChecked(True)
        col.addWidget(self.ck_boost)
        self.boost_info = label("", "muted")
        col.addWidget(self.boost_info)
        r.addLayout(col, 1)
        boost.lay.addLayout(r)
        self.body.addWidget(boost)

        ex = Card()
        r = QHBoxLayout()
        r.setSpacing(14)
        r.addWidget(IconTile("flag", 44, 15), 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.addWidget(label("<b>Extras para Windows recém-instalado</b>", "h3", rich=True))
        col.addWidget(label("Preferências que costumam ir num Windows novo. Tudo pode ser desfeito em Restauração.",
                            "muted"))
        self.ck_rp = QCheckBox("Criar um ponto de restauração antes de tudo")
        self.ck_rp.setChecked(True)
        self.ck_photo = QCheckBox("Visualizador de Fotos clássico do Windows")
        self.ck_onedrive = QCheckBox("Remover o OneDrive")
        for ck in (self.ck_rp, self.ck_photo, self.ck_onedrive):
            col.addWidget(ck)
        r.addLayout(col, 1)
        ex.lay.addLayout(r)
        self.body.addWidget(ex)

        go = Card(hero=True)
        r = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(label("<b>Iniciar configuração</b>", "h3", rich=True))
        self.go_sum = label("", "muted")
        col.addWidget(self.go_sum)
        r.addLayout(col, 1)
        self.go_btn = button("Iniciar configuração", "primary", self._run)
        self.go_btn.setMinimumHeight(46)
        self.go_btn.setMinimumWidth(240)
        r.addWidget(self.go_btn)
        go.lay.addLayout(r)
        self.body.addWidget(go)
        self.ck_boost.toggled.connect(self._count)
        self._count()
        run_async(lambda: (winget.ensure_winget() and winget.installed_ids()) or set(), on_done=self._installed)
        run_async(self._boost_pending, on_done=lambda n: self.boost_info.setText(
            tr("{} ajuste(s) pendente(s) neste PC serão aplicados, mais a limpeza dos temporários.")
            .replace("{}", str(n))), _pool=status_pool())

    @staticmethod
    def _boost_pending():
        from lolitos.catalog.presets import boost_ids
        return sum(1 for i in boost_ids() if CATALOG[i].status() not in ("on", "na"))

    def _installed(self, ids):
        self.grid.mark_installed(ids)
        n = sum(1 for t in self.grid.tiles if t.installed)
        self.status.setText(tr("{} app(s) da lista já instalados (ponto verde).").replace("{}", str(n)) if ids else
                            tr("O winget não está disponível neste PC ou nada foi encontrado."))

    def _count(self, *_):
        n = len(self.grid.selected())
        self.count.setText(tr("{} selecionado(s)").replace("{}", str(n)))
        parts = [tr("{} app(s) marcado(s)").replace("{}", str(n)) if n else tr("nenhum app marcado")]
        if self.ck_boost.isChecked():
            parts.append(tr("Boost completo"))
        self.go_sum.setText(" · ".join(parts) + ". " + tr("Tudo numa janela só; no fim, pergunta se pode reiniciar."))

    def _run(self):
        ids = self.grid.selected()
        boost = self.ck_boost.isChecked()
        extras = [i for i, ck in (("photo_viewer_classic", self.ck_photo), ("onedrive_remove", self.ck_onedrive))
                  if ck.isChecked()]
        if not ids and not boost and not extras:
            info(self, "Formatação", "Marque pelo menos um app, o Boost completo ou um extra.")
            return
        todo = []
        if self.ck_rp.isChecked():
            todo.append(tr("ponto de restauração"))
        if boost:
            todo.append(tr("Boost completo (ajustes + debloat recomendados)"))
        if extras:
            todo.append(tr("{} extra(s)").replace("{}", str(len(extras))))
        if ids:
            todo.append(tr("{} programa(s)").replace("{}", str(len(ids))))
        if boost:
            todo.append(tr("limpeza dos temporários"))
        if not confirm(self, "Iniciar configuração", "Vai fazer, nesta ordem:<br>• " + "<br>• ".join(todo) +
                       "<br><br>" + tr("Pode levar de 5 a 30 minutos dependendo da internet."), yes="Começar"):
            return
        TaskDialog(self, "Preparando o Windows", fresh_setup, self.ck_rp.isChecked(), boost, boost, ids, boost,
                   extras, on_done=lambda _: self._done()).exec()

    def _done(self):
        if self.main:
            self.main.changed()
        if confirm(self, "Formatação", "Pronto. Vários ajustes só valem depois de reiniciar. Reiniciar o PC agora?",
                   yes="Reiniciar agora", no="Depois"):
            from lolitos.core.system import run
            run(["shutdown", "/r", "/t", "5", "/c", "Chinese Control: reiniciando para concluir os ajustes."])
