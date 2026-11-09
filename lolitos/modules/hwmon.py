"""Leituras de sensores para o Hardware Monitor, sem driver próprio.

* Clock de cada núcleo: contadores de desempenho do Windows (PDH, 'Processor Information'), o mesmo cálculo do
  Gerenciador de Tarefas: frequência base × % de desempenho.
* Uso por núcleo, memória, discos e rede: psutil.
* Placa NVIDIA: NVML (temperatura, clocks, uso, VRAM, energia, ventoinha).
* Temperatura do processador: LibreHardwareMonitor/HWiNFO abertos ou zona térmica ACPI (lolitos.modules.sensors).
"""
from __future__ import annotations

import ctypes
import platform
import time
from dataclasses import dataclass

import psutil

from lolitos.core.system import IS_WIN


@dataclass
class Reading:
    device: str      # "AMD Ryzen 7 9800X3D…"
    group: str       # "Clocks", "Utilização"…
    name: str        # "Núcleo #0"
    value: float | None
    unit: str        # "MHz", "%", "°C"…


def cpu_name() -> str:
    if IS_WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    return platform.processor() or "Processador"


# ------------------------------------------------------------------ clocks por núcleo (PDH)
class _PdhCore:
    """'\\Processor Information(*)\\Processor Frequency' × '% Processor Performance' / 100, por núcleo lógico."""

    class _Item(ctypes.Structure):
        class _Val(ctypes.Structure):
            _fields_ = [("CStatus", ctypes.c_ulong), ("doubleValue", ctypes.c_double)]
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
            self.c_freq, self.c_perf = ctypes.c_void_p(), ctypes.c_void_p()
            add = self.pdh.PdhAddEnglishCounterW
            if add(self.q, "\\Processor Information(*)\\Processor Frequency", None, ctypes.byref(self.c_freq)):
                return
            add(self.q, "\\Processor Information(*)\\% Processor Performance", None, ctypes.byref(self.c_perf))
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

    def read(self) -> list[float]:
        if not self.ok or self.pdh.PdhCollectQueryData(self.q):
            return []
        freq, perf = self._array(self.c_freq), self._array(self.c_perf)
        out = []
        for name, f in freq.items():
            if "_Total" in name:
                continue
            try:
                grp, idx = name.split(",")
                key = (int(grp), int(idx))
            except ValueError:
                continue
            out.append((key, f * perf.get(name, 100.0) / 100.0))
        return [v for _, v in sorted(out)]


_PDH: _PdhCore | None = None
_prev_io: dict = {}


def _rate(key: str, value: float) -> float | None:
    now = time.time()
    old = _prev_io.get(key)
    _prev_io[key] = (now, value)
    if not old or now - old[0] <= 0:
        return None
    return max(0.0, (value - old[1]) / (now - old[0]))


def read_all() -> list[Reading]:
    """Uma leitura de todos os sensores disponíveis (rápida: < 50 ms, sem PowerShell)."""
    global _PDH
    out: list[Reading] = []
    cpu = cpu_name()
    if _PDH is None:
        _PDH = _PdhCore()
    clocks = _PDH.read()
    if not clocks:
        f = psutil.cpu_freq()
        if f and f.current:
            clocks = [f.current]
    phys = psutil.cpu_count(logical=False) or 1
    logical = psutil.cpu_count() or 1
    if clocks:
        out.append(Reading(cpu, "Clocks", "Média", sum(clocks) / len(clocks), "MHz"))
        step = max(1, len(clocks) // phys) if len(clocks) == logical else 1
        for i, v in enumerate(clocks[::step]):
            out.append(Reading(cpu, "Clocks", f"Núcleo #{i}", v, "MHz"))
    from lolitos.modules import sensors
    t, src = sensors.cpu_temp(10)
    if t is not None:
        out.append(Reading(cpu, "Temperaturas", f"Processador ({src})", t, "°C"))
    per = psutil.cpu_percent(percpu=True)
    out.append(Reading(cpu, "Utilização", "Processador (total)", sum(per) / max(1, len(per)), "%"))
    step = max(1, len(per) // phys) if len(per) == logical and logical > phys else 1
    for i in range(0, len(per), step):
        out.append(Reading(cpu, "Utilização", f"Núcleo #{i // step}", max(per[i:i + step]), "%"))

    from lolitos.modules import gpu
    if gpu.available():
        g, gname = gpu.read(), gpu.name() or "Placa de vídeo"
        if g.get("temp") is not None:
            out.append(Reading(gname, "Temperaturas", "GPU", g["temp"], "°C"))
        if g.get("clock") is not None:
            out.append(Reading(gname, "Clocks", "Núcleo (gráficos)", g["clock"], "MHz"))
        if g.get("mem_clock") is not None:
            out.append(Reading(gname, "Clocks", "Memória", g["mem_clock"], "MHz"))
        if g.get("util") is not None:
            out.append(Reading(gname, "Utilização", "GPU", g["util"], "%"))
        if g.get("vram_used") is not None and g.get("vram_total"):
            out.append(Reading(gname, "Utilização", "Memória de vídeo", g["vram_used"] / g["vram_total"] * 100, "%"))
            out.append(Reading(gname, "Dados", "VRAM em uso", g["vram_used"] / 1024 ** 3, "GB"))
        if g.get("power_w") is not None:
            out.append(Reading(gname, "Energia", "Placa", g["power_w"], "W"))
        if g.get("fan") is not None:
            out.append(Reading(gname, "Ventoinhas", "Ventoinha", g["fan"], "%"))

    vm = psutil.virtual_memory()
    out.append(Reading("Memória", "Utilização", "Memória em uso", vm.percent, "%"))
    out.append(Reading("Memória", "Dados", "Em uso", vm.used / 1024 ** 3, "GB"))
    out.append(Reading("Memória", "Dados", "Disponível", vm.available / 1024 ** 3, "GB"))
    sw = psutil.swap_memory()
    if sw.total:
        out.append(Reading("Memória", "Utilização", "Arquivo de paginação", sw.percent, "%"))

    try:
        disks = psutil.disk_io_counters(perdisk=True) or {}
    except (OSError, RuntimeError):
        disks = {}
    for name, d in disks.items():
        dev = f"Disco {name.replace('PhysicalDrive', '')}"
        r, w = _rate(f"dr{name}", d.read_bytes), _rate(f"dw{name}", d.write_bytes)
        out.append(Reading(dev, "Velocidade", "Leitura", None if r is None else r / 1024 ** 2, "MB/s"))
        out.append(Reading(dev, "Velocidade", "Escrita", None if w is None else w / 1024 ** 2, "MB/s"))
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        out.append(Reading("Armazenamento", "Espaço usado", part.device.rstrip("\\"), u.percent, "%"))

    stats = psutil.net_if_stats()
    for name, n in (psutil.net_io_counters(pernic=True) or {}).items():
        st = stats.get(name)
        if not st or not st.isup or "loopback" in name.lower() or (n.bytes_recv + n.bytes_sent) == 0:
            continue
        rx, tx = _rate(f"nr{name}", n.bytes_recv), _rate(f"nt{name}", n.bytes_sent)
        out.append(Reading(f"Rede · {name}", "Velocidade", "Download", None if rx is None else rx * 8 / 1e6, "Mbps"))
        out.append(Reading(f"Rede · {name}", "Velocidade", "Upload", None if tx is None else tx * 8 / 1e6, "Mbps"))
    return out
