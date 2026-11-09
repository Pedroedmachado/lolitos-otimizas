"""Instalar apps pelo winget (catálogo do projeto WinUtil, licença MIT)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QListWidget, QListWidgetItem

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
        self.q = QLineEdit()
        self.q.setPlaceholderText("Buscar apps…")
        self.q.textChanged.connect(self._filter)
        self.cat = QComboBox()
        self.cat.addItem("Todos", "")
        for k, v in CATEGORIES.items():
            self.cat.addItem(v, k)
        self.cat.currentIndexChanged.connect(lambda: self._filter(self.q.text()))
        self.body.addLayout(hrow(self.q, self.cat, stretch_first=True))
        self.body.addLayout(hrow(button("Instalar/atualizar selecionados", "primary", self._install),
                                 button("Desinstalar selecionados", "danger", self._uninstall),
                                 button("Atualizar todos os apps instalados", on_click=self._upgrade_all), None))
        self.status = label("Verificando o que já está instalado…", "muted")
        self.body.addWidget(self.status)
        self.lst = QListWidget()
        self.lst.setMinimumHeight(560)
        self.lst.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lst.customContextMenuRequested.connect(self._open_site)
        self.body.addWidget(self.lst)
        self.installed: set[str] = set()
        for a in winget.catalog():
            it = QListWidgetItem(f"[{CATEGORIES.get(a.category, a.category)}] {a.name} — {a.desc[:90]}")
            it.setData(Qt.UserRole, a.winget)
            it.setData(Qt.UserRole + 1, a.category)
            it.setData(Qt.UserRole + 2, a.link)
            it.setToolTip(f"{a.winget}\n{a.link}\nClique direito: abrir o site")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.lst.addItem(it)
        self.body.addWidget(label("Catálogo de apps: projeto WinUtil (licença MIT).", "muted"))
        run_async(lambda: (winget.ensure_winget() and winget.installed_ids()) or set(), on_done=self._mark)

    def _open_site(self, pos):
        import webbrowser
        it = self.lst.itemAt(pos)
        if it and it.data(Qt.UserRole + 2):
            webbrowser.open(it.data(Qt.UserRole + 2))

    def _mark(self, ids):
        self.installed = ids
        n = 0
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            if it.data(Qt.UserRole).lower() in ids:
                it.setText("● " + it.text().lstrip("● "))
                n += 1
        self.status.setText(f"{n} app(s) deste catálogo já instalados (bolinha ●)."
                            if ids else "O winget não está disponível neste PC ou nada foi encontrado.")

    def _filter(self, text):
        text = text.lower()
        cat = self.cat.currentData()
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            hide = (bool(text) and text not in it.text().lower()) or (cat and it.data(Qt.UserRole + 1) != cat)
            it.setHidden(bool(hide))

    def _selected(self):
        return [self.lst.item(i).data(Qt.UserRole) for i in range(self.lst.count())
                if self.lst.item(i).checkState() == Qt.Checked]

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
