"""Detalhes do processador para a tela Meu PC: identificação (família, modelo, stepping, microcódigo), codinome e
arquitetura, caches, instruções e clocks ao vivo. Tudo lido do próprio Windows; nada é alterado.

A tabela de codinomes é nossa, montada a partir das famílias/modelos públicos da AMD e da Intel. Quando o modelo não
está na tabela, a tela simplesmente não mostra o codinome."""
from __future__ import annotations

import ctypes
import re
import struct
from dataclasses import dataclass, field

from lolitos.core.system import IS_WIN

# ---------------------------------------------------------------- codinomes
# (família, faixa de modelos) → (codinome, arquitetura, processo)
AMD = [
    (0x17, range(0x00, 0x08), "Summit Ridge", "Zen", "14 nm"),
    (0x17, range(0x08, 0x10), "Pinnacle Ridge", "Zen+", "12 nm"),
    (0x17, range(0x11, 0x12), "Raven Ridge", "Zen", "14 nm"),
    (0x17, range(0x18, 0x19), "Picasso", "Zen+", "12 nm"),
    (0x17, range(0x20, 0x21), "Dali", "Zen", "14 nm"),
    (0x17, range(0x31, 0x32), "Castle Peak", "Zen 2", "7 nm"),
    (0x17, range(0x60, 0x61), "Renoir", "Zen 2", "7 nm"),
    (0x17, range(0x68, 0x69), "Lucienne", "Zen 2", "7 nm"),
    (0x17, range(0x71, 0x72), "Matisse", "Zen 2", "7 nm"),
    (0x17, range(0x90, 0x92), "Van Gogh", "Zen 2", "7 nm"),
    (0x17, range(0xA0, 0xB0), "Mendocino", "Zen 2", "6 nm"),
    (0x19, range(0x20, 0x22), "Vermeer", "Zen 3", "7 nm"),
    (0x19, range(0x40, 0x48), "Rembrandt", "Zen 3+", "6 nm"),
    (0x19, range(0x50, 0x51), "Cezanne", "Zen 3", "7 nm"),
    (0x19, range(0x61, 0x62), "Raphael", "Zen 4", "5 nm"),
    (0x19, range(0x74, 0x76), "Phoenix", "Zen 4", "4 nm"),
    (0x19, range(0x78, 0x79), "Phoenix 2", "Zen 4", "4 nm"),
    (0x1A, range(0x20, 0x25), "Strix Point", "Zen 5", "4 nm"),
    (0x1A, range(0x40, 0x48), "Granite Ridge", "Zen 5", "4 nm"),
    (0x1A, range(0x60, 0x61), "Krackan Point", "Zen 5", "4 nm"),
    (0x1A, range(0x70, 0x71), "Strix Halo", "Zen 5", "4 nm"),
]
INTEL = {  # família 6
    0x2A: ("Sandy Bridge", "Sandy Bridge", "32 nm"), 0x3A: ("Ivy Bridge", "Ivy Bridge", "22 nm"),
    0x3C: ("Haswell", "Haswell", "22 nm"), 0x45: ("Haswell", "Haswell", "22 nm"), 0x46: ("Haswell", "Haswell", "22 nm"),
    0x3D: ("Broadwell", "Broadwell", "14 nm"), 0x47: ("Broadwell", "Broadwell", "14 nm"),
    0x4E: ("Skylake", "Skylake", "14 nm"), 0x5E: ("Skylake", "Skylake", "14 nm"),
    0x8E: ("Kaby Lake / Whiskey Lake", "Skylake", "14 nm"), 0x9E: ("Kaby Lake / Coffee Lake", "Skylake", "14 nm"),
    0xA5: ("Comet Lake", "Skylake", "14 nm"), 0xA6: ("Comet Lake", "Skylake", "14 nm"),
    0xA7: ("Rocket Lake", "Cypress Cove", "14 nm"), 0x7E: ("Ice Lake", "Sunny Cove", "10 nm"),
    0x8C: ("Tiger Lake", "Willow Cove", "10 nm SuperFin"), 0x8D: ("Tiger Lake", "Willow Cove", "10 nm SuperFin"),
    0x97: ("Alder Lake", "Golden Cove + Gracemont", "Intel 7"), 0x9A: ("Alder Lake", "Golden Cove + Gracemont", "Intel 7"),
    0xB7: ("Raptor Lake", "Raptor Cove + Gracemont", "Intel 7"), 0xBA: ("Raptor Lake", "Raptor Cove + Gracemont", "Intel 7"),
    0xBF: ("Raptor Lake", "Raptor Cove + Gracemont", "Intel 7"),
    0xAA: ("Meteor Lake", "Redwood Cove + Crestmont", "Intel 4"), 0xAC: ("Meteor Lake", "Redwood Cove + Crestmont", "Intel 4"),
    0xBD: ("Lunar Lake", "Lion Cove + Skymont", "TSMC N3B"),
    0xC5: ("Arrow Lake", "Lion Cove + Skymont", "TSMC N3B"), 0xC6: ("Arrow Lake", "Lion Cove + Skymont", "TSMC N3B"),
}
# TDP de fábrica dos modelos mais comuns (W). Sem o modelo na lista, a linha não aparece.
TDP = [
    (r"9950X3D|9950X\b", 170), (r"9900X3D", 120), (r"9900X\b", 120), (r"9800X3D", 120), (r"9700X", 65),
    (r"9600X", 65), (r"7950X3D", 120), (r"7950X\b", 170), (r"7900X3D", 120), (r"7900X\b", 170), (r"7900\b", 65),
    (r"7800X3D", 120), (r"7700X", 105), (r"7700\b", 65), (r"7600X3D", 65), (r"7600X", 105), (r"7600\b", 65),
    (r"5950X", 105), (r"5900X", 105), (r"5800X3D", 105), (r"5800X\b", 105), (r"5700X3D", 105), (r"5700X\b", 65),
    (r"5600X3D", 105), (r"5600X\b", 65), (r"5600\b", 65), (r"5500\b", 65), (r"5700G", 65), (r"5600G", 65),
    (r"3900X", 105), (r"3800X", 105), (r"3700X", 65), (r"3600X", 95), (r"3600\b", 65),
    (r"14900K", 125), (r"14700K", 125), (r"14600K", 125), (r"14400F?\b", 65), (r"13900K", 125), (r"13700K", 125),
    (r"13600K", 125), (r"13400F?\b", 65), (r"12900K", 125), (r"12700K", 125), (r"12600K", 125), (r"12400F?\b", 65),
    (r"Ultra 9 285K", 125), (r"Ultra 7 265K", 125), (r"Ultra 5 245K", 125),
]
# IsProcessorFeaturePresent → nome
FEATURES = [(3, "MMX"), (6, "SSE"), (10, "SSE2"), (13, "SSE3"), (36, "SSSE3"), (37, "SSE4.1"), (38, "SSE4.2"),
            (39, "AVX"), (40, "AVX2"), (41, "AVX-512F"), (28, "RDRAND"), (32, "RDTSCP"), (17, "NX")]


@dataclass
class CpuId:
    vendor: str = ""
    family: int = 0
    model: int = 0
    stepping: int = 0
    microcode: int = 0
    codename: str = ""
    arch: str = ""
    process: str = ""
    tdp: int = 0
    features: list[str] = field(default_factory=list)


def parse_identifier(ident: str) -> tuple[int, int, int]:
    """'AMD64 Family 26 Model 68 Stepping 0' → (26, 68, 0)."""
    def num(k):
        m = re.search(k + r"\s+(\d+)", ident)
        return int(m.group(1)) if m else 0
    return num("Family"), num("Model"), num("Stepping")


def family_text(fam: int) -> str:
    """Como o CPU-Z mostra: 'F (estendida 8) → 1Ah'."""
    if fam < 0xF:
        return f"{fam:X}h"
    return f"F (estendida {fam - 0xF:X}) → {fam:X}h"


def model_text(model: int) -> str:
    return f"{model & 0xF:X} (estendido {model >> 4:X}) → {model:X}h"


def lookup(vendor: str, fam: int, model: int, name: str = "") -> tuple[str, str, str, int]:
    code = arch = proc = ""
    if vendor == "amd":
        for f, rng, c, a, p in AMD:
            if f == fam and model in rng:
                code, arch, proc = c, a, p
                break
    elif vendor == "intel" and fam == 6 and model in INTEL:
        code, arch, proc = INTEL[model]
    tdp = next((w for rx, w in TDP if re.search(rx, name, re.I)), 0)
    return code, arch, proc, tdp


def _microcode(raw: bytes | None) -> int:
    if not raw or len(raw) < 8:
        return 0
    lo, hi = struct.unpack_from("<II", raw)
    return hi or lo


def read_id(name: str = "") -> CpuId:
    c = CpuId()
    if not IS_WIN:
        return c
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            ident = winreg.QueryValueEx(k, "Identifier")[0]
            vend = winreg.QueryValueEx(k, "VendorIdentifier")[0]
            try:
                raw = winreg.QueryValueEx(k, "Update Revision")[0]
            except OSError:
                raw = None
            if not name:
                name = winreg.QueryValueEx(k, "ProcessorNameString")[0]
    except OSError:
        return c
    c.vendor = "amd" if "AMD" in vend.upper() else "intel" if "INTEL" in vend.upper() else ""
    c.family, c.model, c.stepping = parse_identifier(ident)
    c.microcode = _microcode(raw if isinstance(raw, bytes) else None)
    c.codename, c.arch, c.process, c.tdp = lookup(c.vendor, c.family, c.model, name)
    try:
        f = ctypes.windll.kernel32.IsProcessorFeaturePresent
        c.features = ["x86-64"] + [n for i, n in FEATURES if f(i)]
    except (OSError, AttributeError):
        pass
    return c


# ---------------------------------------------------------------- caches
CACHE_TYPES = {0: "Unificado", 1: "Instruções", 2: "Dados", 3: "Trace"}


def parse_caches(raw: bytes) -> list[dict]:
    """Do buffer do GetLogicalProcessorInformationEx: um item por cache (nível, tipo, tamanho, vias, linha)."""
    out, off = [], 0
    while off + 8 <= len(raw):
        rel, sz = struct.unpack_from("<II", raw, off)
        if sz == 0:
            break
        if rel == 2:
            level, assoc = raw[off + 8], raw[off + 9]
            line, size, typ = struct.unpack_from("<HII", raw, off + 10)
            out.append({"level": level, "assoc": assoc, "line": line, "size": size, "type": typ})
        off += sz
    return out


def cache_rows(caches: list[dict]) -> list[tuple[str, str]]:
    """[('L1 Dados', '8 × 48 KB · 12-way · linha de 64 bytes'), …, ('L3 total', '96 MB')]."""
    groups: dict[tuple, int] = {}
    for c in caches:
        key = (c["level"], c["type"], c["size"], c["assoc"], c["line"])
        groups[key] = groups.get(key, 0) + 1
    rows = []
    for (lvl, typ, size, assoc, line), n in sorted(groups.items(), key=lambda x: (x[0][0], -x[0][1])):
        sz = f"{size // 1024 ** 2} MB" if size >= 1024 ** 2 else f"{size // 1024} KB"
        way = "totalmente associativo" if assoc == 0xFF else f"{assoc}-way"
        rows.append((f"L{lvl} {CACHE_TYPES.get(typ, '')}", f"{n} × {sz} · {way} · linha de {line} bytes"))
    l3 = sum(c["size"] for c in caches if c["level"] == 3)
    if l3:
        rows.append(("L3 total", f"{l3 // 1024 ** 2} MB"))
    return rows


def read_caches() -> list[dict]:
    if not IS_WIN:
        return []
    k32 = ctypes.windll.kernel32
    size = ctypes.c_ulong(0)
    k32.GetLogicalProcessorInformationEx(2, None, ctypes.byref(size))
    if not size.value:
        return []
    buf = ctypes.create_string_buffer(size.value)
    if not k32.GetLogicalProcessorInformationEx(2, buf, ctypes.byref(size)):
        return []
    return parse_caches(buf.raw[:size.value])


# ---------------------------------------------------------------- clocks ao vivo
def live_clocks() -> dict:
    """{'avg': MHz, 'max': MHz, 'mult': x} pelos contadores do Windows (os mesmos do Hardware Monitor)."""
    from lolitos.modules import hwmon
    if hwmon._PDH is None:
        hwmon._PDH = hwmon._PdhCore()
    v = hwmon._PDH.read()
    if not v:
        import psutil
        f = psutil.cpu_freq()
        v = [f.current] if f and f.current else []
    if not v:
        return {}
    avg = sum(v) / len(v)
    return {"avg": avg, "max": max(v), "mult": avg / 100.0}
