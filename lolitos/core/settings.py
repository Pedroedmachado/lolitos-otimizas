"""Preferências do app (JSON em %LOCALAPPDATA%\\LolitosOtimizacoes)."""
from __future__ import annotations

import json
import threading

from lolitos.core.system import data_dir

_LOCK = threading.RLock()
DEFAULTS = {
    "theme": "dark",
    "tray_on_close": True,
    "restore_point_before": True,
    "overlay_hotkey": "Ctrl+Shift+F10",
    "overlay_corner": "top-left",
    "overlay_opacity": 0.55,
    "overlay_items": ["fps", "cpu", "gpu", "gpu_temp", "ram", "vram", "ping"],
    "overlay_with_game": True,
    "play_power_plan": True,
    "play_free_ram": True,
    "play_priority": "high",
    "ping_target": "1.1.1.1",
    "bdo_dir": "",
    "seen_tour": False,
}


def _file():
    return data_dir() / "config.json"


def load() -> dict:
    with _LOCK:
        try:
            d = json.loads(_file().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            d = {}
        return {**DEFAULTS, **d}


def get(key: str, default=None):
    return load().get(key, DEFAULTS.get(key, default))


def set(key: str, value) -> None:  # noqa: A001
    with _LOCK:
        d = load()
        d[key] = value
        _file().write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
