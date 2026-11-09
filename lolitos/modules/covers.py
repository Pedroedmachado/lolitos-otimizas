"""Capas dos jogos (arte vertical 600×900, a mesma da biblioteca da Steam).

Ordem: cache do app → cache local da Steam (appcache/librarycache) → CDN da Steam pelo appid → busca do nome na
loja da Steam (jogos da Epic, GOG, Ubisoft…). Fica tudo guardado em %LOCALAPPDATA%\\ChineseControl\\covers;
se nada for achado, a tela desenha uma capa com as iniciais."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

from lolitos.core import registry as reg
from lolitos.core.system import data_dir

CDN = ("https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/library_600x900_2x.jpg",
       "https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/library_600x900.jpg",
       "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{id}/library_600x900.jpg")
HEADER = "https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/header.jpg"
SEARCH = "https://store.steampowered.com/api/storesearch/?term={q}&l=english&cc=BR"
ALLOWED = ("steamstatic.com", "steampowered.com", "akamaihd.net")
KNOWN_APPID = {"bdo": "582660"}          # Black Desert (cliente da Pearl Abyss usa a mesma arte)


def cover_dir() -> Path:
    d = data_dir() / "covers"
    d.mkdir(exist_ok=True)
    return d


def _safe(gid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", gid)


def cached(gid: str) -> Path | None:
    """Capa já guardada (sem rede) — rápido o bastante para a tela."""
    for ext in (".jpg", ".png"):
        p = cover_dir() / (_safe(gid) + ext)
        if p.exists() and p.stat().st_size > 1000:
            return p
    return None


def _misses() -> dict:
    try:
        return json.loads((cover_dir() / "misses.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _get(url: str, timeout: float = 8) -> bytes | None:
    host = urllib.parse.urlparse(url).hostname or ""
    if not any(host == h or host.endswith("." + h) for h in ALLOWED):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": "ChineseControl"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                return None
            return r.read(8 * 1024 * 1024)
    except Exception:  # noqa: BLE001  (sem internet, 404…)
        return None


def _steam_local(appid: str) -> Path | None:
    r = reg.read("HKCU", r"Software\Valve\Steam", "SteamPath")
    if not r:
        return None
    lc = Path(str(r[1])) / "appcache" / "librarycache"
    cands = [lc / f"{appid}_library_600x900_2x.jpg", lc / f"{appid}_library_600x900.jpg"]
    sub = lc / appid
    if sub.is_dir():   # formato novo da Steam: librarycache/<appid>/…/library_600x900.jpg
        cands += sorted(sub.rglob("library_600x900*.jpg"), key=lambda p: -p.stat().st_size)
    for c in cands:
        if c.exists() and c.stat().st_size > 1000:
            return c
    return None


def _norm(s: str) -> str:
    s = re.sub(r"[®™©:]", " ", s.lower())
    s = re.sub(r"\b(game of the year|goty|edition|definitive|remastered|deluxe)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


ITEMS = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1/?input_json="
ASSET_BASE = "https://shared.cloudflare.steamstatic.com/store_item_assets/"


def asset_urls(appid: str) -> list[str]:
    """Endereços atuais da arte do jogo, pela API da loja da Steam (jogos novos usam caminhos com hash)."""
    q = json.dumps({"ids": [{"appid": int(appid)}], "context": {"language": "english", "country_code": "BR"},
                    "data_request": {"include_assets": True}}, separators=(",", ":"))
    data = _get(ITEMS + urllib.parse.quote(q))
    if not data:
        return []
    try:
        item = json.loads(data)["response"]["store_items"][0]
        a = item.get("assets") or {}
    except (ValueError, KeyError, IndexError, TypeError):
        return []
    fmt = a.get("asset_url_format") or f"steam/apps/{appid}/${{FILENAME}}"
    out = []
    for k in ("library_capsule_2x", "library_capsule", "header"):
        if a.get(k):
            out.append(ASSET_BASE + fmt.replace("${FILENAME}", a[k]))
    return out


def search_appid(name: str) -> str | None:
    """Acha o jogo na loja da Steam pelo nome (só aceita nome bem parecido)."""
    data = _get(SEARCH.format(q=urllib.parse.quote(name)))
    if not data:
        return None
    try:
        items = json.loads(data).get("items", [])
    except ValueError:
        return None
    best, score = None, 0.0
    for it in items[:10]:
        r = SequenceMatcher(None, _norm(name), _norm(it.get("name", ""))).ratio()
        if r > score:
            best, score = str(it.get("id")), r
    return best if score >= 0.82 else None


def fetch(g) -> Path | None:
    """Garante a capa do jogo (pode usar a rede). Roda fora da interface."""
    hit = cached(g.id)
    if hit:
        return hit
    misses = _misses()
    if time.time() - float(misses.get(g.id) or 0) < 2 * 86400:   # sem capa: tenta de novo a cada 2 dias
        return None
    appid = g.id.split(":", 1)[1] if g.id.startswith("steam:") else KNOWN_APPID.get(g.store)
    dst = cover_dir() / (_safe(g.id) + ".jpg")
    if appid:
        local = _steam_local(appid)
        if local:
            dst.write_bytes(local.read_bytes())
            return dst
    if not appid:
        appid = search_appid(g.name)
    if appid:
        urls = [u.format(id=appid) for u in CDN] + asset_urls(appid) + [HEADER.format(id=appid)]
        for url in urls:          # o último é o banner horizontal, se não houver arte vertical
            data = _get(url)
            if data and len(data) > 1000 and data[:3] in (b"\xff\xd8\xff", b"\x89PN"):
                dst.write_bytes(data)
                return dst
    misses[g.id] = time.time()
    try:
        (cover_dir() / "misses.json").write_text(json.dumps(misses), encoding="utf-8")
    except OSError:
        pass
    return None


def set_custom(gid: str, image: str) -> Path:
    """Capa escolhida pelo usuário."""
    src = Path(image)
    dst = cover_dir() / (_safe(gid) + (".png" if src.suffix.lower() == ".png" else ".jpg"))
    for old in (cover_dir() / (_safe(gid) + ".jpg"), cover_dir() / (_safe(gid) + ".png")):
        old.unlink(missing_ok=True)
    dst.write_bytes(src.read_bytes())
    m = _misses()
    m.pop(gid, None)
    (cover_dir() / "misses.json").write_text(json.dumps(m), encoding="utf-8")
    return dst
