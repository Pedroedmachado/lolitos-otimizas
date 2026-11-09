"""Lista de ajustes com estado ao vivo, aplicar/desfazer individual e em lote."""
from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from lolitos.core import engine, history, restore, settings
from lolitos.core.tweaks import ADVANCED
from lolitos.ui.theme import C
from lolitos.ui.widgets import TaskDialog, TweakRow, button, confirm, hrow, info, label, run_async


def statuses(tweaks):
    return {t.id: t.status() for t in tweaks}


def bulk_apply(tweaks, progress=None, restore_point=True):
    say = progress or (lambda s: None)
    if restore_point and settings.get("restore_point_before"):
        say("Criando ponto de restauração (ou reaproveitando o das últimas 24 h)…")
        ok, msg = restore.create()
        say(f"   {msg}")
    res = engine.apply_many(tweaks, say)
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
    def __init__(self, tweaks, parent_page, search: bool = True, bulk: bool = True):
        super().__init__()
        self.page = parent_page
        self.tweaks = tweaks
        self.rows: dict[str, TweakRow] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        bar = []
        if search:
            self.q = QLineEdit()
            self.q.setPlaceholderText("Buscar ajuste por nome ou descrição…")
            self.q.textChanged.connect(self._filter)
            bar.append(self.q)
        if bulk:
            bar += [button("Marcar recomendados", on_click=self._mark_rec),
                    button("Aplicar selecionados", "primary", self._apply_selected)]
        if bar:
            lay.addLayout(hrow(*bar, stretch_first=True) if search else hrow(*bar, None))
        self.summary = label("", "muted")
        lay.addWidget(self.summary)
        for t in tweaks:
            r = TweakRow(t, self._toggle, selectable=bulk)
            self.rows[t.id] = r
            lay.addWidget(r)
        self.refresh()

    # ---------------------------------------------------------------- estado
    def refresh(self):
        run_async(statuses, self.tweaks, on_done=self._apply_states)

    def _apply_states(self, st: dict):
        blocked = history.blocked()
        on = 0
        for tid, s in st.items():
            row = self.rows.get(tid)
            if row:
                row.set_state(s, tid in blocked)
                on += s == "on"
        valid = sum(1 for s in st.values() if s != "na")
        self.summary.setText(f"{on} de {valid} ativos neste PC.")

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
