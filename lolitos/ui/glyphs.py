"""Ícones de linha: a fonte de ícones do próprio Windows (Segoe Fluent Icons no 11, Segoe MDL2 Assets no 10).

Fora do Windows (ou se a fonte faltar) cai num símbolo de texto equivalente, para a interface nunca mostrar
quadradinhos."""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QLabel

# nome → (código na fonte de ícones do Windows, símbolo de reserva)
GLYPHS = {
    "home": ("", "⌂"), "repair": ("", "🛠"), "speed": ("", "📈"), "pc": ("", "🖥"),
    "sensor": ("", "🌡"), "bdo": ("", "⚔"), "bolt": ("", "⚡"), "fresh": ("", "💿"),
    "debloat": ("", "✂"), "windows": ("", "⊞"), "mouse": ("", "🖱"), "keyboard": ("", "⌨"),
    "gpu": ("", "🎨"), "profiles": ("", "★"), "games": ("", "🎮"), "apps": ("", "📦"),
    "clean": ("", "🧹"), "power": ("", "⏻"), "overlay": ("", "◱"), "monitor": ("", "🖵"),
    "download": ("", "⭳"), "upload": ("", "⭱"), "network": ("", "📉"), "compare": ("", "⚖"),
    "shield": ("", "🛡"), "heart": ("", "✔"), "history": ("", "↺"), "settings": ("", "☰"),
    "sync": ("", "⟳"), "menu": ("", "≡"), "check": ("", "✓"), "warning": ("", "⚠"),
    "ping": ("", "📶"), "jitter": ("", "≈"), "info": ("", "ⓘ"), "game": ("", "🎮"),
    "sun": ("", "☀"), "flag": ("", "⚑"), "cpu": ("", "▣"), "ram": ("", "▤"),
    "disk": ("", "◫"), "wifi": ("", "📶"), "folder": ("", "📁"), "copy": ("", "⧉"),
}


@lru_cache(maxsize=1)
def icon_family() -> str:
    try:
        fams = set(QFontDatabase.families())
    except Exception:  # noqa: BLE001
        return ""
    for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if f in fams:
            return f
    return ""


def char(name: str) -> str:
    code, fallback = GLYPHS.get(name, ("", "•"))
    return code if icon_family() else fallback


def font(pt: float = 12) -> QFont:
    fam = icon_family()
    f = QFont(fam) if fam else QFont()
    f.setPointSizeF(pt)
    return f


def glyph(name: str, pt: float = 12, color: str = "") -> QLabel:
    lb = QLabel(char(name))
    lb.setFont(font(pt))
    lb.setAlignment(Qt.AlignCenter)
    if color:
        lb.setStyleSheet(f"color:{color}; background: transparent;")
    return lb
