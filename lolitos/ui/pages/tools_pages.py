"""Ferramentas: teste do mouse, teste de monitor, teste de velocidade, perda de pacotes e check-up."""
from __future__ import annotations

import csv
import json
import platform
import threading
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QInputDialog,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from lolitos import APP_NAME, VERSION
from lolitos.core import settings
from lolitos.core.system import data_dir
from lolitos.modules import checkup, netdiag, repair, speedtest
from lolitos.ui.theme import C
from lolitos.ui.widgets import Badge, Card, Page, TaskDialog, button, hrow, info, label, run_async


# ===================================================================== teste do mouse
class MouseTestPage(Page):
    title = "Teste do mouse"
    subtitle = ("Mede o polling rate: quantas vezes por segundo o mouse informa a posição ao PC. "
                "1000 Hz = resposta a cada 1 ms, o ideal para jogos.")

    def build(self):
        from lolitos.ui.tests import MousePad, mouse_verdict
        self.verdict = mouse_verdict
        self.out = label("Faça círculos rápidos e contínuos na área abaixo por uns 5 segundos. "
                         "Movimento em linha reta mede o seu braço, não o mouse.", "muted")
        self.big = label("— Hz", "big")
        self.badge = Badge("loading")
        self.badge.set("unknown")
        self.badge.setFixedHeight(26)
        top = Card(hero=True)
        top.lay.addLayout(hrow(self.big, self.badge, None))
        top.lay.addWidget(self.out)
        self.body.addWidget(top)
        self.pad = MousePad(self._upd)
        self.body.addWidget(self.pad)
        self.body.addLayout(hrow(button("Zerar", on_click=self._reset), None))

    def _upd(self, hz, best):
        st, txt = self.verdict(best)
        self.big.setText(f"{best:.0f} Hz")
        self.badge.set(st)
        self.out.setText(f"Agora: {hz:.0f} Hz · pico estável: {best:.0f} Hz. {txt}")

    def _reset(self):
        self.pad.reset()
        self.big.setText("— Hz")
        self.badge.set("unknown")


# ===================================================================== teste de monitor
class MonitorTestPage(Page):
    title = "Teste de monitor"
    subtitle = ("Testes locais em tela cheia — nenhum site é aberto. Use no monitor onde você joga, com o brilho "
                "como você usa no dia a dia.")

    def build(self):
        grid = QGridLayout()
        grid.setSpacing(10)
        items = [
            ("Teste de movimento (ghosting e taxas de quadros)", "motion",
             "Objeto em movimento com faixas de quadros cheios, 1/2 e 1/4: veja ghosting, borrão e suavidade, com "
             "quadros por segundo, pixels por quadro e pixels por segundo. Troque objeto (O), fundo (B), cores (K) "
             "e quantidade (N)."),
            ("Cores e pixels", "colors",
             "Cores sólidas para pixels mortos ou travados e uniformidade, degradê para faixas (banding) e degraus "
             "de preto para ver esmagamento nos tons escuros."),
            ("Teste de OLED e vazamento de luz", "oled",
             "Preto total para achar clarões nos cantos (backlight bleed), IPS glow e manchas, e cinzas para "
             "retenção/burn-in. Faça no escuro, com o brilho no máximo."),
        ]
        for i, (t, mode, d) in enumerate(items):
            c = Card(hero=mode == "motion")
            c.lay.addWidget(label(f"<b>{t}</b>", rich=True))
            c.lay.addWidget(label(d, "muted"))
            c.lay.addLayout(hrow(button("Iniciar em tela cheia", "primary", lambda _=False, m=mode: self._go(m)),
                                 None))
            grid.addWidget(c, i, 0)
        self.body.addLayout(grid)
        how = Card()
        how.lay.addWidget(label("Como ler o resultado", "h2"))
        how.lay.addWidget(label(
            "<b>Siga o objeto com os olhos</b>: um rastro escuro atrás dele é ghosting (painel lento); um contorno "
            "claro ou colorido é overshoot (overdrive forte demais) — mais visível no fundo cinza 50%.<br>"
            "<b>Quadros/s igual ao Hz do monitor</b>: o teste está sincronizado. Se ficar abaixo, coloque o monitor "
            "na taxa máxima (GPU › Monitor na taxa de atualização máxima) ou feche programas pesados.<br>"
            "<b>Pixels por quadro</b> = velocidade ÷ quadros por segundo. Quanto menor, mais suave.", rich=True))
        self.body.addWidget(how)

    def _go(self, mode):
        from lolitos.ui.tests import MonitorTest
        self._mt = MonitorTest(mode)
        scr = self.screen() or QGuiApplication.primaryScreen()
        self._mt.setGeometry(scr.geometry())
        self._mt.showFullScreen()


# ===================================================================== velocidade
def _hist_file():
    return data_dir() / "velocidade.json"


class SpeedTestPage(Page):
    title = "Teste de velocidade"
    subtitle = ("Mede download, upload, ping, variação (jitter) e o ping com a conexão carregada, usando os servidores "
                "públicos de teste da Cloudflare mais próximos. Pause downloads e streaming para um resultado fiel.")

    def build(self):
        c = Card(hero=True)
        self.btn = button("INICIAR", "primary", self._run)
        self.btn.setMinimumHeight(44)
        self.btn.setMinimumWidth(180)
        c.lay.addLayout(hrow(self.btn, None))
        grid = QGridLayout()
        self.vals = {}
        for i, (k, name) in enumerate([("down", "DOWNLOAD"), ("up", "UPLOAD"), ("ping", "PING"),
                                       ("jitter", "VARIAÇÃO"), ("loaded", "PING SOB CARGA")]):
            box = QVBoxLayout()
            box.addWidget(label(name, "muted"))
            v = label("—", "h1")
            box.addWidget(v)
            self.vals[k] = v
            grid.addLayout(box, 0, i)
        c.lay.addLayout(grid)
        self.out = label("O teste dura cerca de 25 segundos e usa bastante banda nesse tempo.", "muted", rich=True)
        c.lay.addWidget(self.out)
        self.body.addWidget(c)
        self.body.addWidget(label("Resultados anteriores", "h2"))
        self.hist = label("", "muted", rich=True)
        self.body.addWidget(self.hist)
        self.body.addWidget(label("Servidores de teste: Cloudflare (speed.cloudflare.com). O app não guarda nem envia "
                                  "seus resultados; o histórico fica só neste PC.", "muted"))
        self._show_hist()

    def _load(self):
        try:
            return json.loads(_hist_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _show_hist(self):
        rows = self._load()[-8:][::-1]
        self.hist.setText("<br>".join(
            f"{time.strftime('%d/%m %H:%M', time.localtime(r['time']))} — ↓ {r['down']:.0f} Mbps · ↑ {r['up']:.0f} "
            f"Mbps · ping {r['ping']:.0f} ms · sob carga {r['loaded']:.0f} ms" for r in rows) or "Nenhum teste feito ainda.")

    def _run(self):
        self.btn.setEnabled(False)
        self.btn.setText("MEDINDO…")
        for v in self.vals.values():
            v.setText("—")

        def work(progress=None):
            return speedtest.full_test(lambda s, v=0: progress(f"{s}|{v}"))

        def prog(s):
            st, v = s.split("|")
            v = float(v)
            if st in ("download", "upload") and v:
                self.vals["down" if st == "download" else "up"].setText(f"{v:.0f} Mbps")
            self.out.setText({"ping": "Medindo o ping…", "download": "Download…", "upload": "Upload…",
                              "loaded": "Ping com a linha cheia…"}[st])

        def done(r):
            self.btn.setEnabled(True)
            self.btn.setText("TESTAR DE NOVO")
            self.vals["down"].setText(f"{r['down']:.0f} Mbps")
            self.vals["up"].setText(f"{r['up']:.0f} Mbps")
            self.vals["ping"].setText(f"{r['ping']:.0f} ms")
            self.vals["jitter"].setText(f"{r['jitter']:.1f} ms")
            self.vals["loaded"].setText(f"{r['loaded']:.0f} ms")
            bb = r["bufferbloat"]
            txt = (f"<span style='color:{C['warn']}'>O ping sobe {bb:.0f} ms com a linha cheia (bufferbloat): ative "
                   "QoS/SQM no roteador se puder.</span>" if bb > 30 else
                   f"<span style='color:{C['ok']}'>Sem bufferbloat relevante: ping estável mesmo com a linha cheia."
                   "</span>")
            ping_txt = ("ping excelente para jogos competitivos" if r["ping"] < 20 else
                        "ping bom para jogos" if r["ping"] < 50 else "ping alto para jogos competitivos")
            self.out.setText(f"{txt}<br>{ping_txt.capitalize()} · servidor Cloudflare {r['colo']}")
            rows = self._load() + [r]
            try:
                _hist_file().write_text(json.dumps(rows[-50:]), encoding="utf-8")
            except OSError:
                pass
            self._show_hist()

        def err(e):
            self.btn.setEnabled(True)
            self.btn.setText("INICIAR")
            self.out.setText(f"Não foi possível concluir o teste: {e}. Verifique a conexão com a internet.")
        run_async(work, on_done=done, on_progress=prog, on_error=err)


# ===================================================================== perda de pacotes
TARGETS = [("Cloudflare (1.1.1.1)", "1.1.1.1"), ("Google (8.8.8.8)", "8.8.8.8"),
           ("Meu roteador (rede local)", "gateway"), ("Outro endereço (IP ou site)…", "custom")]


class Timeline(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(28)
        self.items: list[str] = []

    def set(self, items):
        self.items = items
        self.update()

    def paintEvent(self, _):
        if not self.items:
            return
        p = QPainter(self)
        w = self.width() / max(1, len(self.items))
        colors = {"ok": QColor(C["info"]), "late": QColor(C["warn"]), "lost": QColor(C["bad"])}
        for i, s in enumerate(self.items):
            p.fillRect(int(i * w), 0, max(1, int(w + 0.5)), self.height(), colors[s])


class PacketLossPage(Page):
    title = "Perda de pacotes"
    subtitle = ("Envia pacotes pequenos no mesmo ritmo de um jogo ou chamada e mede quantos se perdem, quantos chegam "
                "atrasados, a latência e a variação. Depois mostra em que ponto da rota a perda começa.")

    def build(self):
        c = Card(hero=True)
        self.target = QComboBox()
        for name, val in TARGETS:
            self.target.addItem(name, val)
        self.long = QCheckBox("Teste longo (2 minutos)")
        self.btn = button("INICIAR", "primary", self._loss)
        self.route_btn = button("Analisar rota", on_click=self._route)
        self.csv_btn = button("Exportar CSV", on_click=self._csv)
        self.csv_btn.setEnabled(False)
        c.lay.addLayout(hrow(self.target, self.long, self.btn, self.route_btn, self.csv_btn, None))
        self.timeline = Timeline()
        c.lay.addWidget(self.timeline)
        c.lay.addWidget(label("pacotes ao longo do teste · azul = ok · amarelo = atrasado · vermelho = perdido",
                              "muted"))
        self.out = label("", rich=True)
        c.lay.addWidget(self.out)
        self.body.addWidget(c)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Salto", "Endereço", "Perda", "Média", "Nome"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setVisible(False)
        self.table.setMinimumHeight(300)
        self.body.addWidget(self.table)
        self.body.addWidget(label("Os pacotes são pings (ICMP) enviados pelo próprio Windows; nada passa por servidores "
                                  "do app. Perda que aparece num salto e continua até o fim é real; perda só num salto "
                                  "do meio é o roteador ignorando ping, o que é normal.", "muted"))
        rp = Card()
        rp.lay.addWidget(label("<b>Reparos rápidos de rede</b>", rich=True))
        row = []
        for tid in ("flushdns", "renew_ip", "reset_net"):
            t = repair.TOOLS_BY_ID[tid]
            row.append(button(t.name, on_click=lambda _=False, tt=t: TaskDialog(
                self, tt.name, repair.run_tool, tt, intro=f"Comando: {tt.cmd}").exec(), tip=t.desc))
        rp.lay.addLayout(hrow(*row, None))
        self.body.addWidget(rp)
        self.last = None

    def _resolve(self):
        v = self.target.currentData()
        if v == "gateway":
            gw = netdiag.default_gateway()
            if not gw:
                info(self, "Perda de pacotes", "Não encontrei o roteador da conexão ativa.")
            return gw
        if v == "custom":
            txt, ok = QInputDialog.getText(self, "Destino", "IP do servidor do jogo ou site, ex.: 8.8.4.4",
                                           text=settings.get("ping_target") or "")
            if not ok or not txt.strip():
                return None
            settings.set("ping_target", txt.strip())
            return txt.strip()
        return v

    def _loss(self):
        tgt = self._resolve()
        if not tgt:
            return
        secs = 120 if self.long.isChecked() else 30
        self.btn.setEnabled(False)
        self.btn.setText("MEDINDO…")
        self.table.setVisible(False)
        self.stop = threading.Event()

        def work(progress=None):
            return netdiag.packet_loss(tgt, seconds=secs, on_tick=lambda r: progress(r), stop=self.stop)

        def tick(r):
            self.timeline.set(list(r.timeline))
            self.out.setText(f"{r.sent} enviados · perda {r.loss_pct:.1f}% · média {r.avg:.0f} ms")

        def done(r):
            self.last = r
            self.csv_btn.setEnabled(True)
            self.btn.setEnabled(True)
            self.btn.setText("TESTAR DE NOVO")
            self.timeline.set(list(r.timeline))
            kind, txt = r.verdict()
            col = {"otimo": C["ok"], "bom": C["ok"], "atencao": C["warn"]}.get(kind, C["bad"])
            wifi = ""
            try:
                from lolitos.modules.pcprofile import detect
                if detect().wifi:
                    wifi = "<br>Você tem Wi-Fi: teste também com cabo — o Wi-Fi é a causa mais comum de perda."
            except Exception:  # noqa: BLE001
                pass
            self.out.setText(f"<b>{r.target}</b> ({r.ip}) · {r.sent} pacotes · <b>perda {r.loss_pct:.1f}%</b> · "
                             f"atrasados {r.late} · média {r.avg:.0f} ms · variação {r.jitter:.1f} ms<br>"
                             f"<span style='color:{col}'>{txt}</span>{wifi}")

        def err(e):
            self.btn.setEnabled(True)
            self.btn.setText("INICIAR")
            self.out.setText(f"Não foi possível testar: {e}")
        run_async(work, on_done=done, on_progress=tick, on_error=err)

    def _route(self):
        tgt = self._resolve()
        if not tgt:
            return
        self.route_btn.setEnabled(False)
        self.out.setText(f"Descobrindo cada roteador até {tgt} e testando todos ao mesmo tempo (cerca de 30 s)…")

        def done(r):
            ip, hops, diag = r
            self.route_btn.setEnabled(True)
            self.table.setVisible(True)
            self.table.setRowCount(len(hops))
            for i, h in enumerate(hops):
                vals = [str(h.n), h.ip, f"{h.loss_pct:.0f}%" if h.sent else "—",
                        f"{h.avg:.0f} ms" if h.rtts else "—", h.name]
                for j, v in enumerate(vals):
                    it = QTableWidgetItem(v)
                    if j == 2 and h.sent and h.loss_pct >= 2:
                        it.setForeground(QColor(C["bad"]))
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(i, j, it)
            self.table.resizeColumnsToContents()
            self.out.setText(f"<b>{tgt}</b> ({ip}) — {diag}")
        run_async(netdiag.analyze_route, tgt, on_done=done,
                  on_error=lambda e: (self.route_btn.setEnabled(True), self.out.setText(f"Falhou: {e}")))

    def _csv(self):
        r = self.last
        if not r:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar resultado",
                                              time.strftime("Perda de pacotes %Y-%m-%d %H-%M.csv"), "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["destino", "ip", "enviados", "perdidos", "atrasados", "perda_%", "media_ms", "jitter_ms"])
            w.writerow([r.target, r.ip, r.sent, r.lost, r.late, f"{r.loss_pct:.2f}", f"{r.avg:.1f}",
                        f"{r.jitter:.1f}"])
            w.writerow([])
            w.writerow(["pacote", "estado"])
            for i, s in enumerate(r.timeline, 1):
                w.writerow([i, s])
        info(self, "Exportar", f"Resultado salvo em {path}")


# ===================================================================== check-up
from lolitos.ui.pages.dashboard import FIX_PAGE  # noqa: E402

class CheckupPage(Page):
    title = "Check-up"
    subtitle = "Cada item é medido e comparado com um limite. Nada é alterado sem você pedir."


    def build(self):
        self.summary = label("Clique em Executar check-up para analisar o PC.", "muted")
        self.body.addLayout(hrow(button("Executar check-up", "primary", self.run_check),
                                 button("Exportar relatório…", on_click=self._export),
                                 button("Copiar minha configuração", on_click=self._copy), None))
        self.body.addWidget(self.summary)
        self.box = QVBoxLayout()
        self.box.setSpacing(8)
        self.body.addLayout(self.box)
        self.checks = []
        self.run_check()

    def run_check(self):
        self.summary.setText("Analisando o PC…")
        run_async(checkup.run_checkup, on_done=self._show)

    def _show(self, checks):
        self.checks = checks
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        n = {s: sum(1 for c in checks if c.state == s) for s in ("ok", "atencao", "corrigir")}
        self.summary.setText(f"{n['ok']} itens corretos · {n['atencao']} atenção · {n['corrigir']} a corrigir.")
        order = {"corrigir": 0, "atencao": 1, "ok": 2}
        for c in sorted(checks, key=lambda c: order[c.state]):
            card = Card()
            row = QHBoxLayout()
            col = QVBoxLayout()
            col.addWidget(label(f"<b>{c.title}</b>", rich=True))
            col.addWidget(label(c.detail, "muted"))
            row.addLayout(col, 1)
            row.addWidget(Badge(c.state))
            if c.state != "ok" and c.fix in FIX_PAGE and self.main:
                row.addWidget(button("Corrigir", on_click=lambda _=False, p=FIX_PAGE[c.fix]: self.main.go(p)))
            elif c.state != "ok" and c.fix == "relaunch_admin" and self.main:
                from lolitos.core.system import relaunch_as_admin
                row.addWidget(button("Abrir como admin", on_click=lambda: relaunch_as_admin() and self.main.quit()))
            card.lay.addLayout(row)
            self.box.addWidget(card)

    def _report(self) -> str:
        from lolitos.modules import pcprofile
        p = pcprofile.detect()
        lines = [f"{APP_NAME} {VERSION} — relatório do PC", time.strftime("%d/%m/%Y %H:%M"), "",
                 f"Perfil: {p.tier_name}", *p.summary(), f"Windows: {platform.platform()}", "", "Check-up:"]
        for c in self.checks:
            lines.append(f"[{c.state.upper()}] {c.title}: {c.detail}")
        return "\n".join(lines)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar relatório", "Meu PC - Lolitos Control.txt",
                                              "Texto (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._report())
            info(self, "Relatório", f"Relatório salvo em {path}")

    def _copy(self):
        QGuiApplication.clipboard().setText(self._report())
        info(self, "Copiado", "Configuração copiada. Agora é só colar (WhatsApp, Discord, fórum).")
