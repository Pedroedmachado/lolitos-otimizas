"""Grade de programas (Formatação e Instalar apps): blocos com ícone, filtros em botões por categoria,
instalados marcados com um ponto verde e seleção por clique."""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QGridLayout, QLayout, QPushButton, QVBoxLayout, QWidget

from lolitos.i18n import tr
from lolitos.modules import appicons
from lolitos.ui.theme import C
from lolitos.ui.widgets import label, run_async

TILE_W, TILE_H = 240, 54
MIN_W = 220
CATEGORY_PT = {
    "Essentials": "Essenciais para jogos", "Browsers": "Navegadores", "Communications": "Comunicação",
    "Development": "Desenvolvimento", "Document": "Documentos", "Games": "Jogos",
    "Microsoft Tools": "Ferramentas Microsoft", "Multimedia Tools": "Multimídia", "Pro Tools": "Ferramentas Pro",
    "Utilities": "Utilitários", "Selfhosted Tools": "Auto-hospedados", "Hardware": "Hardware e periféricos",
}
ORDER = ["Essentials", "Games", "Browsers", "Communications", "Hardware", "Multimedia Tools", "Utilities",
         "Pro Tools", "Microsoft Tools", "Document", "Development", "Selfhosted Tools"]

_ICON_POOL = None


def _pool():
    global _ICON_POOL
    if _ICON_POOL is None:
        _ICON_POOL = QThreadPool()
        _ICON_POOL.setMaxThreadCount(4)
    return _ICON_POOL


class FlowLayout(QLayout):
    """Itens em linha que quebram para a próxima quando acaba a largura (botões de filtro)."""

    def __init__(self, spacing=8):
        super().__init__()
        self.items = []
        self.sp = spacing

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, i):
        return self.items[i] if 0 <= i < len(self.items) else None

    def takeAt(self, i):
        return self.items.pop(i) if 0 <= i < len(self.items) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._do(r, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self.items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, r, test):
        x, y, line = r.x(), r.y(), 0
        for it in self.items:
            hint = it.sizeHint()
            if x + hint.width() > r.right() and line > 0:
                x, y, line = r.x(), y + line + self.sp, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self.sp
            line = max(line, hint.height())
        return y + line - r.y()


class AppTile(QWidget):
    toggled = Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.selected = False
        self.installed = False
        self.hover = False
        self.pix: QPixmap | None = None
        self.setFixedSize(TILE_W, TILE_H)
        self.tw = TILE_W
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{app.name}\n{app.desc[:220]}\n{app.winget}\n" + tr("Clique direito: abrir o site oficial"))
        hit = appicons.cached(app.winget)
        if hit:
            self.set_icon(hit)

    def set_icon(self, path):
        pm = QPixmap(str(path))
        if not pm.isNull():
            dpr = self.devicePixelRatioF() or 1
            self.pix = pm.scaled(int(26 * dpr), int(26 * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.pix.setDevicePixelRatio(dpr)
            self.update()

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.selected = not self.selected
            self.update()
            self.toggled.emit()
        elif e.button() == Qt.RightButton and self.app.link:
            webbrowser.open(self.app.link)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W = self.width()
        r = QRectF(1, 1, W - 2, TILE_H - 2)
        bg = QColor(C["deepbg"] if self.selected else (C["panel2"] if self.hover else C["panel"]))
        p.setBrush(bg)
        p.setPen(QColor(C["accent"] if self.selected else (C["border2"] if self.hover else C["border"])))
        p.drawRoundedRect(r, 10, 10)
        ic = QRectF(14, (TILE_H - 26) / 2, 26, 26)
        if self.pix:
            path = QPainterPath()
            path.addRoundedRect(ic, 6, 6)
            p.save()
            p.setClipPath(path)
            p.drawPixmap(ic.toRect(), self.pix)
            p.restore()
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["panel2"] if not self.hover else C["border2"]))
            p.drawRoundedRect(ic, 6, 6)
            p.setPen(QColor(C["accent2"]))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            p.drawText(ic, Qt.AlignCenter, (self.app.name[:1] or "?").upper())
        right = W - 14
        if self.installed:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["ok"]))
            p.drawEllipse(QRectF(right - 8, TILE_H / 2 - 4, 8, 8))
            right -= 16
        if self.selected:
            p.setPen(QColor(C["accent2"]))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            p.drawText(QRectF(right - 16, 0, 16, TILE_H), Qt.AlignCenter, "✓")
            right -= 20
        p.setPen(QColor(C["text"]))
        f = QFont("Segoe UI", 9)
        f.setBold(True)
        p.setFont(f)
        name = p.fontMetrics().elidedText(self.app.name, Qt.ElideRight, int(right - 52))
        p.drawText(QRectF(50, 0, right - 50, TILE_H), Qt.AlignVCenter | Qt.AlignLeft, name)


class AppGrid(QWidget):
    """Seções por categoria com filtro por texto e por botão."""
    changed = Signal()

    def __init__(self, apps, defaults=()):
        super().__init__()
        self.tiles: list[AppTile] = []
        self.sections: list[tuple[str, QWidget, QGridLayout, list[AppTile]]] = []
        self.chip = ""          # "", "@installed", "@selected", "@foss" ou categoria
        self.text = ""
        self._cols = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        groups: dict[str, list] = {}
        for a in apps:
            groups.setdefault(a.category, []).append(a)
        cats = sorted(groups, key=lambda c: (ORDER.index(c) if c in ORDER else 99, c))
        self.categories = cats
        for cat in cats:
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 8, 0, 0)
            bl.setSpacing(8)
            bl.addWidget(label(CATEGORY_PT.get(cat, cat), "h2"))
            gw = QWidget()
            grid = QGridLayout(gw)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(10)
            grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            bl.addWidget(gw)
            tl = []
            for a in sorted(groups[cat], key=lambda x: x.name.lower()):
                t = AppTile(a)
                t.selected = a.winget in defaults
                t.toggled.connect(self.changed.emit)
                tl.append(t)
                self.tiles.append(t)
            self.sections.append((cat, box, grid, tl))
            lay.addWidget(box)
        for t in self.tiles:
            if t.pix is None:
                run_async(appicons.fetch, t.app.winget, t.app.link,
                          on_done=lambda pth, tt=t: pth and tt.set_icon(pth), _pool=_pool())

    # ---------------------------------------------------------------- estado
    def selected(self) -> list[str]:
        seen, out = set(), []
        for t in self.tiles:
            if t.selected and t.app.winget not in seen:
                seen.add(t.app.winget)
                out.append(t.app.winget)
        return out

    def set_selected(self, ids):
        ids = set(ids)
        for t in self.tiles:
            t.selected = t.app.winget in ids
            t.update()
        self.changed.emit()
        self.apply_filter()

    def mark_installed(self, ids):
        ids = {i.lower() for i in ids}
        for t in self.tiles:
            t.installed = t.app.winget.lower() in ids
            t.update()
        self.apply_filter()

    # ---------------------------------------------------------------- filtro e grade
    def set_filter(self, text=None, chip=None):
        if text is not None:
            self.text = text.lower().strip()
        if chip is not None:
            self.chip = chip
        self.apply_filter()

    def _visible(self, t: AppTile) -> bool:
        a = t.app
        if self.text and self.text not in a.name.lower() and self.text not in a.winget.lower():
            return False
        if self.chip == "@installed":
            return t.installed
        if self.chip == "@selected":
            return t.selected
        if self.chip == "@foss":
            return a.foss
        return not self.chip or a.category == self.chip

    def apply_filter(self):
        self._cols = 0
        self._relayout()

    def _relayout(self):
        w = self.width() if self.width() > 300 else 1400
        cols = max(1, (w + 10) // (MIN_W + 10))
        tw = int((w - 10 * (cols - 1)) / cols)
        if cols == self._cols and tw == getattr(self, "_tw", 0):
            return
        self._cols, self._tw = cols, tw
        for t in self.tiles:
            t.setFixedWidth(tw)
        for cat, box, grid, tl in self.sections:
            while grid.count():
                grid.takeAt(0)
            vis = [t for t in tl if self._visible(t)]
            for t in tl:
                t.setVisible(t in vis)
            for i, t in enumerate(vis):
                grid.addWidget(t, i // cols, i % cols)
            box.setVisible(bool(vis))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()


def chip_bar(grid: AppGrid, on_change=None) -> QWidget:
    """Botões de filtro: Todos, Instalados, Selecionados, Código aberto e uma por categoria."""
    w = QWidget()
    fl = FlowLayout(8)
    w.setLayout(fl)
    buttons = []

    def pick(key, btn):
        for b in buttons:
            b.setChecked(b is btn)
        grid.set_filter(chip=key)
        if on_change:
            on_change()
    items = [("", "Todos"), ("@installed", "● Instalados"), ("@selected", "Selecionados"), ("@foss", "Código aberto")]
    items += [(c, CATEGORY_PT.get(c, c)) for c in grid.categories]
    for key, text in items:
        b = QPushButton(tr(text))
        b.setObjectName("chip")
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setChecked(key == "")
        b.clicked.connect(lambda _=False, k=key, bb=b: pick(k, bb))
        buttons.append(b)
        fl.addWidget(b)
    return w
