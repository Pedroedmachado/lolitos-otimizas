"""Limpeza (com tamanho antes de apagar) e liberação de RAM."""
from PySide6.QtWidgets import QCheckBox, QHBoxLayout

from lolitos.core import history
from lolitos.core.system import human_size, is_admin
from lolitos.modules import cleanup, memory
from lolitos.ui.widgets import Card, Page, TaskDialog, button, hrow, info, label, run_async


class CleanupPage(Page):
    title = "Limpeza"
    subtitle = ("Temporários, caches e Lixeira, com o tamanho de cada um antes de apagar. Arquivos em uso são "
                "mantidos; atalhos/links são removidos sem tocar no destino.")

    def build(self):
        ram = Card(hero=True)
        ram.lay.addWidget(label("<b>Liberar memória RAM</b> (sem fechar nenhum programa)", rich=True))
        ram.lay.addWidget(label("Esvazia a memória de trabalho dos processos e a lista de espera. Útil antes de "
                                "entrar na Guerra de Nodes.", "muted"))
        self.ram_lbl = label("", "muted")
        ram.lay.addLayout(hrow(button("Liberar RAM agora", "primary", self._ram), self.ram_lbl, None))
        self.body.addWidget(ram)

        self.body.addWidget(label("O que limpar", "h2"))
        self.checks = {}
        self.sizes = {}
        for t in cleanup.TARGETS:
            c = Card()
            row = QHBoxLayout()
            ck = QCheckBox(t.name)
            ck.setChecked(t.default and (is_admin() or not t.admin))
            self.checks[t.id] = ck
            row.addWidget(ck, 1)
            sz = label("medindo…", "muted", wrap=False)
            self.sizes[t.id] = sz
            row.addWidget(sz)
            c.lay.addLayout(row)
            c.lay.addWidget(label(t.desc + (" (precisa de administrador)" if t.admin and not is_admin() else ""),
                                  "muted"))
            self.body.addWidget(c)
        rb = Card()
        row = QHBoxLayout()
        self.rb_check = QCheckBox("Lixeira")
        row.addWidget(self.rb_check, 1)
        self.rb_size = label("", "muted", wrap=False)
        row.addWidget(self.rb_size)
        rb.lay.addLayout(row)
        rb.lay.addWidget(label("Esvazia a Lixeira de todas as unidades.", "muted"))
        self.body.addWidget(rb)
        self.body.addLayout(hrow(button("Limpar selecionados", "primary", self._clean),
                                 button("Medir de novo", on_click=self._measure), None))
        self._measure()

    def _measure(self):
        def work():
            out = {t.id: cleanup.measure(t) for t in cleanup.TARGETS}
            return out, cleanup.recycle_bin_size()

        def done(r):
            sizes, rb = r
            for tid, (n, b) in sizes.items():
                self.sizes[tid].setText(f"{human_size(b)} · {n} item(ns)")
            self.rb_size.setText(f"{human_size(rb[1])} · {rb[0]} item(ns)")
        run_async(work, on_done=done)

    def _clean(self):
        ids = [k for k, c in self.checks.items() if c.isChecked()]
        rb = self.rb_check.isChecked()
        if not ids and not rb:
            info(self, "Limpeza", "Marque pelo menos um item.")
            return

        def work(progress=None):
            res = {}
            for tid in ids:
                t = cleanup.TARGETS_BY_ID[tid]
                progress(f"Limpando {t.name}…")
                res[tid] = cleanup.clean(t)
                progress(f"   {human_size(res[tid][1])} liberados")
            if rb:
                progress("Esvaziando a Lixeira…")
                n, b = cleanup.recycle_bin_size()
                cleanup.empty_recycle_bin()
                res["rb"] = (n, b, 0)
            s = cleanup.summary_text(res)
            history.add("task", f"Limpeza: {s}", "Limpeza", reversible=False)
            return s
        TaskDialog(self, "Limpeza", work, on_done=lambda _: self._measure()).exec()

    def _ram(self):
        self.ram_lbl.setText("Liberando…")
        run_async(memory.free_ram, on_done=lambda r: self.ram_lbl.setText(
            f"{human_size(r['freed'])} liberados ({r['processes']} processos)."))
