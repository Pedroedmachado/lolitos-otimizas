"""Hardware Monitor: árvore de sensores com valor, mínimo e máximo desde que a tela foi aberta."""
from __future__ import annotations

import csv
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFileDialog, QHeaderView, QTreeWidget, QTreeWidgetItem

from lolitos.i18n import current, tr
from lolitos.modules import hwmon
from lolitos.ui.theme import C
from lolitos.ui.widgets import Page, button, info, label, run_async, status_pool

DECIMALS = {"MHz": 0, "%": 0, "°C": 1, "GB": 1, "W": 1, "MB/s": 1, "Mbps": 1}


def fmt(v: float | None, unit: str) -> str:
    if v is None:
        return "—"
    d = DECIMALS.get(unit, 1)
    s = f"{v:,.{d}f}"
    if current() != "en":     # 5.065 MHz / 47,0 °C
        s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{s} {unit}"


class HwMonitorPage(Page):
    title = "Hardware Monitor"
    icon = "sensor"
    subtitle = ("Temperaturas, clocks, energia, uso, discos e rede ao vivo, com o mínimo e o máximo desde que a tela "
                "foi aberta. Lido direto do Windows e do driver da placa de vídeo, sem instalar nada.")

    def build(self):
        self.actions.addWidget(button("Recolher tudo", on_click=self._toggle_all))
        self.actions.addWidget(button("Zerar mín./máx.", on_click=self._reset))
        self.actions.addWidget(button("Gravar em CSV…", on_click=self._csv))
        self.tree = QTreeWidget()
        self.tree.setObjectName("sensors")
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Sensor", "Valor", "Mínimo", "Máximo"])
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(18)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in (1, 2, 3):
            h.setSectionResizeMode(i, QHeaderView.Fixed)
            self.tree.setColumnWidth(i, 150)
            self.tree.headerItem().setTextAlignment(i, Qt.AlignRight | Qt.AlignVCenter)
        self.tree.setMinimumHeight(620)
        self.body.addWidget(self.tree)
        self.foot = label("", "muted")
        self.body.addWidget(self.foot)
        self.body.addWidget(label("Clock de cada núcleo: contadores de desempenho do Windows (o mesmo cálculo do "
                                  "Gerenciador de Tarefas). Placa NVIDIA: driver (NVML). A temperatura do processador "
                                  "aparece quando o LibreHardwareMonitor ou o HWiNFO estão abertos, ou pela zona "
                                  "térmica da placa-mãe; tensões e ventoinhas da placa-mãe não são lidas.", "muted"))
        self.items: dict[tuple, QTreeWidgetItem] = {}
        self.nodes: dict[tuple, QTreeWidgetItem] = {}
        self.stats: dict[tuple, list] = {}       # chave -> [min, max, unit]
        self.history: list[tuple] = []
        self.expanded = True
        self.busy = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def on_show(self):
        if self._built:
            self.timer.start(1000)
            self._tick()

    def hideEvent(self, e):
        super().hideEvent(e)
        if hasattr(self, "timer"):
            self.timer.stop()

    def _tick(self):
        if self.busy:
            return
        self.busy = True
        run_async(hwmon.read_all, on_done=self._show, on_error=lambda e: setattr(self, "busy", False),
                  _pool=status_pool())

    def _node(self, key: tuple, parent, text: str, bold: bool) -> QTreeWidgetItem:
        it = self.nodes.get(key)
        if it is None:
            it = QTreeWidgetItem([tr(text), "", "", ""])
            f = QFont(self.tree.font())
            f.setBold(bold)
            it.setFont(0, f)
            if parent is None:
                self.tree.addTopLevelItem(it)
            else:
                parent.addChild(it)
            it.setExpanded(self.expanded)
            self.nodes[key] = it
        return it

    def _show(self, readings):
        self.busy = False
        now = time.time()
        for r in readings:
            dev = self._node((r.device,), None, r.device, True)
            grp = self._node((r.device, r.group), dev, r.group, False)
            key = (r.device, r.group, r.name)
            it = self.items.get(key)
            if it is None:
                it = QTreeWidgetItem([tr(r.name), "", "", ""])
                for i in (1, 2, 3):
                    it.setTextAlignment(i, Qt.AlignRight | Qt.AlignVCenter)
                grp.addChild(it)
                self.items[key] = it
            st = self.stats.setdefault(key, [None, None, r.unit])
            if r.value is not None:
                st[0] = r.value if st[0] is None else min(st[0], r.value)
                st[1] = r.value if st[1] is None else max(st[1], r.value)
            it.setText(1, fmt(r.value, r.unit))
            it.setText(2, fmt(st[0], r.unit))
            it.setText(3, fmt(st[1], r.unit))
            if r.unit == "°C" and r.value is not None:
                it.setForeground(1, QColor(C["bad"] if r.value >= 85 else C["warn"] if r.value >= 75 else C["text"]))
            self.history.append((now, r.device, r.group, r.name, r.value, r.unit))
        self.history = self.history[-200000:]
        self.foot.setText(tr("{} sensores · atualiza a cada 1 s").replace("{}", str(len(self.items))))

    def _toggle_all(self):
        self.expanded = not self.expanded
        for it in self.nodes.values():
            it.setExpanded(self.expanded)
        b = self.sender()
        if b:
            b.setText(tr("Recolher tudo" if self.expanded else "Expandir tudo"))

    def _reset(self):
        self.stats.clear()
        self._tick()

    def _csv(self):
        if not self.history:
            info(self, "Hardware Monitor", "Ainda não há leituras.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Gravar em CSV", time.strftime("sensores %Y-%m-%d %H-%M.csv"),
                                              "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["hora", "dispositivo", "grupo", "sensor", "valor", "unidade"])
            for t, d, g, n, v, u in self.history:
                w.writerow([time.strftime("%H:%M:%S", time.localtime(t)), d, g, n,
                            "" if v is None else f"{v:.2f}", u])
        info(self, "Hardware Monitor", f"Leituras salvas em {path}")
