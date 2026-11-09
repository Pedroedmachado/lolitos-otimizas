"""Análise do PC: classifica a máquina para recomendar só o que ajuda NELA.

Rápido (registro, psutil, API do Windows) — pode ser consultado a qualquer momento.
A parte lenta (tipo do disco do sistema) é medida uma vez em segundo plano e guardada."""
from __future__ import annotations

import ctypes
import re
import struct
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from lolitos.core import registry as reg
from lolitos.core import settings
from lolitos.core.system import IS_WIN, cpu_name, is_laptop, powershell, ram_gb, windows_build

GPU_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
TIER_NAMES = {"modesto": "PC modesto", "intermediario": "PC intermediário", "forte": "PC forte"}


@dataclass
class Profile:
    cpu: str = ""
    vendor: str = ""              # intel | amd | outro
    cores: int = 0
    threads: int = 0
    hybrid: bool = False          # Intel com P-cores e E-cores
    pcores: list[int] = field(default_factory=list)   # CPUs lógicas dos núcleos de desempenho
    x3d: bool = False
    x3d_dual_ccd: bool = False    # 7900X3D/7950X3D/9900X3D/9950X3D
    ram_gb: float = 0.0
    laptop: bool = False
    gpus: list[str] = field(default_factory=list)
    gpu_vendor: str = ""          # nvidia | amd | intel | ""
    dedicated_gpu: bool = False
    hags_capable: bool = False
    system_ssd: bool | None = None
    wifi: bool = False
    win11: bool = False
    tier: str = "intermediario"

    @property
    def tier_name(self) -> str:
        return TIER_NAMES.get(self.tier, self.tier)

    def summary(self) -> list[str]:
        out = [f"{self.cpu} · {self.cores} núcleos / {self.threads} threads"
               + (" · híbrido (P+E)" if self.hybrid else "") + (" · 3D V-Cache" if self.x3d else ""),
               f"{self.ram_gb:.0f} GB de RAM",
               ", ".join(self.gpus) or "Placa de vídeo não identificada",
               ("Notebook" if self.laptop else "Desktop") + " · Windows " + ("11" if self.win11 else "10")
               + (" · sistema em SSD" if self.system_ssd else " · sistema em HD" if self.system_ssd is False else "")]
        return out


# ------------------------------------------------------------------ processador
def _core_efficiency() -> list[tuple[int, list[int]]]:
    """[(classe_de_eficiência, [cpus lógicas])] por núcleo físico — via GetLogicalProcessorInformationEx."""
    if not IS_WIN:
        return []
    k32 = ctypes.windll.kernel32
    size = ctypes.c_ulong(0)
    k32.GetLogicalProcessorInformationEx(0, None, ctypes.byref(size))   # RelationProcessorCore = 0
    if not size.value:
        return []
    buf = ctypes.create_string_buffer(size.value)
    if not k32.GetLogicalProcessorInformationEx(0, buf, ctypes.byref(size)):
        return []
    raw, off, out = buf.raw, 0, []
    while off < size.value:
        rel, sz = struct.unpack_from("<II", raw, off)
        if rel == 0:
            eff = raw[off + 9]
            group_count = struct.unpack_from("<H", raw, off + 30)[0]
            cpus = []
            for g in range(group_count):
                mask, group = struct.unpack_from("<QH", raw, off + 32 + g * 16)
                cpus += [group * 64 + b for b in range(64) if mask >> b & 1]
            out.append((eff, cpus))
        off += sz or 1
    return out


def _gpus() -> list[str]:
    names = []
    for sub in reg.subkeys("HKLM", GPU_CLASS):
        if not sub.isdigit():
            continue
        d = reg.read("HKLM", f"{GPU_CLASS}\\{sub}", "DriverDesc")
        if d and str(d[1]).strip() and "basic" not in str(d[1]).lower() and "virtual" not in str(d[1]).lower():
            n = str(d[1]).strip()
            if n not in names:
                names.append(n)
    return names


def _is_dedicated(name: str) -> bool:
    n = name.lower()
    if "nvidia" in n or "geforce" in n or "quadro" in n or "rtx" in n:
        return True
    if "arc" in n and "intel" in n:
        return True
    if ("amd" in n or "radeon" in n) and re.search(r"\b(rx|r9|r7|pro w|vega 56|vega 64)\b", n):
        return True
    return False


def _hags_capable(names: list[str]) -> bool:
    """HAGS: NVIDIA GTX 10xx+, AMD RX 5000+, Intel Arc (driver atual)."""
    for n in (x.lower() for x in names):
        if re.search(r"rtx|gtx 1[0-6]\d\d|gtx 16", n):
            return True
        m = re.search(r"rx\s?(\d{4})", n)
        if m and int(m.group(1)) >= 5000:
            return True
        if "arc" in n and "intel" in n:
            return True
    return False


def _wifi() -> bool:
    try:
        import psutil
        return any(re.search(r"wi-?fi|wlan|wireless|sem fio", n, re.I) for n in psutil.net_if_stats())
    except Exception:
        return False


def _system_ssd() -> bool | None:
    slow = settings.get("pc_profile_slow", {}) or {}
    if slow and time.time() - slow.get("t", 0) < 7 * 86400:
        return slow.get("ssd")
    return None


def refresh_slow(force: bool = False) -> None:
    """Mede o tipo do disco do Windows (≈1 s via PowerShell) e guarda por 7 dias."""
    if not force and _system_ssd() is not None:
        return
    r = powershell("(Get-Partition -DriveLetter ($env:SystemDrive[0]) | Get-Disk | Get-PhysicalDisk).MediaType",
                   timeout=60)
    media = r.out.strip().upper() if r.ok else ""
    ssd = True if "SSD" in media else False if "HDD" in media else None
    if ssd is None:   # NVMe às vezes vem 'Unspecified'
        r2 = powershell("(Get-Partition -DriveLetter ($env:SystemDrive[0]) | Get-Disk).BusType", timeout=60)
        if r2.ok and "NVME" in r2.out.upper():
            ssd = True
    settings.set("pc_profile_slow", {"t": time.time(), "ssd": ssd})
    detect.cache_clear()


@lru_cache(maxsize=1)
def detect() -> Profile:
    import psutil
    p = Profile()
    p.cpu = cpu_name()
    low = p.cpu.lower()
    p.vendor = "intel" if "intel" in low else "amd" if ("amd" in low or "ryzen" in low) else "outro"
    p.threads = psutil.cpu_count(logical=True) or 1
    p.cores = psutil.cpu_count(logical=False) or p.threads
    cores = _core_efficiency()
    if cores:
        classes = {c for c, _ in cores}
        if len(classes) > 1:
            p.hybrid = True
            top = max(classes)
            p.pcores = sorted(cpu for c, cpus in cores if c == top for cpu in cpus)
    p.x3d = "x3d" in low
    p.x3d_dual_ccd = p.x3d and bool(re.search(r"\b(7900|7950|9900|9950)x3d", low))
    p.ram_gb = ram_gb()
    p.laptop = is_laptop()
    p.gpus = _gpus()
    p.dedicated_gpu = any(_is_dedicated(n) for n in p.gpus)
    lows = " ".join(p.gpus).lower()
    p.gpu_vendor = ("nvidia" if "nvidia" in lows else "amd" if ("amd" in lows or "radeon" in lows)
                    else "intel" if "intel" in lows else "")
    if p.dedicated_gpu:   # fabricante da dedicada tem prioridade
        ded = next(n for n in p.gpus if _is_dedicated(n)).lower()
        p.gpu_vendor = "nvidia" if "nvidia" in ded or "geforce" in ded else "amd" if "radeon" in ded else "intel"
    p.hags_capable = _hags_capable(p.gpus)
    p.system_ssd = _system_ssd()
    p.wifi = _wifi()
    p.win11 = windows_build() >= 22000
    # nível do PC
    if p.ram_gb < 12 or p.cores <= 4 or not p.dedicated_gpu:
        p.tier = "modesto"
    elif p.ram_gb >= 24 and p.cores >= 6 and p.dedicated_gpu:
        p.tier = "forte"
    else:
        p.tier = "intermediario"
    return p


def as_dict() -> dict:
    return asdict(detect())


# ------------------------------------------------------------------ atalhos para as regras do catálogo
def desktop() -> bool:
    return not detect().laptop


def ssd_or_unknown() -> bool:
    return detect().system_ssd is not False


def modest_or_mid() -> bool:
    return detect().tier != "forte"


def modest() -> bool:
    return detect().tier == "modesto"


def nvidia() -> bool:
    return detect().gpu_vendor == "nvidia"


def hags_ok() -> bool:
    return detect().hags_capable and windows_build() >= 19041


def wifi_desktop() -> bool:
    p = detect()
    return p.wifi and not p.laptop


def advice() -> list[tuple[str, str]]:
    """Dicas específicas para o tipo de PC (título, texto)."""
    p = detect()
    out = []
    if p.laptop:
        out.append(("Notebook", "Jogue na tomada e com o modo de energia 'Melhor desempenho'. O app mantém as "
                                "economias de bateria (núcleos, PCIe, USB, Wi-Fi) para não drenar a bateria fora "
                                "do jogo; o plano de desempenho entra só durante a partida."))
    if not p.dedicated_gpu:
        out.append(("Vídeo integrado", "Sem placa dedicada, a RAM vira memória de vídeo: dual channel faz muita "
                                       "diferença e o pacote 'PC modesto' corta peso visual do Windows."))
    if p.hybrid:
        out.append(("Processador híbrido (P-cores + E-cores)",
                    "Em jogos com travadas, use em Jogos › afinidade 'Só P-cores'. Mantenha o Windows 11 e o "
                    "driver de chipset/Intel DTT em dia: o agendador usa isso para colocar o jogo nos P-cores."))
    if p.x3d_dual_ccd:
        out.append(("Ryzen X3D com dois CCDs",
                    "O cache 3D fica em um dos CCDs. Instale o driver de chipset AMD e deixe a Xbox Game Bar "
                    "instalada (é ela que avisa o driver que um jogo está aberto). Em jogos que ficarem no CCD "
                    "errado, use a afinidade 'CCD com V-Cache'."))
    elif p.x3d:
        out.append(("Ryzen X3D", "Um CCD só: não precisa de afinidade. EXPO/XMP ligado e driver de chipset AMD "
                                 "em dia já entregam o melhor do cache 3D."))
    if p.system_ssd is False:
        out.append(("Windows em HD", "O SysMain fica ligado (ele acelera o HD). Se puder, instale um SSD — é o "
                                     "maior ganho possível nesse PC."))
    if p.ram_gb < 12:
        out.append(("Pouca RAM", f"{p.ram_gb:.0f} GB: feche o navegador antes de jogar e use 'Preparar e jogar' "
                                 "(libera RAM). A compressão de memória continua ligada porque ajuda nesse caso."))
    return out
