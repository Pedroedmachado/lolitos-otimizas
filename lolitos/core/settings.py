"""Preferências do app (JSON em %LOCALAPPDATA%\\ChineseControl)."""
from __future__ import annotations

import json
import threading

from lolitos.core.system import data_dir, write_atomic

_LOCK = threading.RLock()
DEFAULTS = {
    "theme": "blue",          # dark (Escuro) | light (Claro) | blue (Azul)
    "visual_effects": True,   # vidro e animações
    "effects_level": 2,       # 0 desligados, 1 básicos, 2 completos
    "tray_on_close": True,
    "restore_point_before": True,
    "overlay_hotkey": "Ctrl+Shift+F10",
    "overlay_corner": "top-left",
    "overlay_opacity": 0.55,
    "overlay_scale": 1.0,
    "overlay_layout": "vertical",
    "overlay_items": ["fps", "frametime", "low1", "cpu", "cpu_temp", "gpu", "gpu_temp", "ram", "ping"],
    "overlay_with_game": True,
    "play_power_plan": True,
    "play_free_ram": True,
    "play_priority": "high",
    "ping_target": "1.1.1.1",
    "bdo_dir": "",
    "seen_tour": False,
    "check_updates": True,
}


def _file():
    return data_dir() / "config.json"


_CACHE: dict = {"mtime": None, "data": {}}


def load() -> dict:
    """Lê o config.json só quando ele muda no disco (é consultado o tempo todo pela interface)."""
    with _LOCK:
        f = _file()
        try:
            st = f.stat()
            mt = (st.st_mtime_ns, st.st_size)     # tamanho junto: gravações no mesmo instante têm a mesma data
        except OSError:
            mt = -1
        if mt != _CACHE["mtime"]:
            try:
                d = json.loads(f.read_text(encoding="utf-8")) if mt != -1 else {}
            except (OSError, ValueError):
                d = {}
            if not isinstance(d, dict):       # arquivo estragado (ou editado à mão): volta ao padrão sem derrubar o app
                d = {}
            _CACHE.update(mtime=mt, data=d)
        return {**DEFAULTS, **_CACHE["data"]}


def get(key: str, default=None):
    return load().get(key, DEFAULTS.get(key, default))


def set(key: str, value) -> None:  # noqa: A001
    with _LOCK:
        load()
        data = dict(_CACHE["data"])
        data[key] = value
        f = _file()
        write_atomic(f, json.dumps(data, ensure_ascii=False, indent=1))
        try:
            st = f.stat()
            _CACHE.update(mtime=(st.st_mtime_ns, st.st_size), data=data)
        except OSError:
            _CACHE.update(mtime=None, data=data)
