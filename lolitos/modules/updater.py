"""Atualização pelo GitHub Releases: procura a versão nova, baixa o instalador, confere e instala.

Segurança:
- só consulta o repositório oficial e só aceita o instalador com o nome esperado;
- só baixa por HTTPS de domínios do GitHub;
- confere o tamanho e o SHA-256 informados pela API do GitHub antes de executar (sem SHA-256 publicado, não
  instala sozinho);
- o instalador fica numa pasta que só administradores alteram (a do próprio app, em Arquivos de Programas) e é
  conferido de novo no instante de executar: nenhum outro programa consegue trocar o arquivo no meio do caminho."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from lolitos import APP_ID, VERSION
from lolitos.core.system import IS_WIN

REPO = "Pedroedmachado/lolitos-otimizas"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
# "LolitosControl-…" é o nome antigo: continua publicado junto para as versões antigas acharem a atualização
ASSET_RE = re.compile(r"^(?:Chinese|Lolitos)Control-(\d+\.\d+\.\d+)-Setup\.exe$")
ALLOWED_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
UA = {"User-Agent": f"{APP_ID}/{VERSION}", "Accept": "application/vnd.github+json"}
MAX_SIZE = 300 * 1024 * 1024
CHECK_EVERY_H = 6          # enquanto o app está aberto (ou na bandeja)
RETRY_WAITS = (0, 5, 20)   # segundos antes de cada tentativa
_NET_ERRORS = (urllib.error.URLError, TimeoutError, ConnectionError, OSError)


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


def _retry(fn, *args, waits=RETRY_WAITS, sleep=time.sleep, **kw):
    """Tenta de novo quando é a rede que falha (Wi-Fi acordando, GitHub lento). Erros de conferência não repetem."""
    last = None
    for w in waits:
        if w:
            sleep(w)
        try:
            return fn(*args, **kw)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):      # limite da API ou repositório fora do ar: tentar de novo não ajuda
                raise
            last = e
        except _NET_ERRORS as e:
            last = e
    raise last


def check_retry(timeout: float = 15) -> dict | None:
    return _retry(check, timeout)


def _host_ok(url: str) -> bool:
    u = urlparse(url)
    return u.scheme == "https" and any(u.hostname == h or (u.hostname or "").endswith("." + h)
                                       for h in ALLOWED_HOSTS)


def download(info: dict, progress=None) -> Path:
    """Baixa e confere; se a conexão cair no meio, tenta de novo (até 3 vezes)."""
    return _retry(_download, info, progress)


def update_dir() -> Path:
    """Onde o instalador baixado fica. O app roda como administrador, então o arquivo não pode ficar em pasta
    que programas comuns alteram (como %TEMP%): fica na pasta do app, protegida pelo Windows."""
    if getattr(sys, "frozen", False):
        d = Path(sys.executable).parent / "update"
        try:
            d.mkdir(exist_ok=True)
            probe = d / ".w"
            probe.write_bytes(b"")
            probe.unlink()
            return d
        except OSError:
            pass
    d = Path(tempfile.gettempdir()) / f"{APP_ID}-update"
    d.mkdir(exist_ok=True)
    return d


def _clean_old(folder: Path, keep: str = "") -> None:
    for f in folder.glob("*-Setup.exe*"):
        if f.name != keep:
            try:
                f.unlink()
            except OSError:
                pass


def cleanup_leftovers() -> None:
    """Ao abrir o app: apaga instaladores de atualizações já feitas (na pasta do app e na pasta antiga do %TEMP%)."""
    import shutil
    try:
        _clean_old(update_dir())
    except OSError:
        pass
    shutil.rmtree(Path(tempfile.gettempdir()) / f"{APP_ID}-update", ignore_errors=True)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def _download(info: dict, progress=None) -> Path:
    if not _host_ok(info["url"]):
        raise RuntimeError("Endereço de download inesperado; atualização cancelada.")
    if info["size"] <= 0 or info["size"] > MAX_SIZE:
        raise RuntimeError("Tamanho do instalador inesperado; atualização cancelada.")
    if not re.fullmatch(r"[0-9a-f]{64}", info.get("sha256") or ""):
        raise RuntimeError("O GitHub não informou o SHA-256 deste instalador, então ele não é instalado "
                           "automaticamente. Baixe pela página de versões.")
    if not ASSET_RE.match(info.get("name", "")):
        raise RuntimeError("Nome de instalador inesperado; atualização cancelada.")
    folder = update_dir()
    _clean_old(folder)
    dst = folder / info["name"]
    part = folder / (info["name"] + ".part")
    h = hashlib.sha256()
    got = 0
    req = urllib.request.Request(info["url"], headers={"User-Agent": UA["User-Agent"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
            if not _host_ok(r.geturl()):
                raise RuntimeError("Redirecionamento inesperado; atualização cancelada.")
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                got += len(chunk)
                if got > MAX_SIZE or got > info["size"]:
                    raise RuntimeError("Download maior do que o esperado; cancelado.")
                h.update(chunk)
                f.write(chunk)
                if progress:
                    progress(got * 100 // info["size"])
        if got != info["size"]:
            raise ConnectionError("O download veio incompleto. Tente de novo.")
        if h.hexdigest().lower() != info["sha256"]:
            raise RuntimeError("O arquivo baixado não confere com o SHA-256 publicado. Nada foi instalado.")
        part.replace(dst)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return dst


def install_and_restart(installer: Path, sha256: str = "") -> None:
    """Roda o instalador sem janelas; ele fecha este app, atualiza e reabre o app novo.
    Com o SHA-256 informado, o arquivo é conferido de novo aqui, no instante de executar."""
    installer = Path(installer)
    if sha256 and file_sha256(installer) != sha256.lower():
        installer.unlink(missing_ok=True)
        raise RuntimeError("O instalador mudou depois de conferido. Nada foi instalado.")
    flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/relaunch=1"],
                     creationflags=flags, close_fds=True)
