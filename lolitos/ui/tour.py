"""Apresentação do app: escurece a janela, recorta um "furo" em volta da parte explicada e mostra um balão com
Próximo / Voltar / Pular. Abre sozinha na primeira vez e pelo botão 'Rever a apresentação' das Configurações."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QRectF, Qt, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from lolitos.i18n import tr
from lolitos.ui import theme
from lolitos.ui.widgets import button

# (chave da tela a abrir ou "", alvo, título, texto). Alvo: "nav:<chave>", "side", "header", "content", "theme",
# "update" ou "" (balão no meio, sem destaque).
STEPS = [
    ("painel", "", "Bem-vindo ao Chinese Control",
     "Uma volta rápida pelas partes principais. Leva menos de um minuto e dá para pular quando quiser."),
    ("painel", "side", "Menu lateral",
     "Todas as telas ficam aqui, separadas em Principal, Otimizar, Ferramentas e Sistema. O botão 'Recolher menu' "
     "deixa só os ícones."),
    ("painel", "score", "Pontuação e Boost",
     "A pontuação mostra o quanto o Windows já está otimizado. O Boost aplica de uma vez o que é seguro para "
     "este computador, com ponto de restauração antes."),
    ("desempenho", "nav:desempenho", "Desempenho",
     "Gráficos ao vivo do processador, memória, placa de vídeo, disco e rede, com gravação em CSV."),
    ("meupc", "nav:meupc", "Meu PC",
     "Cada peça do computador em detalhe: processador, memória, placa-mãe, placa de vídeo, discos e mais."),
    ("completa", "nav:completa", "Otimização Completa",
     "Escolha o que aplicar, por categoria. Cada ajuste diz o que faz e mostra se já estava assim."),
    ("restauracao", "nav:restauracao", "Restauração",
     "Tudo o que o app muda fica no histórico e pode ser desfeito daqui, um por um ou tudo de uma vez."),
    ("config", "theme", "Tema e efeitos",
     "Troque entre Escuro, Claro e Azul e escolha o nível dos efeitos visuais. Em PC fraco, desligue os efeitos."),
    ("config", "update", "Atualizações",
     "O app confere no GitHub se há versão nova e se atualiza sozinho, mantendo histórico e configurações."),
    ("painel", "", "Pronto!",
     "Você pode rever esta apresentação quando quiser em Configurações › Aparência."),
]


class Tour(QWidget):
    def __init__(self, main, on_close=None):
        super().__init__(main)
        self.main, self.on_close, self.i = main, on_close, 0
        self.hole = QRectF()
        self._anim = None
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setGeometry(main.rect())
        main.installEventFilter(self)

        self.bubble = QFrame(self)
        self.bubble.setObjectName("tourbubble")
        self.bubble.setFixedWidth(360)
        v = QVBoxLayout(self.bubble)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(8)
        self.step_lbl = QLabel()
        self.step_lbl.setObjectName("tourstep")
        self.title = QLabel()
        self.title.setObjectName("h2")
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setObjectName("muted")
        self.dots = QLabel()
        self.dots.setObjectName("tourdots")
        v.addWidget(self.step_lbl)
        v.addWidget(self.title)
        v.addWidget(self.text)
        v.addWidget(self.dots)
        row = QHBoxLayout()
        row.addStretch()
        self.skip = button("Pular", on_click=self.close_tour)
        self.back = button("Voltar", on_click=lambda: self.show_step(self.i - 1))
        self.next = button("Próximo", "primary", on_click=lambda: self.show_step(self.i + 1))
        for b in (self.skip, self.back, self.next):
            row.addWidget(b)
        v.addLayout(row)
        self.show()
        self.raise_()
        self.setFocus()
        self.show_step(0)

    # ------------------------------------------------------------------ alvo de cada passo
    def _target(self, what: str) -> QRect:
        m = self.main

        def rect_of(w):
            if w is None or not w.isVisible():
                return QRect()
            tl = w.mapTo(m, w.rect().topLeft())
            return QRect(tl, w.size())
        if what == "side":
            return rect_of(getattr(m, "side", None))
        if what == "content":
            return rect_of(m.stack)
        if what == "score":
            pg = m.stack.currentWidget()
            g = getattr(pg, "gauge", None)
            return rect_of(g.parentWidget()) if g is not None else QRect()
        if what == "theme":
            return rect_of(getattr(m, "theme_btn", None))
        if what == "update":
            return rect_of(getattr(m, "update_btn", None))
        if what.startswith("nav:"):
            idx = m.index.get(what[4:])
            if idx is not None:
                b = m.nav_buttons[idx]
                try:
                    b.parentWidget().parentWidget().parentWidget().ensureWidgetVisible(b)  # QScrollArea
                except Exception:  # noqa: BLE001
                    pass
                return rect_of(b)
        return QRect()

    def show_step(self, i: int):
        if i >= len(STEPS):
            self.close_tour()
            return
        self.i = max(0, i)
        key, target, title, text = STEPS[self.i]
        if key and key in self.main.index:
            self.main.go(key)
        self.step_lbl.setText(tr("Passo {} de {}").replace("{}", str(self.i + 1), 1).replace("{}", str(len(STEPS)), 1))
        self.title.setText(tr(title))
        self.text.setText(tr(text))
        self.dots.setText("".join("●" if n == self.i else "○" for n in range(len(STEPS))))
        self.back.setVisible(self.i > 0)
        self.skip.setVisible(self.i < len(STEPS) - 1)
        self.next.setText(tr("Concluir") if self.i == len(STEPS) - 1 else tr("Próximo"))
        r = self._target(target)
        new = QRectF(r.adjusted(-6, -6, 6, 6)) if not r.isNull() else QRectF()
        self._move_hole(new)

    def _move_hole(self, new: QRectF):
        old = QRectF(self.hole)
        if self._anim:
            self._anim.stop()
        if old.isNull() or new.isNull() or theme.level() == 0:
            self.hole = new
            self._place()
            return
        a = QVariantAnimation(self)
        a.setDuration(320)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.setStartValue(0.0)
        a.setEndValue(1.0)

        def step(t):
            t = float(t)
            self.hole = QRectF(old.x() + (new.x() - old.x()) * t, old.y() + (new.y() - old.y()) * t,
                               old.width() + (new.width() - old.width()) * t,
                               old.height() + (new.height() - old.height()) * t)
            self._place()
        a.valueChanged.connect(step)
        a.start()
        self._anim = a

    def _place(self):
        """Balão ao lado do furo (direita, depois embaixo/em cima); sem furo, no meio da janela."""
        self.bubble.adjustSize()
        bw, bh = self.bubble.width(), self.bubble.sizeHint().height()
        W, H = self.width(), self.height()
        h = self.hole
        if h.isNull():
            x, y = (W - bw) // 2, (H - bh) // 2
        elif h.right() + 16 + bw < W and h.width() < W * 0.5:
            x, y = int(h.right()) + 16, int(h.center().y() - bh / 2)
        elif h.bottom() + 16 + bh < H:
            x, y = int(h.center().x() - bw / 2), int(h.bottom()) + 16
        else:
            x, y = int(h.center().x() - bw / 2), int(h.top()) - 16 - bh
        x = max(12, min(x, W - bw - 12))
        y = max(12, min(y, H - bh - 12))
        self.bubble.setGeometry(x, y, bw, bh)
        self.update()

    # ------------------------------------------------------------------ desenho e eventos
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        if not self.hole.isNull():
            hole = QPainterPath()
            hole.addRoundedRect(self.hole, 12, 12)
            path = path.subtracted(hole)
        p.fillPath(path, QColor(0, 0, 0, 165))
        if not self.hole.isNull():
            p.setPen(QPen(QColor(theme.C["accent"]), 2))
            p.drawRoundedRect(self.hole, 12, 12)

    def mousePressEvent(self, e):
        e.accept()          # cliques fora do balão não passam para a tela de baixo

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_tour()
        elif e.key() in (Qt.Key_Right, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.show_step(self.i + 1)
        elif e.key() == Qt.Key_Left:
            self.show_step(self.i - 1)

    def eventFilter(self, obj, ev):
        if obj is self.main and ev.type() == QEvent.Resize:
            self.setGeometry(self.main.rect())
            self.show_step(self.i)
        return False

    def close_tour(self):
        from lolitos.core import settings
        settings.set("seen_tour", True)
        self.main.removeEventFilter(self)
        self.main.go("painel")
        cb = self.on_close
        self.deleteLater()
        if cb:
            cb()


def start(main, on_close=None) -> Tour:
    return Tour(main, on_close)
