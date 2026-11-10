"""Painel: saudação, pontuação, Boost em um clique, cartões rápidos, Windows recém-formatado e monitor ao vivo."""
from __future__ import annotations

import logging
import os
import time

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QProgressBar, QPushButton, QVBoxLayout

from lolitos.catalog.presets import boost_ids
from lolitos.core import settings
from lolitos.core.system import is_admin
from lolitos.core.tweaks import CATALOG
from lolitos.modules import checkup, cleanup, gpu, memory, pcprofile
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import bulk_apply
from lolitos.i18n import tr
from lolitos.ui.widgets import (Card, IconTile, Page, StatTile, TaskDialog, button, card_header, info,
                                label, pill, run_async, status_pool)

FIX_PAGE = {"cleanup": "limpeza", "startup": "inicializacao", "antivirus": "defender", "restore_point": "restauracao",
            "refresh_max": "gpu", "bios": "meupc", "reboot": "restauracao"}
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
    from lolitos.i18n import tr
    rec = tr(f"{len(boost_ids())} ajustes recomendados; {len(skipped)} deixados de fora porque não se aplicam ou "
             f"não ajudam neste PC") + ((": " + ", ".join(tr(t) for t in skipped[:6]) + ("…" if len(skipped) > 6 else "."))
                                        if skipped else ".")
    return p, pcprofile.advice(), rec


_SCORE_POOL = None


def _score_pool():
    global _SCORE_POOL
    if _SCORE_POOL is None:
        from PySide6.QtCore import QThreadPool
        _SCORE_POOL = QThreadPool()
        _SCORE_POOL.setMaxThreadCount(2)
    return _SCORE_POOL


def _safe_status(t) -> str:
    try:
        return t.status()
    except Exception:  # noqa: BLE001 — um ajuste com leitura quebrada não pode travar a análise inteira
        return "off"


def compute_score():
    ids = boost_ids()
    st = {i: _safe_status(CATALOG[i]) for i in ids}
    valid = [s for s in st.values() if s != "na"]
    ratio = sum(1 for s in valid if s == "on") / len(valid) if valid else 1
    try:
        checks = checkup.run_checkup()
    except Exception:  # noqa: BLE001 — sem o check-up a nota usa só os ajustes
        logging.getLogger("lolitos").exception("check-up do Painel")
        checks = []
    pending = sum(1 for s in valid if s != "on")
    pend_ids = [i for i, s in st.items() if s not in ("on", "na")]
    return checkup.score(checks, ratio), pending, checks, pend_ids


def _clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            it.widget().deleteLater()
        elif it.layout():
            _clear_layout(it.layout())


def user_name() -> str:
    """Primeiro nome do usuário do Windows (nome de exibição da conta; senão, o login)."""
    name = settings.get("user_name") or ""
    if name:
        return name
    try:
        import ctypes
        size = ctypes.c_ulong(256)
        buf = ctypes.create_unicode_buffer(256)
        if ctypes.windll.secur32.GetUserNameExW(3, buf, ctypes.byref(size)) and buf.value.strip():  # NameDisplay
            return buf.value.split()[0]
    except (AttributeError, OSError):
        pass
    try:
        return os.getlogin().split(".")[0].capitalize()
    except OSError:
        return ""


def quick_stats() -> dict:
    """Pontos de restauração, o que dá para limpar (temporários) e RAM."""
    from lolitos.core import restore
    out = {}
    try:
        out["points"] = len(restore.list_points())
    except Exception:  # noqa: BLE001
        out["points"] = None
    total = 0
    for t in cleanup.TARGETS:
        if t.default and t.id in ("user_temp", "win_temp", "thumbs", "wer", "dumps", "delivery"):
            try:
                total += cleanup.measure(t)[1]
            except Exception:  # noqa: BLE001
                pass
    out["clean"] = total
    return out


def grade(score: int) -> tuple[str, str]:
    if score >= 90:
        return "ÓTIMO", C["ok"]
    if score >= 70:
        return "BOM", C["accent2"]
    if score >= 50:
        return "REGULAR", C["gold"]
    return "BAIXO", C["bad"]


class Dashboard(Page):
    title = ""

    def build(self):
        from lolitos.core.system import human_size
        from lolitos.ui.charts import CircuitArt, LineChart, Ring, Speedometer
        self.human = human_size
        # ------------------------------------------------ cabeçalho
        head = QHBoxLayout()
        nm = user_name()
        hello = label(f"{tr('Olá')}, <span style='color:{C['accent']}'>{nm}!</span>" if nm else tr("Olá!"),
                      "hello", rich=True, wrap=False)
        head.addWidget(hello, 0, Qt.AlignVCenter)
        head.addStretch()
        head.addWidget(CircuitArt(), 2)
        self.pend_card = Card()
        self.pend_card.setFixedWidth(280)
        pr = QHBoxLayout()
        pc = QVBoxLayout()
        pc.setSpacing(0)
        self.pend_title = label("OTIMIZAÇÃO PENDENTE", "pendtitle")
        self.pend_sub = label("Analisando…", "muted")
        pc.addWidget(self.pend_title)
        pc.addWidget(self.pend_sub)
        pr.addLayout(pc, 1)
        self.pend_icon = IconTile("warning", 40, 14, C["gold"])
        pr.addWidget(self.pend_icon)
        self.pend_card.lay.addLayout(pr)
        head.addWidget(self.pend_card, 0, Qt.AlignTop)
        self.body.addLayout(head)
        if not is_admin():
            self.body.addWidget(label(f"<span style='color:{C['bad']}'>Sem administrador: ajustes do sistema vão "
                                      "falhar. Feche e abra de novo aceitando o pedido do Windows.</span>", rich=True))

        # ------------------------------------------------ linha principal
        row = QHBoxLayout()
        row.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(12)
        self.c_points, self.v_points = self._mini("history", "PONTOS DE RESTAURAÇÃO", "Pontos de restauração do "
                                                  "Windows", "Criar ponto", self._create_point, C["ok"])
        self.c_clean, self.v_clean = self._mini("clean", "ARQUIVOS PARA LIMPAR", "Arquivos do Windows que podem ser "
                                                "limpos", "Limpeza", lambda: self.main.go("limpeza"), C["gold"])
        self.c_ram, self.v_ram = self._mini("ram", "MEMÓRIA RAM", "", "Limpar memória", self._free_ram, C["accent2"])
        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setFixedHeight(6)
        self.c_ram.lay.insertWidget(1, self.ram_bar)
        for c in (self.c_points, self.c_clean, self.c_ram):
            left.addWidget(c)
        row.addLayout(left, 3)

        mid = Card()
        mid.lay.addWidget(label("PONTUAÇÃO DE OTIMIZAÇÃO", "cardcap", wrap=False), 0, Qt.AlignHCenter)
        self.gauge = Speedometer()
        mid.lay.addWidget(self.gauge, 1)
        self.score_lbl = label("—", "scorebig", rich=True, wrap=False)
        mid.lay.addWidget(self.score_lbl, 0, Qt.AlignHCenter)
        self.grade = pill("…")
        mid.lay.addWidget(self.grade, 0, Qt.AlignHCenter)
        self.score_line = label("", "muted", wrap=False)
        mid.lay.addWidget(self.score_line, 0, Qt.AlignHCenter)
        self.boost_btn = button("⚡  Boost agora", "primary", self._boost)
        self.boost_btn.setMinimumHeight(48)
        mid.lay.addWidget(self.boost_btn)
        row.addWidget(mid, 3)

        fresh = Card(hero=True)
        art = QHBoxLayout()
        art.addStretch()
        art.addWidget(IconTile("windows", 96, 40))
        art.addStretch()
        fresh.lay.addLayout(art)
        fresh.lay.addSpacing(8)
        fresh.lay.addWidget(label("NOVO", "newtag"))
        fresh.lay.addWidget(label("Configurar Windows recém-formatado", "h2"))
        fresh.lay.addWidget(label("Acabou de formatar? Deixe tudo pronto de uma vez, numa janela só.", "muted"))
        for t in ("Apps escolhidos instalados em um clique", "Boost e Debloat completos", "Extras e contas novas"):
            fresh.lay.addWidget(label(f"✓  {tr(t)}", "muted", wrap=False))
        fresh.lay.addStretch()
        go = button("Começar configuração  ›", "primary", lambda: self.main.go("formatacao"))
        go.setMinimumHeight(44)
        fresh.lay.addWidget(go)
        row.addWidget(fresh, 4)
        self.body.addLayout(row)

        # ------------------------------------------------ monitor ao vivo
        mon = Card()
        top = QHBoxLayout()
        from lolitos.ui import glyphs
        top.addWidget(glyphs.glyph("speed", 14, C["accent2"]))
        tc = QVBoxLayout()
        tc.setSpacing(0)
        tc.addWidget(label("<b>Monitor de Desempenho em Tempo Real</b>", "h3", rich=True, wrap=False))
        from lolitos.modules.hwmon import cpu_name
        self.mon_sub = label(cpu_name(), "muted", wrap=False)
        tc.addWidget(self.mon_sub)
        top.addLayout(tc)
        top.addStretch()
        self.tabs = QButtonGroup(self)
        seg = QHBoxLayout()
        seg.setSpacing(0)
        for i, k in enumerate(("CPU", "GPU", "RAM", "Disco", "Rede")):
            b = QPushButton(tr(k))
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.tabs.addButton(b, i)
            seg.addWidget(b)
        self.tabs.button(0).setChecked(True)
        self.tabs.idClicked.connect(self._tab)
        top.addLayout(seg)
        mon.lay.addLayout(top)
        mr = QHBoxLayout()
        self.ring = Ring(tr("USO DA CPU"))
        mr.addWidget(self.ring, 0, Qt.AlignVCenter)
        self.chart = LineChart()
        mr.addWidget(self.chart, 1)
        mon.lay.addLayout(mr)
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_clock = StatTile("Clock atual", "—", "", "cpu", Qt.AlignLeft)
        self.t_cores = StatTile("Núcleos / threads", "—", "", "cpu", Qt.AlignLeft)
        self.t_mem = StatTile("Memória RAM", "—", "", "ram", Qt.AlignLeft)
        self.t_gpu = StatTile("Carga da GPU", "—", "", "gpu", Qt.AlignLeft)
        for t in (self.t_clock, self.t_cores, self.t_mem, self.t_gpu):
            tiles.addWidget(t)
        mon.lay.addLayout(tiles)
        self.body.addWidget(mon)

        # ------------------------------------------------ ações recomendadas
        self.act_card = Card()
        hdr = card_header("bolt", "Ações recomendadas")
        self.act_all = button("Ver todos ›", on_click=lambda: self.main and self.main.go("completa"))
        self.act_all.setObjectName("outline")
        hdr.addWidget(self.act_all)
        self.act_card.lay.addLayout(hdr)
        self.act_card.lay.addWidget(label("Ajustes recomendados para este PC que ainda estão desligados.", "muted"))
        self.act_box = QVBoxLayout()
        self.act_box.setSpacing(12)
        self.act_card.lay.addLayout(self.act_box)
        self.body.addWidget(self.act_card)

        # ------------------------------------------------ seu PC
        self.pc_card = Card()
        self.pc_card.lay.addLayout(card_header("pc", "Seu PC"))
        self.pc_lbl = label("Analisando o hardware…", rich=True)
        self.pc_card.lay.addWidget(self.pc_lbl)
        self.body.addWidget(self.pc_card)
        run_async(pc_analysis, on_done=self._pc, on_error=lambda e: (
            self.pc_lbl.setText(tr("Não deu para ler o hardware agora; tentando de novo…")),
            QTimer.singleShot(8000, lambda: run_async(pc_analysis, on_done=self._pc))))

        self.tab = 0
        self._prev = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        psutil.cpu_percent()
        cores = psutil.cpu_count(logical=False) or 0
        self.t_cores.set(f"{cores} / {psutil.cpu_count() or 0}")
        self.refresh()

    def _mini(self, icon, cap, sub, btn_text, on_click, color):
        c = Card()
        r = QHBoxLayout()
        r.setSpacing(12)
        r.addWidget(IconTile(icon, 42, 14, color), 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(cap, "cardcap", wrap=False))
        v = label("…", "miniv", wrap=False)
        col.addWidget(v)
        sub_l = label(sub, "muted")
        col.addWidget(sub_l)
        v.sub = sub_l
        r.addLayout(col, 1)
        c.lay.addLayout(r)
        b = button(btn_text, on_click=on_click)
        b.setObjectName("outline")
        c.lay.addWidget(b)
        return c, v

    # ---------------------------------------------------------------- dados
    def _pc(self, r):
        p, adv, rec = r
        lines = [f"<b style='color:{C['accent2']}'>{p.tier_name}</b> — " + " · ".join(p.summary())]
        lines.append(f"<span style='color:{C['muted']}'>{tr('O Boost foi ajustado para este PC:')} {rec}</span>")
        for t, txt in adv:
            lines.append(f"<br><b>{t}</b><br><span style='color:{C['muted']}'>{txt}</span>")
        self.pc_lbl.setText("<br>".join(lines))

    SCORE_TIMEOUT_MS = 120_000

    def refresh(self, attempt: int = 0):
        """A análise sempre termina: roda numa fila só dela, tenta de novo se falhar e, se passar de 2 minutos
        sem resposta, começa de novo (antes ela podia ficar presa em 'Analisando…')."""
        self._score_gen = getattr(self, "_score_gen", 0) + 1
        gen = self._score_gen

        def done(r):
            if gen == self._score_gen:
                self._score_watch.stop()
                self._scored(r)

        def failed(err):
            if gen != self._score_gen:
                return
            self._score_watch.stop()
            logging.getLogger("lolitos").warning("análise do Painel falhou (%s): %s", attempt + 1, err)
            if attempt < 3:
                self.pend_sub.setText(tr("A análise falhou; tentando de novo…"))
                QTimer.singleShot(5000 * (attempt + 1), lambda: self.refresh(attempt + 1))
            else:
                self._score_failed()
        self._score_fail = failed
        if not hasattr(self, "_score_watch"):
            self._score_watch = QTimer(self)
            self._score_watch.setSingleShot(True)
            self._score_watch.timeout.connect(lambda: self._score_fail("tempo esgotado"))
        self._score_watch.start(self.SCORE_TIMEOUT_MS)
        run_async(compute_score, on_done=done, on_error=failed, _pool=_score_pool())
        run_async(quick_stats, on_done=self._quick, on_error=lambda e: None, _pool=status_pool())

    def _quick(self, q):
        self.v_points.setText("—" if q.get("points") is None else str(q["points"]))
        self.v_clean.setText(self.human(q.get("clean", 0)))
        self._clean_bytes = q.get("clean", 0)
        self._update_line()

    def _actions(self, pend_ids):
        while self.act_box.count():
            it = self.act_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                _clear_layout(it.layout())
        if not pend_ids:
            self.act_box.addWidget(label("Tudo que é recomendado já está ativo neste PC.", "muted"))
            self.act_all.hide()
            return
        self.act_all.show()
        from lolitos.core.tweaks import CATS
        for tid in pend_ids[:5]:
            t = CATALOG[tid]
            row = QHBoxLayout()
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(label(f"<b>{tr(t.title)}</b>", rich=True))
            col.addWidget(label(tr(t.desc), "muted"))
            row.addLayout(col, 1)
            row.addWidget(pill(tr(CATS.get(t.cat, t.cat)).upper()), 0, Qt.AlignVCenter)
            b = button("Aplicar", "primary", lambda _=False, tt=t: self._apply_one(tt))
            row.addWidget(b, 0, Qt.AlignVCenter)
            self.act_box.addLayout(row)
        if len(pend_ids) > 5:
            self.act_box.addWidget(label(tr("e mais {} ajuste(s)…").replace("{}", str(len(pend_ids) - 5)), "muted"))

    def _apply_one(self, t):
        from lolitos.ui.tweaklist import confirm_advanced
        if not confirm_advanced(self, t):
            return
        TaskDialog(self, tr(t.title), bulk_apply, [t], restore_point=False,
                   on_done=lambda _: (self.refresh(), self.main and self.main.changed())).exec()

    def _score_failed(self):
        """Três tentativas sem resposta: libera o Painel mesmo assim e tenta de novo daqui a 5 minutos."""
        self.boost_btn.setEnabled(True)
        self.boost_btn.setText(f"⚡  {tr('Boost agora')}")
        self.score_lbl.setText("—")
        self.pend_title.setText(tr("ANÁLISE INDISPONÍVEL"))
        self.pend_sub.setText(tr("O Windows demorou para responder. Vou tentar de novo em alguns minutos."))
        QTimer.singleShot(300_000, self.refresh)

    def _scored(self, r):
        score, pending, checks, pend_ids = r
        self.boost_btn.setEnabled(True)
        self._actions(pend_ids)
        self.score, self.pending_n = score, pending
        self.gauge.set(score)
        self.score_lbl.setText(f"{score}<span style='font-size:14pt'>%</span>")
        g, col = grade(score)
        self.grade.setText(tr(g))
        self.grade.setStyleSheet(f"color:{col}; border-color:{col};")
        valid = [t for t in (CATALOG[i] for i in boost_ids())]
        self._boost_total = len(valid)
        self.boost_btn.setText(f"⚡  {tr('Boost agora')}" + (f"  ·  {pending} {tr('ajustes')}" if pending else ""))
        if pending:
            self.pend_title.setText(tr("OTIMIZAÇÃO PENDENTE"))
            self.pend_title.setStyleSheet(f"color:{C['accent2']};")
            self.pend_sub.setText(tr("{} ajuste(s) desligado(s).").replace("{}", str(pending)))
        else:
            self.pend_title.setText(tr("PC OTIMIZADO"))
            self.pend_title.setStyleSheet(f"color:{C['ok']};")
            self.pend_sub.setText(tr("Tudo que é recomendado está ativo."))
        self._update_line()

    def _update_line(self):
        if not hasattr(self, "_boost_total"):
            return
        done = self._boost_total - getattr(self, "pending_n", 0)
        mem = psutil.virtual_memory().percent
        parts = [f"{tr('Otimizações')} {done}/{self._boost_total}", f"{tr('memória')} {mem:.0f}% {tr('em uso')}"]
        if hasattr(self, "_clean_bytes"):
            parts.append(f"{tr('limpeza')} {self.human(self._clean_bytes)}")
        self.score_line.setText(" · ".join(parts))

    def _tab(self, i):
        self.tab = i
        self.chart.reset(fixed=i in (0, 1, 2))
        self.ring.set(0, "—", tr(["USO DA CPU", "USO DA GPU", "USO DA RAM", "DISCO MB/S", "REDE MBPS"][i]))
        g = gpu.name() if i == 1 and gpu.available() else ""
        from lolitos.modules.hwmon import cpu_name
        self.mon_sub.setText([cpu_name(), g or tr("Placa de vídeo"), tr("Memória do sistema"), tr("Todos os discos"),
                              tr("Todas as conexões")][i])

    def _rate(self, key, value):
        now = time.time()
        old = self._prev.get(key)
        self._prev[key] = (now, value)
        return (value - old[1]) / (now - old[0]) if old and now > old[0] else 0.0

    def _tick(self):
        if not self.isVisible():
            return
        cpu = psutil.cpu_percent()
        vm = psutil.virtual_memory()
        g = gpu.read() if gpu.available() else {}
        d = psutil.disk_io_counters()
        n = psutil.net_io_counters()
        disk = self._rate("d", (d.read_bytes + d.write_bytes) if d else 0) / 1024 ** 2
        net = self._rate("n", (n.bytes_recv + n.bytes_sent) if n else 0) * 8 / 1e6
        vals = [cpu, g.get("util") or 0, vm.percent, disk, net]
        v = vals[self.tab]
        self.chart.push(v)
        if self.tab < 3:
            self.ring.set(v / 100, f"{v:.0f}%")
        else:
            self.ring.set(min(1.0, v / max(1.0, self.chart.scale_max)), f"{v:.0f}")
        f = psutil.cpu_freq()
        self.t_clock.set(f"{f.current / 1000:.1f} GHz" if f and f.current else "—")
        self.t_mem.set(f"{vm.total / 1024 ** 3:.1f} GB")
        self.t_gpu.set(f"{g['util']}%" if g.get("util") is not None else "—")
        self.v_ram.setText(f"{vm.percent:.0f}%")
        self.v_ram.sub.setText(f"{vm.used / 1024 ** 3:.1f} GB {tr('de')} {vm.total / 1024 ** 3:.1f} GB {tr('em uso')}")
        self.ram_bar.setValue(int(vm.percent))

    # ---------------------------------------------------------------- ações
    def _create_point(self):
        from lolitos.core import restore
        TaskDialog(self, "Ponto de restauração", lambda progress=None: restore.create(force=True)[1],
                   on_done=lambda _: self.refresh()).exec()

    def _free_ram(self):
        def done(r):
            info(self, "Memória", tr("{} MB liberados.").replace("{}", f"{r['freed'] / 1024 ** 2:.0f}"))
        run_async(memory.free_ram, on_done=done)

    def _boost(self):
        TaskDialog(self, "Boost completo", boost,
                   intro="Aplica os ajustes recomendados que faltam, limpa temporários e libera RAM. "
                         "Um ponto de restauração é criado antes (ou reaproveitado).",
                   on_done=lambda _: (self.refresh(), self.main.changed())).exec()
