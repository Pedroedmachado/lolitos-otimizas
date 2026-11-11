"""Desempenho: monitor ao vivo em gráficos (processador, memória, placa de vídeo, disco e rede), com mínimo e
máximo desde que a tela foi aberta e gravação em CSV. (O Meu PC fica em mypc_page.py.)"""
import csv
import time

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout

from lolitos.core.system import human_size
from lolitos.i18n import tr
from lolitos.modules import gpu, hwinfo, sensors
from lolitos.ui.charts import LineChart
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, button, label, run_async

COLORS = {"cpu": "#2f8bff", "ram": "#2dd4f5", "gpu": "#a46bff", "disk": "#f5b82e", "net": "#22d39b"}


def rate(b: float) -> str:
    """bytes/s → '6,1 MB/s'."""
    for unit, div in (("GB/s", 1e9), ("MB/s", 1e6), ("KB/s", 1e3)):
        if b >= div:
            return f"{b / div:.1f} {unit}".replace(".", ",")
    return f"{b:.0f} B/s"


class _Chart(Card):
    def __init__(self, title: str, color: str, fixed=True, fmt=None, height=150):
        super().__init__()
        top = QHBoxLayout()
        top.addWidget(label(title, "h3"))
        top.addStretch()
        self.value = label("—", wrap=False)
        self.value.setStyleSheet(f"color:{color}; font-size:17pt; font-weight:700;")
        top.addWidget(self.value)
        self.lay.addLayout(top)
        self.chart = LineChart(color=color, fmt=fmt)
        self.chart.fixed = fixed
        self.chart.setMinimumHeight(height)
        self.lay.addWidget(self.chart, 1)
        self.foot = label("", "muted", rich=True)
        self.lay.addWidget(self.foot)

    def set(self, value_txt: str, v: float, foot: str = "", v2: float | None = None):
        self.value.setText(value_txt)
        self.chart.push(v, v2)
        if foot:
            self.foot.setText(foot)


class PerformancePage(Page):
    title = "Desempenho"
    subtitle = "Monitor em tempo real: processador, memória, placa de vídeo, disco e rede."

    def build(self):
        self.rec_btn = button("Gravar em CSV…", on_click=self._rec)
        self.actions.addWidget(button("Zerar mín./máx.", on_click=self._reset))
        self.actions.addWidget(self.rec_btn)
        self.cpu = _Chart("Processador", COLORS["cpu"], height=170)
        self.ram = _Chart("Memória", COLORS["ram"])
        self.gpu = _Chart("Placa de vídeo", COLORS["gpu"])
        self.disk = _Chart("Disco", COLORS["disk"])
        self.net = _Chart("Rede", COLORS["net"], fixed=False, fmt=lambda v: rate(v).replace(",0 ", " "))
        g = QGridLayout()
        g.setSpacing(14)
        g.addWidget(self.cpu, 0, 0, 1, 2)
        g.addWidget(self.ram, 1, 0)
        g.addWidget(self.gpu, 1, 1)
        g.addWidget(self.disk, 2, 0)
        g.addWidget(self.net, 2, 1)
        self.body.addLayout(g)
        self.mm_lbl = label("", "muted", rich=True)
        self.body.addWidget(self.mm_lbl)
        self.mm: dict = {}
        self.rec = None
        self.hw: dict = {}
        self.prev_net = psutil.net_io_counters()
        self.prev_disk = psutil.disk_io_counters()
        self.prev_t = time.time()
        run_async(hwinfo.read_all, on_done=self._hw)
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(1000)

    def _hw(self, d):
        self.hw = {"d": d, "rs": hwinfo.ram_summary(d)}

    def _reset(self):
        self.mm = {}

    def _rec(self):
        if self.rec:
            self.rec[0].close()
            self.rec = None
            self.rec_btn.setText(tr("Gravar em CSV…"))
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("Gravar sensores"),
                                              time.strftime("Sensores %Y-%m-%d %H-%M.csv"), "CSV (*.csv)")
        if path:
            f = open(path, "w", newline="", encoding="utf-8")
            wr = csv.writer(f, delimiter=";")
            wr.writerow(["hora", "cpu_%", "ram_%", "gpu_%", "gpu_c", "vram_mb", "gpu_mhz", "gpu_w", "cpu_c",
                         "disco_%", "leitura_mb_s", "escrita_mb_s", "rede_down_mb_s", "rede_up_mb_s"])
            self.rec = (f, wr)
            self.rec_btn.setText(tr("Parar gravação"))

    def _mm(self, k, v):
        if v is None:
            return
        lo, hi = self.mm.get(k, (v, v))
        self.mm[k] = (min(lo, v), max(hi, v))

    def _tick(self):
        if not self.isVisible() and not self.rec:
            return
        now = time.time()
        dt = max(0.1, now - self.prev_t)
        n, d = psutil.net_io_counters(), psutil.disk_io_counters()
        down = (n.bytes_recv - self.prev_net.bytes_recv) / dt
        up = (n.bytes_sent - self.prev_net.bytes_sent) / dt
        rd = (d.read_bytes - self.prev_disk.read_bytes) / dt if d and self.prev_disk else 0
        wrt = (d.write_bytes - self.prev_disk.write_bytes) / dt if d and self.prev_disk else 0
        busy = 0.0
        if d and self.prev_disk and hasattr(d, "busy_time"):
            busy = min(100.0, (d.busy_time - self.prev_disk.busy_time) / (dt * 10))
        elif d and self.prev_disk:
            busy = min(100.0, (d.read_time + d.write_time - self.prev_disk.read_time - self.prev_disk.write_time)
                       / (dt * 10))
        self.prev_net, self.prev_disk, self.prev_t = n, d, now
        g = gpu.read()
        if time.time() - getattr(self, "_ct_t", 0) > 10:       # temperatura da CPU: fora da interface
            self._ct_t = time.time()
            run_async(lambda: sensors.cpu_temp(10), on_done=lambda r: setattr(self, "_ct", r))
        ctemp, _src = getattr(self, "_ct", (None, ""))
        cpu = psutil.cpu_percent()
        vm = psutil.virtual_memory()
        hw, rs = self.hw.get("d") or {}, self.hw.get("rs") or {}

        # processador
        c0 = (hw.get("cpu") or [{}])[0]
        f = psutil.cpu_freq()
        foot = [f"<b>{(c0.get('Name') or '').strip()}</b>" if c0.get("Name") else "",
                f"{psutil.cpu_count(logical=False)} {tr('núcleos')} / {psutil.cpu_count()} threads",
                f"{f.current / 1000:.2f} GHz".replace(".", ",") if f and f.current else "",
                f"{ctemp:.0f} °C" if ctemp else ""]
        self.cpu.set(f"{cpu:.0f}%", cpu, " · ".join(x for x in foot if x))
        # memória
        gb = vm.total / 1024 ** 3
        foot = [f"<b>{rs['kind']} {rs['running']} MT/s</b>" if rs.get("running") else "",
                f"{rs['count']}/{rs['slots'] or '?'} slots" if rs else "",
                f"{human_size(vm.available)} {tr('disponível')}"]
        self.ram.set(f"{vm.used / 1024 ** 3:.1f} / {gb:.0f} GB ({vm.percent:.0f}%)", vm.percent,
                     " · ".join(x for x in foot if x))
        # placa de vídeo
        util = g.get("util")
        if util is not None:
            foot = [f"<b>{gpu.name()}</b>",
                    f"VRAM {human_size(g['vram_used'])} {tr('em uso de')} {human_size(g['vram_total'])}"
                    if g.get("vram_total") else "",
                    f"{g['temp']} °C" if g.get("temp") is not None else ""]
            self.gpu.set(f"{util}%", util, " · ".join(x for x in foot if x))
        else:
            self.gpu.set("—", 0, tr("Uso da placa de vídeo: driver NVIDIA ou contadores do Windows."))
        # disco
        kind = ""
        for x in hw.get("disks", []):
            if str(x.get("MediaType")) in ("SSD", "HDD"):
                kind = str(x.get("MediaType"))
                break
        foot = [f"{tr('Leitura')} {rate(rd)}", f"{tr('Escrita')} {rate(wrt)}", kind]
        self.disk.set(f"{busy:.0f}%", busy, " · ".join(x for x in foot if x))
        # rede
        self.net.set(f"↓ {rate(down)}", down,
                     f"{tr('Recebendo')} {rate(down)} · {tr('Enviando')} {rate(up)} "
                     f"<span style='color:{C['muted']}'>({tr('linha cinza')})</span>", up)

        for k, v in (("cpu", cpu), ("ram", vm.percent), ("gpu", util), ("disk", busy), ("down", down / 1e6),
                     ("up", up / 1e6), ("cpu_c", ctemp), ("gpu_c", g.get("temp"))):
            self._mm(k, v)
        names = {"cpu": ("CPU", "%"), "ram": ("RAM", "%"), "gpu": ("GPU", "%"), "disk": (tr("Disco"), "%"),
                 "down": ("Download", " MB/s"), "up": ("Upload", " MB/s"), "cpu_c": ("CPU", " °C"),
                 "gpu_c": ("GPU", " °C")}
        self.mm_lbl.setText(tr("Mínimo / máximo desde que a tela abriu: ") + " · ".join(
            f"{names[k][0]} {lo:.0f}–{hi:.0f}{names[k][1]}" for k, (lo, hi) in self.mm.items()))
        if self.rec:
            self.rec[1].writerow([time.strftime("%H:%M:%S")] + [
                "" if v is None else f"{v:.1f}" for v in
                (cpu, vm.percent, util, g.get("temp"), (g.get("vram_used") or 0) / 1024 ** 2 if g else None,
                 g.get("clock"), g.get("power_w"), ctemp, busy, rd / 1e6, wrt / 1e6, down / 1e6, up / 1e6)])

