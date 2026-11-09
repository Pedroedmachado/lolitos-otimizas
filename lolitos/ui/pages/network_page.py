"""Rede: teste de velocidade, perda de pacotes, análise de rota e reparos rápidos."""
import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QComboBox, QTableWidget, QTableWidgetItem, QWidget

from lolitos.core import settings
from lolitos.modules import netdiag, repair, speedtest
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, TaskDialog, button, hrow, label, run_async

TARGETS = [("Cloudflare (1.1.1.1)", "1.1.1.1"), ("Google (8.8.8.8)", "8.8.8.8"),
           ("Meu roteador", "gateway"), ("Outro IP ou site…", "custom")]


class Timeline(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(26)
        self.items = []

    def set(self, items):
        self.items = items
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if not self.items:
            return
        w = self.width() / max(1, len(self.items))
        colors = {"ok": QColor(C["info"]), "late": QColor(C["warn"]), "lost": QColor(C["bad"])}
        for i, s in enumerate(self.items):
            p.fillRect(int(i * w), 0, max(1, int(w + 0.5)), self.height(), colors[s])


class NetworkPage(Page):
    title = "Rede"
    subtitle = "Meça a conexão, encontre perda de pacotes e veja em que ponto da rota ela começa."

    def build(self):
        # velocidade
        sp = Card()
        sp.lay.addWidget(label("<b>Teste de velocidade</b> — servidores públicos da Cloudflare mais próximos. "
                               "Pause downloads e streaming antes.", rich=True))
        self.sp_out = label("", rich=True)
        self.sp_btn = button("Iniciar teste", "primary", self._speed)
        sp.lay.addLayout(hrow(self.sp_btn, None))
        sp.lay.addWidget(self.sp_out)
        self.body.addWidget(sp)

        # perda de pacotes
        pl = Card()
        pl.lay.addWidget(label("<b>Perda de pacotes</b> — 20 pacotes/s por 30 s, no ritmo de um jogo. "
                               "No Wi-Fi, teste também com cabo.", rich=True))
        self.target = QComboBox()
        for name, val in TARGETS:
            self.target.addItem(name, val)
        self.custom = None
        self.pl_btn = button("Medir perda", "primary", self._loss)
        self.route_btn = button("Analisar rota", on_click=self._route)
        pl.lay.addLayout(hrow(self.target, self.pl_btn, self.route_btn, None))
        self.timeline = Timeline()
        pl.lay.addWidget(self.timeline)
        self.pl_out = label("", rich=True)
        pl.lay.addWidget(self.pl_out)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Salto", "Endereço", "Perda", "Média", "Nome"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setVisible(False)
        self.table.setMinimumHeight(260)
        pl.lay.addWidget(self.table)
        self.body.addWidget(pl)

        # reparos
        rp = Card()
        rp.lay.addWidget(label("<b>Reparos rápidos de rede</b>", rich=True))
        row = []
        for tid in ("flushdns", "renew_ip", "reset_net"):
            t = repair.TOOLS_BY_ID[tid]
            row.append(button(t.name, on_click=lambda _=False, tt=t: TaskDialog(
                self, tt.name, repair.run_tool, tt, intro=f"Comando: {tt.cmd}").exec(), tip=t.desc))
        rp.lay.addLayout(hrow(*row, None))
        self.body.addWidget(rp)

    def _resolve_target(self):
        from PySide6.QtWidgets import QInputDialog
        v = self.target.currentData()
        if v == "gateway":
            return netdiag.default_gateway()
        if v == "custom":
            txt, ok = QInputDialog.getText(self, "Destino", "IP ou endereço (ex.: o IP do servidor do BDO):",
                                           text=settings.get("ping_target") or "")
            if not ok or not txt.strip():
                return None
            settings.set("ping_target", txt.strip())
            return txt.strip()
        return v

    def _speed(self):
        self.sp_btn.setEnabled(False)
        stages = {"ping": "Medindo ping…", "download": "Download", "upload": "Upload", "loaded": "Ping com a linha cheia…"}

        def prog(stage, v=0):
            txt = stages[stage] + (f": {v:.0f} Mbps" if v else "")
            self.sp_out.setText(txt)

        def work(progress=None):
            return speedtest.full_test(lambda s, v=0: progress(f"{s}|{v}"))

        def on_prog(s):
            st, v = s.split("|")
            prog(st, float(v))

        def done(r):
            self.sp_btn.setEnabled(True)
            bb = r["bufferbloat"]
            bbtxt = (f"<span style='color:{C['warn']}'>o ping sobe {bb:.0f} ms com a linha cheia (bufferbloat): "
                     "ative QoS/SQM no roteador se puder</span>" if bb > 30 else
                     f"<span style='color:{C['ok']}'>sem bufferbloat relevante</span>")
            self.sp_out.setText(f"<b>Download</b> {r['down']:.0f} Mbps · <b>Upload</b> {r['up']:.0f} Mbps · "
                                f"<b>Ping</b> {r['ping']:.0f} ms · <b>Variação</b> {r['jitter']:.1f} ms · "
                                f"<b>Com carga</b> {r['loaded']:.0f} ms<br>{bbtxt}<br>"
                                f"<span style='color:{C['muted']}'>Servidor Cloudflare {r['colo']}</span>")
        run_async(work, on_done=done, on_progress=on_prog,
                  on_error=lambda e: (self.sp_btn.setEnabled(True), self.sp_out.setText(f"Falhou: {e}")))

    def _loss(self):
        tgt = self._resolve_target()
        if not tgt:
            return
        self.pl_btn.setEnabled(False)
        self.table.setVisible(False)
        self.stop = threading.Event()

        def work(progress=None):
            return netdiag.packet_loss(tgt, on_tick=lambda r: progress(r), stop=self.stop)

        def tick(r):
            self.timeline.set(list(r.timeline))
            self.pl_out.setText(f"{r.sent} enviados · perda {r.loss_pct:.1f}% · média {r.avg:.0f} ms")

        def done(r):
            self.pl_btn.setEnabled(True)
            self.timeline.set(list(r.timeline))
            kind, txt = r.verdict()
            col = {"otimo": C["ok"], "bom": C["ok"], "atencao": C["warn"]}.get(kind, C["bad"])
            self.pl_out.setText(f"<b>{r.target}</b> ({r.ip}) · {r.sent} pacotes · <b>perda {r.loss_pct:.1f}%</b> · "
                                f"atrasados {r.late} · média {r.avg:.0f} ms · variação {r.jitter:.1f} ms<br>"
                                f"<span style='color:{col}'>{txt}</span>")
        run_async(work, on_done=done, on_progress=tick,
                  on_error=lambda e: (self.pl_btn.setEnabled(True), self.pl_out.setText(f"Falhou: {e}")))

    def _route(self):
        tgt = self._resolve_target()
        if not tgt:
            return
        self.route_btn.setEnabled(False)
        self.pl_out.setText(f"Descobrindo a rota até {tgt} e testando cada salto (≈ 30 s)…")

        def done(r):
            ip, hops, diag = r
            self.route_btn.setEnabled(True)
            self.table.setVisible(True)
            self.table.setRowCount(len(hops))
            for i, h in enumerate(hops):
                vals = [str(h.n), h.ip, f"{h.loss_pct:.0f}%" if h.sent else "—", f"{h.avg:.0f} ms" if h.rtts else "—",
                        h.name]
                for j, v in enumerate(vals):
                    it = QTableWidgetItem(v)
                    if j == 2 and h.sent and h.loss_pct >= 2:
                        it.setForeground(QColor(C["bad"]))
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(i, j, it)
            self.table.resizeColumnsToContents()
            self.pl_out.setText(f"<b>{tgt}</b> ({ip}) — {diag}")
        run_async(netdiag.analyze_route, tgt, on_done=done,
                  on_error=lambda e: (self.route_btn.setEnabled(True), self.pl_out.setText(f"Falhou: {e}")))
