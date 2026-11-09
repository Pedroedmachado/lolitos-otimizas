"""Pontos de restauração do Windows."""
from __future__ import annotations

import time

from lolitos import APP_NAME
from lolitos.core import history
from lolitos.core import registry as reg
from lolitos.core.system import as_list, powershell, powershell_json

_SR = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore"
REUSE_SECONDS = 24 * 3600


def last_own_point() -> float | None:
    for e in reversed(history.load()):
        if e["kind"] == "restore" and e["success"]:
            return e["time"]
    return None


def list_points() -> list[dict]:
    rows = powershell_json(
        "Get-ComputerRestorePoint | Select-Object SequenceNumber,Description,"
        "@{n='When';e={$_.ConvertToDateTime($_.CreationTime).ToString('dd/MM/yyyy HH:mm')}}", timeout=60)
    return [r for r in as_list(rows) if r]


def create(description: str = "", force: bool = False) -> tuple[bool, str]:
    """Cria um ponto. Reaproveita um criado por nós nas últimas 24 h, salvo force=True."""
    last = last_own_point()
    if not force and last and time.time() - last < REUSE_SECONDS:
        h = (time.time() - last) / 3600
        return True, f"reaproveitado o ponto criado há {h:.0f} h"
    desc = description or f"{APP_NAME} - antes das otimizações"
    try:  # o Windows só deixa criar 1 ponto a cada 24 h, a menos que isso seja zerado
        reg.write("HKLM", _SR, "SystemRestorePointCreationFrequency", "dword", 0)
    except OSError:
        pass
    r = powershell(
        "Enable-ComputerRestore -Drive ($env:SystemDrive + '\\') -ErrorAction SilentlyContinue;"
        f"Checkpoint-Computer -Description '{desc}' -RestorePointType MODIFY_SETTINGS", timeout=600)
    ok = r.ok
    history.add("restore", "Ponto de restauração criado" if ok else "Falha ao criar ponto de restauração",
                "Restauração", success=ok, detail=(r.err or "")[:300], reversible=False)
    return ok, ("ponto criado" if ok else (r.err or r.out).strip()[:300])


def open_system_restore() -> None:
    from lolitos.core.system import run
    run("start rstrui.exe", shell=True)
