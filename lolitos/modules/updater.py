"""Atualização pelo GitHub Releases: procura a versão nova, baixa o instalador, confere e instala.

Segurança:
- só consulta o repositório oficial e só aceita o instalador com o nome esperado;
- só baixa por HTTPS de domínios do GitHub;
- confere o tamanho e o SHA-256 informados pela API do GitHub antes de executar."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from lolitos import APP_ID, VERSION
from lolitos.core.system import IS_WIN

REPO = "Pedroedmachado/lolitos-otimizas"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
ASSET_RE = re.compile(r"^LolitosControl-(\d+\.\d+\.\d+)-Setup\.exe$")
ALLOWED_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
UA = {"User-Agent": f"{APP_ID}/{VERSION}", "Accept": "application/vnd.github+json"}
MAX_SIZE = 300 * 1024 * 1024


def parse_version(v: str) -> tuple[int, ...]:
    m = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in m[:3]) + (0,) * (3 - len(m[:3]))


def can_self_update() -> bool:
    """Só a versão instalada (empacotada) se atualiza sozinha."""
    return IS_WIN and getattr(sys, "frozen", False)


def check(timeout: float = 10) -> dict | None:
    """Retorna dados da versão nova, ou None se já está na mais recente."""
    req = urllib.request.Request(API, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    tag = data.get("tag_name", "")
    if parse_version(tag) <= parse_version(VERSION):
        return None
    for a in data.get("assets", []):
        m = ASSET_RE.match(a.get("name", ""))
        if not m:
            continue
        digest = (a.get("digest") or "")
        return {"version": m.group(1), "tag": tag, "name": a["name"], "url": a["browser_download_url"],
                "size": int(a.get("size") or 0),
                "sha256": digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else "",
                "notes": (data.get("body") or "").strip(), "page": data.get("html_url") or RELEASES_PAGE}
    return None


def _host_ok(url: str) -> bool:
    u = urlparse(url)
    return u.scheme == "https" and any(u.hostname == h or (u.hostname or "").endswith("." + h)
                                       for h in ALLOWED_HOSTS)


def download(info: dict, progress=None) -> Path:
    if not _host_ok(info["url"]):
        raise RuntimeError("Endereço de download inesperado; atualização cancelada.")
    if info["size"] <= 0 or info["size"] > MAX_SIZE:
        raise RuntimeError("Tamanho do instalador inesperado; atualização cancelada.")
    folder = Path(tempfile.gettempdir()) / f"{APP_ID}-update"
    folder.mkdir(exist_ok=True)
    dst = folder / info["name"]
    h = hashlib.sha256()
    got = 0
    req = urllib.request.Request(info["url"], headers={"User-Agent": UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=30) as r, open(dst, "wb") as f:
        if not _host_ok(r.geturl()):
            raise RuntimeError("Redirecionamento inesperado; atualização cancelada.")
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            got += len(chunk)
            if got > MAX_SIZE:
                raise RuntimeError("Download maior do que o esperado; cancelado.")
            h.update(chunk)
            f.write(chunk)
            if progress:
                progress(got * 100 // info["size"])
    if got != info["size"]:
        dst.unlink(missing_ok=True)
        raise RuntimeError("O download veio incompleto. Tente de novo.")
    if info["sha256"] and h.hexdigest().lower() != info["sha256"]:
        dst.unlink(missing_ok=True)
        raise RuntimeError("O arquivo baixado não confere com o SHA-256 publicado. Nada foi instalado.")
    return dst


def install_and_restart(installer: Path) -> None:
    """Roda o instalador sem janelas; ele fecha este app, atualiza e reabre o app novo."""
    flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/relaunch=1"],
                     creationflags=flags, close_fds=True)
