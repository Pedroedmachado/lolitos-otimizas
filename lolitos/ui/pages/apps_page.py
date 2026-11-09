"""Instalar apps pelo winget (catálogo do projeto WinUtil, licença MIT)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from lolitos.i18n import tr

from lolitos.modules import winget
from lolitos.ui.widgets import Page, TaskDialog, button, confirm, hrow, info, label, run_async

CATEGORIES = {
    "Browsers": "Navegadores", "Communications": "Comunicação", "Development": "Desenvolvimento",
    "Document": "Documentos", "Games": "Jogos", "Microsoft Tools": "Ferramentas Microsoft",
    "Multimedia Tools": "Multimídia", "Pro Tools": "Ferramentas Pro", "Utilities": "Utilitários",
    "Selfhosted Tools": "Auto-hospedados",
}


class AppsPage(Page):
    title = "Instalar apps"
    subtitle = ("Escolha os programas e instale, atualize ou desinstale tudo de uma vez pelo winget, o gerenciador de "
                "pacotes oficial do Windows. Os instaladores vêm direto das fontes oficiais de cada programa.")

    def build(self):
        from lolitos.ui.appgrid import AppGrid, chip_bar
        from lolitos.ui.widgets import pill
        self.count = pill("0 selecionado(s)")
        self.actions.addWidget(self.count, 0, Qt.AlignTop)
        self.q = QLineEdit()
        self.q.setPlaceholderText("Buscar apps…")
        self.body.addLayout(hrow(self.q, button("Limpar seleção", on_click=lambda: self.grid.set_selected([])),
                                 stretch_first=True))
        self.body.addLayout(hrow(button("Instalar/atualizar selecionados", "primary", self._install),
                                 button("Desinstalar selecionados", "danger", self._uninstall),
                                 button("Atualizar todos os apps instalados", on_click=self._upgrade_all), None))
        self.grid = AppGrid(winget.catalog())
        self.grid.changed.connect(lambda: self.count.setText(
            tr("{} selecionado(s)").replace("{}", str(len(self.grid.selected())))))
        self.q.textChanged.connect(lambda t: self.grid.set_filter(text=t))
        self.body.addWidget(chip_bar(self.grid))
        self.status = label("Verificando o que já está instalado…", "muted")
        self.body.addWidget(self.status)
        self.body.addWidget(self.grid)
        self.body.addWidget(label("Catálogo de apps: projeto WinUtil (licença MIT). Clique direito em um app abre o "
                                  "site oficial.", "muted"))
        self.installed: set[str] = set()
        run_async(lambda: (winget.ensure_winget() and winget.installed_ids()) or set(), on_done=self._mark)

    def _mark(self, ids):
        self.installed = ids
        self.grid.mark_installed(ids)
        n = sum(1 for t in self.grid.tiles if t.installed)
        self.status.setText(tr("{} app(s) deste catálogo já instalados (ponto verde).").replace("{}", str(n))
                            if ids else tr("O winget não está disponível neste PC ou nada foi encontrado."))

    def _selected(self):
        return self.grid.selected()

    def _install(self):
        ids = self._selected()
        if not ids:
            info(self, "Instalar apps", "Marque os apps na lista.")
            return

        def work(progress=None):
            if not winget.ensure_winget():
                return "O winget não está disponível neste PC."
            for wid in ids:
                progress(f"Instalando/atualizando {wid}…")
                r = winget.install_or_upgrade(wid, self.installed)
                progress("   ok" if r.ok else f"   código {r.code}: {(r.out or r.err).strip()[-200:]}")
            return f"{len(ids)} app(s) processados."
        TaskDialog(self, "Instalar apps", work, on_done=lambda _: run_async(winget.installed_ids,
                                                                              on_done=self._mark)).exec()

    def _uninstall(self):
        ids = self._selected()
        if not ids or not confirm(self, "Desinstalar", "Desinstalar estes programas?<br>• " + "<br>• ".join(ids)):
            return

        def work(progress=None):
            for wid in ids:
                progress(f"Desinstalando {wid}…")
                r = winget.uninstall(wid)
                progress("   ok" if r.ok else f"   código {r.code}")
            return "Concluído."
        TaskDialog(self, "Desinstalar apps", work).exec()

    def _upgrade_all(self):
        from lolitos.core.system import run

        def work(progress=None):
            progress("winget upgrade --all …")
            r = run(["winget", "upgrade", "--all", "--silent", "--accept-package-agreements",
                     "--accept-source-agreements", "--include-unknown"], timeout=3600)
            return (r.out or r.err)[-3000:]
        TaskDialog(self, "Atualizar todos os apps", work,
                   intro="Atualiza pelo winget todos os programas instalados que têm versão nova.").exec()
