"""Aplicar e desfazer ajustes, registrando tudo no histórico."""
from __future__ import annotations

import logging
from typing import Callable, Iterable

from lolitos.core import history
from lolitos.core.actions import ActionError, BlockedError
from lolitos.core.system import run
from lolitos.core.tweaks import CATALOG, CATS, Tweak

log = logging.getLogger("lolitos.engine")

Progress = Callable[[str], None]


class ApplyResult:
    def __init__(self, tweak: Tweak, ok: bool, msg: str = "", blocked: bool = False):
        self.tweak, self.ok, self.msg, self.blocked = tweak, ok, msg, blocked


def apply_tweak(t: Tweak, progress: Progress | None = None) -> ApplyResult:
    say = progress or (lambda s: None)
    say(f"Aplicando: {t.title}")
    snaps, errors, blocked = [], [], False
    for idx, a in enumerate(t.actions):
        try:
            if not a.applicable():
                snaps.append({"i": idx, "skip": True})
                continue
            snap = a.capture()
            a.apply()
            snaps.append({"i": idx, "snap": snap})
        except BlockedError as e:
            blocked = True
            errors.append(str(e))
        except ActionError as e:
            errors.append(str(e))
        except Exception as e:  # noqa: BLE001 — nunca derrubar o app por um ajuste
            log.exception("erro inesperado em %s", t.id)
            errors.append(f"{a.describe()}: {e}")
    applied = [s for s in snaps if "snap" in s]
    ok = bool(applied) and not errors
    if applied:
        history.add("tweak", t.title, CATS.get(t.cat, t.cat), tweak_id=t.id, snaps=snaps,
                    success=True, detail="; ".join(errors), reversible=t.reversible)
    if blocked and not applied:
        history.set_blocked(t.id)
    if t.explorer and applied:
        restart_explorer()
    msg = "; ".join(errors) if errors else ("reinicie o PC para valer" if t.restart else "")
    if errors:
        say(f"   não aplicado por completo: {msg}")
    return ApplyResult(t, ok, msg, blocked)


def undo_entry(entry: dict, progress: Progress | None = None) -> tuple[bool, str]:
    say = progress or (lambda s: None)
    t = CATALOG.get(entry.get("tweak_id", ""))
    if t is None:
        return False, "ajuste não existe mais no catálogo"
    if not entry.get("reversible", True):
        return False, "esta alteração não tem desfazer"
    say(f"Desfazendo: {t.title}")
    errors = []
    for s in reversed(entry.get("snaps", [])):
        if "snap" not in s:
            continue
        try:
            t.actions[s["i"]].revert(s["snap"])
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
    history.mark_undone(entry["id"])
    history.set_blocked(t.id, False)
    if t.explorer:
        restart_explorer()
    return not errors, "; ".join(errors)


def undo_tweak(t: Tweak, progress: Progress | None = None) -> tuple[bool, str]:
    e = history.active_for(t.id)
    if e is None:
        return False, "nada aplicado por este app para desfazer"
    return undo_entry(e, progress)


def undo_all(progress: Progress | None = None) -> tuple[int, list[str]]:
    errs, n = [], 0
    for e in reversed(history.active_entries()):
        ok, msg = undo_entry(e, progress)
        n += 1
        if not ok and msg:
            errs.append(f"{e['title']}: {msg}")
    return n, errs


def apply_many(tweaks: Iterable[Tweak], progress: Progress | None = None,
               skip_applied: bool = True) -> list[ApplyResult]:
    out = []
    blocked = history.blocked()
    done_explorer = False
    for t in tweaks:
        if t.id in blocked:
            continue
        st = t.status()
        if st == "na" or (skip_applied and st == "on"):
            continue
        needs_explorer = t.explorer
        t.explorer = False           # reinicia o Explorer só uma vez no fim
        try:
            out.append(apply_tweak(t, progress))
        finally:
            t.explorer = needs_explorer
        done_explorer |= needs_explorer
    if done_explorer:
        restart_explorer()
    return out


def restart_explorer() -> None:
    run(["taskkill", "/f", "/im", "explorer.exe"], timeout=20)
    run("start explorer.exe", shell=True, timeout=20)
