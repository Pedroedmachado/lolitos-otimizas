"""Desempenho: monitor ao vivo com gravação em CSV. (O Meu PC fica em mypc_page.py.)"""
import csv
import time

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog

from lolitos.modules import gpu, sensors
from lolitos.ui.theme import C
from lolitos.ui.widgets import Page, button, hrow, label, run_async


def kv(rows):
    return "<table cellspacing=4>" + "".join(
        f"<tr><td style='color:{C['muted']}'>{k}</td><td><b>{v}</b></td></tr>" for k, v in rows if v not in
        (None, "")) + "</table>"


class PerformancePage(Page):
    title = "Desempenho"
    subtitle = ""

    def build(self):
        lay = self.body
        lay.addWidget(label("Processador, memória, placa de vídeo, disco e rede ao vivo, com mínimo e máximo desde "
                            "que a tela foi aberta. Compare antes e depois de aplicar.", "muted"))
        self.rec_btn = button("Gravar em CSV…", on_click=self._rec)
        lay.addLayout(hrow(button("Zerar mín./máx.", on_click=self._reset), self.rec_btn, None))
        self.live = label("", rich=True)
        lay.addWidget(self.live)
        self.mm = {}
        self.rec = None
        self.prev_net = psutil.net_io_counters()
        self.prev_disk = psutil.disk_io_counters()
        self.prev_t = time.time()
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(1000)

    def _reset(self):
        self.mm = {}

    def _rec(self):
        if self.rec:
            self.rec[0].close()
            self.rec = None
            self.rec_btn.setText("Gravar em CSV…")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Gravar sensores", time.strftime("Sensores %Y-%m-%d %H-%M.csv"),
                                              "CSV (*.csv)")
        if path:
            f = open(path, "w", newline="", encoding="utf-8")
            wr = csv.writer(f, delimiter=";")
            wr.writerow(["hora", "cpu_%", "ram_%", "gpu_%", "gpu_c", "vram_mb", "gpu_mhz", "gpu_w", "cpu_c",
                         "disco_mb_s", "rede_down_mb_s"])
            self.rec = (f, wr)
            self.rec_btn.setText("Parar gravação")

    def _tick(self):
        if not self.isVisible() and not self.rec:
            return
        now = time.time()
        dt = max(0.1, now - self.prev_t)
        n, d = psutil.net_io_counters(), psutil.disk_io_counters()
        down = (n.bytes_recv - self.prev_net.bytes_recv) / dt / 1e6
        up = (n.bytes_sent - self.prev_net.bytes_sent) / dt / 1e6
        disk = ((d.read_bytes + d.write_bytes) - (self.prev_disk.read_bytes + self.prev_disk.write_bytes)) / dt / 1e6 \
            if d and self.prev_disk else 0
        self.prev_net, self.prev_disk, self.prev_t = n, d, now
        g = gpu.read()
        # temperatura da CPU vem do PowerShell: nunca na thread da interface
        if time.time() - getattr(self, "_ct_t", 0) > 10:
            self._ct_t = time.time()
            run_async(lambda: sensors.cpu_temp(10), on_done=lambda r: setattr(self, "_ct", r))
        ctemp, src = getattr(self, "_ct", (None, ""))
        vals = {
            "CPU (uso)": (psutil.cpu_percent(), "%"), "RAM (uso)": (psutil.virtual_memory().percent, "%"),
            "GPU (uso)": (g.get("util"), "%"), "GPU (temperatura)": (g.get("temp"), "°C"),
            "VRAM em uso": ((g.get("vram_used") or 0) / 1024**2 if g else None, "MB"),
            "GPU (clock)": (g.get("clock"), "MHz"), "GPU (energia)": (g.get("power_w"), "W"),
            "CPU (temperatura)": (ctemp, "°C"), "Disco (atividade)": (disk, "MB/s"),
            "Rede (download)": (down, "MB/s"), "Rede (upload)": (up, "MB/s"),
        }
        rows = []
        for k, (v, unit) in vals.items():
            if v is None:
                rows.append((k, "—", "", ""))
                continue
            lo, hi = self.mm.get(k, (v, v))
            self.mm[k] = (min(lo, v), max(hi, v))
            rows.append((k, f"{v:.0f} {unit}", f"{self.mm[k][0]:.0f}", f"{self.mm[k][1]:.0f}"))
        html = (f"<table cellspacing=6><tr><td></td><td style='color:{C['muted']}'>Atual</td>"
                f"<td style='color:{C['muted']}'>Mín</td><td style='color:{C['muted']}'>Máx</td></tr>" +
                "".join(f"<tr><td>{a}</td><td><b>{b}</b></td><td>{c}</td><td>{e}</td></tr>" for a, b, c, e in rows) +
                "</table>")
        if not ctemp:
            html += (f"<p style='color:{C['muted']}'>Temperatura da CPU: abra o LibreHardwareMonitor (com 'Run as "
                     "service'/WMI ligado) para o app ler o sensor do processador.</p>")
        elif src:
            html += f"<p style='color:{C['muted']}'>CPU °C: {src}</p>"
        self.live.setText(html)
        if self.rec:
            self.rec[1].writerow([time.strftime("%H:%M:%S")] + [
                f"{vals[k][0]:.1f}" if vals[k][0] is not None else "" for k in
                ("CPU (uso)", "RAM (uso)", "GPU (uso)", "GPU (temperatura)", "VRAM em uso", "GPU (clock)",
                 "GPU (energia)", "CPU (temperatura)", "Disco (atividade)", "Rede (download)")])
