"""Histórico de mudanças (com o estado anterior de cada ação, para desfazer)."""
from __future__ import annotations

import json
import threading
import time
import uuid

from lolitos.core.system import data_dir, write_atomic

_LOCK = threading.RLock()


def _file():
    return data_dir() / "historico.json"


def _blocked_file():
    return data_dir() / "bloqueados.json"


_CACHE: dict = {"key": None, "data": []}


def _norm(e) -> dict | None:
    """Entrada sempre com os campos que o resto do app lê (arquivo antigo, editado à mão ou estragado)."""
    if not isinstance(e, dict) or not e.get("id"):
        return None
    e.setdefault("kind", "")
    e.setdefault("title", "")
    e.setdefault("group", "")
    e.setdefault("tweak_id", "")
    e.setdefault("time", 0)
    e.setdefault("success", True)
    e.setdefault("undone", False)
    if not isinstance(e.get("snaps"), list):
        e["snaps"] = []
    return e


def _keep_broken(f) -> None:
    """Histórico ilegível: guarda uma cópia antes que a próxima gravação passe por cima (é ele que sabe desfazer)."""
    try:
        f.replace(f.with_name(f"historico-ilegivel-{time.strftime('%Y%m%d-%H%M%S')}.json"))
    except OSError:
        pass


def load() -> list[dict]:
    """Lê o histórico só quando o arquivo muda no disco (a interface consulta a cada ajuste mostrado)."""
    with _LOCK:
        f = _file()
        try:
            mt = (str(f), f.stat().st_mtime_ns)
        except OSError:
            _CACHE.update(key=None, data=[])
            return []
        if mt != _CACHE["key"]:
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    raise ValueError("formato inesperado")
            except (ValueError, OSError):
                _keep_broken(f)
                raw, mt = [], None
            _CACHE.update(key=mt, data=[x for x in (_norm(e) for e in raw) if x])
        return [dict(e) for e in _CACHE["data"]]


def save(entries: list[dict]) -> None:
    with _LOCK:
        f = _file()
        write_atomic(f, json.dumps(entries, ensure_ascii=False, indent=1))
        try:
            mt = (str(f), f.stat().st_mtime_ns)
        except OSError:
            mt = None
        _CACHE.update(key=mt, data=[x for x in (_norm(dict(e)) for e in entries) if x])


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
        d = json.loads(_blocked_file().read_text(encoding="utf-8"))
        return {x for x in d if isinstance(x, str)} if isinstance(d, list) else set()
    except (OSError, ValueError):
        return set()


def set_blocked(tweak_id: str, value: bool = True) -> None:
    b = blocked()
    (b.add if value else b.discard)(tweak_id)
    write_atomic(_blocked_file(), json.dumps(sorted(b)))
