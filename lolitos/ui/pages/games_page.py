"""Jogos: todos os jogos instalados, 'Preparar e jogar' e otimizações por jogo."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from lolitos.core import settings
from lolitos.modules import game_tweaks, gameserver, games, pcprofile
from lolitos.modules.known_games import lookup
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import TweakList
from lolitos.ui.widgets import Card, Page, ui_call, button, hrow, info, label, run_async

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


class GamesPage(Page):
    title = "Jogos"
    subtitle = ("Todos os jogos do PC (Steam, Epic, GOG, Ubisoft, EA app, Riot, Battle.net, Rockstar e outros). "
                "'Preparar e jogar' libera RAM, liga o plano de energia só durante a partida e aplica prioridade/"
                "afinidade. 'Otimizar este jogo' grava no Windows prioridade, GPU dedicada e tela cheia para o "
                "executável. Os arquivos e a memória do jogo nunca são tocados.")

    def build(self):
        self.q = QLineEdit()
        self.q.setPlaceholderText("Buscar jogo…")
        self.q.textChanged.connect(self._filter)
        self.body.addLayout(hrow(self.q, button("Atualizar lista", on_click=self.reload),
                                 button("Adicionar jogo pelo executável…", on_click=self._add), stretch_first=True))
        self.status = label("", "muted")
        self.body.addWidget(self.status)
        self.box = QVBoxLayout()
        self.box.setSpacing(10)
        self.body.addLayout(self.box)
        self.cards: list[GameCard] = []
        self.reload()

    def reload(self):
        self.status.setText("Procurando jogos…")
        run_async(games.all_games, on_done=self._show)

    def _show(self, gs):
        for c in self.cards:
            c.deleteLater()
        self.cards = []
        stores = {}
        for g in gs:
            stores[STORE.get(g.store, g.store)] = stores.get(STORE.get(g.store, g.store), 0) + 1
        self.status.setText(f"{len(gs)} jogo(s) encontrados — " + ", ".join(f"{k}: {v}" for k, v in stores.items())
                            if gs else "Nenhum jogo encontrado. Use 'Adicionar jogo pelo executável'.")
        for g in gs:
            c = GameCard(self, g)
            self.cards.append(c)
            self.box.addWidget(c)
        self._filter(self.q.text())

    def _filter(self, text):
        t = text.lower().strip()
        for c in self.cards:
            c.setVisible(not t or t in c.g.name.lower())

    def _add(self):
        exe, _ = QFileDialog.getOpenFileName(self, "Escolha o executável do jogo", "", "Executável (*.exe)")
        if exe:
            games.add_manual_game(exe)
            info(self, "Jogos", "Jogo adicionado.")
            self.reload()
