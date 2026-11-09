"""Ferramentas: teste do mouse, teste de monitor, teste de velocidade, perda de pacotes e check-up."""
from __future__ import annotations

import csv
import json
import platform
import threading
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import (QCheckBox, QLabel, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QInputDialog,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from lolitos import APP_NAME, VERSION
from lolitos.core import settings
from lolitos.core.system import data_dir
from lolitos.i18n import tr
from lolitos.modules import checkup, netdiag, repair, speedtest
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, TaskDialog, button, hrow, info, label, run_async


# ===================================================================== teste do mouse
class MouseTestPage(Page):
    title = "Teste do mouse"
    subtitle = ("Mede o polling rate: quantas vezes por segundo o mouse informa a posição ao PC. "
                "1000 Hz = resposta a cada 1 ms, o ideal para jogos.")

    def build(self):
        from lolitos.ui.tests import MousePad, mouse_verdict
        from lolitos.ui.widgets import StatTile
        self.verdict = mouse_verdict
        self.actions.addWidget(button("Zerar", on_click=lambda: self.pad.reset()))
        row = QHBoxLayout()
        row.setSpacing(12)
        self.t_now, self.t_max = StatTile("Atual", "0", "Hz"), StatTile("Máximo", "0", "Hz")
        self.t_resp, self.t_n = StatTile("Resposta", "—", "ms"), StatTile("Amostras", "0", "eventos")
        for t in (self.t_now, self.t_max, self.t_resp, self.t_n):
            row.addWidget(t)
        self.body.addLayout(row)
        self.pad = MousePad(self._upd)
        self.pad.setMinimumHeight(520)
        self.body.addWidget(self.pad, 1)
        self.out = label("", rich=True)
        self.body.addWidget(self.out)

    def _upd(self, hz, best, n):
        self.t_now.set(f"{hz:.0f}")
        self.t_max.set(f"{best:.0f}")
        self.t_resp.set(f"{1000 / best:.2f}" if best else "—")
        self.t_n.set(str(n))
        if best:
            st, txt = self.verdict(best)
            col = {"ok": C["ok"], "atencao": C["warn"]}.get(st, C["bad"])
            self.out.setText(f"<span style='color:{col}'>{txt}</span>")
        else:
            self.out.setText("")


# ===================================================================== teste de monitor
class MonitorTestPage(Page):
    title = "Teste de monitor"
    subtitle = ("Teste de movimento local, em tela cheia: veja ghosting, borrão e suavidade, com quadros por segundo, "
                "taxa de atualização, pixels por quadro e pixels por segundo. Não abre nenhum site.")

    def build(self):
        from lolitos.ui.tests import BACKGROUNDS, OBJ_COLORS, OBJECTS
        from lolitos.ui.widgets import card_header
        self.body.addWidget(label("Seus monitores", "h2"))
        self.mon_card = Card()
        self.mon_box = QVBoxLayout()
        self.mon_card.lay.addLayout(self.mon_box)
        self.mon_box.addWidget(label("Lendo os monitores…", "muted"))
        self.body.addWidget(self.mon_card)

        mc = Card(hero=True)
        mc.lay.addLayout(card_header("monitor", "Teste de movimento (ghosting e taxas de quadros)"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        self.c_screen = QComboBox()
        self.c_mode = QComboBox()
        for k, v in (("multi", "Várias taxas de quadros (cheios, 1/2 e 1/4)"), ("full", "Só quadros cheios")):
            self.c_mode.addItem(v, k)
        self.c_speed = QComboBox()
        for v in (480, 960, 1440, 1920, 2880):
            self.c_speed.addItem(f"{v} pixels por segundo", v)
        self.c_speed.setCurrentIndex(1)
        self.c_obj = QComboBox()
        self.c_obj.addItems(OBJECTS)
        self.c_col = QComboBox()
        self.c_col.addItems([n for n, _, _ in OBJ_COLORS])
        self.c_bg = QComboBox()
        self.c_bg.addItems([n for n, _, _ in BACKGROUNDS])
        self.c_n = QComboBox()
        for n in (1, 2, 3):
            self.c_n.addItem(f"{n} por faixa", n)
        self.c_txt = QComboBox()
        for k, v in (("", "Automática"), ("#ffffff", "Branco"), ("#101010", "Preto"), ("#f5b82e", "Amarelo")):
            self.c_txt.addItem(v, k)
        fields = [("Monitor", self.c_screen), ("Modo", self.c_mode), ("Velocidade", self.c_speed),
                  ("Objeto", self.c_obj), ("Cores do objeto", self.c_col), ("Fundo", self.c_bg),
                  ("Quantidade de objetos", self.c_n), ("Cor do texto", self.c_txt)]
        for i, (t, w) in enumerate(fields):
            grid.addWidget(label(t, "muted"), (i // 4) * 2, i % 4)
            grid.addWidget(w, (i // 4) * 2 + 1, i % 4)
        mc.lay.addLayout(grid)
        self.bg_note = label("", "muted")
        self.c_bg.currentIndexChanged.connect(self._bg_note)
        self._bg_note()
        mc.lay.addWidget(self.bg_note)
        mc.lay.addLayout(hrow(button("Iniciar teste em tela cheia", "primary", self._motion),
                              label("Esc sai · ↑/↓ velocidade · Espaço pausa · O objeto · K cores · B fundo · "
                                    "N quantidade · H esconde o texto", "muted", wrap=False), None))
        self.body.addWidget(mc)

        two = QHBoxLayout()
        two.setSpacing(12)
        for ico, title, txt, mode in (
                ("monitor", "Teste de OLED e pixels",
                 "Cores sólidas para pixels mortos ou travados e uniformidade, cinzas para retenção de imagem "
                 "(burn-in), degradê para faixas e degraus de preto para ver esmagamento nos tons escuros.", "colors"),
                ("sun", "Vazamento de luz",
                 "Tela preta total para achar clarões nos cantos (backlight bleed), IPS glow e manchas (clouding). "
                 "Faça no escuro, com o brilho no máximo.", "bleed")):
            c = Card()
            c.lay.addLayout(card_header(ico, title))
            c.lay.addWidget(label(txt, "muted"))
            c.lay.addLayout(hrow(button("Abrir em tela cheia", on_click=lambda _=False, m=mode: self._go(m)), None))
            two.addWidget(c)
        self.body.addLayout(two)

        how = Card()
        how.lay.addWidget(label("Como ler o resultado", "h2"))
        how.lay.addWidget(label(
            "• <b>Quadros/s igual aos Hz do monitor</b>: o teste está sincronizado. Se ficar abaixo, ative a taxa "
            "máxima do monitor (acima) ou feche programas pesados.<br>"
            "• <b>Siga o objeto com os olhos</b>: um rastro escuro atrás dele é ghosting (painel lento); um contorno "
            "claro ou colorido é overshoot (overdrive forte demais) — mais visível no fundo cinza 50%.<br>"
            "• <b>Pixels por quadro</b> = velocidade ÷ quadros por segundo. Quanto menor, mais suave: a 240 Hz e "
            "960 px/s o objeto anda 4 px por quadro; a 60 Hz, 16 px.<br>"
            "• <b>Faixas 1/2 e 1/4</b> mostram como o mesmo movimento fica com metade e um quarto dos quadros.",
            rich=True))
        self.body.addWidget(how)
        from lolitos.modules import display
        run_async(display.monitors, on_done=self._mons, on_error=lambda e: None)

    def _bg_note(self):
        notes = ["Cinza claro com faixas pretas: mistura transições cinza-cinza (onde o LCD é mais lento) com bordas "
                 "de alto contraste. Bom ponto de partida para qualquer painel.",
                 "Cinza sobre cinza escuro: mostra o ghosting típico de painéis LCD.",
                 "Cinza escuro sobre preto: mostra o 'black smearing' de painéis VA.",
                 "Branco e preto sobre cinza 50%: mostra o overshoot (contorno claro) do overdrive."]
        self.bg_note.setText(notes[self.c_bg.currentIndex() % len(notes)])

    def _mons(self, mons):
        from lolitos.modules import display
        from lolitos.ui.widgets import Toggle
        while self.mon_box.count():
            w = self.mon_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.c_screen.clear()
        screens = QGuiApplication.screens()
        gname = ""
        try:
            from lolitos.modules import pcprofile
            gname = (pcprofile.detect().gpus or [""])[0]
        except Exception:  # noqa: BLE001
            pass
        for i, m in enumerate(mons, 1):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 6, 0, 6)
            from lolitos.ui import glyphs
            rl.addWidget(glyphs.glyph("monitor", 15, C["accent2"]))
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(f"<b>Monitor {i} · {m['name']}</b>", rich=True, wrap=False))
            col.addWidget(label(f"{m['width']}×{m['height']}" + (f" · {gname}" if gname else ""), "muted", wrap=False))
            rl.addLayout(col, 1)
            hz = QVBoxLayout()
            hz.setSpacing(0)
            hz.addWidget(label(f"<b>{m['hz']} Hz</b>", rich=True, wrap=False), 0, Qt.AlignRight)
            hz.addWidget(label(f"máx. {m['max_hz']} Hz", "muted", wrap=False), 0, Qt.AlignRight)
            rl.addLayout(hz)
            tg = QVBoxLayout()
            tg.setSpacing(2)
            tg.addWidget(label("Taxa máxima", "muted", wrap=False))
            sw = Toggle(m["hz"] >= m["max_hz"])
            sw.setEnabled(m["hz"] < m["max_hz"])
            sw.setToolTip("Coloca o monitor na maior taxa de atualização que ele aceita nesta resolução.")

            def on(v, mm=m, w=sw):
                if v:
                    r = display.set_refresh(mm["device"], mm["max_hz"])
                    if r != 0:
                        w.setChecked(False)
                        info(self, "Monitor", "O Windows não aceitou a mudança (código {}).".replace("{}", str(r)))
                    run_async(display.monitors, on_done=self._mons)
            sw.toggled.connect(on)
            tg.addWidget(sw, 0, Qt.AlignRight)
            rl.addLayout(tg)
            self.mon_box.addWidget(row)
            self.c_screen.addItem(f"Monitor {i} — {m['width']}×{m['height']} @ {m['hz']} Hz", i - 1)
        if not mons:
            self.mon_box.addWidget(label("Nenhum monitor encontrado.", "muted"))
            for i, sc in enumerate(screens):
                self.c_screen.addItem(sc.name(), i)

    def _screen(self):
        screens = QGuiApplication.screens()
        i = self.c_screen.currentData() or 0
        return screens[i] if i < len(screens) else (self.screen() or QGuiApplication.primaryScreen())

    def _open(self, w):
        self._mt = w
        w.setGeometry(self._screen().geometry())
        w.showFullScreen()

    def _motion(self):
        from lolitos.ui.tests import MonitorTest
        self._open(MonitorTest("motion", speed=self.c_speed.currentData(), obj=self.c_obj.currentIndex(),
                               bg=self.c_bg.currentIndex(), col=self.c_col.currentIndex(),
                               count=self.c_n.currentData(), bands=self.c_mode.currentData() == "multi",
                               text=self.c_txt.currentData()))

    def _go(self, mode):
        from lolitos.ui.tests import MonitorTest
        self._open(MonitorTest(mode))


# ===================================================================== velocidade
def _hist_file():
    return data_dir() / "velocidade.json"


class StartRing(QWidget):
    """Botão circular grande (INICIAR / MEDINDO… / TESTAR DE NOVO) com anel de progresso."""

    def __init__(self, on_click):
        super().__init__()
        self.on_click = on_click
        self.text = tr("INICIAR")
        self.progress = 0.0
        self.enabled = True
        self.hover = False
        self.setFixedSize(340, 340)
        self.setCursor(Qt.PointingHandCursor)

    def set(self, text, progress=None, enabled=True):
        self.text = tr(text)
        if progress is not None:
            self.progress = progress
        self.enabled = enabled
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        self.update()

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if self.enabled and e.button() == Qt.LeftButton:
            self.on_click()

    def paintEvent(self, _):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QFont, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(10, 10, 320, 320)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["deepbg"]))
        p.drawEllipse(r)
        inner = r.adjusted(16, 16, -16, -16)
        p.setBrush(QColor(C["panel"] if not self.hover else C["panel2"]))
        p.drawEllipse(inner)
        pen = QPen(QColor(C["accent"]), 5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        if self.enabled or self.progress <= 0:
            p.drawEllipse(inner)
        else:
            p.setPen(QPen(QColor(C["border2"]), 5))
            p.drawEllipse(inner)
            p.setPen(pen)
            p.drawArc(inner, 90 * 16, int(-360 * 16 * min(1.0, self.progress)))
        p.setPen(QColor(C["text"]))
        f = QFont("Segoe UI", 30 if len(self.text) < 10 else 18, QFont.Black)
        p.setFont(f)
        p.drawText(r, Qt.AlignCenter, self.text)


class SpeedTestPage(Page):
    title = "Teste de velocidade"
    subtitle = ("Mede download, upload, ping, variação (jitter) e o ping com a conexão carregada, usando os "
                "servidores públicos de teste da Cloudflare mais próximos de você.")

    def build(self):
        from lolitos.ui.widgets import StatTile
        c = Card(hero=True)
        row = QHBoxLayout()
        row.setSpacing(24)
        self.ring = StartRing(self._run)
        row.addWidget(self.ring, 0, Qt.AlignVCenter)
        right = QVBoxLayout()
        right.setSpacing(10)
        self.head = label("<b>Clique em INICIAR para testar a sua conexão.</b>", rich=True)
        right.addWidget(self.head)
        self.out = label("O teste dura cerca de 25 segundos e usa bastante banda nesse tempo. Pause downloads e "
                         "streaming para um resultado fiel.", "muted", rich=True)
        right.addWidget(self.out)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.vals = {}
        for i, (k, name, unit, ico) in enumerate([("down", "Download", "Mbps", "download"),
                                                  ("up", "Upload", "Mbps", "upload"),
                                                  ("ping", "Ping", "ms", "ping"),
                                                  ("jitter", "Variação (jitter)", "ms", "jitter"),
                                                  ("loaded", "Ping sob carga", "ms", "bolt")]):
            t = StatTile(name, "—", unit, icon=ico, align=Qt.AlignLeft)
            self.vals[k] = t
            grid.addWidget(t, i // 2, i % 2)
        right.addLayout(grid)
        row.addLayout(right, 1)
        c.lay.addLayout(row)
        self.body.addWidget(c)
        self.body.addWidget(label("Resultados anteriores", "h2"))
        hc = Card()
        self.hist = label("", rich=True)
        hc.lay.addWidget(self.hist)
        self.body.addWidget(hc)
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
        if not rows:
            self.hist.setText(tr("Nenhum teste feito ainda."))
            return
        self.hist.setText("<table cellspacing=6>" + "".join(
            f"<tr><td>{time.strftime('%d/%m %H:%M', time.localtime(r['time']))}</td>"
            f"<td>&nbsp;↓ <b>{r['down']:.0f}</b> Mbps</td><td>&nbsp;↑ <b>{r['up']:.0f}</b> Mbps</td>"
            f"<td>&nbsp;ping <b>{r['ping']:.0f}</b> ms</td><td>&nbsp;{tr('sob carga')} <b>{r['loaded']:.0f}</b> ms</td>"
            f"</tr>" for r in rows) + "</table>")

    def _run(self):
        self.ring.set("MEDINDO…", 0.02, enabled=False)
        for v in self.vals.values():
            v.set("—")
        stage_pos = {"ping": 0.05, "download": 0.15, "upload": 0.55, "loaded": 0.9}

        def work(progress=None):
            return speedtest.full_test(lambda s, v=0: progress(f"{s}|{v}"))

        def prog(s):
            st, v = s.split("|")
            v = float(v)
            self.ring.set("MEDINDO…", stage_pos.get(st, 0.5) + (0.3 * min(1, v / 1000) if v else 0), enabled=False)
            if st in ("download", "upload") and v:
                self.vals["down" if st == "download" else "up"].set(f"{v:.0f}")
            self.head.setText("<b>" + {"ping": tr("Medindo o ping…"), "download": tr("Download…"),
                                       "upload": tr("Upload…"), "loaded": tr("Ping com a linha cheia…")}[st] + "</b>")

        def done(r):
            self.ring.set("TESTAR DE NOVO", 1.0)
            self.vals["down"].set(f"{r['down']:.0f}")
            self.vals["up"].set(f"{r['up']:.0f}")
            self.vals["ping"].set(f"{r['ping']:.0f}")
            self.vals["jitter"].set(f"{r['jitter']:.1f}")
            self.vals["loaded"].set(f"{r['loaded']:.0f}")
            bb = r["bufferbloat"]
            txt = (f"<span style='color:{C['warn']}'>O ping sobe {bb:.0f} ms com a linha cheia (bufferbloat): ative "
                   "QoS/SQM no roteador se puder.</span>" if bb > 30 else
                   f"<span style='color:{C['ok']}'>Sem bufferbloat relevante: ping estável mesmo com a linha cheia."
                   "</span>")
            ping_txt = ("ping excelente para jogos competitivos" if r["ping"] < 20 else
                        "ping bom para jogos" if r["ping"] < 50 else "ping alto para jogos competitivos")
            self.head.setText(f"<b>{tr('Concluído')} · Cloudflare {r['colo']}</b>")
            self.out.setText(f"{txt}<br>{tr(ping_txt).capitalize()}")
            rows = self._load() + [r]
            try:
                _hist_file().write_text(json.dumps(rows[-50:]), encoding="utf-8")
            except OSError:
                pass
            self._show_hist()

        def err(e):
            self.ring.set("INICIAR", 0)
            self.head.setText(f"<b>{tr('Não foi possível concluir o teste')}</b>")
            self.out.setText(f"{e}. " + tr("Verifique a conexão com a internet."))
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
        from lolitos.ui.widgets import StatTile
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.tiles = {k: StatTile(n, "—", u) for k, n, u in (("sent", "Enviados", "pacotes"), ("loss", "Perda", "%"),
                                                            ("late", "Atrasados", "pacotes"), ("avg", "Média", "ms"),
                                                            ("jit", "Variação", "ms"))}
        for t in self.tiles.values():
            tiles.addWidget(t)
        self.body.addLayout(tiles)
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
            self._tiles(r)
            self.out.setText(f"{r.sent} enviados · perda {r.loss_pct:.1f}% · média {r.avg:.0f} ms")

        def done(r):
            self.last = r
            self.csv_btn.setEnabled(True)
            self.btn.setEnabled(True)
            self.btn.setText("TESTAR DE NOVO")
            self.timeline.set(list(r.timeline))
            self._tiles(r)
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

    def _tiles(self, r):
        self.tiles["sent"].set(str(r.sent))
        self.tiles["loss"].set(f"{r.loss_pct:.1f}")
        self.tiles["loss"].value.setStyleSheet(f"color:{C['ok'] if r.loss_pct < 1 else C['warn'] if r.loss_pct < 3 else C['bad']}")
        self.tiles["late"].set(str(r.late))
        self.tiles["avg"].set(f"{r.avg:.0f}" if r.avg else "—")
        self.tiles["jit"].set(f"{r.jitter:.1f}" if r.jitter else "—")

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
        self.run_btn = button("Executar check-up", "primary", self.run_check)
        self.actions.addWidget(self.run_btn)
        self.summary = label("Clique em Executar check-up para analisar o PC.", "muted", wrap=False)
        self.body.addLayout(hrow(self.summary, None, button("Exportar relatório…", on_click=self._export),
                                 button("Copiar minha configuração", on_click=self._copy)))
        self.card = Card()
        self.box = QVBoxLayout()
        self.box.setSpacing(2)
        self.card.lay.addLayout(self.box)
        self.body.addWidget(self.card)
        self.checks = []
        self.run_check()

    def run_check(self):
        self.summary.setText(tr("Analisando o PC…"))
        self.run_btn.setEnabled(False)
        run_async(checkup.run_checkup, on_done=self._show, on_error=lambda e: self.run_btn.setEnabled(True))

    def _show(self, checks):
        self.run_btn.setEnabled(True)
        self.checks = checks
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        n_ok = sum(1 for c in checks if c.state in ("ok", "info"))
        self.summary.setText(tr("Resultado: {} em ordem, {} pedem atenção.").replace("{}", str(n_ok), 1)
                             .replace("{}", str(len(checks) - n_ok), 1) + "  " +
                             tr("Medido às {}.").replace("{}", time.strftime("%H:%M")))
        colors = {"ok": C["ok"], "atencao": C["warn"], "corrigir": C["bad"], "info": C["info"]}
        for c in checks:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 6, 4, 6)
            rl.setSpacing(12)
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{colors[c.state]}; font-size:13pt;")
            rl.addWidget(dot, 0, Qt.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(c.title))
            if c.detail:
                col.addWidget(label(c.detail, "muted"))
            rl.addLayout(col, 1)
            if c.value:
                rl.addWidget(label(c.value, wrap=False), 0, Qt.AlignTop | Qt.AlignRight)
            if c.state in ("atencao", "corrigir") and c.fix in FIX_PAGE and self.main:
                rl.addWidget(button("Corrigir", on_click=lambda _=False, p=FIX_PAGE[c.fix]: self.main.go(p)),
                             0, Qt.AlignVCenter)
            elif c.state in ("atencao", "corrigir") and c.fix == "relaunch_admin" and self.main:
                from lolitos.core.system import relaunch_as_admin
                rl.addWidget(button("Abrir como admin", on_click=lambda: relaunch_as_admin() and self.main.quit()))
            self.box.addWidget(row)

    def _report(self) -> str:
        from lolitos.modules import pcprofile
        p = pcprofile.detect()
        lines = [f"{APP_NAME} {VERSION} — relatório do PC", time.strftime("%d/%m/%Y %H:%M"), "",
                 f"Perfil: {p.tier_name}", *p.summary(), f"Windows: {platform.platform()}", "", "Check-up:"]
        for c in self.checks:
            lines.append(f"[{c.state.upper()}] {c.title}: {c.value} {c.detail}".rstrip())
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
