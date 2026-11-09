"""Painel: pontuação, Boost em um clique, check-up e atalhos."""
from __future__ import annotations

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QProgressBar, QVBoxLayout

from lolitos import APP_NAME
from lolitos.catalog.presets import boost_ids
from lolitos.core import settings
from lolitos.core.system import is_admin
from lolitos.core.tweaks import CATALOG
from lolitos.modules import checkup, cleanup, gpu, memory, pcprofile
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import bulk_apply
from lolitos.ui.widgets import Badge, Card, Page, TaskDialog, button, hrow, label, run_async

FIX_PAGE = {"cleanup": "limpeza", "startup": "ferramentas", "antivirus": "config", "restore_point": "restauracao",
            "refresh_max": "ajustes", "bios": "hardware", "reboot": "restauracao"}


def boost(progress=None):
    say = progress or (lambda s: None)
    pend = [CATALOG[i] for i in boost_ids() if CATALOG[i].status() not in ("on", "na")]
    say(f"{len(pend)} ajuste(s) recomendados pendentes neste PC.")
    out = bulk_apply(pend, say) if pend else "Todos os ajustes do Boost já estavam ativos."
    say("Limpando temporários do Windows e do usuário…")
    freed = 0
    for tid in ("user_temp", "win_temp"):
        _, b, _ = cleanup.clean(cleanup.TARGETS_BY_ID[tid])
        freed += b
    from lolitos.core.system import human_size
    say(f"   {human_size(freed)} liberados")
    say("Liberando memória RAM…")
    r = memory.free_ram()
    say(f"   {r['freed'] / 1024**2:.0f} MB liberados")
    return out


def pc_analysis():
    """Perfil do PC, dicas e o que o Boost deixa de fora/inclui por causa dele."""
    pcprofile.refresh_slow()
    p = pcprofile.detect()
    skipped = [t.title for t in CATALOG.values() if t.level != "avancado" and t.cat != "debloat" and t.when
               and not t.recommended_here()]
    rec = (f"{len(boost_ids())} ajustes recomendados; {len(skipped)} deixados de fora porque não se aplicam ou "
           f"não ajudam neste PC" + (f": {', '.join(skipped[:6])}{'…' if len(skipped) > 6 else ''}."
                                            if skipped else "."))
    return p, pcprofile.advice(), rec


def compute_score():
    ids = boost_ids()
    st = {i: CATALOG[i].status() for i in ids}
    valid = [s for s in st.values() if s != "na"]
    ratio = sum(1 for s in valid if s == "on") / len(valid) if valid else 1
    checks = checkup.run_checkup()
    pending = sum(1 for s in valid if s != "on")
    return checkup.score(checks, ratio), pending, checks


class Dashboard(Page):
    title = ""

    def build(self):
        hero = Card(hero=True)
        top = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(label(f"Olá! Este é o {APP_NAME}", "h1"))
        left.addWidget(label("Diagnóstico do quanto o seu PC já está otimizado e o que falta. O Boost aplica de uma "
                             "vez os ajustes recomendados para a sua máquina — tudo fica no histórico com Desfazer.",
                             "muted"))
        self.pending = label("Analisando o PC…", "muted")
        left.addWidget(self.pending)
        self.boost_btn = button("⚡  Boost agora", "primary", self._boost)
        self.boost_btn.setMinimumHeight(42)
        left.addLayout(hrow(self.boost_btn, button("🎮  Meus jogos", on_click=lambda: self.main.go("jogos")),
                            None))
        if not is_admin():
            left.addWidget(label(f"<span style='color:{C['bad']}'>Sem administrador: ajustes do sistema vão falhar. "
                                 "Feche e abra de novo aceitando o pedido do Windows.</span>", rich=True))
        top.addLayout(left, 3)
        sc = QVBoxLayout()
        sc.addWidget(label("PONTUAÇÃO DE OTIMIZAÇÃO", "muted"))
        self.score = label("…", "big")
        sc.addWidget(self.score)
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        sc.addWidget(self.score_bar)
        top.addLayout(sc, 1)
        hero.lay.addLayout(top)
        self.body.addWidget(hero)

        # métricas ao vivo
        grid = QGridLayout()
        grid.setSpacing(12)
        self.live = {}
        for i, (k, name) in enumerate([("cpu", "USO DA CPU"), ("ram", "USO DA RAM"), ("gpu", "USO DA GPU"),
                                       ("gtemp", "TEMPERATURA DA GPU")]):
            c = Card()
            c.lay.addWidget(label(name, "muted"))
            v = label("—", "h1")
            c.lay.addWidget(v)
            self.live[k] = v
            grid.addWidget(c, 0, i)
        self.body.addLayout(grid)

        # análise do PC
        self.pc_card = Card()
        self.pc_card.lay.addWidget(label("Seu PC", "h2"))
        self.pc_lbl = label("Analisando o hardware…", rich=True)
        self.pc_card.lay.addWidget(self.pc_lbl)
        self.body.addWidget(self.pc_card)
        run_async(pc_analysis, on_done=self._pc)

        self.body.addWidget(label("Check-up do PC", "h2"))
        self.checks_box = QVBoxLayout()
        self.body.addLayout(self.checks_box)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1500)
        psutil.cpu_percent()
        self.refresh()

    def _pc(self, r):
        p, adv, rec = r
        lines = [f"<b style='color:{C['accent2']}'>{p.tier_name}</b> — " + " · ".join(p.summary())]
        lines.append(f"<span style='color:{C['muted']}'>O Boost foi ajustado para este PC: {rec}</span>")
        for t, txt in adv:
            lines.append(f"<br><b>{t}</b><br><span style='color:{C['muted']}'>{txt}</span>")
        self.pc_lbl.setText("<br>".join(lines))

    def refresh(self):
        self.pending.setText("Analisando o PC…")
        run_async(compute_score, on_done=self._scored)

    def _scored(self, r):
        score, pending, checks = r
        self.score.setText(str(score))
        self.score_bar.setValue(score)
        self.pending.setText(f"{pending} ajuste(s) recomendados pendentes." if pending
                             else "Nada pendente no Boost. Ótimo trabalho!")
        while self.checks_box.count():
            w = self.checks_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        order = {"corrigir": 0, "atencao": 1, "ok": 2}
        for c in sorted(checks, key=lambda c: order[c.state]):
            card = Card()
            row = QHBoxLayout()
            col = QVBoxLayout()
            col.addWidget(label(f"<b>{c.title}</b>", rich=True))
            col.addWidget(label(c.detail, "muted"))
            row.addLayout(col, 1)
            b = Badge(c.state)
            row.addWidget(b)
            if c.state != "ok" and c.fix in FIX_PAGE:
                row.addWidget(button("Resolver", on_click=lambda _=False, p=FIX_PAGE[c.fix]: self.main.go(p)))
            elif c.state != "ok" and c.fix == "relaunch_admin":
                from lolitos.core.system import relaunch_as_admin
                row.addWidget(button("Abrir como admin", on_click=lambda: relaunch_as_admin() and self.main.quit()))
            card.lay.addLayout(row)
            self.checks_box.addWidget(card)

    def _tick(self):
        if not self.isVisible():
            return
        self.live["cpu"].setText(f"{psutil.cpu_percent():.0f}%")
        vm = psutil.virtual_memory()
        self.live["ram"].setText(f"{vm.percent:.0f}%")
        g = gpu.read()
        self.live["gpu"].setText(f"{g['util']}%" if g.get("util") is not None else "—")
        self.live["gtemp"].setText(f"{g['temp']} °C" if g.get("temp") is not None else "—")

    def _boost(self):
        TaskDialog(self, "Boost completo", boost,
                   intro="Aplica os ajustes recomendados que faltam, limpa temporários e libera RAM. "
                         "Um ponto de restauração é criado antes (ou reaproveitado).",
                   on_done=lambda _: (self.refresh(), self.main.changed())).exec()

    def on_show(self):
        if self._built and settings.get("dirty", False):
            settings.set("dirty", False)
            self.refresh()
