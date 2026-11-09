"""Histórico de mudanças (com o estado anterior de cada ação, para desfazer)."""
from __future__ import annotations

import json
import threading
import time
import uuid

from lolitos.core.system import data_dir

_LOCK = threading.RLock()


def _file():
    return data_dir() / "historico.json"


def _blocked_file():
    return data_dir() / "bloqueados.json"


def load() -> list[dict]:
    with _LOCK:
        f = _file()
        if not f.exists():
            return []
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []


def save(entries: list[dict]) -> None:
    with _LOCK:
        tmp = _file().with_suffix(".tmp")
        tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(_file())


def add(kind: str, title: str, group: str, *, tweak_id: str = "", snaps=None,
        success: bool = True, detail: str = "", reversible: bool = True) -> dict:
    e = {
        "id": uuid.uuid4().hex, "time": time.time(), "kind": kind, "title": title,
        "group": group, "tweak_id": tweak_id, "snaps": snaps or [], "success": success,
        "detail": detail, "reversible": reversible, "undone": False,
    }
    with _LOCK:
        items = load()
        items.append(e)
        save(items)
    return e


def mark_undone(entry_id: str) -> None:
    with _LOCK:
        items = load()
        for e in items:
            if e["id"] == entry_id:
                e["undone"] = True
                e["undone_time"] = time.time()
        save(items)


def active_for(tweak_id: str) -> dict | None:
    """Última aplicação ainda não desfeita de um ajuste."""
    for e in reversed(load()):
        if e.get("tweak_id") == tweak_id and e["kind"] == "tweak" and not e["undone"] and e["success"]:
            return e
    return None


def active_entries() -> list[dict]:
    return [e for e in load() if e["kind"] == "tweak" and not e["undone"] and e["success"]
            and e.get("reversible", True)]


def clear() -> None:
    save([])


# ------------------------------------------------------------------ bloqueados
def blocked() -> set[str]:
    try:
        return set(json.loads(_blocked_file().read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return set()


def set_blocked(tweak_id: str, value: bool = True) -> None:
    b = blocked()
    (b.add if value else b.discard)(tweak_id)
    _blocked_file().write_text(json.dumps(sorted(b)), encoding="utf-8")
