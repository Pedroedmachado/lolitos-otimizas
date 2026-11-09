"""Restauração: histórico com desfazer item a item, desfazer tudo e pontos de restauração."""
import time

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from lolitos.core import engine, history, restore
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, TaskDialog, button, confirm, hrow, info, label, run_async


class RestorePage(Page):
    title = "Restauração"
    subtitle = ("Tudo o que este app aplicou pode ser desfeito aqui — cada ajuste volta exatamente ao valor que "
                "existia antes. O ponto de restauração do Windows é a segunda rede de segurança.")

    def build(self):
        rp = Card(hero=True)
        rp.lay.addWidget(label("<b>Pontos de restauração do Windows</b>", rich=True))
        self.rp_lbl = label("Lendo…", "muted", rich=True)
        rp.lay.addWidget(self.rp_lbl)
        rp.lay.addLayout(hrow(button("Criar ponto agora", "primary", self._create),
                              button("Abrir a Restauração do Sistema", on_click=restore.open_system_restore), None))
        self.body.addWidget(rp)
        self.body.addLayout(hrow(label("Histórico", "h2"), None,
                                 button("Reverter tudo", "danger", self._undo_all),
                                 button("Limpar histórico", on_click=self._clear)))
        self.box = QVBoxLayout()
        self.body.addLayout(self.box)

    def on_show(self):
        if not self._built:
            return
        self._load()
        run_async(restore.list_points, on_done=self._points)

    def _points(self, pts):
        last = restore.last_own_point()
        own = time.strftime("%d/%m/%Y %H:%M", time.localtime(last)) if last else "nenhum ainda"
        win = pts[-1] if pts else None
        self.rp_lbl.setText(f"Último criado por este app: <b>{own}</b><br>Último do Windows: <b>"
                            f"{win['When'] + ' — ' + win['Description'] if win else '—'}</b>")

    def _create(self):
        TaskDialog(self, "Ponto de restauração", lambda progress=None: restore.create(force=True)[1],
                   intro="Snapshot do disco; leva um ou dois minutos.", on_done=lambda _: self.on_show()).exec()

    def _load(self):
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        items = list(reversed(history.load()))
        if not items:
            self.box.addWidget(label("Nada no histórico ainda.", "muted"))
        for e in items[:150]:
            c = Card()
            row = QHBoxLayout()
            when = time.strftime("%d/%m %H:%M", time.localtime(e["time"]))
            st = ("desfeito" if e["undone"] else "ativo" if e["kind"] == "tweak" else "")
            col = C["muted"] if e["undone"] else C["ok"]
            row.addWidget(label(f"<b>{e['title']}</b> <span style='color:{C['muted']}'>· {e['group']} · {when}</span>"
                                + (f" <span style='color:{col}'>· {st}</span>" if st else ""), rich=True), 1)
            if e["kind"] == "tweak" and not e["undone"] and e.get("reversible", True):
                row.addWidget(button("Desfazer", on_click=lambda _=False, ee=e: self._undo(ee)))
            c.lay.addLayout(row)
            if e.get("detail"):
                c.lay.addWidget(label(e["detail"][:300], "muted"))
            self.box.addWidget(c)

    def _undo(self, e):
        if confirm(self, "Desfazer", f"Voltar ao estado anterior?<br><b>{e['title']}</b>"):
            ok, msg = engine.undo_entry(e)
            if not ok and msg:
                info(self, "Desfazer", msg)
            self._load()
            self.main and self.main.changed()

    def _undo_all(self):
        n = len(history.active_entries())
        if not n:
            info(self, "Reverter tudo", "Nenhum ajuste ativo aplicado por este app.")
            return
        if confirm(self, "Reverter tudo", f"Desfazer {n} ajuste(s) e voltar aos valores anteriores?"):
            def work(progress=None):
                cnt, errs = engine.undo_all(progress)
                return f"{cnt} desfeito(s)." + ("\n" + "\n".join(errs) if errs else "")
            TaskDialog(self, "Reverter tudo", work, on_done=lambda _: (self._load(),
                                                                        self.main and self.main.changed())).exec()

    def _clear(self):
        if confirm(self, "Limpar histórico", "Apagar o histórico? Depois disso nada do que está listado poderá ser "
                   "desfeito por aqui."):
            history.clear()
            self._load()
