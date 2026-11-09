"""Instalar, atualizar e desinstalar programas pelo winget (catálogo do projeto WinUtil, MIT)."""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from lolitos.core.system import powershell, resource_path, run

FLAGS = ["--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"]


@dataclass
class App:
    key: str
    name: str
    desc: str
    category: str
    winget: str
    link: str
    foss: bool = False


def catalog() -> list[App]:
    f = resource_path("apps_winutil.json")
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for key, a in data.items():
        wid = (a.get("winget") or "").strip()
        if not wid or wid.lower() == "na":
            continue
        out.append(App(key, a.get("content", key), a.get("description", ""), a.get("category", "Outros"),
                       wid.split(";")[0], a.get("link", ""), bool(a.get("foss"))))
    return sorted(out, key=lambda a: (a.category, a.name.lower()))


def available() -> bool:
    return run(["winget", "--version"], timeout=20).ok


def ensure_winget() -> bool:
    if available():
        return True
    # registra o App Installer (vem com o Windows, às vezes não registrado em instalações novas)
    powershell("Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe",
               timeout=300)
    return available()


def installed_ids() -> set[str]:
    """IDs do winget instalados (via 'winget export', que não depende do idioma)."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "export.json"
        run(["winget", "export", "-o", str(out), "--accept-source-agreements"], timeout=180)
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
    ids = set()
    for src in data.get("Sources", []):
        for p in src.get("Packages", []):
            if p.get("PackageIdentifier"):
                ids.add(p["PackageIdentifier"].lower())
    return ids


def install(wid: str):
    return run(["winget", "install", "--id", wid, "-e", "--silent", *FLAGS], timeout=1800)


def upgrade(wid: str):
    return run(["winget", "upgrade", "--id", wid, "-e", "--silent", *FLAGS], timeout=1800)


def uninstall(wid: str):
    return run(["winget", "uninstall", "--id", wid, "-e", "--silent", "--disable-interactivity"], timeout=1800)


def install_or_upgrade(wid: str, installed: set[str]):
    return upgrade(wid) if wid.lower() in installed else install(wid)
