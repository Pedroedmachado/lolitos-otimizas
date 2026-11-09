"""Ícones dos programas do catálogo: o ícone do site oficial de cada um (serviço de favicons do Google),
guardado em %LOCALAPPDATA%\\LolitosControl\\icons. Sem ícone, a tela desenha a inicial."""
from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from lolitos.core.system import data_dir

SERVICE = "https://www.google.com/s2/favicons?domain={host}&sz=64"
# sites cujo domínio não tem o ícone do programa (página de projeto genérica)
GENERIC = {"github.com", "sourceforge.net", "learn.microsoft.com", "docs.microsoft.com", "apps.microsoft.com",
           "www.microsoft.com", "microsoft.com", "gitlab.com", "codeberg.org"}


def icon_dir() -> Path:
    d = data_dir() / "icons"
    d.mkdir(exist_ok=True)
    return d


def _safe(wid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", wid)


def cached(wid: str) -> Path | None:
    p = icon_dir() / (_safe(wid) + ".png")
    return p if p.exists() and p.stat().st_size > 100 else None


def fetch(wid: str, link: str) -> Path | None:
    hit = cached(wid)
    if hit:
        return hit
    miss = icon_dir() / (_safe(wid) + ".miss")
    if miss.exists() and time.time() - miss.stat().st_mtime < 7 * 86400:
        return None
    host = urllib.parse.urlparse(link or "").hostname or ""
    if not host or host in GENERIC:
        miss.touch()
        return None
    req = urllib.request.Request(SERVICE.format(host=host), headers={"User-Agent": "LolitosControl"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read(512 * 1024)
    except Exception:  # noqa: BLE001
        return None
    if len(data) < 200 or not data.startswith(b"\x89PNG"):
        miss.touch()
        return None
    dst = icon_dir() / (_safe(wid) + ".png")
    dst.write_bytes(data)
    return dst
