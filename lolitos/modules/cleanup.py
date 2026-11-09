"""Limpeza de temporários e caches, sempre medindo antes."""
from __future__ import annotations

import glob
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from lolitos.core.system import IS_WIN, expand, human_size, run

TWO_HOURS = 2 * 3600


@dataclass
class Target:
    id: str
    name: str
    desc: str
    patterns: list[str]
    min_age: int = 0          # só arquivos mais velhos que isso (s)
    default: bool = True
    admin: bool = False
    pre: str = ""             # comando antes (ex.: parar serviço)
    post: str = ""


TARGETS = [
    Target("user_temp", "Temporários do usuário", "Pasta %TEMP%: sobras de instaladores (arquivos com mais de 2 h).",
           [r"%TEMP%\*"], TWO_HOURS),
    Target("win_temp", "Temporários do Windows", r"C:\Windows\Temp (arquivos com mais de 2 h).",
           [r"%SystemRoot%\Temp\*"], TWO_HOURS, admin=True),
    Target("shader", "Cache de shaders (DirectX, NVIDIA, AMD)",
           "Recriado sozinho. Ajuda quando jogos têm falhas gráficas depois de atualizar o driver. "
           "O primeiro carregamento depois fica um pouco mais lento.",
           [r"%LOCALAPPDATA%\D3DSCache\*", r"%LOCALAPPDATA%\NVIDIA\DXCache\*", r"%LOCALAPPDATA%\NVIDIA\GLCache\*",
            r"%LOCALAPPDATA%Low\NVIDIA\PerDriverVersion\DXCache\*", r"%LOCALAPPDATA%\AMD\DxCache\*",
            r"%LOCALAPPDATA%\AMD\DxcCache\*", r"%LOCALAPPDATA%\AMD\VkCache\*"], default=False),
    Target("thumbs", "Cache de miniaturas", "Miniaturas do Explorer; recriadas ao abrir as pastas.",
           [r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache_*.db",
            r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache_*.db"], default=False),
    Target("wu_cache", "Cache do Windows Update", "Atualizações já instaladas. O serviço é parado durante a limpeza.",
           [r"%SystemRoot%\SoftwareDistribution\Download\*"], admin=True,
           pre="net stop wuauserv /y & net stop bits /y", post="net start bits & net start wuauserv"),
    Target("delivery", "Cache de Otimização de Entrega", "Cópias de atualizações compartilhadas com outros PCs.",
           [r"%SystemRoot%\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache\*"],
           admin=True, pre="net stop dosvc /y", post="net start dosvc"),
    Target("prefetch", "Arquivos Prefetch", r"C:\Windows\Prefetch. O primeiro início de cada programa fica mais lento.",
           [r"%SystemRoot%\Prefetch\*.pf"], default=False, admin=True),
    Target("wer", "Relatórios de erro do Windows", "Relatórios de falhas já enviados ou na fila.",
           [r"%ProgramData%\Microsoft\Windows\WER\ReportArchive\*", r"%ProgramData%\Microsoft\Windows\WER\ReportQueue\*",
            r"%LOCALAPPDATA%\Microsoft\Windows\WER\*"], admin=True),
    Target("dumps", "Despejos de memória de programas", "Arquivos .dmp que programas deixam ao travar.",
           [r"%LOCALAPPDATA%\CrashDumps\*", r"%SystemRoot%\Minidump\*", r"%SystemRoot%\MEMORY.DMP"], admin=True),
    Target("browsers", "Cache dos navegadores", "Chrome, Edge, Brave, Opera e Firefox. Feche os navegadores antes; "
           "senhas e histórico não são tocados.",
           [r"%LOCALAPPDATA%\Google\Chrome\User Data\*\Cache\Cache_Data\*",
            r"%LOCALAPPDATA%\Google\Chrome\User Data\*\Code Cache\*",
            r"%LOCALAPPDATA%\Microsoft\Edge\User Data\*\Cache\Cache_Data\*",
            r"%LOCALAPPDATA%\Microsoft\Edge\User Data\*\Code Cache\*",
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\*\Cache\Cache_Data\*",
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\*\Code Cache\*",
            r"%LOCALAPPDATA%\Opera Software\Opera Stable\Cache\Cache_Data\*",
            r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles\*\cache2\*"], default=False),
    Target("discord_cache", "Cache do Discord", "Imagens e vídeos em cache do Discord. Feche o Discord antes.",
           [r"%APPDATA%\discord\Cache\Cache_Data\*", r"%APPDATA%\discord\Code Cache\*"], default=False),
]
TARGETS_BY_ID = {t.id: t for t in TARGETS}


def _files(t: Target):
    now = time.time()
    for pat in t.patterns:
        for p in glob.glob(expand(pat)):
            path = Path(p)
            try:
                if path.is_symlink():
                    yield path, 0, False
                    continue
                if path.is_file():
                    st = path.stat()
                    if not t.min_age or now - st.st_mtime > t.min_age:
                        yield path, st.st_size, False
                elif path.is_dir():
                    size, newest = 0, 0.0
                    for root, _, files in os.walk(path):
                        for f in files:
                            try:
                                s = os.stat(os.path.join(root, f))
                                size += s.st_size
                                newest = max(newest, s.st_mtime)
                            except OSError:
                                pass
                    if not t.min_age or now - (newest or path.stat().st_mtime) > t.min_age:
                        yield path, size, True
            except OSError:
                continue


def measure(t: Target) -> tuple[int, int]:
    n = total = 0
    for _, size, _ in _files(t):
        n += 1
        total += size
    return n, total


def clean(t: Target, dry_run: bool = False) -> tuple[int, int, int]:
    """Apaga. Retorna (removidos, bytes, mantidos_em_uso)."""
    if t.pre and not dry_run and IS_WIN:
        run(t.pre, shell=True, timeout=60)
    removed = freed = kept = 0
    try:
        for path, size, is_dir in list(_files(t)):
            if dry_run:
                removed += 1
                freed += size
                continue
            try:
                if path.is_symlink():
                    path.unlink()        # remove o link, nunca o destino
                elif is_dir:
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed += 1
                freed += size
            except OSError:
                kept += 1
    finally:
        if t.post and not dry_run and IS_WIN:
            run(t.post, shell=True, timeout=60)
    return removed, freed, kept


# ------------------------------------------------------------------ lixeira
def recycle_bin_size() -> tuple[int, int]:
    if not IS_WIN:
        return 0, 0
    import ctypes

    class SHQUERYRBINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint32), ("i64Size", ctypes.c_int64), ("i64NumItems", ctypes.c_int64)]

    info = SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
    return int(info.i64NumItems), int(info.i64Size)


def empty_recycle_bin() -> bool:
    if not IS_WIN:
        return False
    import ctypes
    flags = 0x1 | 0x2 | 0x4   # sem confirmação, sem progresso, sem som
    rc = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
    return rc in (0, -2147418113)  # S_OK ou E_UNEXPECTED (já vazia)


def summary_text(results: dict[str, tuple[int, int, int]]) -> str:
    files = sum(r[0] for r in results.values())
    freed = sum(r[1] for r in results.values())
    kept = sum(r[2] for r in results.values())
    s = f"Liberados {human_size(freed)} ({files} item(ns))."
    if kept:
        s += f" {kept} em uso foram mantidos."
    return s
