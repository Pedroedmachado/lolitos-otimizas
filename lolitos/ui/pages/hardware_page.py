"""Meu PC (componentes lidos do Windows) e Desempenho (monitor ao vivo com gravação em CSV)."""
import csv
import re
import time

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QGridLayout, QVBoxLayout, QWidget

from lolitos.core.system import human_size
from lolitos.modules import display, gpu, hwinfo, sensors
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, button, hrow, label, run_async


def kv(rows):
    return "<table cellspacing=4>" + "".join(
        f"<tr><td style='color:{C['muted']}'>{k}</td><td><b>{v}</b></td></tr>" for k, v in rows if v not in
        (None, "")) + "</table>"


class MyPcPage(Page):
    title = "Meu PC"
    subtitle = "Tudo sobre o hardware deste PC, lido direto do Windows, e o perfil que o app usa para escolher os ajustes."

    def build(self):
        self.prof = label("Analisando o PC…", "muted", rich=True)
        pc = Card(hero=True)
        pc.lay.addWidget(label("Perfil deste PC", "h2"))
        pc.lay.addWidget(self.prof)
        pc.lay.addLayout(hrow(button("Copiar minha configuração", on_click=self._copy),
                              button("Check-up completo", on_click=lambda: self.main.go("checkup")), None))
        self.body.addWidget(pc)
        self.info_w = QWidget()
        self.info_l = QVBoxLayout(self.info_w)
        self.info_l.setContentsMargins(0, 0, 0, 0)
        self.info_l.addWidget(label("Lendo o hardware…", "muted"))
        self.body.addWidget(self.info_w)
        self._text = ""
        from lolitos.ui.pages.dashboard import pc_analysis
        run_async(pc_analysis, on_done=self._prof)
        run_async(hwinfo.read_all, on_done=self._show)

    def _prof(self, r):
        p, adv, rec = r
        self._text = "\n".join([f"Perfil: {p.tier_name}", *p.summary()])
        lines = [f"<b style='color:{C['accent2']}'>{p.tier_name}</b>", *p.summary(),
                 f"<span style='color:{C['muted']}'>{rec}</span>"]
        lines += [f"<b>{t}</b> — <span style='color:{C['muted']}'>{txt}</span>" for t, txt in adv]
        self.prof.setText("<br>".join(lines))

    def _copy(self):
        from PySide6.QtGui import QGuiApplication

        from lolitos import APP_NAME, VERSION
        from lolitos.ui.widgets import info
        QGuiApplication.clipboard().setText(f"{APP_NAME} {VERSION} — meu PC\n" + (self._text or "") +
                                            ("\n\n" + self._plain if getattr(self, "_plain", "") else ""))
        info(self, "Copiado", "Configuração copiada. Agora é só colar (WhatsApp, Discord, fórum).")

    def _show(self, d):
        while self.info_l.count():
            w = self.info_l.takeAt(0).widget()
            if w:
                w.deleteLater()
        grid = QGridLayout()
        cards = []
        for cpu in d.get("cpu", []):
            cards.append(("Processador", kv([
                ("Modelo", cpu.get("Name", "").strip()),
                ("Núcleos / threads", f"{cpu.get('NumberOfCores')} / {cpu.get('NumberOfLogicalProcessors')}"),
                ("Clock base", f"{cpu.get('MaxClockSpeed')} MHz"),
                ("Cache L2 / L3", f"{(cpu.get('L2CacheSize') or 0) // 1024} MB / {(cpu.get('L3CacheSize') or 0) // 1024} MB"),
                ("Soquete", cpu.get("SocketDesignation")),
                ("Virtualização", "ativada na BIOS" if cpu.get("VirtualizationFirmwareEnabled") else "desativada"),
            ])))
        rs = hwinfo.ram_summary(d)
        if rs:
            xmp = (f"<span style='color:{C['bad']}'>desligado: {rs['running']} de {rs['rated']} MT/s — ative na BIOS"
                   "</span>" if rs["xmp_off"] else f"<span style='color:{C['ok']}'>ok</span>")
            sticks = "<br>".join(f"{s.get('DeviceLocator')} · {human_size(int(s.get('Capacity') or 0))} · "
                                 f"{(s.get('Manufacturer') or '').strip()} {(s.get('PartNumber') or '').strip()}"
                                 for s in rs["sticks"])
            cards.append(("Memória", kv([
                ("Total", f"{rs['total_gb']:.0f} GB {rs['kind']}"),
                ("Velocidade", f"{rs['running']} MT/s (nominal {rs['rated']})"),
                ("XMP/EXPO", xmp),
                ("Canais", ("dual channel" if rs["dual"] else "single channel" if rs["count"] == 1 else
                            "verifique os slots") + (f" ({', '.join(rs['channels'])})" if rs["channels"] else "")),
                ("Slots", f"{rs['count']} de {rs['slots'] or '?'} ocupados"),
                ("Pentes", sticks),
            ])))
        b, bios = d.get("board") or {}, d.get("bios") or {}
        cards.append(("Placa-mãe e BIOS", kv([
            ("Placa", f"{b.get('Manufacturer', '')} {b.get('Product', '')}"),
            ("BIOS", f"{bios.get('SMBIOSBIOSVersion', '')} ({bios.get('Date', '')})"),
            ("Firmware", d.get("firmware")),
            ("Secure Boot", {True: "ligado", False: "desligado", None: "—"}.get(d.get("secureboot"))),
            ("TPM", "pronto" if (d.get("tpm") or {}).get("ready") else "ausente/desligado"),
        ])))
        g = gpu.read()
        for v in d.get("gpu", []):
            rows = [("Modelo", v.get("Name")), ("Driver", v.get("DriverVersion"))]
            if g and gpu.name() and gpu.name() in (v.get("Name") or ""):
                rows += [("VRAM", human_size(g.get("vram_total") or 0)),
                         ("Link PCIe", f"Gen {g.get('pcie_gen')} x{g.get('pcie_width')} (máx Gen {g.get('pcie_gen_max')} "
                                       f"x{g.get('pcie_width_max')})"),
                         ("Driver NVIDIA", gpu.driver_version())]
                if g.get("pcie_width") and g.get("pcie_width_max") and g["pcie_width"] < g["pcie_width_max"]:
                    rows.append(("Atenção", f"<span style='color:{C['warn']}'>usando x{g['pcie_width']} de "
                                            f"x{g['pcie_width_max']}: confira se a placa está no 1º slot x16 e se um "
                                            "SSD M.2 divide as linhas</span>"))
            cards.append(("Placa de vídeo", kv(rows)))
        mons = display.monitors()
        if mons:
            cards.append(("Monitores", kv([(m["name"] + (" (principal)" if m["primary"] else ""),
                                            f"{m['width']}×{m['height']} a {m['hz']} Hz (máx {m['max_hz']} Hz)")
                                           for m in mons])))
        disks = d.get("disks", [])
        if disks:
            cards.append(("Discos", kv([(x.get("FriendlyName"), f"{x.get('MediaType')} · {x.get('BusType')} · "
                                         f"{human_size(int(x.get('Size') or 0))} · {x.get('HealthStatus')}")
                                        for x in disks])))
        os_ = d.get("os") or {}
        cards.append(("Sistema", kv([("Windows", f"{os_.get('Caption', '')} (build {os_.get('BuildNumber', '')})"),
                                     ("Antivírus", ", ".join(a.get("displayName", "") for a in d.get("av", [])))])))
        self._plain = "\n".join(f"{t}: " + re.sub(r"<[^>]+>", " ", h.replace("</tr>", " | ")).strip()
                                for t, h in cards)
        for i, (t, html) in enumerate(cards):
            c = Card()
            c.lay.addWidget(label(t, "h2"))
            c.lay.addWidget(label(html, rich=True))
            grid.addWidget(c, i // 2, i % 2)
        self.info_l.addLayout(grid)
        self.info_l.addStretch()


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
