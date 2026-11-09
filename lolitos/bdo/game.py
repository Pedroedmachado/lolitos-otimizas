"""Black Desert: instalação, processo, servidor conectado, travamentos e caches."""
from __future__ import annotations

import os
import re
import socket
import string
import time
from dataclasses import dataclass
from pathlib import Path

from lolitos.core import registry as reg
from lolitos.core import settings
from lolitos.core.system import IS_WIN, human_size

EXE = "BlackDesert64.exe"
LAUNCHER = "BlackDesertLauncher.exe"
STEAM_APPID = "582660"
DOCS = Path.home() / "Documents" / "Black Desert"


# ------------------------------------------------------------------ instalação
def _steam_libraries() -> list[Path]:
    r = reg.read("HKCU", r"Software\Valve\Steam", "SteamPath")
    if not r:
        return []
    steam = Path(str(r[1]))
    libs = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore")):
            libs.append(Path(m.group(1).replace("\\\\", "\\")))
    return libs


def _from_steam() -> Path | None:
    for lib in _steam_libraries():
        acf = lib / "steamapps" / f"appmanifest_{STEAM_APPID}.acf"
        if acf.exists():
            m = re.search(r'"installdir"\s+"([^"]+)"', acf.read_text(encoding="utf-8", errors="ignore"))
            if m:
                p = lib / "steamapps" / "common" / m.group(1)
                if p.exists():
                    return p
    return None


def _from_uninstall() -> Path | None:
    for base in (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"):
        for hive in ("HKLM", "HKCU"):
            for sub in reg.subkeys(hive, base):
                name = reg.read(hive, f"{base}\\{sub}", "DisplayName")
                if name and "black desert" in str(name[1]).lower():
                    loc = reg.read(hive, f"{base}\\{sub}", "InstallLocation")
                    if loc and Path(str(loc[1])).exists():
                        return Path(str(loc[1]))
    return None


def _from_defaults() -> Path | None:
    drives = [f"{d}:\\" for d in string.ascii_uppercase if Path(f"{d}:\\").exists()] if IS_WIN else []
    names = ["Pearl Abyss\\BlackDesert_SA", "Pearl Abyss\\BlackDesert", "Pearl Abyss\\Black Desert",
             "Program Files (x86)\\Black Desert Online", "Black Desert Online", "BlackDesert"]
    for d in drives:
        for n in names:
            p = Path(d) / n
            if (p / "bin64" / EXE).exists() or (p / LAUNCHER).exists():
                return p
        pa = Path(d) / "Pearl Abyss"
        if pa.exists():
            for sub in pa.iterdir():
                if (sub / "bin64" / EXE).exists():
                    return sub
    return None


_miss = {"t": 0.0}


def install_dir(refresh: bool = False) -> Path | None:
    saved = settings.get("bdo_dir")
    if saved and Path(saved).exists() and not refresh:
        return Path(saved)
    if not refresh and time.time() - _miss["t"] < 60:   # evita varrer o PC a cada consulta
        return None
    for f in (_from_uninstall, _from_steam, _from_defaults):
        try:
            p = f()
        except OSError:
            p = None
        if p:
            settings.set("bdo_dir", str(p))
            return p
    _miss["t"] = time.time()
    return None


def set_install_dir(p: str) -> None:
    settings.set("bdo_dir", p)


def exe_path() -> Path | None:
    d = install_dir()
    if not d:
        return None
    for c in (d / "bin64" / EXE, d / EXE):
        if c.exists():
            return c
    return None


def launcher_path() -> Path | None:
    d = install_dir()
    if d and (d / LAUNCHER).exists():
        return d / LAUNCHER
    return None


def is_steam_install() -> bool:
    d = install_dir()
    return bool(d and "steamapps" in str(d).lower())


# ------------------------------------------------------------------ processo e servidor
def game_process():
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            if (p.info["name"] or "").lower() == EXE.lower():
                return p
    except Exception:
        pass
    return None


def _private(ip: str) -> bool:
    return ip.startswith(("10.", "192.168.", "127.", "169.254.", "0.")) or \
        re.match(r"^172\.(1[6-9]|2\d|3[01])\.", ip) is not None or ":" in ip


@dataclass
class Conn:
    ip: str
    port: int


def server_connections() -> list[Conn]:
    """Conexões TCP do BDO com a internet (lidas da tabela do Windows, não do jogo)."""
    p = game_process()
    if not p:
        return []
    try:
        conns = p.net_connections(kind="tcp") if hasattr(p, "net_connections") else p.connections(kind="tcp")
    except Exception:
        return []
    out, seen = [], set()
    for c in conns:
        if not c.raddr or c.status != "ESTABLISHED":
            continue
        ip, port = c.raddr.ip, c.raddr.port
        if _private(ip) or (ip, port) in seen:
            continue
        seen.add((ip, port))
        out.append(Conn(ip, port))
    # portas web (443/80) costumam ser loja/navegador interno: vão para o fim
    out.sort(key=lambda c: c.port in (80, 443))
    return out


def tcp_ping(ip: str, port: int, timeout: float = 2.0) -> float | None:
    """Tempo de handshake TCP em ms (funciona mesmo quando o servidor ignora ping ICMP)."""
    t = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return (time.perf_counter() - t) * 1000
    except OSError:
        return None


# ------------------------------------------------------------------ travamentos
@dataclass
class Crash:
    when: float
    address: str
    path: Path


def crashes() -> list[Crash]:
    d = DOCS / "Dump"
    if not d.exists():
        return []
    out = []
    for f in d.glob("*.dmp"):
        m = re.match(r"r\d+_(0x[0-9A-Fa-f]+)_", f.name)
        out.append(Crash(f.stat().st_mtime, m.group(1) if m else "?", f))
    return sorted(out, key=lambda c: c.when, reverse=True)


def crash_summary() -> dict:
    cs = crashes()
    now = time.time()
    by_addr: dict[str, int] = {}
    for c in cs:
        by_addr[c.address] = by_addr.get(c.address, 0) + 1
    driver = ""
    traces = sorted((DOCS / "Dump").glob("*_trace.txt"), key=os.path.getmtime, reverse=True) \
        if (DOCS / "Dump").exists() else []
    if traces:
        m = re.search(r"GPU : (.+?)\(.*Version : ([^\s(]+)", traces[0].read_text(errors="ignore"))
        if m:
            driver = f"{m.group(1).strip()} · driver {m.group(2)}"
    return {"total": len(cs), "d7": sum(1 for c in cs if now - c.when < 7 * 86400),
            "d30": sum(1 for c in cs if now - c.when < 30 * 86400),
            "last": cs[0].when if cs else None, "repeat": max(by_addr.values()) if by_addr else 0,
            "gpu": driver}


# ------------------------------------------------------------------ caches seguros
CACHE_TARGETS = [
    ("dump", "Relatórios de travamento (Dump)", DOCS / "Dump", "*",
     "Arquivos .dmp e logs de cada crash. Não afetam o jogo."),
    ("facetex", "Cache de rostos (FaceTexture)", DOCS / "FaceTexture", "*.bmp",
     "Miniaturas de rostos de personagens; o jogo recria quando precisa."),
    ("temp", "Pacotes temporários (Temp)", DOCS / "Temp", "UserCachePack*.bdcp",
     "Pacotes de cache baixados; o jogo baixa de novo se precisar."),
]
# UserCache NÃO entra: guarda atalhos, barra de skills e layout da interface.


def cache_sizes() -> list[dict]:
    out = []
    for cid, name, folder, pattern, desc in CACHE_TARGETS:
        files = [f for f in folder.glob(pattern) if f.is_file()] if folder.exists() else []
        size = sum(f.stat().st_size for f in files)
        out.append({"id": cid, "name": name, "desc": desc, "files": len(files), "bytes": size,
                    "human": human_size(size)})
    return out


def clean_caches(ids: list[str]) -> tuple[int, int]:
    from lolitos.core.system import process_running
    if process_running(EXE):
        raise RuntimeError("Feche o Black Desert antes de limpar os caches dele.")
    n = freed = 0
    for cid, _, folder, pattern, _ in CACHE_TARGETS:
        if cid not in ids or not folder.exists():
            continue
        for f in folder.glob(pattern):
            try:
                if f.is_file():
                    s = f.stat().st_size
                    f.unlink()
                    n += 1
                    freed += s
            except OSError:
                pass
    return n, freed
