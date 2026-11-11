"""Meu PC: tudo sobre o hardware deste computador, lido direto do Windows, em abas (processador, caches, placa-mãe,
memória, slots, gráficos, armazenamento e check-up). As peças do desenho da placa abrem a aba certa."""
from __future__ import annotations

import html
import re
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QGridLayout, QSizePolicy, QTabWidget, QVBoxLayout, QWidget

from lolitos.core.system import human_size
from lolitos.i18n import tr
from lolitos.modules import cpuinfo, display, gpu, hwcheck, hwinfo
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, button, hrow, info, label, pill, run_async

TABS = ["Processador", "Caches", "Placa-mãe", "Memória", "Slots de memória", "Gráficos", "Armazenamento", "Check-up"]
PART_TAB = {"cpu": 0, "chipset": 2, "gpu": 5}


def kv(rows) -> str:
    return "<table cellspacing=3>" + "".join(
        f"<tr><td style='color:{C['muted']}; padding-right:18px'>{tr(k)}</td><td>{v}</td></tr>"
        for k, v in rows if v not in (None, "", "None")) + "</table>"


def _box(title: str, rows) -> Card:
    c = Card()
    c.lay.addWidget(label(title, "h3"))
    c.lay.addWidget(label(kv(rows), rich=True))
    c.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    return c


def _collect():
    d = hwinfo.read_all()
    cpu0 = (d.get("cpu") or [{}])[0]
    return {"d": d, "rs": hwinfo.ram_summary(d), "id": cpuinfo.read_id((cpu0.get("Name") or "").strip()),
            "caches": cpuinfo.read_caches(), "nv": {**gpu.read(), **gpu.details(), "name": gpu.name()},
            "mons": display.monitors()}


class MyPcPage(Page):
    title = "Meu PC"
    subtitle = ("Tudo sobre o hardware deste computador, lido direto do Windows: processador, caches, placa-mãe, "
                "memória, placa de vídeo e discos.")

    def build(self):
        self.actions.addWidget(button("Copiar minha configuração", on_click=self._copy))
        self.actions.addWidget(button("Exportar relatório…", on_click=self._export))
        self.prof = label("Analisando o PC…", "muted", rich=True)
        pc = Card(hero=True)
        pc.lay.addWidget(label("Perfil deste PC", "h2"))
        pc.lay.addWidget(self.prof)
        self.body.addWidget(pc)
        from lolitos.ui.board import BoardView
        bc = Card()
        bc.lay.addWidget(label("Passe o mouse em cada peça para ver os detalhes; clique para abrir a aba dela.", "muted"))
        self.board = BoardView(bc)
        from lolitos.ui.board import H as BH, W as BW
        self.board.setFixedSize(600, int(600 * BH / BW))
        self.board.clicked.connect(self._part)
        bc.lay.addWidget(self.board, 0, Qt.AlignHCenter)
        self.body.addWidget(bc)
        self.tabs = QTabWidget()
        self.tab_lay: list[QVBoxLayout] = []
        for t in TABS:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 12, 0, 0)
            lay.setSpacing(12)
            lay.addWidget(label("Lendo o hardware…", "muted"))
            self.tab_lay.append(lay)
            self.tabs.addTab(w, t)
        self.body.addWidget(self.tabs)
        self.data: dict = {}
        self._text = ""
        self.live_cpu = self.live_gpu = None
        from lolitos.ui.pages.dashboard import pc_analysis
        run_async(pc_analysis, on_done=self._prof)
        run_async(_collect, on_done=self._show)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(2000)

    # ---------------------------------------------------------------- perfil (nosso)
    def _prof(self, r):
        p, adv, rec = r
        self._text = "\n".join([f"Perfil: {p.tier_name}", *p.summary()])
        lines = [f"<b style='color:{C['accent2']}'>{p.tier_name}</b>", *p.summary(),
                 f"<span style='color:{C['muted']}'>{rec}</span>"]
        lines += [f"<b>{t}</b> — <span style='color:{C['muted']}'>{txt}</span>" for t, txt in adv]
        self.prof.setText("<br>".join(lines))

    def _part(self, key: str):
        if key in PART_TAB:
            self.tabs.setCurrentIndex(PART_TAB[key])
        elif key.startswith("ram"):
            self.tabs.setCurrentIndex(4)
        elif key.startswith(("m2", "sata")):
            self.tabs.setCurrentIndex(6)

    @staticmethod
    def _clear(lay):
        while lay.count():
            it = lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    # ---------------------------------------------------------------- abas
    def _show(self, data):
        self.data = data
        d, rs = data["d"], data["rs"]
        self.board.set_data(d, rs)
        builders = [self._cpu, self._caches, self._board, self._mem, self._slots, self._gpu, self._disks, self._check]
        for lay, fn in zip(self.tab_lay, builders):
            self._clear(lay)
            try:
                fn(lay)
            except Exception as e:  # noqa: BLE001 — uma aba com erro não derruba as outras
                lay.addWidget(label(tr("Não deu para ler: {}").replace("{}", str(e)), "muted"))
            lay.addStretch()

    def _cpu(self, lay):
        d, cid = self.data["d"], self.data["id"]
        cpu = (d.get("cpu") or [{}])[0]
        name = (cpu.get("Name") or "").strip()
        head = Card(hero=True)
        vend = "AMD" if cid.vendor == "amd" else "Intel" if cid.vendor == "intel" else ""
        head.lay.addWidget(label(f"<span style='color:{C['accent2']}'>{vend}</span><br>"
                                 f"<span style='font-size:15pt'><b>{html.escape(name)}</b></span><br>"
                                 f"<span style='color:{C['muted']}'>"
                                 f"{' · '.join(x for x in (cid.codename, cid.arch) if x)}</span>", rich=True))
        lay.addWidget(head)
        g = QGridLayout()
        g.setSpacing(12)
        rows = [
            ("Codinome", cid.codename), ("Arquitetura", cid.arch), ("Soquete", cpu.get("SocketDesignation")),
            ("Família", cpuinfo.family_text(cid.family) if cid.family else ""),
            ("Modelo", cpuinfo.model_text(cid.model) if cid.family else ""),
            ("Stepping", str(cid.stepping) if cid.family else ""),
            ("Núcleos", f"{cpu.get('NumberOfCores')} {tr('núcleos')} / {cpu.get('NumberOfLogicalProcessors')} threads"),
            ("Clock base", f"{cpu.get('MaxClockSpeed')} MHz" if cpu.get("MaxClockSpeed") else ""),
            ("Tecnologia", cid.process), ("TDP (especificação)", f"{cid.tdp} W" if cid.tdp else ""),
            ("Microcódigo", f"0x{cid.microcode:X}" if cid.microcode else ""),
            ("Instruções", ", ".join(cid.features)),
            ("Virtualização", {True: tr("Ativada na BIOS"), False: tr("Desativada na BIOS")}.get(
                cpu.get("VirtualizationFirmwareEnabled"))),
        ]
        g.addWidget(_box("Processador", rows), 0, 0)
        self.live_cpu = label("", rich=True)
        lc = Card()
        lc.lay.addWidget(label("Clocks (ao vivo)", "h3"))
        lc.lay.addWidget(self.live_cpu)
        g.addWidget(lc, 0, 1, Qt.AlignTop)
        g.setColumnStretch(0, 3)
        g.setColumnStretch(1, 2)
        lay.addLayout(g)
        self._tick()

    def _caches(self, lay):
        rows = cpuinfo.cache_rows(self.data["caches"])
        if not rows:
            cpu = (self.data["d"].get("cpu") or [{}])[0]
            rows = [("L2", f"{(cpu.get('L2CacheSize') or 0) // 1024} MB"),
                    ("L3", f"{(cpu.get('L3CacheSize') or 0) // 1024} MB")]
        c = _box("Memória cache do processador", rows)
        c.lay.addWidget(label("L1 e L2 são de cada núcleo; o L3 é compartilhado (no X3D inclui o 3D V-Cache).",
                              "muted"))
        lay.addWidget(c)

    def _board(self, lay):
        d = self.data["d"]
        b, bios, os_ = d.get("board") or {}, d.get("bios") or {}, d.get("os") or {}
        g = QGridLayout()
        g.setSpacing(12)
        g.addWidget(_box("Placa-mãe", [("Fabricante", b.get("Manufacturer")), ("Modelo", b.get("Product")),
                                       ("Chipset", hwinfo.chipset(b.get("Product", ""))),
                                       ("Revisão", b.get("Version"))]), 0, 0)
        tpm = d.get("tpm") or {}
        g.addWidget(_box("BIOS", [("Fabricante", bios.get("Manufacturer")), ("Versão", bios.get("SMBIOSBIOSVersion")),
                                  ("Data", bios.get("Date")), ("Firmware", d.get("firmware")),
                                  ("Microcódigo da CPU", f"0x{self.data['id'].microcode:X}"
                                   if self.data["id"].microcode else ""),
                                  ("Secure Boot", {True: tr("ligado"), False: tr("desligado")}.get(d.get("secureboot"))),
                                  ("TPM", tr("pronto") if tpm.get("ready") else tr("ausente/desligado") if tpm else "")]),
                    0, 1)
        g.addWidget(_box("Sistema", [("Windows", os_.get("Caption")),
                                     ("Versão", f"{os_.get('Version', '')} ({os_.get('OSArchitecture', '')})"),
                                     ("Instalado em", os_.get("Installed")),
                                     ("Antivírus", ", ".join(a.get("displayName", "") for a in d.get("av", [])))]),
                    1, 0, 1, 2)
        lay.addLayout(g)

    def _mem(self, lay):
        rs = self.data["rs"]
        if not rs:
            lay.addWidget(label("O Windows não informou os pentes de memória.", "muted"))
            return
        import psutil
        vm = psutil.virtual_memory()
        lay.addWidget(_box("Memória", [
            ("Total", f"{rs['total_gb']:.0f} GB {rs['kind']}"),
            ("Em uso agora", f"{human_size(vm.used)} ({vm.percent:.0f}%) · {human_size(vm.available)} "
                             f"{tr('livre')}"),
            ("Velocidade", f"{rs['running']} MT/s ({tr('nominal')} {rs['rated']} MT/s)"),
            ("XMP / EXPO", f"<span style='color:{C['bad']}'>{tr('desligado na BIOS')}</span>" if rs["xmp_off"] else
             f"<span style='color:{C['ok']}'>{tr('ativado')}</span>" if rs.get("xmp_on") else tr("na velocidade nominal")),
            ("Canais", (tr("dual channel") if rs["dual"] else tr("single channel") if rs["count"] == 1 else
                        tr("verifique os slots")) + (f" ({', '.join(rs['channels'])})" if rs["channels"] else "")),
            ("Pentes", f"{rs['count']} de {rs['slots'] or '?'} {tr('slots ocupados')}"),
            ("Pentes iguais", tr("sim") if rs["same_model"] else tr("não")),
        ]))

    def _slots(self, lay):
        rs = self.data["rs"]
        sticks = rs.get("sticks", []) if rs else []
        g = QGridLayout()
        g.setSpacing(12)
        for i, s in enumerate(sticks):
            v = s.get("ConfiguredVoltage")
            g.addWidget(_box(f"{s.get('DeviceLocator') or tr('Slot')} · {s.get('BankLabel') or ''}".strip(" ·"), [
                ("Tamanho", human_size(int(s.get("Capacity") or 0))),
                ("Fabricante", (s.get("Manufacturer") or "").strip()),
                ("Modelo", (s.get("PartNumber") or "").strip()),
                ("Velocidade", f"{s.get('ConfiguredClockSpeed') or s.get('Speed')} MT/s "
                               f"({tr('nominal')} {s.get('Speed')})"),
                ("Tensão", f"{int(v) / 1000:.2f} V" if v else ""),
            ]), i // 2, i % 2)
        empty = (rs.get("slots") or 0) - len(sticks) if rs else 0
        for j in range(max(0, empty)):
            k = len(sticks) + j
            c = Card()
            c.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            c.lay.addWidget(label("Slot vazio", "h3"))
            c.lay.addWidget(label("Sem pente de memória neste encaixe.", "muted"))
            g.addWidget(c, k // 2, k % 2)
        lay.addLayout(g)

    def _gpu(self, lay):
        d, nv, mons = self.data["d"], self.data["nv"], self.data["mons"]
        prim = next((m for m in mons if m.get("primary")), None)
        for v in d.get("gpu", []):
            nm = (v.get("Name") or "").strip()
            is_nv = bool(nv.get("name")) and nv["name"] in nm
            rows = [("Fabricante", hwinfo.gpu_vendor(v)), ("Fabricante da placa", hwinfo.board_vendor(v.get("PNPDeviceID")))]
            vram = hwinfo.vram_bytes(d, v)
            if is_nv:
                rows += [("Arquitetura", nv.get("arch")), ("Tecnologia", nv.get("process")),
                         ("Núcleos CUDA", f"{nv['cores']:,}".replace(",", ".") if nv.get("cores") else ""),
                         ("TDP", f"{nv['tdp_w']} W" if nv.get("tdp_w") else ""),
                         ("Memória dedicada", human_size(nv.get("vram_total") or vram)),
                         ("Tipo de memória", nv.get("memtype")),
                         ("Barramento", f"{nv['bus_bits']} bits" if nv.get("bus_bits") else ""),
                         ("Clocks máximos", f"{tr('núcleo')} {nv['max_clock']} MHz · {tr('memória')} "
                                            f"{nv['max_mem_clock']} MHz" if nv.get("max_clock") else ""),
                         ("VBIOS", nv.get("vbios"))]
            else:
                rows += [("Chip", v.get("VideoProcessor")), ("Memória dedicada", human_size(vram) if vram else "")]
            rows += [("Driver", f"{v.get('DriverVersion', '')}" + (f" ({v['DriverDate']})" if v.get("DriverDate") else "")),
                     ("Interface", f"PCIe {nv.get('pcie_gen_max') or nv.get('pcie_gen')}.0 x{nv.get('pcie_width')}"
                      if is_nv and nv.get("pcie_width") else "")]
            if prim and (is_nv or len(d.get("gpu", [])) == 1):
                rows.append(("Monitor principal", f"{prim['width']}×{prim['height']} a {prim['hz']} Hz"))
            lay.addWidget(_box(nm, rows))
        if nv.get("name"):
            c = Card()
            c.lay.addWidget(label("Ao vivo", "h3"))
            self.live_gpu = label("", rich=True)
            c.lay.addWidget(self.live_gpu)
            lay.addWidget(c)

    def _disks(self, lay):
        g = QGridLayout()
        g.setSpacing(12)
        for i, x in enumerate(self.data["d"].get("disks", [])):
            temp, wear, hours = x.get("Temperature"), x.get("Wear"), x.get("PowerOnHours")
            g.addWidget(_box((x.get("FriendlyName") or tr("Disco")).strip(), [
                ("Tipo", " · ".join(str(v) for v in (x.get("MediaType"), x.get("BusType")) if v and v != "Unspecified")),
                ("Tamanho", human_size(int(x.get("Size") or 0))),
                ("Saúde", tr("saudável") if str(x.get("HealthStatus")).lower() == "healthy" else x.get("HealthStatus")),
                ("Temperatura", f"{temp} °C" if temp else ""),
                ("Desgaste", f"{wear}%" if wear not in (None, "") else ""),
                ("Horas ligado", f"{hours} h" if hours else ""),
            ]), i // 2, i % 2)
        lay.addLayout(g)

    def _check(self, lay):
        items = hwcheck.run(self.data["d"], self.data["rs"], self.data["nv"])
        c = Card()
        bad = sum(1 for i in items if i.level != hwcheck.OK)
        c.lay.addWidget(label("Check-up do hardware", "h2"))
        c.lay.addWidget(label(tr("Tudo certo: {} itens verificados sem problemas.").replace("{}", str(len(items)))
                              if not bad else tr("{} de {} itens pedem atenção.").replace("{}", str(bad), 1)
                              .replace("{}", str(len(items)), 1), "muted"))
        col = {hwcheck.OK: C["ok"], hwcheck.WARN: C["warn"], hwcheck.BAD: C["bad"]}
        for it in items:
            row = hrow(label(f"<span style='color:{col[it.level]}'>●</span>&nbsp; <b>{html.escape(tr(it.title))}</b>"
                             f"<br><span style='color:{C['muted']}'>{html.escape(tr(it.detail))}</span>", rich=True),
                       pill(tr(it.area).upper()), stretch_first=True)
            c.lay.addLayout(row)
        c.lay.addWidget(label("Baseado no que o Windows informa sobre a placa-mãe e os componentes (SMBIOS). Nada é "
                              "alterado: mudanças de slot e de BIOS são feitas por você.", "muted"))
        lay.addWidget(c)
        self._check_items = items

    # ---------------------------------------------------------------- ao vivo
    def _tick(self):
        if not self.isVisible() or not self.data:
            return
        run_async(self._read_live, on_done=self._paint_live)

    @staticmethod
    def _read_live():
        return cpuinfo.live_clocks(), gpu.read() if gpu.available() else {}

    def _paint_live(self, r):
        cl, g = r
        try:
            if self.live_cpu and cl:
                self.live_cpu.setText(kv([("Clock médio", f"{cl['avg']:.0f} MHz"),
                                          ("Núcleo mais rápido", f"{cl['max']:.0f} MHz"),
                                          ("Multiplicador aprox.", f"× {cl['mult']:.1f} ({tr('base de 100 MHz')})")]))
            if self.live_gpu and g:
                lim = self.data["nv"].get("limit_w") or self.data["nv"].get("tdp_w")
                self.live_gpu.setText(kv([
                    ("Clock do núcleo", f"{g['clock']} MHz" if g.get("clock") else ""),
                    ("Temperatura", f"{g['temp']} °C" if g.get("temp") is not None else ""),
                    ("Clock da memória", f"{g['mem_clock']} MHz" if g.get("mem_clock") else ""),
                    ("Ventoinha", (f"{g['fan']}%" if g["fan"] else tr("0 RPM (parada)")) if g.get("fan") is not None
                     else ""),
                    ("Energia", f"{g['power_w']:.0f} W" + (f" ({g['power_w'] / lim * 100:.0f}% {tr('do limite')})"
                                                          if lim else "") if g.get("power_w") is not None else ""),
                    ("Uso", f"{g['util']}%" if g.get("util") is not None else ""),
                ]))
        except RuntimeError:          # a tela foi fechada no meio da leitura
            pass

    # ---------------------------------------------------------------- copiar / exportar
    def _report(self) -> str:
        out = [f"{time.strftime('%d/%m/%Y %H:%M')}", self._text, ""]
        for i, name in enumerate(TABS):
            out.append(f"== {tr(name)} ==")
            lay = self.tab_lay[i]
            for k in range(lay.count()):
                w = lay.itemAt(k).widget()
                for lb in (w.findChildren(type(self.prof)) if w else []):
                    t = re.sub(r"</tr>", "\n", lb.text())
                    t = re.sub(r"</td><td>", ": ", t)
                    t = html.unescape(re.sub(r"<[^>]+>", " ", t.replace("<br>", "\n")))
                    t = "\n".join(re.sub(r"\s+", " ", x).strip() for x in t.splitlines() if x.strip())
                    if t:
                        out.append(t)
            out.append("")
        return "\n".join(out)

    def _copy(self):
        from PySide6.QtGui import QGuiApplication

        from lolitos import APP_NAME, VERSION
        QGuiApplication.clipboard().setText(f"{APP_NAME} {VERSION} — {tr('meu PC')}\n" + self._report())
        info(self, "Copiado", "Configuração copiada. Agora é só colar (WhatsApp, Discord, fórum).")

    def _export(self):
        from lolitos import APP_NAME, VERSION
        path, _ = QFileDialog.getSaveFileName(self, tr("Exportar relatório"), f"MeuPC-{time.strftime('%Y%m%d')}.txt",
                                              "Texto (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{APP_NAME} {VERSION} — {tr('relatório do PC')}\n" + self._report())
        info(self, "Exportar relatório", tr("Relatório salvo em {}").replace("{}", path))
