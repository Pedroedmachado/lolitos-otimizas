"""Leituras da placa de vídeo via NVML (vem com o driver NVIDIA). Sem instalar nada."""
from __future__ import annotations

import ctypes
import threading

from lolitos.core.system import IS_WIN

_lock = threading.Lock()
_nvml = None
_handle = None


class _Mem(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


class _Util(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


def _init() -> bool:
    global _nvml, _handle
    if _handle is not None:
        return True
    if not IS_WIN:
        return False
    with _lock:
        if _handle is not None:
            return True
        for path in ("nvml.dll", r"C:\Windows\System32\nvml.dll",
                     r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll"):
            try:
                _nvml = ctypes.CDLL(path)
                break
            except OSError:
                continue
        if _nvml is None or _nvml.nvmlInit_v2() != 0:
            _nvml = None
            return False
        h = ctypes.c_void_p()
        if _nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h)) != 0:
            return False
        _handle = h
        return True


def available() -> bool:
    return _init()


def name() -> str:
    if not _init():
        return ""
    buf = ctypes.create_string_buffer(96)
    _nvml.nvmlDeviceGetName(_handle, buf, 96)
    return buf.value.decode(errors="ignore")


def driver_version() -> str:
    if not _init():
        return ""
    buf = ctypes.create_string_buffer(80)
    _nvml.nvmlSystemGetDriverVersion(buf, 80)
    return buf.value.decode(errors="ignore")


def _uint(fn, *args) -> int | None:
    v = ctypes.c_uint()
    try:
        if getattr(_nvml, fn)(_handle, *args, ctypes.byref(v)) == 0:
            return v.value
    except AttributeError:
        pass
    return None


def read() -> dict:
    """{'util','temp','vram_used','vram_total','clock','mem_clock','power_w','fan','pcie_gen','pcie_gen_max',
    'pcie_width','pcie_width_max'} (valores ausentes = None)."""
    if not _init():
        return {}
    u, m = _Util(), _Mem()
    out = {}
    if _nvml.nvmlDeviceGetUtilizationRates(_handle, ctypes.byref(u)) == 0:
        out["util"] = u.gpu
    if _nvml.nvmlDeviceGetMemoryInfo(_handle, ctypes.byref(m)) == 0:
        out["vram_used"], out["vram_total"] = m.used, m.total
    out["temp"] = _uint("nvmlDeviceGetTemperature", 0)          # NVML_TEMPERATURE_GPU
    out["clock"] = _uint("nvmlDeviceGetClockInfo", 0)           # graphics
    out["mem_clock"] = _uint("nvmlDeviceGetClockInfo", 2)       # memory
    p = _uint("nvmlDeviceGetPowerUsage")
    out["power_w"] = p / 1000 if p is not None else None
    out["fan"] = _uint("nvmlDeviceGetFanSpeed")
    out["pcie_gen"] = _uint("nvmlDeviceGetCurrPcieLinkGeneration")
    out["pcie_gen_max"] = _uint("nvmlDeviceGetMaxPcieLinkGeneration")
    out["pcie_width"] = _uint("nvmlDeviceGetCurrPcieLinkWidth")
    out["pcie_width_max"] = _uint("nvmlDeviceGetMaxPcieLinkWidth")
    return out
