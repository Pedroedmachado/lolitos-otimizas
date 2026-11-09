"""Configuração do overlay de jogo."""
import webbrowser

from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSlider
from PySide6.QtCore import Qt

from lolitos.core import settings
from lolitos.modules import fps
from lolitos.ui.theme import C
from lolitos.ui.widgets import Card, Page, TaskDialog, button, hrow, label

ITEMS = [("fps", "FPS e 1% low"), ("cpu", "Uso da CPU"), ("cpu_temp", "Temperatura da CPU"), ("gpu", "Uso da GPU"),
         ("gpu_temp", "Temperatura da GPU"), ("vram", "VRAM em uso"), ("ram", "Uso da RAM"), ("ping", "Ping")]
CORNERS = [("top-left", "Canto superior esquerdo"), ("top-right", "Canto superior direito"),
           ("bottom-left", "Canto inferior esquerdo"), ("bottom-right", "Canto inferior direito")]


class OverlayPage(Page):
    title = "Overlay de jogo"
    subtitle = ("FPS, uso e temperaturas por cima do jogo, ligado/desligado por uma tecla. O overlay é uma janela "
                "separada que deixa os cliques passarem: nada é injetado no jogo.")

    def build(self):
        c = Card(hero=True)
        c.lay.addLayout(hrow(button("Mostrar/ocultar agora", "primary", lambda: self.main.overlay_toggle()), None))
        c.lay.addWidget(label("Funciona com o BDO em 'Janela sem bordas'. Em tela cheia exclusiva o jogo pode "
                              "desenhar por cima.", "muted"))
        self.body.addWidget(c)

        cfg = Card()
        cfg.lay.addWidget(label("Tecla para ligar/desligar", "h2"))
        self.hotkey = QLineEdit(settings.get("overlay_hotkey"))
        self.hotkey.setToolTip("Ex.: Ctrl+Shift+F10. Use uma combinação que o BDO não usa.")
        cfg.lay.addLayout(hrow(self.hotkey, button("Salvar tecla", on_click=self._save_hotkey), None))
        cfg.lay.addWidget(label("Posição e aparência", "h2"))
        self.corner = QComboBox()
        for k, v in CORNERS:
            self.corner.addItem(v, k)
        self.corner.setCurrentIndex([k for k, _ in CORNERS].index(settings.get("overlay_corner")))
        self.corner.currentIndexChanged.connect(lambda: self._set("overlay_corner", self.corner.currentData()))
        self.op = QSlider(Qt.Horizontal)
        self.op.setRange(0, 100)
        self.op.setValue(int(settings.get("overlay_opacity") * 100))
        self.op.valueChanged.connect(lambda v: self._set("overlay_opacity", v / 100))
        cfg.lay.addLayout(hrow(self.corner, label("Opacidade do fundo", "muted", wrap=False), self.op, None))
        cfg.lay.addWidget(label("O que mostrar", "h2"))
        cur = set(settings.get("overlay_items"))
        for k, v in ITEMS:
            ck = QCheckBox(v)
            ck.setChecked(k in cur)
            ck.toggled.connect(lambda on, kk=k: self._toggle_item(kk, on))
            cfg.lay.addWidget(ck)
        auto = QCheckBox("Ligar o overlay junto com o jogo ('Preparar e jogar')")
        auto.setChecked(settings.get("overlay_with_game"))
        auto.toggled.connect(lambda v: settings.set("overlay_with_game", v))
        cfg.lay.addWidget(auto)
        self.body.addWidget(cfg)

        f = Card()
        f.lay.addWidget(label("<b>Medição de FPS</b>", rich=True))
        self.pm_lbl = label("", rich=True)
        f.lay.addWidget(self.pm_lbl)
        self.pm_btn = button("Baixar o PresentMon agora", "primary", self._download_pm)
        f.lay.addLayout(hrow(self.pm_btn, button("Página do PresentMon", on_click=lambda: webbrowser.open(fps.RELEASES)),
                             None))
        f.lay.addWidget(label("O FPS vem dos eventos de apresentação de quadros que o próprio Windows publica, lidos "
                              "pelo PresentMon (Intel, licença MIT). Nada é injetado no jogo. O overlay mostra o FPS "
                              "do jogo que estiver em primeiro plano.", "muted"))
        self.body.addWidget(f)
        self._pm_status()

    def _pm_status(self):
        pm = fps.find_presentmon()
        self.pm_lbl.setText(f"<span style='color:{C['ok']}'>PresentMon pronto: {pm}</span>" if pm else
                            f"<span style='color:{C['warn']}'>PresentMon não encontrado.</span> Sem ele o overlay "
                            "não mostra o FPS. Baixe com o botão abaixo (versão fixada, arquivo conferido).")
        self.pm_btn.setVisible(pm is None)

    def _download_pm(self):
        def work(progress=None):
            progress(f"Baixando PresentMon {fps.PM_VERSION} do GitHub da Intel…")
            dst = fps.download_presentmon()
            return f"Pronto: {dst}\nArquivo conferido (SHA-256)."

        def done(_):
            self._pm_status()
            if self.main:
                self.main.overlay_reconfigure()
        TaskDialog(self, "PresentMon", work, on_done=done).exec()

    def _set(self, k, v):
        settings.set(k, v)
        if self.main:
            self.main.overlay_reconfigure()

    def _toggle_item(self, k, on):
        cur = list(settings.get("overlay_items"))
        if on and k not in cur:
            cur.append(k)
        if not on and k in cur:
            cur.remove(k)
        self._set("overlay_items", cur)

    def _save_hotkey(self):
        self._set("overlay_hotkey", self.hotkey.text().strip() or "Ctrl+Shift+F10")
        if self.main:
            ok = self.main.register_hotkey()
            self.hotkey.setStyleSheet("" if ok else f"border-color:{C['bad']}")
