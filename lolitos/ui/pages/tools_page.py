"""Ferramentas: reparos do Windows, inicialização, instalar apps (winget) e testes de mouse/monitor."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from lolitos.modules import repair, startup, winget
from lolitos.ui.widgets import Card, Page, TaskDialog, button, confirm, hrow, info, label, run_async


class ToolsPage(Page):
    title = "Ferramentas"
    subtitle = "Ferramentas do próprio Windows para manter o sistema saudável. O comando exato é mostrado antes."

    def build(self):
        tabs = QTabWidget()
        tabs.addTab(self._repairs(), "Reparos")
        tabs.addTab(self._startup(), "Inicialização")
        tabs.addTab(self._apps(), "Instalar apps")
        tabs.addTab(self._tests(), "Testes")
        self.body.addWidget(tabs)

    # ---------------------------------------------------------------- reparos
    def _repairs(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        groups = {}
        for t in repair.TOOLS:
            groups.setdefault(t.group, []).append(t)
        for g, items in groups.items():
            lay.addWidget(label(g, "h2"))
            grid = QGridLayout()
            for i, t in enumerate(items):
                c = Card()
                c.lay.addWidget(label(f"<b>{t.name}</b>" + (f" · <span>{t.minutes}</span>" if t.minutes else ""),
                                      rich=True))
                c.lay.addWidget(label(t.desc, "muted"))
                c.lay.addLayout(hrow(button("Executar", on_click=lambda _=False, tt=t: self._run(tt)), None))
                grid.addWidget(c, i // 2, i % 2)
            lay.addLayout(grid)
        return w

    def _run(self, t):
        if not confirm(self, t.name, f"<p>{t.desc}</p><p><b>O que será executado:</b><br><code>{t.cmd}</code></p>",
                       yes="Executar"):
            return

        def work(progress=None):
            progress(f"> {t.cmd}")
            ok, out = repair.run_tool(t)
            return (out or "") + ("\n\nReinicie o PC para concluir." if t.restart else "") + \
                ("" if ok else "\n\nTerminou com avisos ou erros (veja acima).")
        TaskDialog(self, t.name, work).exec()

    # ---------------------------------------------------------------- inicialização
    def _startup(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.addWidget(label("Programas que abrem com o Windows. Desligar não desinstala nada e funciona como o "
                            "Gerenciador de Tarefas (dá para religar quando quiser).", "muted"))
        lay.addLayout(hrow(button("Atualizar", on_click=self._load_startup), None))
        self.st_box = QVBoxLayout()
        lay.addLayout(self.st_box)
        self._load_startup()
        return w

    def _load_startup(self):
        while self.st_box.count():
            it = self.st_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for e in startup.list_entries():
            c = Card()
            row = QHBoxLayout()
            ck = QCheckBox(e.name)
            ck.setChecked(e.enabled)
            ck.toggled.connect(lambda v, ee=e: startup.set_enabled(ee, v))
            row.addWidget(ck, 1)
            row.addWidget(label(e.source, "muted", wrap=False))
            c.lay.addLayout(row)
            c.lay.addWidget(label(e.command[:160], "muted"))
            self.st_box.addWidget(c)

    # ---------------------------------------------------------------- apps
    def _apps(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.addWidget(label("Escolha os programas e instale, atualize ou desinstale tudo de uma vez pelo winget. "
                            "Os instaladores vêm das fontes oficiais. Catálogo: projeto WinUtil (licença MIT).",
                            "muted"))
        self.q = QLineEdit()
        self.q.setPlaceholderText("Buscar apps…")
        self.q.textChanged.connect(self._filter_apps)
        lay.addLayout(hrow(self.q, button("Instalar/atualizar selecionados", "primary", self._install),
                           button("Desinstalar selecionados", "danger", self._uninstall), stretch_first=True))
        self.app_status = label("Verificando o que já está instalado…", "muted")
        lay.addWidget(self.app_status)
        self.app_list = QListWidget()
        self.app_list.setMinimumHeight(520)
        lay.addWidget(self.app_list)
        self.installed = set()
        apps = winget.catalog()
        for a in apps:
            it = QListWidgetItem(f"[{a.category}] {a.name} — {a.desc[:90]}")
            it.setData(Qt.UserRole, a.winget)
            it.setToolTip(f"{a.winget}\n{a.link}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.app_list.addItem(it)
        run_async(lambda: (winget.ensure_winget() and winget.installed_ids()) or set(), on_done=self._mark_installed)
        return w

    def _mark_installed(self, ids):
        self.installed = ids
        n = 0
        for i in range(self.app_list.count()):
            it = self.app_list.item(i)
            if it.data(Qt.UserRole).lower() in ids:
                it.setText("● " + it.text().lstrip("● "))
                n += 1
        self.app_status.setText(f"{n} app(s) deste catálogo já instalados (marcados com ●)."
                                if ids else "winget indisponível ou nada encontrado.")

    def _filter_apps(self, text):
        text = text.lower()
        for i in range(self.app_list.count()):
            it = self.app_list.item(i)
            it.setHidden(bool(text) and text not in it.text().lower())

    def _selected(self):
        return [self.app_list.item(i).data(Qt.UserRole) for i in range(self.app_list.count())
                if self.app_list.item(i).checkState() == Qt.Checked]

    def _install(self):
        ids = self._selected()
        if not ids:
            info(self, "Apps", "Marque os apps na lista.")
            return

        def work(progress=None):
            if not winget.ensure_winget():
                return "O winget não está disponível neste PC."
            for wid in ids:
                progress(f"Instalando/atualizando {wid}…")
                r = winget.install_or_upgrade(wid, self.installed)
                progress("   ok" if r.ok else f"   código {r.code}: {(r.out or r.err).strip()[-200:]}")
            return f"{len(ids)} app(s) processados."
        TaskDialog(self, "Instalar apps", work).exec()

    def _uninstall(self):
        ids = self._selected()
        if not ids or not confirm(self, "Desinstalar", "Desinstalar:<br>• " + "<br>• ".join(ids)):
            return

        def work(progress=None):
            for wid in ids:
                progress(f"Desinstalando {wid}…")
                r = winget.uninstall(wid)
                progress("   ok" if r.ok else f"   código {r.code}")
            return "Concluído."
        TaskDialog(self, "Desinstalar apps", work).exec()

    # ---------------------------------------------------------------- testes
    def _tests(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 0, 0)
        c1 = Card()
        c1.lay.addWidget(label("<b>Teste do mouse</b> — mede o polling rate real (Hz).", rich=True))
        c1.lay.addWidget(label("Faça círculos rápidos e contínuos dentro da área por uns 5 segundos.", "muted"))
        c1.lay.addLayout(hrow(button("Abrir teste do mouse", "primary", self._mouse), None))
        lay.addWidget(c1)
        c2 = Card()
        c2.lay.addWidget(label("<b>Teste de monitor</b> — pixels mortos, uniformidade, vazamento de luz e teste de "
                               "movimento (ghosting) em tela cheia. Não abre nenhum site.", rich=True))
        c2.lay.addLayout(hrow(button("Cores e pixels", on_click=lambda: self._monitor("colors")),
                              button("Teste de movimento", "primary", lambda: self._monitor("motion")), None))
        lay.addWidget(c2)
        return w

    def _mouse(self):
        from lolitos.ui.tests import MouseTest
        MouseTest(self).exec()

    def _monitor(self, mode):
        from lolitos.ui.tests import MonitorTest
        self._mt = MonitorTest(mode)
        self._mt.showFullScreen()
