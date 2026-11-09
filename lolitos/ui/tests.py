"""Teste de polling do mouse e teste de monitor (cores + movimento) em tela cheia."""
from __future__ import annotations

import statistics
import time

from PySide6.QtCore import QElapsedTimer, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QVBoxLayout, QWidget


class _Pad(QFrame):
    def __init__(self, on_move):
        super().__init__()
        self.setMouseTracking(True)
        self.setMinimumSize(520, 320)
        self.setStyleSheet("background:#0a1526; border:1px dashed #1d3d6b; border-radius:10px;")
        self.on_move = on_move

    def mouseMoveEvent(self, e):
        self.on_move(time.perf_counter())


class MouseTest(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Teste do mouse")
        lay = QVBoxLayout(self)
        self.out = QLabel("Faça círculos rápidos aqui dentro…")
        self.out.setStyleSheet("font-size:16pt; font-weight:700;")
        lay.addWidget(_Pad(self._move))
        lay.addWidget(self.out)
        lay.addWidget(QLabel("Movimento em linha reta mede o seu braço, não o mouse. Resultado aproximado: o Windows "
                             "pode agrupar eventos; o valor real costuma ser o pico estável."))
        self.ts: list[float] = []
        self.best = 0.0
        t = QTimer(self)
        t.timeout.connect(self._calc)
        t.start(300)

    def _move(self, t):
        self.ts.append(t)
        if len(self.ts) > 3000:
            self.ts = self.ts[-3000:]

    def _calc(self):
        now = time.perf_counter()
        recent = [t for t in self.ts if now - t < 0.6]
        if len(recent) < 20:
            return
        gaps = [b - a for a, b in zip(recent, recent[1:]) if 0 < b - a < 0.05]
        if not gaps:
            return
        hz = 1 / statistics.median(gaps)
        self.best = max(self.best, hz)
        verdict = ("excelente (1000 Hz ou mais)" if self.best >= 900 else "bom (500 Hz)" if self.best >= 450
                   else "baixo para jogos — veja no software do mouse se dá para subir")
        self.out.setText(f"{hz:.0f} Hz agora · pico {self.best:.0f} Hz · {verdict}")


class MonitorTest(QWidget):
    COLORS = [("Branco", "#ffffff"), ("Preto total (vazamento de luz)", "#000000"), ("Vermelho", "#ff0000"),
              ("Verde", "#00ff00"), ("Azul", "#0000ff"), ("Cinza 50%", "#808080"), ("Cinza 18%", "#2e2e2e")]

    def __init__(self, mode="colors"):
        super().__init__()
        self.setWindowTitle("Teste de monitor")
        self.mode = mode
        self.i = 0
        self.x = 0.0
        self.speed = 960.0
        self.timer = QElapsedTimer()
        self.timer.start()
        self.last = 0
        self.frames: list[float] = []
        self.setCursor(Qt.BlankCursor)
        if mode == "motion":
            t = QTimer(self)
            t.setTimerType(Qt.PreciseTimer)
            t.timeout.connect(self.update)
            t.start(0)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape:
            self.close()
        elif k in (Qt.Key_Right, Qt.Key_Space) and self.mode == "colors":
            self.i = (self.i + 1) % (len(self.COLORS) + 1)
            self.update()
        elif k == Qt.Key_Left and self.mode == "colors":
            self.i = (self.i - 1) % (len(self.COLORS) + 1)
            self.update()
        elif k == Qt.Key_Up:
            self.speed = min(3840, self.speed + 240)
        elif k == Qt.Key_Down:
            self.speed = max(240, self.speed - 240)

    def mousePressEvent(self, e):
        if self.mode == "colors":
            self.i = (self.i + 1) % (len(self.COLORS) + 1)
            self.update()

    def mouseDoubleClickEvent(self, e):
        self.close()

    def paintEvent(self, _):
        p = QPainter(self)
        if self.mode == "colors":
            if self.i < len(self.COLORS):
                name, col = self.COLORS[self.i]
                p.fillRect(self.rect(), QColor(col))
            else:  # degraus de preto 0..20
                name = "Degraus de preto (0 a 20 de 255)"
                w = self.width() / 21
                for v in range(21):
                    p.fillRect(QRectF(v * w, 0, w + 1, self.height()), QColor(v, v, v))
            p.setPen(QColor("#888888"))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(20, self.height() - 20, f"{name} · clique ou → próximo · ← anterior · Esc sai")
            return
        # movimento
        now = self.timer.nsecsElapsed() / 1e9
        dt = now - self.last if self.last else 0
        self.last = now
        if dt:
            self.frames.append(dt)
            self.frames = self.frames[-240:]
        self.x = (self.x + self.speed * dt) % (self.width() + 120)
        p.fillRect(self.rect(), QColor("#9a9a9a"))
        h = self.height()
        for row, frac in enumerate((1, 2, 4)):
            y = h * (0.2 + row * 0.25)
            x = (self.x // frac) * frac if frac > 1 else self.x
            p.fillRect(QRectF(x - 120, y, 120, 80), QColor("#101010"))
            p.fillRect(QRectF(x - 100, y + 20, 30, 40), QColor("#ffffff"))
        fps = 1 / statistics.mean(self.frames) if self.frames else 0
        p.setPen(QColor("#101010"))
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.drawText(20, 30, f"{fps:.0f} quadros/s · {self.speed:.0f} px/s · {self.speed / max(fps, 1):.1f} px por "
                           f"quadro · ↑/↓ velocidade · Esc sai")
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(20, 52, "Siga o objeto com os olhos: rastro escuro atrás = ghosting (painel lento); contorno claro = "
                           "overdrive forte demais. Quadros/s igual ao Hz do monitor = teste sincronizado.")
