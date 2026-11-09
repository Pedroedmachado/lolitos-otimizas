"""Perfis prontos e personalizados (salvar, exportar, importar)."""
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QListWidget, QListWidgetItem,
                               QVBoxLayout)
from PySide6.QtCore import Qt

from lolitos.catalog import presets
from lolitos.core import engine
from lolitos.core.tweaks import CATALOG, CATS
from lolitos.ui.tweaklist import bulk_apply
from lolitos.ui.widgets import Card, Page, TaskDialog, button, confirm, hrow, info, label, run_async


class ProfileEditor(QDialog):
    def __init__(self, parent, name="", ids=()):
        super().__init__(parent)
        self.setWindowTitle("Perfil personalizado")
        self.resize(620, 640)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Marque os ajustes do perfil. Nada é aplicado agora: depois use 'Aplicar'.", "muted"))
        self.lst = QListWidget()
        for t in sorted((t for t in CATALOG.values() if t.cat != "jogo"), key=lambda t: (t.cat, t.title)):
            it = QListWidgetItem(f"[{CATS.get(t.cat, t.cat)}] {t.title}")
            it.setData(Qt.UserRole, t.id)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if t.id in ids else Qt.Unchecked)
            self.lst.addItem(it)
        lay.addWidget(self.lst)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.name = name

    def ids(self):
        return [self.lst.item(i).data(Qt.UserRole) for i in range(self.lst.count())
                if self.lst.item(i).checkState() == Qt.Checked]


class ProfilesPage(Page):
    title = "Perfis"
    subtitle = "Pacotes prontos para cada estilo de uso e os perfis que você montar. Um clique aplica o pacote."

    def build(self):
        self.body.addWidget(label("Pacotes prontos", "h2"))
        for p in [presets.BASIC_PACK] + presets.PRESETS:
            c = Card(hero=p.id == "online")
            c.lay.addWidget(label(f"<b>{p.name}</b>", rich=True))
            c.lay.addWidget(label(p.desc, "muted"))
            cnt = label("", "muted")
            c.lay.addWidget(cnt)
            c.lay.addLayout(hrow(button("Aplicar", "primary", lambda _=False, pp=p: self._apply(pp.name, pp.ids())),
                                 button("Desfazer este pacote", on_click=lambda _=False, pp=p: self._undo(pp.ids())),
                                 None))
            run_async(lambda pp=p: len(pp.ids()), on_done=lambda n, lb=cnt: lb.setText(f"{n} ajustes no pacote."))
            self.body.addWidget(c)
        self.body.addWidget(label("Meus perfis", "h2"))
        self.body.addLayout(hrow(button("Criar perfil…", on_click=self._new),
                                 button("Salvar ajustes ativos como perfil…", on_click=self._from_active),
                                 button("Importar…", on_click=self._import), None))
        self.mine = QVBoxLayout()
        self.body.addLayout(self.mine)
        self._load_mine()

    def _load_mine(self):
        while self.mine.count():
            w = self.mine.takeAt(0).widget()
            if w:
                w.deleteLater()
        items = presets.user_profiles()
        if not items:
            self.mine.addWidget(label("Nenhum perfil salvo ainda.", "muted"))
        for p in items:
            c = Card()
            c.lay.addWidget(label(f"<b>{p['name']}</b> — {len(p['ids'])} ajustes", rich=True))
            c.lay.addLayout(hrow(
                button("Aplicar", "primary", lambda _=False, pp=p: self._apply(pp["name"], pp["ids"])),
                button("Editar", on_click=lambda _=False, pp=p: self._edit(pp)),
                button("Exportar", on_click=lambda _=False, pp=p: self._export(pp)),
                button("Excluir", "danger", lambda _=False, pp=p: self._delete(pp)), None))
            self.mine.addWidget(c)

    def _apply(self, name, ids):
        ts = [CATALOG[i] for i in ids if i in CATALOG]
        TaskDialog(self, f"Aplicando: {name}", bulk_apply, ts,
                   on_done=lambda _: self.main and self.main.changed()).exec()

    def _undo(self, ids):
        from lolitos.core import history
        ents = [e for e in history.active_entries() if e["tweak_id"] in set(ids)]
        if not ents:
            info(self, "Desfazer", "Nenhum ajuste deste pacote foi aplicado por este app.")
            return
        if confirm(self, "Desfazer", f"Desfazer {len(ents)} ajuste(s) deste pacote?"):
            def work(progress=None):
                for e in reversed(ents):
                    engine.undo_entry(e, progress)
                return f"{len(ents)} desfeito(s)."
            TaskDialog(self, "Desfazendo", work).exec()

    def _new(self):
        name, ok = QInputDialog.getText(self, "Novo perfil", "Nome do perfil:")
        if ok and name.strip():
            self._edit({"name": name.strip(), "ids": []})

    def _edit(self, p):
        d = ProfileEditor(self, p["name"], set(p["ids"]))
        if d.exec():
            presets.upsert_profile(p["name"], d.ids())
            self._load_mine()

    def _from_active(self):
        from lolitos.core import history
        ids = sorted({e["tweak_id"] for e in history.active_entries()})
        if not ids:
            info(self, "Perfil", "Nenhum ajuste ativo aplicado por este app.")
            return
        name, ok = QInputDialog.getText(self, "Salvar perfil", f"Nome do perfil ({len(ids)} ajustes ativos):")
        if ok and name.strip():
            presets.upsert_profile(name.strip(), ids)
            self._load_mine()

    def _export(self, p):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar perfil", f"{p['name']}.json", "Perfil (*.json)")
        if path:
            presets.export_profile(p["name"], p["ids"], path)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar perfil", "", "Perfil (*.json)")
        if path:
            try:
                name, n, skipped = presets.import_profile(path)
                info(self, "Perfil", f"Perfil '{name}' importado com {n} ajustes"
                     + (f" ({skipped} desconhecidos ignorados)." if skipped else "."))
            except (ValueError, OSError) as e:
                info(self, "Perfil", str(e))
            self._load_mine()

    def _delete(self, p):
        if confirm(self, "Excluir", f"Excluir o perfil '{p['name']}'? Os ajustes aplicados continuam."):
            presets.delete_profile(p["name"])
            self._load_mine()
