"""Temperatura real do processador pelo PawnIO (driver assinado e de código aberto, o mesmo que o
LibreHardwareMonitor usa hoje). Nada é injetado em jogo: só lê registradores de temperatura da CPU.

- AMD Ryzen (Zen, família 17h em diante): Tctl/Tdie pelo SMN 0x59800 (módulo AMDFamily17).
- Intel (Core 2ª geração em diante): TjMax − leitura digital do pacote (MSR 0x1A2 e 0x1B1, módulo IntelMSR).

O driver só é instalado quando você pede (winget, pacote namazso.PawnIO). Os módulos assinados vêm junto com o
app (projeto PawnIO.Modules, LGPL-2.1) e o próprio driver confere a assinatura antes de carregar."""
from __future__ import annotations

import ctypes
import logging
import os
import shutil
import sys
import threading
from pathlib import Path

from lolitos.core.system import IS_WIN, data_dir, run

log = logging.getLogger("lolitos")
WINGET_ID = "namazso.PawnIO"
SMN_THM_TCON_CUR_TMP = 0x00059800
MSR_TEMPERATURE_TARGET, MSR_PACKAGE_THERM_STATUS, MSR_THERM_STATUS = 0x1A2, 0x1B1, 0x19C


# ---------------------------------------------------------------- conversões (testáveis fora do Windows)
def amd_tctl(smn: int) -> float:
    """Valor do registrador THM_TCON_CUR_TMP → °C (com o deslocamento de −49 °C quando o bit de faixa está ligado)."""
    t = ((smn >> 21) & 0x7FF) / 8.0
    if smn & 0x80000:
        t -= 49.0
    return t


def intel_package(target_msr: int, status_msr: int) -> float | None:
    """TjMax (bits 23:16 do 0x1A2) − leitura digital (bits 22:16 do 0x1B1); None se a leitura não for válida."""
    tjmax = (target_msr >> 16) & 0xFF or 100
    if not status_msr & (1 << 31):            # bit 31: leitura válida
        return None
    return float(tjmax - ((status_msr >> 16) & 0x7F))


def cpu_vendor_family() -> tuple[str, int]:
    """('amd'|'intel'|'', família) pelo registro do Windows."""
    if not IS_WIN:
        return "", 0
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            vendor = winreg.QueryValueEx(k, "VendorIdentifier")[0]
            ident = winreg.QueryValueEx(k, "Identifier")[0]        # "AMD64 Family 25 Model 97 Stepping 2"
    except OSError:
        return "", 0
    fam = 0
    parts = ident.split()
    if "Family" in parts:
        try:
            fam = int(parts[parts.index("Family") + 1])
        except (ValueError, IndexError):
            fam = 0
    v = "amd" if "AMD" in vendor.upper() else "intel" if "INTEL" in vendor.upper() else ""
    return v, fam


# ---------------------------------------------------------------- instalação
def lib_path() -> Path | None:
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramW6432", "")):
        if base:
            p = Path(base) / "PawnIO" / "PawnIOLib.dll"
            if p.exists():
                return p
    return None


def modules_dir() -> Path | None:
    cands = []
    if getattr(sys, "frozen", False):
        cands.append(Path(sys.executable).parent / "tools" / "pawnio")
    cands += [data_dir() / "tools" / "pawnio", Path(__file__).resolve().parents[2] / "vendor" / "pawnio"]
    for c in cands:
        if c.is_dir() and any(c.iterdir()):
            return c
    return None


def module_file(name: str) -> Path | None:
    d = modules_dir()
    if not d:
        return None
    for f in d.iterdir():
        if f.stem.lower() == name.lower() and f.suffix.lower() in (".bin", ".amx"):
            return f
    return None


def needed_module() -> str:
    v, fam = cpu_vendor_family()
    if v == "amd" and fam >= 0x17:
        return "AMDFamily17"
    if v == "intel":
        return "IntelMSR"
    return ""


def supported() -> bool:
    return IS_WIN and bool(needed_module())


def installed() -> bool:
    return lib_path() is not None


def install(progress=None) -> str:
    say = progress or (lambda s: None)
    if installed():
        return "O PawnIO já está instalado."
    if not shutil.which("winget"):
        raise RuntimeError("O winget (Instalador de Aplicativo da Microsoft Store) não está disponível neste Windows.")
    say("Instalando o PawnIO (driver assinado, código aberto) pelo winget…")
    r = run(["winget", "install", "--id", WINGET_ID, "-e", "--silent", "--accept-package-agreements",
             "--accept-source-agreements", "--disable-interactivity"], timeout=600)
    if not installed():
        raise RuntimeError("O winget não conseguiu instalar o PawnIO: " + (r.err or r.out).strip()[-300:])
    reset()
    return "PawnIO instalado. A temperatura do processador já aparece no overlay."


# ---------------------------------------------------------------- leitura
class _Pawn:
    def __init__(self, dll: Path, blob: bytes):
        self.lib = ctypes.WinDLL(str(dll))
        H = ctypes.c_void_p
        self.lib.pawnio_open.argtypes = [ctypes.POINTER(H)]
        self.lib.pawnio_load.argtypes = [H, ctypes.c_char_p, ctypes.c_size_t]
        self.lib.pawnio_execute.argtypes = [H, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t,
                                            ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t,
                                            ctypes.POINTER(ctypes.c_size_t)]
        self.lib.pawnio_close.argtypes = [H]
        for fn in ("pawnio_open", "pawnio_load", "pawnio_execute", "pawnio_close"):
            getattr(self.lib, fn).restype = ctypes.c_long
        self.h = H()
        hr = self.lib.pawnio_open(ctypes.byref(self.h))
        if hr < 0:
            raise OSError(f"pawnio_open 0x{hr & 0xFFFFFFFF:08X} (precisa de administrador)")
        hr = self.lib.pawnio_load(self.h, blob, len(blob))
        if hr < 0:
            self.lib.pawnio_close(self.h)
            raise OSError(f"pawnio_load 0x{hr & 0xFFFFFFFF:08X}")

    def call(self, name: str, *args: int) -> int:
        inp = (ctypes.c_uint64 * max(1, len(args)))(*args)
        out = (ctypes.c_uint64 * 1)()
        n = ctypes.c_size_t(0)
        hr = self.lib.pawnio_execute(self.h, name.encode(), inp, len(args), out, 1, ctypes.byref(n))
        if hr < 0:
            raise OSError(f"{name} 0x{hr & 0xFFFFFFFF:08X}")
        return int(out[0])

    def close(self):
        try:
            self.lib.pawnio_close(self.h)
        except OSError:
            pass


_lock = threading.Lock()
_state: dict = {"pawn": None, "err": "", "mod": ""}


def reset():
    with _lock:
        if _state["pawn"]:
            _state["pawn"].close()
        _state.update(pawn=None, err="", mod="")


def status() -> str:
    """Texto curto para a tela do overlay."""
    if not IS_WIN:
        return "só no Windows"
    if not needed_module():
        return "processador sem suporte"
    if not installed():
        return "PawnIO não instalado"
    if not module_file(needed_module()):
        return "módulo do PawnIO não encontrado (reinstale o app)"
    return _state["err"] or "ok"


def _open():
    if _state["pawn"] or _state["err"]:
        return _state["pawn"]
    mod = needed_module()
    dll, f = lib_path(), module_file(mod) if mod else None
    if not (dll and f):
        return None
    try:
        _state["pawn"] = _Pawn(dll, f.read_bytes())
        _state["mod"] = mod
        log.info("PawnIO: módulo %s carregado", mod)
    except OSError as e:
        _state["err"] = str(e)
        log.warning("PawnIO: %s", e)
    return _state["pawn"]


def cpu_temp() -> float | None:
    """Temperatura do processador em °C, ou None se o PawnIO não estiver disponível."""
    if not IS_WIN:
        return None
    with _lock:
        p = _open()
        if not p:
            return None
        try:
            if _state["mod"] == "AMDFamily17":
                k32 = ctypes.windll.kernel32
                mtx = k32.CreateMutexW(None, False, "Global\\Access_PCI")   # combinado com outros monitores
                if mtx:
                    k32.WaitForSingleObject(mtx, 200)
                try:
                    v = amd_tctl(p.call("ioctl_read_smn", SMN_THM_TCON_CUR_TMP))
                finally:
                    if mtx:
                        k32.ReleaseMutex(mtx)
                        k32.CloseHandle(mtx)
            else:
                v = intel_package(p.call("ioctl_read_msr", MSR_TEMPERATURE_TARGET),
                                  p.call("ioctl_read_msr", MSR_PACKAGE_THERM_STATUS))
        except OSError as e:
            _state["err"] = str(e)
            log.warning("PawnIO: %s", e)
            return None
    return v if v is not None and 5 < v < 125 else None
