"""Informações do hardware lidas do Windows (WMI/CIM via PowerShell). Nada é alterado."""
from __future__ import annotations

import re

from lolitos.core.system import as_list, powershell_json

SCRIPT = r"""
$o = [ordered]@{}
$o.cpu = Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L2CacheSize,L3CacheSize,SocketDesignation,Manufacturer,VirtualizationFirmwareEnabled
$o.ram = Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber,BankLabel,DeviceLocator,SMBIOSMemoryType,ConfiguredVoltage,SerialNumber
$o.slots = (Get-CimInstance Win32_PhysicalMemoryArray | Measure-Object -Property MemoryDevices -Sum).Sum
$o.board = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,Version
$o.bios = Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,@{n='Date';e={$_.ReleaseDate.ToString('dd/MM/yyyy')}}
$o.gpu = Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,AdapterRAM,AdapterCompatibility,PNPDeviceID,VideoProcessor,@{n='DriverDate';e={if($_.DriverDate){$_.DriverDate.ToString('dd/MM/yyyy')}}}
$o.vram = @(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*' -ErrorAction SilentlyContinue | Where-Object { $_.'HardwareInformation.qwMemorySize' } | ForEach-Object { [ordered]@{desc=$_.DriverDesc; bytes=[int64]$_.'HardwareInformation.qwMemorySize'} })
$o.disks = @(Get-PhysicalDisk | ForEach-Object { [ordered]@{FriendlyName=$_.FriendlyName; MediaType=[string]$_.MediaType; BusType=[string]$_.BusType; HealthStatus=[string]$_.HealthStatus; Size=[int64]$_.Size; DeviceId=[string]$_.DeviceId} })
$o.os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture,@{n='Boot';e={$_.LastBootUpTime.ToString('o')}},@{n='Installed';e={$_.InstallDate.ToString('dd/MM/yyyy')}}
try { $o.secureboot = [bool](Confirm-SecureBootUEFI) } catch { $o.secureboot = $null }
try { $t = Get-Tpm; $o.tpm = [ordered]@{present=$t.TpmPresent;ready=$t.TpmReady} } catch { $o.tpm = $null }
try { $o.av = Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct | Select-Object displayName,productState } catch { $o.av = @() }
$o.firmware = $env:firmware_type
$o
"""

DDR = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5", 35: "LPDDR5"}


def _speed_from_part(part: str) -> int:
    """Velocidade nominal pelo código do pente (G.Skill F5-6000…, Corsair …B6000C30, Kingston KF560C36…)."""
    p = part.upper().replace(" ", "")
    m = re.search(r"KF(\d{3})C", p)
    if m:
        return int(m.group(1)) * 10
    nums = [int(x) for x in re.findall(r"(?<!\d)([2-8]\d00)(?!\d)", p) if 2133 <= int(x) <= 9000]
    return max(nums) if nums else 0


# Temperatura, desgaste e horas dos discos: só no Meu PC (em alguns PCs essa leitura demora muito).
DISK_HEALTH = r"""
@(Get-PhysicalDisk | ForEach-Object { $r = $_ | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue;
  [ordered]@{DeviceId=[string]$_.DeviceId; Temperature=$r.Temperature; Wear=$r.Wear; PowerOnHours=$r.PowerOnHours} })
"""
_CACHE: dict = {"t": 0.0, "d": None}
_CACHE_S = 600


def read_all(full: bool = False) -> dict:
    """Hardware lido do Windows. A leitura básica fica guardada por 10 minutos (o hardware não muda) e é a que o
    Painel e o Check-up usam; full=True acrescenta a saúde dos discos (só o Meu PC pede)."""
    import copy
    import time
    if _CACHE["d"] is None or time.time() - _CACHE["t"] > _CACHE_S:
        d = powershell_json(SCRIPT, timeout=90) or {}
        for k in ("cpu", "ram", "gpu", "disks", "av", "vram"):
            d[k] = [x for x in as_list(d.get(k)) if x]
        if d.get("cpu") or d.get("os"):
            _CACHE.update(t=time.time(), d=d)
        else:
            return d
    d = copy.deepcopy(_CACHE["d"])
    if full:
        health = {x.get("DeviceId"): x for x in as_list(powershell_json(DISK_HEALTH, timeout=45)) if x}
        for disk in d["disks"]:
            h = health.get(disk.get("DeviceId")) or {}
            for k in ("Temperature", "Wear", "PowerOnHours"):
                if h.get(k) not in (None, ""):
                    disk[k] = h[k]
    return d


def ram_summary(d: dict) -> dict:
    sticks = d.get("ram", [])
    if not sticks:
        return {}
    total = sum(int(s.get("Capacity") or 0) for s in sticks)
    rated = max(int(s.get("Speed") or 0) for s in sticks)
    by_model = max((_speed_from_part(s.get("PartNumber") or "") for s in sticks), default=0)
    rated = max(rated, by_model)
    running = min(int(s.get("ConfiguredClockSpeed") or s.get("Speed") or 0) for s in sticks)
    kind = DDR.get(int(sticks[0].get("SMBIOSMemoryType") or 0), "")
    parts = {(s.get("PartNumber") or "").strip() for s in sticks}
    sizes = {int(s.get("Capacity") or 0) for s in sticks}
    chans = set()
    for s in sticks:
        txt = f"{s.get('BankLabel', '')} {s.get('DeviceLocator', '')}".upper()
        m = re.search(r"CHANNEL\s*([A-D])", txt) or re.search(r"DIMM[_\s-]?([A-D])\d", txt) or \
            re.search(r"\b([A-D])[12]\b", txt) or re.search(r"CH(?:ANNEL)?\s*([A-D0-3])", txt)
        if m:
            chans.add(m.group(1))
    # XMP/EXPO: os pentes rodando abaixo da velocidade máxima informada pelo SPD/perfil
    xmp_off = rated > 0 and running > 0 and running < rated - 100
    # Em DDR5 muitas placas informam Speed=JEDEC (4800) mesmo com EXPO ligado; nesse caso
    # ConfiguredClockSpeed > Speed indica perfil ativo.
    xmp_on = running > rated + 100
    return {"total_gb": total / 1024 ** 3, "count": len(sticks), "rated": rated, "running": running,
            "kind": kind, "same_model": len(parts) <= 1 and len(sizes) <= 1, "channels": sorted(chans),
            "dual": len(chans) >= 2 if chans else None, "xmp_off": xmp_off, "xmp_on": xmp_on,
            "slots": d.get("slots"), "sticks": sticks}


# PCI: código do fabricante da placa (subsistema) → nome
SUBVENDORS = {
    "1458": "Gigabyte", "1043": "ASUS", "1462": "MSI", "3842": "EVGA", "19DA": "Zotac", "196E": "PNY",
    "10DE": "NVIDIA", "1DA2": "Sapphire", "174B": "Sapphire", "1682": "XFX", "148C": "PowerColor",
    "1849": "ASRock", "1B4C": "Galax / KFA2", "7377": "Colorful", "1569": "Palit", "10B0": "Gainward",
    "1002": "AMD", "8086": "Intel", "1028": "Dell", "103C": "HP", "17AA": "Lenovo", "1025": "Acer",
    "1D05": "Tongfang", "152D": "Quanta", "1558": "Clevo", "1179": "Toshiba", "144D": "Samsung", "1B0A": "Pegatron",
    "17C0": "Wistron", "1E83": "Gunnir", "1ACC": "Point of View", "1642": "Bitland", "16F3": "Jetway",
}


def board_vendor(pnp: str) -> str:
    """'PCI\\VEN_10DE&DEV_2F04&SUBSYS_41191458&REV_A1\\…' → 'Gigabyte'."""
    m = re.search(r"SUBSYS_[0-9A-F]{4}([0-9A-F]{4})", (pnp or "").upper())
    return SUBVENDORS.get(m.group(1), "") if m else ""


def gpu_vendor(v: dict) -> str:
    txt = f"{v.get('AdapterCompatibility', '')} {v.get('Name', '')}".upper()
    for k, name in (("NVIDIA", "NVIDIA"), ("AMD", "AMD"), ("ADVANCED MICRO", "AMD"), ("INTEL", "Intel")):
        if k in txt:
            return name
    return (v.get("AdapterCompatibility") or "").strip()


def vram_bytes(d: dict, v: dict) -> int:
    """AdapterRAM para em 4 GB; o registro do driver guarda o valor real."""
    for x in d.get("vram", []):
        if (x.get("desc") or "").strip() == (v.get("Name") or "").strip() and x.get("bytes"):
            return int(x["bytes"])
    return int(v.get("AdapterRAM") or 0)


def chipset(board_product: str) -> str:
    """Pelo nome da placa: 'PRIME X870-P' → 'X870', 'B550M AORUS' → 'B550', 'Z790-A' → 'Z790'."""
    m = re.search(r"(?<![A-Z0-9])([ABHXZQW]\d{3})[EM]?(?![0-9])", (board_product or "").upper())
    return m.group(1) if m else ""
