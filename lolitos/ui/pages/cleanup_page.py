"""Limpeza: espaço livre, lixo por categoria (com o tamanho antes de apagar), liberação de RAM e o que limpar."""
from __future__ import annotations

import os
import time

import psutil
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QProgressBar, QVBoxLayout, QWidget

from lolitos.core import history, settings
from lolitos.core.system import human_size, is_admin
from lolitos.i18n import tr
from lolitos.modules import cleanup, memory
from lolitos.ui.charts import Ring
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, TaskDialog, button, info, label, run_async

RB = "recycle"      # a Lixeira entra na lista como mais um item
DNS = "dns"         # o cache de DNS também (não ocupa disco: só aparece na lista de baixo)


def _system_drive() -> str:
    return (os.environ.get("SystemDrive", "C:") + "\\") if os.name == "nt" else "/"


class CleanupPage(Page):
    title = "Limpeza"
    subtitle = "Libera espaço removendo o que o Windows e os programas não precisam mais."

    def build(self):
        self.actions.addWidget(button("Analisar arquivos", on_click=self._measure))
        self.actions.addWidget(button("Limpar selecionados", "primary", self._clean))
        items = [(t.id, t.name, t.desc, t.default and (is_admin() or not t.admin), t.admin) for t in cleanup.TARGETS]
        items.insert(2, (RB, "Lixeira", "Esvazia a Lixeira de todas as unidades.", True, False))
        items.append((DNS, "Cache de DNS", "Esvazia o cache de nomes de sites. Resolve sites que não abrem depois de "
                      "mudarem de servidor.", True, False))
        self.items = items

        # ------------------------------------------------ disco + lixo por categoria
        top = Card()
        row = QHBoxLayout()
        row.setSpacing(24)
        left = QVBoxLayout()
        self.ring = Ring(tr("LIVRE"))
        self.ring.setFixedSize(180, 180)
        left.addWidget(self.ring, 0, Qt.AlignHCenter)
        self.disk_lbl = label("", "muted", wrap=False)
        left.addWidget(self.disk_lbl, 0, Qt.AlignHCenter)
        left.addStretch()
        self.last_lbl = label("", "muted", wrap=False)
        left.addWidget(self.last_lbl, 0, Qt.AlignHCenter)
        row.addLayout(left)
        right = QVBoxLayout()
        right.setSpacing(4)
        hdr = QHBoxLayout()
        hdr.addWidget(label("<b>Lixo encontrado por categoria</b>", "h3", rich=True, wrap=False))
        hdr.addStretch()
        self.total_lbl = label("", "h3", rich=True, wrap=False)
        hdr.addWidget(self.total_lbl)
        right.addLayout(hdr)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(5)
        self.bars, self.bar_sizes = {}, {}
        for i, (tid, name, *_r) in enumerate(i for i in items if i[0] != DNS):
            grid.addWidget(label(name, "barname", wrap=False), i, 0)
            b = QProgressBar()
            b.setRange(0, 1000)
            b.setTextVisible(False)
            b.setFixedHeight(6)
            grid.addWidget(b, i, 1)
            sz = label("…", "barname", wrap=False)
            sz.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sz.setMinimumWidth(70)
            grid.addWidget(sz, i, 2)
            self.bars[tid], self.bar_sizes[tid] = b, sz
        grid.setColumnStretch(1, 1)
        right.addLayout(grid)
        row.addLayout(right, 1)
        top.lay.addLayout(row)
        self.body.addWidget(top)

        # ------------------------------------------------ RAM
        ram = Card()
        rh = QHBoxLayout()
        rh.addWidget(label("<b>Memória RAM</b>", "h3", rich=True))
        rh.addStretch()
        self.ram_btn = button("Liberar RAM", on_click=self._ram)
        rh.addWidget(self.ram_btn)
        ram.lay.addLayout(rh)
        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setFixedHeight(10)
        ram.lay.addWidget(self.ram_bar)
        self.ram_lbl = label("", rich=True)
        ram.lay.addWidget(self.ram_lbl)
        ram.lay.addWidget(label("Esvazia a memória de trabalho dos processos e a lista de espera. Nada é fechado; útil "
                                "antes de abrir um jogo pesado.", "muted"))
        self.body.addWidget(ram)

        # ------------------------------------------------ o que limpar
        self.body.addWidget(label("O que limpar", "h2"))
        lst = Card()
        self.checks, self.sizes = {}, {}
        for i, (tid, name, desc, default, admin) in enumerate(items):
            if i:
                sep = QWidget()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{C['border']};")
                lst.lay.addWidget(sep)
            r = QHBoxLayout()
            col = QVBoxLayout()
            col.setSpacing(1)
            ck = QCheckBox(name)
            ck.setChecked(default)
            ck.toggled.connect(self._update_total)
            self.checks[tid] = ck
            col.addWidget(ck)
            col.addWidget(label(desc + (" " + tr("(precisa de administrador)") if admin and not is_admin() else ""),
                                "muted"))
            r.addLayout(col, 1)
            sz = label("…", wrap=False)
            self.sizes[tid] = sz
            r.addWidget(sz, 0, Qt.AlignVCenter)
            lst.lay.addLayout(r)
        self.body.addWidget(lst)
        self.measured: dict[str, int] = {}
        self._disk()
        self._ram_info()
        self._measure()

    def on_show(self):
        if self._built:
            self._disk()
            self._ram_info()

    # ---------------------------------------------------------------- leituras
    def _disk(self):
        try:
            u = psutil.disk_usage(_system_drive())
        except OSError:
            return
        self.ring.set(u.free / u.total, human_size(u.free), tr("LIVRE"))
        self.disk_lbl.setText(tr("Disco {} — {} usados de {}").replace("{}", _system_drive().rstrip("\\"), 1)
                              .replace("{}", human_size(u.used), 1).replace("{}", human_size(u.total), 1))
        last = settings.get("last_cleanup")
        self.last_lbl.setText(tr("Última limpeza: {}").replace(
            "{}", time.strftime("%d/%m/%Y %H:%M", time.localtime(last)) if last else tr("nunca")))

    def _ram_info(self):
        vm = psutil.virtual_memory()
        self.ram_bar.setValue(int(vm.percent))
        self.ram_lbl.setText(f"{tr('Usado')} <b>{human_size(vm.used)}</b> · {tr('Livre')} <b>{human_size(vm.available)}"
                             f"</b> · {human_size(vm.total)} {tr('no total')}")

    def _measure(self):
        for sz in list(self.sizes.values()) + list(self.bar_sizes.values()):
            sz.setText(tr("medindo…"))
        self.sizes[DNS].setText("—")

        def work():
            out = {t.id: cleanup.measure(t)[1] for t in cleanup.TARGETS}
            out[RB] = cleanup.recycle_bin_size()[1]
            return out

        def done(sizes):
            self.measured = sizes
            top = max(sizes.values() or [1]) or 1
            for tid, b in sizes.items():
                self.sizes[tid].setText(human_size(b))
                self.bar_sizes[tid].setText(human_size(b))
                self.bars[tid].setValue(int(b / top * 1000) if b else 0)
            self._update_total()
        run_async(work, on_done=done)

    def _update_total(self, *_):
        if not getattr(self, "measured", None):
            return
        total = sum(self.measured.values())
        sel = sum(b for tid, b in self.measured.items() if self.checks[tid].isChecked())
        self.total_lbl.setText(f"<b>{human_size(total)} {tr('no total')} · {human_size(sel)} {tr('selecionados')}</b>")

    # ---------------------------------------------------------------- ações
    def _clean(self):
        ids = [k for k, c in self.checks.items() if c.isChecked() and k not in (RB, DNS)]
        rb = self.checks[RB].isChecked()
        dns = self.checks[DNS].isChecked()
        if not ids and not rb and not dns:
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
            if dns:
                from lolitos.core.system import run
                progress("Esvaziando o cache de DNS…")
                r = run(["ipconfig", "/flushdns"], timeout=30)
                progress("   " + ("cache de DNS limpo" if r.ok else "o Windows não deixou limpar o cache de DNS"))
            s = cleanup.summary_text(res)
            history.add("task", f"Limpeza: {s}", "Limpeza", reversible=False)
            settings.set("last_cleanup", time.time())
            return s
        TaskDialog(self, "Limpeza", work, on_done=lambda _: (self._measure(), self._disk())).exec()

    def _ram(self):
        self.ram_btn.setEnabled(False)
        self.ram_btn.setText(tr("Liberando…"))

        def done(r):
            self.ram_btn.setEnabled(True)
            self.ram_btn.setText(tr("Liberar RAM"))
            self._ram_info()
            info(self, "Memória RAM", tr("{} liberados ({} processos).").replace("{}", human_size(r["freed"]), 1)
                 .replace("{}", str(r["processes"]), 1))
        run_async(memory.free_ram, on_done=done)
