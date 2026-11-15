"""Jogos instalados pela Steam (lê os arquivos da biblioteca; não altera nada da Steam)."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOTS = ["~/.local/share/Steam", "~/.steam/steam", "~/.steam/root",
         "~/.var/app/com.valvesoftware.Steam/.local/share/Steam"]
NOT_GAMES = ("proton", "steam linux runtime", "steamworks common", "steam runtime")


def libraries(roots: list[str] | None = None) -> list[Path]:
    out: list[Path] = []
    for r in roots or ROOTS:
        base = Path(r).expanduser()
        vdf = base / "steamapps" / "libraryfolders.vdf"
        if not vdf.is_file():
            continue
        cands = [base] + [Path(m) for m in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(errors="replace"))]
        for c in cands:
            try:
                c = c.resolve()
            except OSError:
                continue
            if (c / "steamapps").is_dir() and c not in out:
                out.append(c)
    return out


def games(roots: list[str] | None = None) -> list[dict]:
    found: dict[str, dict] = {}
    for lib in libraries(roots):
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            try:
                txt = acf.read_text(errors="replace")
            except OSError:
                continue
            a = re.search(r'"appid"\s+"(\d+)"', txt)
            n = re.search(r'"name"\s+"([^"]+)"', txt)
            if not a or not n or any(x in n.group(1).lower() for x in NOT_GAMES):
                continue
            found[a.group(1)] = {"appid": a.group(1), "name": n.group(1), "library": str(lib)}
    return sorted(found.values(), key=lambda g: g["name"].lower())


def launch(appid: str) -> bool:
    if not re.fullmatch(r"\d+", str(appid)):
        return False
    exe = shutil.which("steam") or shutil.which("xdg-open")
    if not exe:
        return False
    subprocess.Popen([exe, f"steam://rungameid/{appid}"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return True


# (chave, texto, o que entra na linha) — a ordem é a da linha final
LAUNCH_PARTS = [
    ("shader", "Manter o cache de shaders (NVIDIA)", "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1"),
    ("log", "Gravar o registro do Proton (para investigar erro)", "PROTON_LOG=1"),
    ("gamemode", "GameMode", "gamemoderun"),
    ("mangohud", "MangoHud (FPS na tela)", "mangohud"),
]


def launch_options(keys) -> str:
    """Texto para colar em Steam › Propriedades › Opções de inicialização."""
    env = [v for k, _t, v in LAUNCH_PARTS if k in keys and "=" in v]
    wrap = [v for k, _t, v in LAUNCH_PARTS if k in keys and "=" not in v]
    return " ".join(env + wrap + ["%command%"])
