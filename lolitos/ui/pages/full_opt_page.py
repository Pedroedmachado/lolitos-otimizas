"""Otimização Completa: tudo que é recomendado para este PC, por área, numa tela só."""
from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout

from lolitos.core.tweaks import CATALOG, CATS, ESSENTIAL, RECOMMENDED
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import bulk_apply
from lolitos.ui.widgets import (Card, Page, TaskDialog, Toggle, button, card_header, confirm, label, pill,
                                run_async, status_pool)

AREAS = [("desempenho", "speed"), ("jogos", "games"), ("gpu", "gpu"), ("rede", "network"), ("entrada", "mouse"),
         ("privacidade", "shield"), ("interface", "windows"), ("ia", "bolt"), ("atualizacoes", "sync"),
         ("debloat", "debloat")]


def candidates(cat: str) -> list:
    """O que entra na otimização completa nesta área: essencial + recomendado para ESTE PC, reversível."""
    return [t for t in CATALOG.values() if t.cat == cat and t.level in (ESSENTIAL, RECOMMENDED)
            and t.recommended_here() and (t.reversible or cat == "debloat")]


def scan() -> dict[str, tuple[int, int]]:
    out = {}
    for cat, _ in AREAS:
        ts = candidates(cat)
        pend = sum(1 for t in ts if t.status() not in ("on", "na"))
        out[cat] = (pend, len(ts))
    return out


class FullOptPage(Page):
    title = "Otimização Completa"
    icon = "bolt"
    subtitle = ("Tudo o que é recomendado para este PC, separado por área, aplicado de uma vez. Cada ajuste fica no "
                "histórico e pode ser desfeito em Restauração; antes de começar é criado um ponto de restauração.")

    def build(self):
        hero = Card(hero=True)
        row = QHBoxLayout()
        col = QVBoxLayout()
        self.big = label("—", "bigtitle")
        col.addWidget(self.big)
        self.sum = label("Analisando o que falta neste PC…", "muted")
        col.addWidget(self.sum)
        row.addLayout(col, 1)
        self.go_btn = button("Aplicar otimização completa", "primary", self._apply)
        self.go_btn.setMinimumHeight(46)
        self.go_btn.setMinimumWidth(260)
        row.addWidget(self.go_btn)
        hero.lay.addLayout(row)
        self.body.addWidget(hero)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.toggles, self.counts = {}, {}
        for i, (cat, ico) in enumerate(AREAS):
            c = Card()
            self.counts[cat] = pill("…")
            c.lay.addLayout(card_header(ico, CATS[cat], self.counts[cat]))
            sw = Toggle(cat != "debloat", on_toggle=lambda *_: self._summary())
            self.toggles[cat] = sw
            r = QHBoxLayout()
            r.addWidget(label("Incluir esta área" if cat != "debloat" else
                              "Incluir (remove apps pré-instalados recomendados)", "muted"), 1)
            r.addWidget(sw)
            c.lay.addLayout(r)
            grid.addWidget(c, i // 2, i % 2)
        self.body.addLayout(grid)
        self.data = {}

    def on_show(self):
        if self._built:
            run_async(scan, on_done=self._show, _pool=status_pool())

    def _show(self, data):
        self.data = data
        for cat, (pend, tot) in data.items():
            self.counts[cat].setText(f"{tot - pend}/{tot}")
            self.counts[cat].setStyleSheet(f"color:{C['ok'] if pend == 0 else C['gold']};")
        self._summary()

    def _summary(self):
        if not self.data:
            return
        pend = sum(self.data[c][0] for c, sw in self.toggles.items() if sw.isChecked())
        tot = sum(self.data[c][1] for c, sw in self.toggles.items() if sw.isChecked())
        self.big.setText(f"{tot - pend}/{tot}")
        self.sum.setText(f"{pend} ajuste(s) pendente(s) nas áreas escolhidas." if pend else
                         "Tudo que é recomendado para este PC já está aplicado nas áreas escolhidas.")
        self.go_btn.setEnabled(pend > 0)

    def _apply(self):
        cats = [c for c, sw in self.toggles.items() if sw.isChecked()]
        if not confirm(self, "Otimização Completa", "Aplicar todos os ajustes pendentes das áreas marcadas?<br><br>"
                       "Um ponto de restauração é criado antes; tudo pode ser desfeito em Restauração.",
                       yes="Aplicar"):
            return

        def work(progress=None):
            ts = [t for c in cats for t in candidates(c) if t.status() not in ("on", "na")]
            return bulk_apply(ts, progress) if ts else "Nada pendente."

        def done(_):
            if self.main:
                self.main.changed()
            self.on_show()
        TaskDialog(self, "Otimização Completa", work, on_done=done).exec()
