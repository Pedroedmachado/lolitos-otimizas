"""Topologia do processador: núcleos físicos (com as threads SMT de cada um) e CCDs (grupos que dividem o mesmo
cache L3). No Ryzen X3D com dois CCDs, o CCD de L3 maior é o que tem o 3D V-Cache.

Fonte: GetLogicalProcessorInformationEx (o mesmo que o Process Lasso e o Gerenciador de Tarefas usam)."""
from __future__ import annotations

import ctypes
import struct
from dataclasses import dataclass, field
from functools import lru_cache

from lolitos.core.system import IS_WIN

REL_CORE, REL_CACHE, REL_ALL = 0, 2, 0xFFFF


@dataclass
class Core:
    idx: int
    cpus: list[int]          # threads lógicas (2 com SMT)
    ccd: int = 0
    eff: int = 0


@dataclass
class Ccd:
    idx: int
    cpus: list[int] = field(default_factory=list)
    l3: int = 0              # bytes
    vcache: bool = False


@dataclass
class Topology:
    cores: list[Core]
    ccds: list[Ccd]

    @property
    def threads(self) -> list[int]:
        return sorted(c for core in self.cores for c in core.cpus)

    @property
    def smt(self) -> bool:
        return any(len(c.cpus) > 1 for c in self.cores)


def _mask_cpus(raw: bytes, off: int, count: int) -> list[int]:
    out = []
    for g in range(count):
        mask, group = struct.unpack_from("<QH", raw, off + g * 16)
        out += [group * 64 + b for b in range(64) if mask >> b & 1]
    return out


def parse(raw: bytes) -> tuple[list[tuple[int, list[int]]], list[tuple[int, list[int]]]]:
    """Lê o buffer do Windows: ([(eficiência, cpus) por núcleo], [(tamanho do L3, cpus) por cache L3])."""
    cores, l3 = [], []
    off = 0
    while off + 8 <= len(raw):
        rel, sz = struct.unpack_from("<II", raw, off)
        if sz == 0:
            break
        if rel == REL_CORE:
            eff = raw[off + 9]
            gc = struct.unpack_from("<H", raw, off + 30)[0] or 1
            cores.append((eff, _mask_cpus(raw, off + 32, gc)))
        elif rel == REL_CACHE and raw[off + 8] == 3:                 # Level 3
            size = struct.unpack_from("<I", raw, off + 12)[0]
            gc = struct.unpack_from("<H", raw, off + 38)[0] or 1
            l3.append((size, _mask_cpus(raw, off + 40, gc)))
        off += sz
    return cores, l3


def build(cores_raw, l3_raw, cpu_name: str = "") -> Topology:
    ccds = [Ccd(i, sorted(cpus), size) for i, (size, cpus) in enumerate(sorted(l3_raw, key=lambda x: min(x[1])))]
    if not ccds:
        ccds = [Ccd(0, sorted(c for _, cpus in cores_raw for c in cpus))]
    sizes = {c.l3 for c in ccds}
    if len(ccds) > 1 and len(sizes) > 1:
        top = max(sizes)
        for c in ccds:
            c.vcache = c.l3 == top
    elif "x3d" in cpu_name.lower():
        for c in ccds:
            c.vcache = True
    cores = []
    for i, (eff, cpus) in enumerate(sorted(cores_raw, key=lambda x: min(x[1]))):
        ccd = next((c.idx for c in ccds if set(cpus) <= set(c.cpus)), 0)
        cores.append(Core(i, sorted(cpus), ccd, eff))
    return Topology(cores, ccds)


def _fallback() -> Topology:
    import psutil
    n = psutil.cpu_count(logical=True) or 1
    phys = psutil.cpu_count(logical=False) or n
    step = max(1, n // phys)
    cores = [Core(i, list(range(i * step, min(n, i * step + step)))) for i in range(phys)]
    return Topology(cores, [Ccd(0, list(range(n)))])


@lru_cache(maxsize=1)
def detect() -> Topology:
    if not IS_WIN:
        return _fallback()
    from lolitos.modules.pcprofile import cpu_name
    k32 = ctypes.windll.kernel32
    size = ctypes.c_ulong(0)
    k32.GetLogicalProcessorInformationEx(REL_ALL, None, ctypes.byref(size))
    if not size.value:
        return _fallback()
    buf = ctypes.create_string_buffer(size.value)
    if not k32.GetLogicalProcessorInformationEx(REL_ALL, buf, ctypes.byref(size)):
        return _fallback()
    cores, l3 = parse(buf.raw[:size.value])
    if not cores:
        return _fallback()
    return build(cores, l3, cpu_name())
