"""Overlay de jogo: prévia ao vivo, liga/desliga, tecla, aparência e o que mostrar."""
import webbrowser

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QSlider, QVBoxLayout

from lolitos.core import settings
from lolitos.i18n import tr
from lolitos.modules import fps
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, TaskDialog, Toggle, button, card_header, hrow, label, pill

ITEMS = [("fps", "FPS"), ("frametime", "Tempo de quadro"), ("low1", "1% low"),
         ("cpu", "Uso da CPU"), ("cpu_temp", "Temperatura da CPU"), ("cpu_freq", "Frequência da CPU"),
         ("gpu", "Uso da GPU"), ("gpu_temp", "Temperatura da GPU"), ("gpu_freq", "Frequência da GPU"),
         ("ram", "Uso da RAM"), ("vram", "VRAM em uso"), ("ping", "Ping"), ("game", "Nome do jogo")]
CORNERS = [("top-left", "Canto superior esquerdo"), ("top-right", "Canto superior direito"),
           ("bottom-left", "Canto inferior esquerdo"), ("bottom-right", "Canto inferior direito")]
LAYOUTS = [("vertical", "Vertical (lista)"), ("horizontal", "Horizontal (barra)")]


class Preview(QFrame):
    """O overlay desenhado aqui dentro, com os números reais deste PC."""

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setObjectName("card")
        self.setMinimumSize(300, 260)
        self.lines = []

    def refresh(self):
        from lolitos.ui.overlay import compute_lines
        ov = self.page.main.overlay if self.page.main else None
        self.lines = compute_lines(getattr(ov, "fps_reader", None), getattr(ov, "cpu_t", None),
                                   getattr(ov, "ping", None))
        from lolitos.ui.overlay import overlay_size
        w, h = overlay_size(self.lines)
        self.setMinimumSize(max(300, w + 40), max(260, h + 70))
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        from lolitos.ui.overlay import overlay_size, paint_lines
        p = QPainter(self)
        w, h = overlay_size(self.lines)
        x = max(12, (self.width() - w) // 2)
        y = max(12, (self.height() - 30 - h) // 2)
        p.save()
        paint_lines(p, self.lines, QRect(x, y, w, h))
        p.restore()
        p.setPen(Qt.gray)
        p.drawText(QRect(0, self.height() - 26, self.width(), 20), Qt.AlignCenter,
                   self.page.tr_preview)


class OverlayPage(Page):
    title = "Overlay"
    subtitle = "FPS, uso e temperaturas por cima do jogo, ligado e desligado por uma tecla que você escolhe."

    def build(self):
        from lolitos.i18n import tr
        self.tr_preview = tr("Prévia com os números reais deste PC")
        top = Card(hero=True)
        row = QHBoxLayout()
        row.setSpacing(18)
        self.preview = Preview(self)
        row.addWidget(self.preview)
        right = QVBoxLayout()
        right.setSpacing(8)
        self.state = pill("DESLIGADO")
        right.addLayout(card_header("game", "Overlay de jogo", self.state))
        self.show_sw = Toggle(False, on_toggle=self._show_now)
        r1 = QHBoxLayout()
        r1.addWidget(label("Mostrar o overlay agora"), 1)
        r1.addWidget(self.show_sw)
        right.addLayout(r1)
        self.auto_sw = Toggle(settings.get("overlay_with_game"),
                              on_toggle=lambda v: settings.set("overlay_with_game", v))
        r2 = QHBoxLayout()
        r2.addWidget(label("Ligar junto com o jogo ('Preparar e jogar')"), 1)
        r2.addWidget(self.auto_sw)
        right.addLayout(r2)
        r3 = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label("Tecla para ligar/desligar"))
        col.addWidget(label("Funciona com o jogo em primeiro plano. Use uma combinação que o jogo não use.", "muted"))
        r3.addLayout(col, 1)
        self.hotkey = QLineEdit(settings.get("overlay_hotkey"))
        self.hotkey.setFixedWidth(170)
        self.hotkey.editingFinished.connect(self._save_hotkey)
        r3.addWidget(self.hotkey)
        right.addLayout(r3)
        self.hk_lbl = label("", "muted")
        right.addWidget(self.hk_lbl)
        self.fps_lbl = label("", rich=True)
        right.addWidget(self.fps_lbl)
        self.pm_btn = button("Baixar o PresentMon agora", "primary", self._download_pm)
        self.pawn_btn = button("Ativar a temperatura do processador", "primary", self._install_pawnio)
        self.pawn_btn.setToolTip(tr("Instala o PawnIO (driver assinado e de código aberto, o mesmo do "
                                    "LibreHardwareMonitor) para ler o sensor do próprio processador."))
        right.addLayout(hrow(self.pm_btn, self.pawn_btn, None))
        right.addStretch()
        row.addLayout(right, 1)
        top.lay.addLayout(row)
        self.body.addWidget(top)

        ap = Card()
        ap.lay.addWidget(label("Aparência", "h2"))
        self.corner = QComboBox()
        for k, v in CORNERS:
            self.corner.addItem(v, k)
        self.corner.setCurrentIndex([k for k, _ in CORNERS].index(settings.get("overlay_corner")))
        self.corner.currentIndexChanged.connect(lambda: self._set("overlay_corner", self.corner.currentData()))
        self.layout_cb = QComboBox()
        for k, v in LAYOUTS:
            self.layout_cb.addItem(v, k)
        self.layout_cb.setCurrentIndex(max(0, self.layout_cb.findData(settings.get("overlay_layout"))))
        self.layout_cb.currentIndexChanged.connect(lambda: self._set("overlay_layout", self.layout_cb.currentData()))
        self.op = QSlider(Qt.Horizontal)
        self.op.setRange(0, 100)
        self.op.setValue(int(settings.get("overlay_opacity") * 100))
        self.op.valueChanged.connect(lambda v: self._set("overlay_opacity", v / 100))
        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(70, 180)
        self.size.setValue(int(float(settings.get("overlay_scale") or 1) * 100))
        self.size.valueChanged.connect(lambda v: self._set("overlay_scale", v / 100))
        for title, sub, w in (("Posição", "Na tela principal.", self.corner), ("Formato", "", self.layout_cb),
                              ("Opacidade do fundo", "", self.op), ("Tamanho", "", self.size)):
            r = QHBoxLayout()
            c = QVBoxLayout()
            c.setSpacing(0)
            c.addWidget(label(title))
            if sub:
                c.addWidget(label(sub, "muted"))
            r.addLayout(c, 1)
            w.setFixedWidth(220)
            r.addWidget(w)
            ap.lay.addLayout(r)
        ap.lay.addWidget(label("O que mostrar", "muted"))
        grid = QGridLayout()
        cur = set(settings.get("overlay_items"))
        for i, (k, v) in enumerate(ITEMS):
            ck = QCheckBox(v)
            ck.setChecked(k in cur)
            ck.toggled.connect(lambda on, kk=k: self._toggle_item(kk, on))
            grid.addWidget(ck, i // 3, i % 3)
        ap.lay.addLayout(grid)
        self.body.addWidget(ap)

        info_c = Card()
        info_c.lay.addLayout(card_header("info", "Como funciona"))
        info_c.lay.addWidget(label(
            "O overlay é uma janela separada que deixa os cliques passarem: nada é injetado no jogo. Funciona com o "
            "jogo em janela sem bordas ou em tela cheia com as otimizações de tela cheia do Windows (o padrão). Em "
            "tela cheia exclusiva o jogo pode desenhar por cima.<br>O FPS vem dos eventos de apresentação de quadros "
            "que o próprio Windows publica, lidos pelo PresentMon (Intel, licença MIT), e é o do jogo em primeiro "
            "plano.", "muted", rich=True))
        info_c.lay.addLayout(hrow(button("Página do PresentMon", on_click=lambda: webbrowser.open(fps.RELEASES)),
                                  None))
        self.body.addWidget(info_c)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._status()

    # ---------------------------------------------------------------- estado
    def on_show(self):
        if self._built:
            self._status()
            self.timer.start(1000)
            self._tick()

    def hideEvent(self, e):
        super().hideEvent(e)
        if hasattr(self, "timer"):
            self.timer.stop()

    def _tick(self):
        self.preview.refresh()
        vis = bool(self.main and self.main.overlay.isVisible())
        self.state.setText("LIGADO" if vis else "DESLIGADO")
        self.state.setStyleSheet(f"color:{C['ok'] if vis else C['muted']};")
        self.show_sw.blockSignals(True)
        self.show_sw.setChecked(vis)
        self.show_sw.blockSignals(False)
        self.show_sw.update()

    def _status(self):
        pm = fps.find_presentmon()
        ov = self.main.overlay if self.main else None
        r = getattr(ov, "fps_reader", None)
        if not pm:
            txt = (f"<span style='color:{C['warn']}'>FPS: PresentMon não encontrado.</span> Baixe com o botão "
                   "abaixo (versão fixada, arquivo conferido).")
        elif r is not None and r.is_alive():
            txt = f"<span style='color:{C['ok']}'>FPS: medição ativa.</span>"
        elif r is not None and r.error:
            txt = f"<span style='color:{C['bad']}'>FPS: {r.error}</span>"
        else:
            txt = "FPS: começa quando o overlay é ligado."
        gpu_txt = "GPU °C: lido do driver da placa." if __import__("lolitos.modules.gpu", fromlist=["x"]).available() \
            else "GPU °C: só placas NVIDIA."
        from lolitos.modules import pawnio
        pst = pawnio.status()
        if pst == "ok":
            cpu_txt = f"<span style='color:{C['ok']}'>{tr('CPU °C: sensor do processador (PawnIO).')}</span>"
        elif pst == "PawnIO não instalado":
            cpu_txt = (f"<span style='color:{C['warn']}'>{tr('CPU °C: aproximada (placa-mãe).')}</span> "
                       + tr("Para a temperatura real do processador, clique em 'Ativar a temperatura do "
                            "processador'."))
        else:
            cpu_txt = tr("CPU °C: {} — usando o LibreHardwareMonitor (se aberto) ou a placa-mãe.").replace(
                "{}", tr(pst))
        self.fps_lbl.setText(f"{txt}<br>{gpu_txt}<br>{cpu_txt}")
        self.pm_btn.setVisible(pm is None)
        self.pawn_btn.setVisible(pawnio.supported() and not pawnio.installed())
        self.hk_lbl.setText(f"Atalho ativo: {settings.get('overlay_hotkey')}")

    def _show_now(self, on):
        if not self.main:
            return
        if on != self.main.overlay.isVisible():
            self.main.overlay_toggle()
        QTimer.singleShot(800, self._status)

    def _install_pawnio(self):
        from lolitos.modules import pawnio
        from lolitos.ui.widgets import confirm
        if not confirm(self, "Temperatura do processador",
                       "Instalar o PawnIO? É um driver assinado e de código aberto (pawnio.eu), usado pelo "
                       "LibreHardwareMonitor e pelo Fan Control, que só lê os sensores de temperatura do processador. "
                       "Nada é injetado em jogo. Pode ser removido em Configurações › Aplicativos.", yes="Instalar"):
            return
        TaskDialog(self, "Temperatura do processador", pawnio.install, on_done=lambda _: self._status()).exec()

    def _download_pm(self):
        def work(progress=None):
            progress(f"Baixando PresentMon {fps.PM_VERSION} do GitHub da Intel…")
            dst = fps.download_presentmon()
            return f"Pronto: {dst}\nArquivo conferido (SHA-256)."

        def done(_):
            self._status()
            if self.main:
                self.main.overlay_reconfigure()
        TaskDialog(self, "PresentMon", work, on_done=done).exec()

    def _set(self, k, v):
        settings.set(k, v)
        if self.main:
            self.main.overlay_reconfigure()
        self.preview.refresh()

    def _toggle_item(self, k, on):
        cur = list(settings.get("overlay_items"))
        if on and k not in cur:
            cur.append(k)
        if not on and k in cur:
            cur.remove(k)
        order = [k for k, _ in ITEMS]
        self._set("overlay_items", sorted(cur, key=lambda x: order.index(x) if x in order else 99))

    def _save_hotkey(self):
        settings.set("overlay_hotkey", self.hotkey.text().strip() or "Ctrl+Shift+F10")
        if self.main:
            ok = self.main.register_hotkey()
            self.hotkey.setStyleSheet("" if ok else f"border-color:{C['bad']}")
        self._status()
