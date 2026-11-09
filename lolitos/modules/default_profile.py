"""Contas novas: copia os ajustes por usuário (HKCU) que estão ativos para o perfil padrão do Windows
(C:\\Users\\Default\\NTUSER.DAT). Toda conta criada depois neste PC já nasce com eles.

As contas que já existem não mudam; cada uma recebe os ajustes ao abrir o app nela."""
from __future__ import annotations

import gc
import os
from pathlib import Path

from lolitos import APP_ID
from lolitos.core import registry as reg
from lolitos.core.system import IS_WIN, run

MOUNT = f"{APP_ID}DefaultUser"


def default_hive() -> Path | None:
    if not IS_WIN:
        return None
    r = reg.read("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList", "Default")
    base = os.path.expandvars(r[1]) if r else os.path.expandvars(r"%SystemDrive%\Users\Default")
    p = Path(base) / "NTUSER.DAT"
    return p if p.exists() else None


def hkcu_values(tweaks) -> list[tuple[str, str, str, object, bool]]:
    """(caminho, nome, tipo, valor, apagar) de cada ação de registro HKCU dos ajustes."""
    from lolitos.core.actions import Reg
    out = []
    for t in tweaks:
        for a in t.actions:
            if isinstance(a, Reg) and a.hive == "HKCU" and a.name is not None:
                try:
                    out.append((a.path, a.name, a.kind, None if a.delete else a.value, a.delete))
                except Exception:  # noqa: BLE001 — valor calculado que falhou: pula
                    continue
    return out


def apply_to_default(tweaks, progress=None) -> tuple[int, str]:
    """Grava os valores no perfil padrão. Devolve (quantidade, mensagem)."""
    say = progress or (lambda s: None)
    hive = default_hive()
    if hive is None:
        return 0, "perfil padrão do Windows não encontrado"
    vals = hkcu_values(tweaks)
    if not vals:
        return 0, "nenhum ajuste por usuário ativo"
    r = run(["reg", "load", f"HKU\\{MOUNT}", str(hive)], timeout=60)
    if not r.ok:
        return 0, (r.err or r.out).strip()[:200] or "o Windows não deixou abrir o perfil padrão"
    n = 0
    try:
        for path, name, kind, value, delete in vals:
            try:
                if delete:
                    reg.delete_value("HKU", f"{MOUNT}\\{path}", name)
                else:
                    reg.write("HKU", f"{MOUNT}\\{path}", name, kind, value)
                n += 1
            except OSError:
                continue
    finally:
        gc.collect()   # solta qualquer chave aberta antes de descarregar
        for _ in range(3):
            if run(["reg", "unload", f"HKU\\{MOUNT}"], timeout=60).ok:
                break
    say(f"   {n} valor(es) gravados no perfil de contas novas")
    return n, ""
