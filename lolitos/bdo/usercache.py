"""Filtro de tela (PostFilter) dentro dos gamevariable.xml do Black Desert.

O jogo guarda uma cópia das opções gráficas em Documents\\Black Desert\\UserCache\\<conta>\\gamevariable.xml
(bloco GameOptionGlobal) e, às vezes, também na pasta de cada personagem. Mudar só o GameOption.txt não basta: o
'Filtro de tela' volta sozinho. Aqui o PostFilter fica em 0 em todos esses arquivos.

Só esta linha é alterada; atalhos, barra de skills, chat e o resto do arquivo continuam iguais, byte a byte.
Sempre há backup antes de gravar, e nada é gravado com o jogo aberto (ele regrava esses arquivos ao fechar)."""
from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from lolitos.bdo.gameoption import GAME_PROCS, default_path, find_gameoption
from lolitos.core.system import backups_dir, process_running

RX = re.compile(rb'(<PostFilter\s+Value=")([^"]*)(")', re.I)


def docs_dir() -> Path:
    g = find_gameoption()
    return (g or default_path()).parent


def files(base: Path | None = None) -> list[Path]:
    root = (base or docs_dir()) / "UserCache"
    if not root.is_dir():
        return []
    try:
        return sorted(p for p in root.rglob("gamevariable.xml") if p.is_file())
    except OSError:
        return []


def read_value(p: Path) -> str | None:
    try:
        m = RX.search(p.read_bytes())
    except OSError:
        return None
    return m.group(2).decode("ascii", "replace") if m else None


def values(base: Path | None = None) -> dict[Path, str]:
    """Arquivo → valor atual do PostFilter (só os que têm a linha)."""
    out = {}
    for p in files(base):
        v = read_value(p)
        if v is not None:
            out[p] = v
    return out


def _backup(p: Path, root: Path) -> None:
    rel = p.relative_to(root)
    dst = backups_dir() / "bdo" / "usercache" / time.strftime("%Y%m%d-%H%M%S") / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dst)


def set_value(target: dict[Path, str] | str, base: Path | None = None) -> int:
    """Grava o PostFilter: um valor para todos os arquivos, ou {arquivo: valor}. Devolve quantos mudaram."""
    if process_running(*GAME_PROCS):
        raise RuntimeError("Feche o Black Desert antes: ele regrava o gamevariable.xml ao sair.")
    root = base or docs_dir()
    cur = values(root)
    want = {p: target for p in cur} if isinstance(target, str) else dict(target)
    n = 0
    for p, v in want.items():
        if p not in cur or cur[p] == v:
            continue
        raw = p.read_bytes()
        _backup(p, root)
        p.write_bytes(RX.sub(lambda m: m.group(1) + v.encode("ascii") + m.group(3), raw))
        n += 1
    return n
