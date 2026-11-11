"""Lista de ajustes com estado ao vivo, aplicar/desfazer individual e em lote."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from lolitos.core import engine, history, restore, settings
from lolitos.core.tweaks import ADVANCED
from lolitos.ui.theme import C
from lolitos.i18n import tr
from lolitos.ui.widgets import (Badge, TaskDialog, TweakRow, button, confirm, hrow, info, label, run_async,
                                status_pool)

# larguras das colunas da tabela (marcar, nível, ajuste, o que faz, estado, ação); 0 = estica
COLS = [(26, 0), (112, 0), (0, 2), (0, 3), (118, 0), (104, 0)]
LEVEL_TXT = {"essencial": ("ESSENCIAL", "ok"), "recomendado": ("RECOMENDADO", "info"), "avancado": ("AVANÇADO", "warn")}


def _cell(h: QHBoxLayout, w, col: int, align=Qt.AlignVCenter):
    fixed, stretch = COLS[col]
    if fixed:
        w.setFixedWidth(fixed)
    h.addWidget(w, stretch, align)


def table_header() -> QFrame:
    f = QFrame()
    f.setObjectName("tablehead")
    h = QHBoxLayout(f)
    h.setContentsMargins(10, 6, 10, 6)
    h.setSpacing(12)
    for i, txt in enumerate(["", "Nível", "Ajuste", "O que faz", "Estado", "Desfazer"]):
        lb = QLabel(tr(txt))
        lb.setObjectName("th")
        _cell(h, lb, i)
    return f


class TweakTableRow(QFrame):
    """Uma linha da tabela: marcar | nível | ajuste | o que faz (e o que se perde) | estado | aplicar/desfazer.
    Mesma interface do TweakRow (t, chk, badge, btn, state, set_state)."""

    def __init__(self, tweak, on_toggle, selectable: bool = True):
        super().__init__()
        from lolitos.ui.theme import C as _C
        self.t = tweak
        self.setObjectName("listrow")
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 9, 10, 9)
        h.setSpacing(12)
        self.chk = QCheckBox(self)
        self.chk.setCursor(Qt.PointingHandCursor)
        self.chk.setVisible(selectable)
        _cell(h, self.chk, 0, Qt.AlignTop)
        txt, color = LEVEL_TXT.get(tweak.level, ("AVANÇADO", "warn"))
        lv = QLabel(tr(txt))
        lv.setAlignment(Qt.AlignCenter)
        col = _C.get(color, _C["muted"])
        lv.setStyleSheet(f"color:{col}; border:1px solid {col}; border-radius:6px; padding:2px 4px; "
                         "font-size:7.5pt; font-weight:800;")
        _cell(h, lv, 1, Qt.AlignTop)
        tags = []
        if tweak.restart:
            tags.append(tr("reinicie para valer"))
        if not tweak.reversible:
            tags.append(f"<span style='color:{_C['bad']}'>{tr('sem desfazer')}</span>")
        title = label(f"<b>{tr(tweak.title)}</b>" + (f"<br><span style='color:{_C['muted']}; font-size:8pt'>"
                                                     f"{' · '.join(tags)}</span>" if tags else ""), rich=True)
        _cell(h, title, 2, Qt.AlignTop)
        what = f"<span style='color:{_C['muted']}'>{tr(tweak.desc)}</span>"
        if tweak.loss and (tweak.level == ADVANCED or not tweak.reversible):
            what += f"<br><span style='color:{_C['warn']}'>− {tr(tweak.loss)}</span>"
        desc = label(what, rich=True)
        tip = []
        if tweak.gain:
            tip.append("+ " + tr(tweak.gain))
        if tweak.loss:
            tip.append("− " + tr(tweak.loss))
        if tip:
            desc.setToolTip("\n".join(tip))
        _cell(h, desc, 3, Qt.AlignTop)
        self.badge = Badge("loading")
        self.badge.setMinimumWidth(0)
        _cell(h, self.badge, 4, Qt.AlignTop)
        self.btn = button("Aplicar", on_click=lambda: on_toggle(self))
        _cell(h, self.btn, 5, Qt.AlignTop)
        self.state = "loading"

    def set_state(self, st: str, blocked: bool = False):
        TweakRow.set_state(self, st, blocked)


def statuses(tweaks):
    return {t.id: t.status() for t in tweaks}


def bulk_apply(tweaks, progress=None, restore_point=True, recheck=True):
    say = progress or (lambda s: None)
    if restore_point and settings.get("restore_point_before"):
        say("Criando ponto de restauração (ou reaproveitando o das últimas 24 h); pode levar alguns minutos…")
        ok, msg = restore.create()
        say(f"   {msg}" if ok else f"   não deu para criar o ponto ({msg}); seguindo mesmo assim")
    res = engine.apply_many(tweaks, say, skip_applied=recheck)
    ok = sum(1 for r in res if r.ok)
    restart = any(r.tweak.restart for r in res if r.ok)
    lines = [f"{ok} de {len(res)} ajuste(s) aplicados."]
    bad = [r for r in res if not r.ok]
    if bad:
        lines.append("Não aplicados: " + "; ".join(f"{r.tweak.title} ({r.msg or 'bloqueado'})" for r in bad[:8]))
    if restart:
        lines.append("Alguns só valem depois de reiniciar o PC.")
    return "\n".join(lines)


def confirm_advanced(parent, t) -> bool:
    if t.level != ADVANCED and t.reversible:
        return True
    txt = f"<p><b>{t.title}</b></p><p>{t.desc}</p>"
    if t.gain:
        txt += f"<p><b style='color:{C['ok']}'>O que melhora</b><br>{t.gain}</p>"
    if t.loss:
        txt += f"<p><b style='color:{C['warn']}'>O que você perde</b><br>{t.loss}</p>"
    if not t.reversible:
        txt += "<p><b>Esta alteração não tem desfazer automático.</b></p>"
    return confirm(parent, "Confirmar ajuste", txt + "<p>Aplicar?</p>", yes="Aplicar")


class TweakList(QWidget):
    def __init__(self, tweaks, parent_page, search: bool = True, bulk: bool = True, bar: bool = True,
                 on_selection=None, on_states=None, table: bool = False):
        super().__init__()
        self.page = parent_page
        self.tweaks = tweaks
        self.rows: dict[str, TweakRow] = {}
        self.states: dict[str, str] = {}
        self.on_selection = on_selection or (lambda: None)
        self.on_states = on_states or (lambda: None)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        show_bar, bar = bar, []
        if search:
            self.q = QLineEdit()
            self.q.setPlaceholderText("Buscar ajuste por nome ou descrição…")
            self.q.textChanged.connect(self._filter)
            bar.append(self.q)
        if bulk and show_bar:
            bar += [button("Marcar recomendados", on_click=self._mark_rec),
                    button("Aplicar selecionados", "primary", self._apply_selected)]
        if bar:
            lay.addLayout(hrow(*bar, stretch_first=True) if search else hrow(*bar, None))
        self.summary = label("", "muted")
        lay.addWidget(self.summary)
        if table:
            lay.setSpacing(0)
            self.summary.setVisible(False)
            lay.addWidget(table_header())
        for t in tweaks:
            r = (TweakTableRow if table else TweakRow)(t, self._toggle, selectable=bulk)
            r.chk.toggled.connect(lambda _=False: self.on_selection())
            self.rows[t.id] = r
            lay.addWidget(r)
        self.refresh()

    # ---------------------------------------------------------------- estado
    def refresh(self):
        run_async(statuses, self.tweaks, on_done=self._apply_states, _pool=status_pool())

    def _apply_states(self, st: dict):
        blocked = history.blocked()
        on = 0
        for tid, s in st.items():
            row = self.rows.get(tid)
            if row:
                row.set_state(s, tid in blocked)
                on += s == "on"
        valid = sum(1 for s in st.values() if s != "na")
        self.states = dict(st)
        self.summary.setText(f"{on} de {valid} ativos neste PC.")
        self.on_states()

    # ---------------------------------------------------------------- seleção (usada por telas com várias listas)
    def set_all(self, checked: bool, only_pending: bool = True):
        for r in self.rows.values():
            if r.chk.isEnabled() and (r.state not in ("on", "na") or not only_pending):
                r.chk.setChecked(checked)

    def mark_defaults(self):
        """Marca o que ainda não está aplicado, menos os itens avançados (como o Debloat do vídeo)."""
        for r in self.rows.values():
            if r.chk.isEnabled():
                r.chk.setChecked(r.t.level != ADVANCED and r.state in ("off", "partial"))

    def selected(self):
        return [r.t for r in self.rows.values() if r.chk.isChecked() and r.chk.isEnabled()]

    def pending(self) -> int:
        return sum(1 for s in self.states.values() if s in ("off", "partial"))

    def _filter(self, text):
        text = text.lower().strip()
        for r in self.rows.values():
            r.setVisible(not text or text in r.t.title.lower() or text in r.t.desc.lower())

    def _mark_rec(self):
        for r in self.rows.values():
            if r.chk.isEnabled() and r.isVisible():
                r.chk.setChecked(r.t.recommended_here())

    # ---------------------------------------------------------------- ações
    def _toggle(self, row: TweakRow):
        t = row.t
        if row.state == "on":
            if not history.active_for(t.id):
                info(self, "Desfazer", "Este ajuste já estava assim antes do app (ou foi aplicado por outro "
                     "programa). Não há valor anterior registrado para voltar.")
                return
            if not confirm(self, "Desfazer", f"Voltar <b>{t.title}</b> ao valor anterior?"):
                return
            row.badge.set("loading")
            run_async(engine.undo_tweak, t, on_done=lambda r: self._after(r[1] if not r[0] else ""))
            return
        if not confirm_advanced(self, t):
            return
        row.badge.set("loading")
        run_async(engine.apply_tweak, t, on_done=lambda r: self._after(r.msg if not r.ok else ""))

    def _after(self, err: str):
        if err:
            info(self, "Aviso", err)
        self.refresh()
        if self.page and getattr(self.page, "main", None):
            self.page.main.changed()

    def _apply_selected(self):
        sel = [r.t for r in self.rows.values() if r.chk.isChecked() and r.chk.isEnabled()]
        if not sel:
            info(self, "Nada selecionado", "Marque os ajustes (ou clique em 'Marcar recomendados').")
            return
        adv = [t for t in sel if t.level == ADVANCED or not t.reversible]
        if adv and not confirm(self, "Itens avançados",
                               "Você marcou itens com contrapartida:<br>• " + "<br>• ".join(t.title for t in adv)
                               + "<br><br>Continuar?"):
            return
        TaskDialog(self, f"Aplicando {len(sel)} ajuste(s)", bulk_apply, sel,
                   on_done=lambda _: self._after("")).exec()
