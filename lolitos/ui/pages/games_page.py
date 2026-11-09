"""Jogos: todos os jogos instalados, 'Preparar e jogar' e otimizações por jogo."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMenu, QVBoxLayout, QWidget)

from lolitos.core import settings
from lolitos.modules import covers, game_tweaks, gameserver, games, pcprofile
from lolitos.modules.known_games import lookup
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import TweakList
from lolitos.ui.widgets import Card, Page, button, hrow, info, label, run_async, ui_call

STORE = {"steam": "Steam", "epic": "Epic Games", "bdo": "Black Desert", "gog": "GOG", "ubisoft": "Ubisoft Connect",
         "instalado": "Programas instalados", "manual": "Adicionado por você"}


def affinity_modes() -> list[tuple[str, str]]:
    """Opções de afinidade que fazem sentido NESTE processador."""
    p = pcprofile.detect()
    out = [("", "Todos os núcleos"), ("skip0", "Fora do núcleo 0")]
    if p.hybrid and p.pcores:
        out.append(("pcores", f"Só P-cores ({len(p.pcores)} threads)"))
    if p.x3d_dual_ccd:
        out.append(("vcache", "CCD com 3D V-Cache"))
    if p.threads > p.cores:
        out.append(("physical", "Só núcleos físicos"))
    return out


def _resolve_exe(g) -> tuple[str | None, str | None]:
    """(nome do exe, caminho completo) — com cache, porque varrer a pasta do jogo pode demorar."""
    cache = settings.get("game_exe_paths", {}) or {}
    path = cache.get(g.id)
    if path and Path(path).exists():
        return Path(path).name, path
    p = games.exe_full_path(g)
    if p:
        cache[g.id] = str(p)
        settings.set("game_exe_paths", cache)
        return p.name, str(p)
    exes = games.guess_exes(g)
    return (exes[0] if exes else None), None


class GameCard(Card):
    def __init__(self, page, g):
        super().__init__(hero=g.store == "bdo")
        self.page, self.g = page, g
        self.k = lookup(g.name, g.folder, g.exes)
        opts = (settings.get("game_opts", {}) or {}).get(g.id, {})
        row = QHBoxLayout()
        col = QVBoxLayout()
        tag = f" <span style='color:{C['muted']}; font-size:8.5pt'>· anti-cheat {self.k.anticheat}</span>" \
            if self.k and self.k.anticheat else ""
        col.addWidget(label(f"<b>{g.name}</b>{tag}", rich=True))
        col.addWidget(label(f"{STORE.get(g.store, g.store)} · {g.folder}", "muted"))
        row.addLayout(col, 1)
        self.pr = QComboBox()
        self.pr.addItems(["Prioridade alta", "Acima do normal", "Normal"])
        self.pr.setCurrentIndex({"high": 0, "above": 1, "normal": 2}.get(opts.get("priority", "high"), 0))
        self.af = QComboBox()
        for key, txt in affinity_modes():
            self.af.addItem(txt, key)
        idx = self.af.findData(opts.get("affinity", ""))
        self.af.setCurrentIndex(max(0, idx))
        self.af.setToolTip("Fora do núcleo 0: o mais ocupado por drivers. Só P-cores: Intel híbrido, deixa o jogo "
                           "fora dos E-cores. CCD com V-Cache: Ryzen X3D de dois CCDs. Só físicos: sem "
                           "SMT/Hyper-Threading (frametime mais estável em alguns jogos, menos FPS em outros).")
        for w in (self.pr, self.af):
            w.currentIndexChanged.connect(self._save)
            row.addWidget(w)
        self.more = button("Otimizar este jogo ▾", on_click=self._toggle)
        row.addWidget(self.more)
        self.play = button("▶  Preparar e jogar", "primary", self._play)
        row.addWidget(self.play)
        self.lay.addLayout(row)
        self.log = label("", "muted")
        self.lay.addWidget(self.log)
        self.detail = None

    # ---------------------------------------------------------------- detalhes
    def _toggle(self):
        if self.detail is not None:
            vis = not self.detail.isVisible()
            self.detail.setVisible(vis)
            self.more.setText("Otimizar este jogo ▴" if vis else "Otimizar este jogo ▾")
            return
        self.more.setText("Procurando o executável…")
        self.more.setEnabled(False)
        run_async(_resolve_exe, self.g, on_done=self._build_detail)

    def _build_detail(self, r):
        exe, path = r
        self.more.setEnabled(True)
        self.more.setText("Otimizar este jogo ▴")
        self.detail = QWidget()
        lay = QVBoxLayout(self.detail)
        lay.setContentsMargins(0, 8, 0, 0)
        info_lines = []
        if path:
            info_lines.append(f"Executável: {path}")
        elif exe:
            info_lines.append(f"Executável: {exe} (caminho não encontrado — GPU e tela cheia ficam indisponíveis)")
        else:
            info_lines.append("Executável não identificado. Use 'Adicionar jogo pelo executável' para escolher.")
        if self.k:
            info_lines += [f"• {n}" for n in self.k.notes]
        lay.addWidget(label("<br>".join(info_lines), "muted", rich=True))
        if self.g.store == "bdo":
            lay.addLayout(hrow(button("Abrir o módulo do Black Desert", "primary",
                                      lambda: self.page.main.go("bdo")), None))
        tws = game_tweaks.tweaks_for(self.g.name, exe, path, self.g.folder)
        if tws:
            lay.addWidget(TweakList(tws, self.page, search=False))
        exes = [exe] if exe else games.guess_exes(self.g)
        self.srv = label("", rich=True)
        lay.addLayout(hrow(button("Medir o servidor (com o jogo aberto)", on_click=lambda: self._server(exes)),
                           button("Abrir pasta", on_click=lambda: os.startfile(self.g.folder)), None))
        lay.addWidget(self.srv)
        self.lay.addWidget(self.detail)

    def _server(self, exes):
        conns, udp = gameserver.connections(exes)
        if not conns:
            if gameserver.find_process(exes) is None:
                self.srv.setText("Abra o jogo, entre numa partida/mapa e clique de novo.")
            else:
                self.srv.setText("Este jogo fala com o servidor por UDP, que o Windows não mostra com o endereço. "
                                 "Use Rede › Perda de pacotes com o IP do servidor (se o jogo mostrar) ou 1.1.1.1."
                                 if udp else "Nenhuma conexão com servidor encontrada agora.")
            return
        c = conns[0]
        self.srv.setText(f"Servidor: <b>{c.ip}:{c.port}</b> — medindo 30 s…")

        def done(r):
            kind, txt = gameserver.verdict(r)
            col = {"otimo": C["ok"], "bom": C["ok"]}.get(kind, C["warn"])
            if not r.get("ok"):
                self.srv.setText(f"Servidor {c.ip}:{c.port}: {txt}")
                return
            self.srv.setText(f"Servidor <b>{c.ip}:{c.port}</b> · média <b>{r['avg']:.0f} ms</b> (mín {r['min']:.0f} / "
                             f"máx {r['max']:.0f}) · variação {r['jitter']:.1f} ms · falhas {r['lost']}/{r['n']}<br>"
                             f"<span style='color:{col}'>{txt}</span>")
        run_async(gameserver.measure, c.ip, c.port, on_done=done,
                  on_progress=lambda s: self.srv.setText(f"Servidor: <b>{c.ip}:{c.port}</b> — medindo… {s}"))

    # ---------------------------------------------------------------- jogar
    def _save(self):
        opts = settings.get("game_opts", {}) or {}
        opts[self.g.id] = {"priority": ["high", "above", "normal"][self.pr.currentIndex()],
                           "affinity": self.af.currentData() or ""}
        settings.set("game_opts", opts)

    def _play(self):
        self.play.setEnabled(False)
        main = self.page.main

        def log(s):
            ui_call(lambda: self.log.setText(s))

        def end():
            def fin():
                self.play.setEnabled(True)
                self.log.setText("Jogo fechado: plano de energia e overlay voltaram ao normal.")
            ui_call(fin)
            if main:
                ui_call(main.overlay_auto_off)

        def start(_p):
            if main:
                ui_call(main.overlay_auto_on)

        games.Session(self.g, log, start, end).start()


# ===================================================================== capas
TILE_W, TILE_H = 168, 252          # proporção 2:3 da arte vertical
_COVER_POOL = None


def _cover_pool():
    from PySide6.QtCore import QThreadPool
    global _COVER_POOL
    if _COVER_POOL is None:
        _COVER_POOL = QThreadPool()
        _COVER_POOL.setMaxThreadCount(3)
    return _COVER_POOL


class Poster(QWidget):
    """Capa do jogo: arte vertical com cantos arredondados, nome embaixo e botão de jogar ao passar o mouse."""

    def __init__(self, page, g):
        super().__init__()
        self.page, self.g = page, g
        self.pix: QPixmap | None = None
        self.hover = False
        self.setFixedSize(TILE_W, TILE_H + 46)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setToolTip(f"{g.name}\n{STORE.get(g.store, g.store)}\nClique: opções do jogo · botão direito: mais")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        hit = covers.cached(g.id)
        if hit:
            self.set_cover(hit)

    def set_cover(self, path):
        pm = QPixmap(str(path))
        if pm.isNull():
            return
        # recorta no centro para 2:3 (banners horizontais também ficam bem)
        target = TILE_W / TILE_H
        w, h = pm.width(), pm.height()
        if w / h > target:
            nw = int(h * target)
            pm = pm.copy((w - nw) // 2, 0, nw, h)
        else:
            nh = int(w / target)
            pm = pm.copy(0, (h - nh) // 2, w, nh)
        dpr = self.devicePixelRatioF() or 1
        self.pix = pm.scaled(int(TILE_W * dpr), int(TILE_H * dpr), Qt.KeepAspectRatioByExpanding,
                             Qt.SmoothTransformation)
        self.pix.setDevicePixelRatio(dpr)
        self.update()

    # ---------------------------------------------------------------- desenho
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(1, 1, TILE_W - 2, TILE_H - 2)
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.setClipPath(path)
        if self.pix:
            p.drawPixmap(r.toRect(), self.pix)
        else:
            g = QLinearGradient(0, 0, 0, TILE_H)
            g.setColorAt(0, QColor(C["panel2"]))
            g.setColorAt(1, QColor(C["bg"]))
            p.fillRect(r, g)
            ini = "".join(w[0] for w in self.g.name.split()[:2] if w[:1].isalnum()).upper() or "?"
            p.setPen(QColor(C["accent2"]))
            p.setFont(QFont("Segoe UI", 30, QFont.Bold))
            p.drawText(r, Qt.AlignCenter, ini)
        if self.hover:
            p.fillRect(r, QColor(0, 0, 0, 90))
            br = QRectF(TILE_W / 2 - 26, TILE_H / 2 - 26, 52, 52)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["accent"]))
            p.drawEllipse(br)
            tri = QPainterPath()
            cx, cy = br.center().x() + 3, br.center().y()
            tri.moveTo(cx - 9, cy - 12)
            tri.lineTo(cx + 12, cy)
            tri.lineTo(cx - 9, cy + 12)
            tri.closeSubpath()
            p.fillPath(tri, QColor("#ffffff"))
        p.setClipping(False)
        p.setBrush(Qt.NoBrush)
        p.setPen(QColor(C["accent"] if self.hover else C["border"]))
        p.drawRoundedRect(r, 10, 10)
        if self.g.store == "bdo" or self.g.name.lower().startswith("black desert"):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["gold"]))
            p.drawRoundedRect(QRectF(8, 8, 46, 18), 5, 5)
            p.setPen(QColor("#1a1200"))
            p.setFont(QFont("Segoe UI", 7, QFont.Bold))
            p.drawText(QRectF(8, 8, 46, 18), Qt.AlignCenter, "BDO")
        p.setPen(QColor(C["text"]))
        f = QFont("Segoe UI", 9, QFont.DemiBold)
        p.setFont(f)
        name = p.fontMetrics().elidedText(self.g.name, Qt.ElideRight, TILE_W - 4)
        p.drawText(QRectF(2, TILE_H + 6, TILE_W - 4, 18), Qt.AlignLeft | Qt.AlignVCenter, name)
        p.setPen(QColor(C["muted"]))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(2, TILE_H + 24, TILE_W - 4, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   STORE.get(self.g.store, self.g.store))

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        play = QRectF(TILE_W / 2 - 30, TILE_H / 2 - 30, 60, 60).contains(e.position())
        self.page.open_game(self.g, play=play)

    def _menu(self, pos):
        m = QMenu(self)
        m.addAction("Opções do jogo", lambda: self.page.open_game(self.g))
        m.addAction("▶  Preparar e jogar", lambda: self.page.open_game(self.g, play=True))
        m.addSeparator()
        m.addAction("Escolher capa…", self._choose)
        m.addAction("Buscar capa de novo", self._refetch)
        m.addAction("Abrir pasta", lambda: os.startfile(self.g.folder) if os.path.isdir(self.g.folder) else None)
        m.exec(self.mapToGlobal(pos))

    def _choose(self):
        img, _ = QFileDialog.getOpenFileName(self, "Capa do jogo", "", "Imagem (*.jpg *.jpeg *.png)")
        if img:
            self.set_cover(covers.set_custom(self.g.id, img))

    def _refetch(self):
        for ext in (".jpg", ".png"):
            (covers.cover_dir() / (covers._safe(self.g.id) + ext)).unlink(missing_ok=True)
        m = covers._misses()
        m.pop(self.g.id, None)
        (covers.cover_dir() / "misses.json").write_text(__import__("json").dumps(m), encoding="utf-8")
        self.pix = None
        self.update()
        run_async(covers.fetch, self.g, on_done=lambda p: p and self.set_cover(p), _pool=_cover_pool())


class GameDialog(QDialog):
    """Opções de um jogo: capa grande + prioridade, afinidade, otimizar e jogar."""

    def __init__(self, page, g):
        super().__init__(page)
        self.setWindowTitle(g.name)
        self.resize(980, 560)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(18)
        cover = QLabel()
        cover.setFixedSize(220, 330)
        hit = covers.cached(g.id)
        if hit:
            pm = QPixmap(str(hit))
            if not pm.isNull():
                cover.setPixmap(pm.scaled(220, 330, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        cover.setStyleSheet(f"border-radius:10px; background:{C['panel2']};")
        cover.setAlignment(Qt.AlignCenter)
        if not hit:
            cover.setText(g.name)
            cover.setWordWrap(True)
        col = QVBoxLayout()
        col.addWidget(cover)
        col.addStretch()
        lay.addLayout(col)
        from PySide6.QtWidgets import QScrollArea
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("gamedlg")
        sc.setStyleSheet(f"QScrollArea, QWidget#gamedlg {{ background: {C['bg']}; border: none; }}")
        self.setStyleSheet(f"QDialog {{ background: {C['bg']}; }}")
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        self.card = GameCard(page, g)
        il.addWidget(self.card)
        il.addStretch()
        sc.setWidget(inner)
        lay.addWidget(sc, 1)
        from lolitos.i18n import translate_tree
        translate_tree(self)


class GamesPage(Page):
    title = "Jogos"
    subtitle = ("Todos os jogos do PC (Steam, Epic, GOG, Ubisoft, EA app, Riot, Battle.net, Rockstar e outros). "
                "Clique na capa para as opções do jogo; o botão ▶ faz 'Preparar e jogar': libera RAM, liga o plano "
                "de energia só durante a partida e aplica prioridade/afinidade. Os arquivos e a memória do jogo nunca "
                "são tocados.")

    def build(self):
        self.q = QLineEdit()
        self.q.setPlaceholderText("Buscar jogo…")
        self.q.textChanged.connect(self._filter)
        self.store = QComboBox()
        self.store.addItem("Todas as lojas", "")
        self.store.currentIndexChanged.connect(lambda: self._filter(self.q.text()))
        self.body.addLayout(hrow(self.q, self.store, button("Atualizar lista", on_click=self.reload),
                                 button("Adicionar jogo pelo executável…", on_click=self._add), stretch_first=True))
        self.status = label("", "muted")
        self.body.addWidget(self.status)
        self.grid_w = QWidget()
        self.grid = QGridLayout(self.grid_w)
        self.grid.setContentsMargins(0, 4, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(18)
        self.grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.body.addWidget(self.grid_w)
        self.tiles: list[Poster] = []
        self._cols = 0
        self.reload()

    def reload(self):
        self.status.setText("Procurando jogos…")
        run_async(games.all_games, on_done=self._show)

    def _show(self, gs):
        for t in self.tiles:
            t.deleteLater()
        self.tiles = []
        stores = {}
        for g in gs:
            stores[g.store] = stores.get(g.store, 0) + 1
        self.status.setText(f"{len(gs)} jogo(s) encontrados — " +
                            ", ".join(f"{STORE.get(k, k)}: {v}" for k, v in stores.items())
                            if gs else "Nenhum jogo encontrado. Use 'Adicionar jogo pelo executável'.")
        cur = self.store.currentData()
        self.store.blockSignals(True)
        self.store.clear()
        self.store.addItem("Todas as lojas", "")
        for k in stores:
            self.store.addItem(STORE.get(k, k), k)
        self.store.setCurrentIndex(max(0, self.store.findData(cur)))
        self.store.blockSignals(False)
        # Black Desert primeiro, depois em ordem alfabética
        gs = sorted(gs, key=lambda g: (not (g.store == "bdo" or g.name.lower().startswith("black desert")),
                                       g.name.lower()))
        for g in gs:
            self.tiles.append(Poster(self, g))
        self._filter(self.q.text())
        missing = [t for t in self.tiles if t.pix is None]
        for t in missing:
            run_async(covers.fetch, t.g, on_done=lambda p, tt=t: p and tt.set_cover(p), _pool=_cover_pool())

    def _layout(self, force=False):
        """Recoloca as capas na grade conforme a largura (só quando o número de colunas muda)."""
        avail = self.grid_w.width() if self.grid_w.width() > 100 else self.width() - 80
        cols = max(1, (avail + 16) // (TILE_W + 16))
        if cols == self._cols and not force:
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        shown = [t for t in self.tiles if t.property("show") is not False]
        for i, t in enumerate(shown):
            self.grid.addWidget(t, i // cols, i % cols)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if getattr(self, "tiles", None):
            self._layout()

    def _filter(self, text):
        t = text.lower().strip()
        st = self.store.currentData() if hasattr(self, "store") else ""
        for p in self.tiles:
            ok = (not t or t in p.g.name.lower()) and (not st or p.g.store == st)
            p.setProperty("show", ok)
            p.setVisible(ok)
        self._layout(force=True)

    def open_game(self, g, play=False):
        d = GameDialog(self, g)
        if play:
            d.card._play()
        d.exec()

    def _add(self):
        exe, _ = QFileDialog.getOpenFileName(self, "Escolha o executável do jogo", "", "Executável (*.exe)")
        if exe:
            games.add_manual_game(exe)
            info(self, "Jogos", "Jogo adicionado.")
            self.reload()
