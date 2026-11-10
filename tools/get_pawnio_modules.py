"""Baixa os módulos assinados do PawnIO (projeto PawnIO.Modules, LGPL-2.1) para vendor/pawnio.

Usado pelo GitHub Actions; o instalador copia para {app}\\tools\\pawnio. Só os módulos de temperatura:
AMDFamily17 (Ryzen) e IntelMSR (Intel). O driver PawnIO confere a assinatura de cada módulo antes de carregar,
então um arquivo adulterado simplesmente não funciona."""
import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = "namazso/PawnIO.Modules"
WANTED = {"amdfamily17", "intelmsr"}
DST = Path(__file__).resolve().parents[1] / "vendor" / "pawnio"


def get(url: str, accept: str = "application/octet-stream") -> bytes:
    h = {"User-Agent": "ChineseControl-build", "Accept": accept}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok and "api.github.com" in url:
        h["Authorization"] = f"Bearer {tok}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
        return r.read()


def main() -> int:
    rel = json.loads(get(f"https://api.github.com/repos/{REPO}/releases/latest", "application/vnd.github+json"))
    DST.mkdir(parents=True, exist_ok=True)
    found = set()
    for a in rel.get("assets", []):
        name = a["name"]
        stem, ext = os.path.splitext(name)
        if ext.lower() in (".bin", ".amx") and stem.lower() in WANTED:
            (DST / name).write_bytes(get(a["browser_download_url"]))
            found.add(stem.lower())
        elif ext.lower() == ".zip":
            z = zipfile.ZipFile(io.BytesIO(get(a["browser_download_url"])))
            for n in z.namelist():
                s, e = os.path.splitext(os.path.basename(n))
                if e.lower() in (".bin", ".amx") and s.lower() in WANTED:
                    (DST / os.path.basename(n)).write_bytes(z.read(n))
                    found.add(s.lower())
    print(f"PawnIO.Modules {rel.get('tag_name')}: {sorted(found)} -> {DST}")
    return 0 if found == WANTED else 1


if __name__ == "__main__":
    sys.exit(main())
