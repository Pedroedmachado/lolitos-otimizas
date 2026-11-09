"""Ajustes em cartões com chave liga/desliga (telas Windows, Mouse, Teclado e GPU).

Cada cartão: selos (★ RECOMENDADO, REINICIA, AVANÇADO), título, o que muda, o aviso 'Evite…' quando há
contrapartida, o estado lido do Windows e a chave. Ligar aplica; desligar desfaz pelo histórico."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from lolitos.core import engine, history
from lolitos.core.tweaks import ADVANCED
from lolitos.i18n import tr
from lolitos.ui.appgrid import FlowLayout
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import bulk_apply, confirm_advanced, statuses
from lolitos.ui.widgets import TaskDialog, Toggle, button, confirm, info, label, pill, run_async, status_pool

CARD_MIN = 250


class TweakCard(QFrame):
    def __init__(self, grid, t, parent=None):
        super().__init__(parent)
        self.grid, self.t = grid, t
        self.state = ""
        rec = t.recommended_here()
        self.setObjectName("tcardrec" if rec else "tcard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(6)
        tags = QHBoxLayout()
        tags.setSpacing(6)
        if rec:
            tags.addWidget(label("★ RECOMENDADO", "tagrec", wrap=False))
        if t.restart:
            tags.addWidget(label("REINICIA", "tagrestart", wrap=False))
        if t.level == ADVANCED:
            tags.addWidget(label("AVANÇADO", "tagadv", wrap=False))
        if tags.count():
            tags.addStretch()
            lay.addLayout(tags)
        lay.addWidget(label(tr(t.title), "tctitle"))
        lay.addWidget(label(tr(t.desc), "muted"))
        if t.loss:
            lay.addWidget(label(f"⚠  {tr('Evite se')}: {tr(t.loss)}" if not t.loss.lower().startswith("evite")
                                else f"⚠  {tr(t.loss)}", "tcwarn"))
        lay.addStretch()
        foot = QHBoxLayout()
        self.st = label("…", "muted", wrap=False)
        foot.addWidget(self.st)
        foot.addStretch()
        self.sw = Toggle(False)
        self.sw.clicked.connect(self._clicked)
        foot.addWidget(self.sw)
        lay.addLayout(foot)
        tip = []
        if t.gain:
            tip.append("+ " + tr(t.gain))
        if t.loss:
            tip.append("− " + tr(t.loss))
        if tip:
            self.setToolTip("\n".join(tip))

    def set_state(self, st: str, blocked: bool):
        self.state = st
        self.sw.blockSignals(True)
        self.sw.setChecked(st == "on")
        self.sw.blockSignals(False)
        self.sw.setEnabled(st != "na")
        txt, col = {"on": ("Ativo", C["ok"]), "na": ("Não se aplica a este PC", C["muted"]),
                    "partial": ("Parcial", C["gold"])}.get(st, ("Inativo", C["muted"]))
        if blocked and st != "on":
            txt, col = "Bloqueado pelo antivírus", C["bad"]
        self.st.setText(tr(txt))
        self.st.setStyleSheet(f"color:{col};")
        self.sw.update()

    def busy(self, txt: str):
        self.sw.setEnabled(False)
        self.st.setText(tr(txt))
        self.st.setStyleSheet(f"color:{C['accent2']};")

    def _clicked(self):
        t = self.t
        want_on = self.sw.isChecked()
        if not want_on:
            if not history.active_for(t.id):
                self.set_state(self.state, False)
                info(self, "Desfazer", "Este ajuste já estava assim antes do app (ou foi aplicado por outro "
                                       "programa). Não há valor anterior registrado para voltar.")
                return
            self.busy("Desfazendo…")
            run_async(engine.undo_tweak, t, on_done=lambda r: self.grid.after(r[1] if not r[0] else ""))
            return
        if not confirm_advanced(self, t):
            self.set_state(self.state, False)
            return
        self.busy("Aplicando…")
        run_async(engine.apply_tweak, t, on_done=lambda r: self.grid.after(r.msg if not r.ok else ""))


class TweakGrid(QWidget):
    """Busca + filtros + cartões. `groups` = [(rótulo, {categorias})] para os botões de filtro."""

    def __init__(self, tweaks, page, groups=(), header=None, profile=True):
        super().__init__()
        self.page = page
        rec = [t for t in tweaks if t.recommended_here()]
        rest = [t for t in tweaks if not t.recommended_here()]
        self.tweaks = rec + rest
        self.cards: dict[str, TweakCard] = {}
        self.filter_key, self.text = "", ""
        self._cols = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        # cabeçalho da página: contador + aplicar recomendados
        self.count = pill("…")
        if header is not None:
            header.addWidget(self.count, 0, Qt.AlignVCenter)
            header.addWidget(button("Aplicar recomendados", "primary", self.apply_recommended), 0, Qt.AlignVCenter)
        top = QHBoxLayout()
        self.q = QLineEdit()
        self.q.setPlaceholderText("Buscar ajustes por nome ou descrição…")
        self.q.textChanged.connect(self._search)
        top.addWidget(self.q, 3)
        if profile:
            self.pname = QLineEdit()
            self.pname.setPlaceholderText("Nome do perfil com os ajustes ativos…")
            top.addWidget(self.pname, 2)
            top.addWidget(button("Salvar perfil", on_click=self._save_profile))
        lay.addLayout(top)
        chips = QWidget()
        fl = FlowLayout(8)
        chips.setLayout(fl)
        self.chip_btns = []
        items = [("", "Todos"), ("@rec", "★ Recomendados"), ("@on", "Ativos")] + [(lbl, lbl) for lbl, _ in groups]
        self.groups = dict(groups)
        if len(items) > 3 or groups:
            for key, txt in items:
                b = QPushButton(tr(txt))
                b.setObjectName("chip")
                b.setCheckable(True)
                b.setChecked(key == "")
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _=False, k=key, bb=b: self._chip(k, bb))
                self.chip_btns.append(b)
                fl.addWidget(b)
            lay.addWidget(chips)
        self.gw = QWidget()
        self.grid = QGridLayout(self.gw)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(14)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        for t in self.tweaks:
            c = TweakCard(self, t, self.gw)
            c.hide()
            self.cards[t.id] = c
        lay.addWidget(self.gw)
        self.empty = label("Nenhum ajuste com esse filtro.", "muted")
        self.empty.hide()
        lay.addWidget(self.empty)
        self.states: dict[str, str] = {}
        self.refresh()

    # ---------------------------------------------------------------- estado
    def refresh(self):
        run_async(statuses, self.tweaks, on_done=self._states, _pool=status_pool())

    def _states(self, st: dict):
        self.states = st
        blocked = history.blocked()
        for tid, s in st.items():
            c = self.cards.get(tid)
            if c:
                c.set_state(s, tid in blocked)
        on = sum(1 for s in st.values() if s == "on")
        valid = sum(1 for s in st.values() if s != "na")
        self.count.setText(tr("{} de {} ativos").replace("{}", str(on), 1).replace("{}", str(valid), 1))
        if self.filter_key == "@on":
            self._relayout(True)

    def after(self, err: str):
        if err:
            info(self, "Aviso", err)
        self.refresh()
        if self.page is not None and getattr(self.page, "main", None):
            self.page.main.changed()

    # ---------------------------------------------------------------- filtro e grade
    def _chip(self, key, btn):
        for b in self.chip_btns:
            b.setChecked(b is btn)
        self.filter_key = key
        self._relayout(True)

    def _search(self, text):
        self.text = text.lower().strip()
        self._relayout(True)

    def _visible(self, t) -> bool:
        if self.text and self.text not in t.title.lower() and self.text not in t.desc.lower() \
                and self.text not in tr(t.title).lower():
            return False
        k = self.filter_key
        if k == "@rec":
            return t.recommended_here()
        if k == "@on":
            return self.states.get(t.id) == "on"
        if k in self.groups:
            return t.cat in self.groups[k]
        return True

    def _relayout(self, force=False):
        w = self.gw.width() if self.gw.width() > 300 else max(600, self.width())
        cols = max(1, (w + 14) // (CARD_MIN + 14))
        cw = int((w - 14 * (cols - 1)) / cols) - 1
        if not force and cols == self._cols and cw == getattr(self, "_cw", 0):
            return
        self._cols, self._cw = cols, cw
        while self.grid.count():
            self.grid.takeAt(0)
        vis = [t for t in self.tweaks if self._visible(t)]
        for t in self.tweaks:
            c = self.cards[t.id]
            c.setFixedWidth(cw)
            c.setVisible(False)
        for i, t in enumerate(vis):
            c = self.cards[t.id]
            self.grid.addWidget(c, i // cols, i % cols)
            c.setVisible(True)
        self.empty.setVisible(not vis)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def showEvent(self, e):
        super().showEvent(e)
        self._relayout(True)

    # ---------------------------------------------------------------- ações
    def apply_recommended(self):
        pend = [t for t in self.tweaks if t.recommended_here() and self.states.get(t.id) not in ("on", "na")]
        if not pend:
            info(self, "Aplicar recomendados", "Todos os ajustes recomendados para este PC já estão ativos.")
            return
        if not confirm(self, "Aplicar recomendados", tr("Aplicar {} ajuste(s) recomendados para este PC?")
                       .replace("{}", str(len(pend))) + "<br>• " + "<br>• ".join(tr(t.title) for t in pend[:12])
                       + ("<br>…" if len(pend) > 12 else ""), yes="Aplicar"):
            return
        TaskDialog(self, "Aplicando recomendados", bulk_apply, pend, on_done=lambda _: self.after("")).exec()

    def _save_profile(self):
        from lolitos.catalog.presets import upsert_profile
        name = self.pname.text().strip()
        if not name:
            info(self, "Salvar perfil", "Dê um nome ao perfil.")
            return
        ids = [tid for tid, s in self.states.items() if s == "on"]
        upsert_profile(name, ids)
        self.pname.clear()
        info(self, "Salvar perfil", tr("Perfil '{}' salvo com {} ajuste(s). Ele aparece em Perfis.")
             .replace("{}", name, 1).replace("{}", str(len(ids)), 1))
