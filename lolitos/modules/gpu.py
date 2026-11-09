"""Leituras da placa de vídeo: NVML (vem com o driver NVIDIA) e, nas outras placas (AMD, Intel), os contadores
de desempenho do próprio Windows — o mesmo que o Gerenciador de Tarefas mostra. Sem instalar nada."""
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


# ------------------------------------------------------------------ AMD/Intel: contadores do Windows (PDH)
class _PdhGpu:
    """Uso do motor 3D e VRAM dedicada por placa (LUID). Fica com a placa que mais usa VRAM dedicada,
    que é a placa de vídeo dedicada mesmo em PCs com vídeo integrado."""

    class _Item(ctypes.Structure):
        class _Val(ctypes.Structure):
            _fields_ = [("CStatus", ctypes.c_ulong), ("_pad", ctypes.c_ulong), ("doubleValue", ctypes.c_double)]
        _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _Val)]

    def __init__(self):
        self.ok = False
        if not IS_WIN:
            return
        try:
            self.pdh = ctypes.WinDLL("pdh")
            self.q = ctypes.c_void_p()
            if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(self.q)):
                return
            self.c_eng, self.c_mem = ctypes.c_void_p(), ctypes.c_void_p()
            add = self.pdh.PdhAddEnglishCounterW
            if add(self.q, "\\GPU Engine(*engtype_3D)\\Utilization Percentage", None, ctypes.byref(self.c_eng)):
                return
            add(self.q, "\\GPU Adapter Memory(*)\\Dedicated Usage", None, ctypes.byref(self.c_mem))
            self.pdh.PdhCollectQueryData(self.q)
            self.ok = True
        except (OSError, AttributeError):
            self.ok = False

    def _array(self, counter) -> dict[str, float]:
        PDH_FMT_DOUBLE = 0x200
        size, count = ctypes.c_ulong(0), ctypes.c_ulong(0)
        self.pdh.PdhGetFormattedCounterArrayW(counter, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), None)
        if not size.value:
            return {}
        buf = ctypes.create_string_buffer(size.value)
        if self.pdh.PdhGetFormattedCounterArrayW(counter, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count),
                                                 buf):
            return {}
        items = ctypes.cast(buf, ctypes.POINTER(self._Item * count.value)).contents
        return {it.szName: it.FmtValue.doubleValue for it in items if it.FmtValue.CStatus in (0, 1)}

    def read(self) -> dict:
        with _lock:
            if not self.ok or self.pdh.PdhCollectQueryData(self.q):
                return {}
            return pick_adapter(self._array(self.c_eng), self._array(self.c_mem))


def _luid(instance: str) -> str:
    """'pid_12_luid_0x00000000_0x0000D1A3_phys_0_eng_0_engtype_3D' → '0x00000000_0x0000D1A3'."""
    low = instance.lower()
    i = low.find("luid_")
    if i < 0:
        return ""
    parts = low[i + 5:].split("_")
    return "_".join(parts[:2])


def pick_adapter(engines: dict[str, float], memory: dict[str, float]) -> dict:
    """Soma o uso 3D por placa e escolhe a que tem mais VRAM dedicada em uso."""
    util: dict[str, float] = {}
    for inst, v in engines.items():
        lu = _luid(inst)
        if lu:
            util[lu] = util.get(lu, 0.0) + v
    mem: dict[str, float] = {}
    for inst, v in memory.items():
        lu = _luid(inst)
        if lu:
            mem[lu] = mem.get(lu, 0.0) + v
    if not util and not mem:
        return {}
    best = max(mem, key=mem.get) if mem and max(mem.values()) > 0 else max(util, key=util.get)
    out = {"util": round(min(100.0, util.get(best, 0.0)))}
    if best in mem:
        out["vram_used"] = int(mem[best])
    return out


_PDH: _PdhGpu | None = None


def _pdh() -> _PdhGpu:
    global _PDH
    if _PDH is None:
        _PDH = _PdhGpu()
    return _PDH


def available() -> bool:
    return _init() or _pdh().ok


def name() -> str:
    if not _init():
        return "Placa de vídeo" if _pdh().ok else ""
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
    'pcie_width','pcie_width_max'} (valores ausentes = None). Sem NVIDIA: uso e VRAM pelo Windows."""
    if not _init():
        return _pdh().read()
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
