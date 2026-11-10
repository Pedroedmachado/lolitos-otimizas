"""Aba 'Núcleos do processador' do Black Desert (processadores AMD): escolher as threads por CCD e núcleo, como
uma regra de afinidade do Process Lasso, aplicada sozinha toda vez que o BDO abre."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from lolitos.bdo import cores
from lolitos.i18n import tr
from lolitos.modules import cputopo, pcprofile
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Toggle, button, info, label, pill, run_async


def _chip(text, checkable=True, checked=False, tip=""):
    b = QPushButton(tr(text))
    b.setObjectName("chip")
    b.setCheckable(checkable)
    b.setChecked(checked)
    b.setCursor(Qt.PointingHandCursor)
    if tip:
        b.setToolTip(tr(tip))
    return b


class CoresPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(12)
        prof = pcprofile.detect()
        if prof.vendor != "amd":
            c = Card()
            c.lay.addWidget(label("<b>Núcleos do processador</b>", "h3", rich=True))
            c.lay.addWidget(label(tr("Esta opção é para processadores AMD Ryzen. Seu processador: {}.")
                                  .replace("{}", prof.cpu or "?"), "muted"))
            lay.addWidget(c)
            lay.addStretch()
            return
        self.topo = cputopo.detect()
        r = cores.rule()
        self.sel: set[int] = set(r["cpus"] or cores.recommended(self.topo))
        self.cpu_btns: dict[int, QPushButton] = {}

        # ------------------------------------------------ regra
        head = Card(hero=True)
        h = QHBoxLayout()
        h.addWidget(label("<b>Núcleos do processador para o BDO</b>", "h3", rich=True, wrap=False))
        self.state = pill("…")
        h.addWidget(self.state, 0, Qt.AlignVCenter)
        h.addStretch()
        h.addWidget(label("Aplicar sempre que o BDO abrir", "muted", wrap=False), 0, Qt.AlignVCenter)
        self.sw = Toggle(bool(r["enabled"]))
        self.sw.clicked.connect(self._toggle)
        h.addWidget(self.sw, 0, Qt.AlignVCenter)
        head.lay.addLayout(h)
        head.lay.addWidget(label(
            "Como uma regra do Process Lasso: você escolhe em quais threads o Black Desert roda e o app aplica "
            "sozinho toda vez que o jogo abre (e de novo, se o jogo mudar). Precisa do app aberto ou na bandeja. "
            "Nada é injetado no jogo: é o mesmo 'Definir afinidade' do Gerenciador de Tarefas.", "muted"))
        ccd_txt = " · ".join(
            f"CCD {c.idx}: {len(c.cpus)} threads, L3 {c.l3 // 1024 ** 2 or '?'} MB" + (" (3D V-Cache)" if c.vcache else "")
            for c in self.topo.ccds)
        head.lay.addWidget(label(f"{prof.cpu} — {len(self.topo.cores)} {tr('núcleos')} / "
                                 f"{len(self.topo.threads)} threads · {ccd_txt}", "muted"))
        mrow = QHBoxLayout()
        mrow.addWidget(label("Método", wrap=False))
        self.method_grp = QButtonGroup(self)
        for key, name in cores.METHODS:
            b = _chip(name, checked=r["method"] == key,
                      tip="Rígido: o jogo só roda nessas threads." if key == "affinity" else
                      "Flexível: o Windows prefere essas threads para o jogo, mas pode usar outras se faltar.")
            b.clicked.connect(lambda _=False, k=key: self._method(k))
            self.method_grp.addButton(b)
            mrow.addWidget(b)
        mrow.addStretch()
        head.lay.addLayout(mrow)
        self.method_txt = label("", "muted")
        head.lay.addWidget(self.method_txt)
        lay.addWidget(head)

        # ------------------------------------------------ predefinições
        pc = Card()
        pc.lay.addWidget(label("Escolha rápida", "h2"))
        self.presets = cores.presets(self.topo)
        rows = [self.presets[:3], self.presets[3:]]
        for chunk in rows:
            if not chunk:
                continue
            rl = QHBoxLayout()
            rl.setSpacing(8)
            for key, name, cpus, why in chunk:
                b = _chip(name, checkable=False, tip=why)
                b.clicked.connect(lambda _=False, c=cpus, w=why: self._preset(c, w))
                rl.addWidget(b)
            rl.addStretch()
            pc.lay.addLayout(rl)
        self.preset_txt = label(tr(cores.recommended_why(self.topo)), "muted")
        pc.lay.addWidget(self.preset_txt)
        lay.addWidget(pc)

        # ------------------------------------------------ grade por CCD e núcleo
        gc = Card()
        top = QHBoxLayout()
        top.addWidget(label("Threads do processador", "h2"))
        top.addStretch()
        self.count = pill("")
        top.addWidget(self.count, 0, Qt.AlignVCenter)
        gc.lay.addLayout(top)
        gc.lay.addWidget(label("Cada núcleo físico tem duas threads (SMT). Clique para ligar ou desligar.", "muted"))
        for ccd in self.topo.ccds:
            box = QVBoxLayout()
            hdr = QHBoxLayout()
            t = f"<b>CCD {ccd.idx}</b>"
            if ccd.l3:
                t += f" · L3 {ccd.l3 // 1024 ** 2} MB"
            if ccd.vcache:
                t += f" · <span style='color:{C['accent2']}'>3D V-Cache</span>"
            hdr.addWidget(label(t, rich=True, wrap=False))
            hdr.addStretch()
            for txt, on in (("Todo o CCD", True), ("Nenhum", False)):
                b = button(txt, on_click=lambda _=False, cc=ccd.cpus, v=on: self._set_many(cc, v))
                hdr.addWidget(b)
            box.addLayout(hdr)
            grid = QGridLayout()
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(6)
            ccd_cores = [c for c in self.topo.cores if c.ccd == ccd.idx]
            cols = 4
            for i, core in enumerate(ccd_cores):
                cell = QFrameCore(core, self)
                grid.addWidget(cell, i // cols, i % cols)
            box.addLayout(grid)
            gc.lay.addLayout(box)
        lay.addWidget(gc)

        # ------------------------------------------------ ações
        ac = Card()
        row = QHBoxLayout()
        row.addWidget(button("Salvar e aplicar", "primary", self._save_apply))
        row.addWidget(button("Restaurar todos os núcleos", on_click=self._restore))
        row.addStretch()
        ac.lay.addLayout(row)
        self.status = label("", "muted")
        ac.lay.addWidget(self.status)
        lay.addWidget(ac)
        lay.addStretch()
        self._paint_sel()
        self._method_text(r["method"])
        self.timer = QTimer(self)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        self._poll()

    # ---------------------------------------------------------------- seleção
    def _set_many(self, cpus, on):
        for c in cpus:
            (self.sel.add if on else self.sel.discard)(c)
        self._paint_sel()

    def toggle_cpu(self, cpu, on):
        (self.sel.add if on else self.sel.discard)(cpu)
        self._paint_sel()

    def _preset(self, cpus, why):
        self.sel = set(cpus)
        self.preset_txt.setText(tr(why))
        self._paint_sel()

    def _paint_sel(self):
        for c, b in self.cpu_btns.items():
            b.blockSignals(True)
            b.setChecked(c in self.sel)
            b.blockSignals(False)
        n, tot = len(self.sel), len(self.topo.threads)
        self.count.setText(tr("{} de {} threads").replace("{}", str(n), 1).replace("{}", str(tot), 1))

    def _method(self, key):
        cores.save_rule(method=key)
        self._method_text(key)

    def _method_text(self, key):
        self.method_txt.setText(tr(
            "Afinidade de CPU (rígida): o jogo só pode usar as threads marcadas. É o modo mais usado no Process Lasso."
            if key == "affinity" else
            "CPU Sets (flexível): o Windows coloca o jogo nas threads marcadas, mas pode usar outras se elas "
            "estiverem cheias. Menos chance de travada quando o PC está ocupado."))

    # ---------------------------------------------------------------- ações
    def _main(self):
        return getattr(self.page, "main", None)

    def _toggle(self):
        on = self.sw.isChecked()
        if on and not self.sel:
            self.sw.setChecked(False)
            info(self, "Núcleos do BDO", "Marque pelo menos uma thread.")
            return
        cores.save_rule(enabled=on, cpus=sorted(self.sel))
        m = self._main()
        if m:
            m.start_bdo_cores() if on else m.stop_bdo_cores()
        self._poll()

    def _save_apply(self):
        if not self.sel:
            info(self, "Núcleos do BDO", "Marque pelo menos uma thread.")
            return
        cores.save_rule(enabled=True, cpus=sorted(self.sel))
        self.sw.blockSignals(True)
        self.sw.setChecked(True)
        self.sw.blockSignals(False)
        self.sw.update()
        m = self._main()
        if m:
            m.start_bdo_cores()
        self._poll()

    def _restore(self):
        cores.save_rule(enabled=False)
        self.sw.blockSignals(True)
        self.sw.setChecked(False)
        self.sw.blockSignals(False)
        self.sw.update()
        m = self._main()
        if m:
            m.stop_bdo_cores()

        def done(err):
            self.status.setText(tr("Regra desligada. ") + (tr("Não deu para restaurar: {}").replace("{}", err) if err
                                else tr("Se o BDO estiver aberto, ele voltou a usar todas as threads.")))
        run_async(cores.restore_all, on_done=done)
        self._poll()

    def _poll(self):
        if not self.isVisible() and self.status.text():
            return
        r = cores.rule()
        m = self._main()
        w = getattr(m, "bdo_cores", None) if m else None

        def done(txt):
            on = r["enabled"]
            self.state.setText(tr("Ligada") if on else tr("Desligada"))
            self.state.setStyleSheet(f"color:{C['ok'] if on else C['muted']}; border-color:{C['ok'] if on else C['border2']};")
            self.status.setText(tr("Estado: {}").replace("{}", tr(txt)) + "  ·  " +
                                tr("Regra salva: {} threads ({}).").replace("{}", str(len(r["cpus"])), 1)
                                .replace("{}", tr(dict(cores.METHODS)[r["method"]]), 1))
        if w and w.is_alive():
            run_async(w.check_now, on_done=done)
        else:
            done("regra desligada" if not r["enabled"] else "esperando o app ligar a regra")


class QFrameCore(QWidget):
    """Um núcleo físico com os botões das suas threads."""

    def __init__(self, core, panel: CoresPanel):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(4)
        self.setObjectName("corecell")
        self.setStyleSheet(f"QWidget#corecell {{ border:1px solid {C['border']}; border-radius:8px; }}")
        v.addWidget(label(f"{tr('Núcleo')} {core.idx}", "muted", wrap=False))
        h = QHBoxLayout()
        h.setSpacing(4)
        for cpu in core.cpus:
            b = _chip(f"CPU {cpu}")
            b.setMinimumWidth(64)
            b.toggled.connect(lambda on, c=cpu: panel.toggle_cpu(c, on))
            panel.cpu_btns[cpu] = b
            h.addWidget(b)
        v.addLayout(h)
