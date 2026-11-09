"""Informações do hardware lidas do Windows (WMI/CIM via PowerShell). Nada é alterado."""
from __future__ import annotations

import re

from lolitos.core.system import as_list, powershell_json

SCRIPT = r"""
$o = [ordered]@{}
$o.cpu = Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L2CacheSize,L3CacheSize,SocketDesignation,Manufacturer,VirtualizationFirmwareEnabled
$o.ram = Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber,BankLabel,DeviceLocator,SMBIOSMemoryType
$o.slots = (Get-CimInstance Win32_PhysicalMemoryArray | Measure-Object -Property MemoryDevices -Sum).Sum
$o.board = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product
$o.bios = Get-CimInstance Win32_BIOS | Select-Object SMBIOSBIOSVersion,@{n='Date';e={$_.ReleaseDate.ToString('dd/MM/yyyy')}}
$o.gpu = Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,AdapterRAM
$o.disks = Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,HealthStatus,@{n='Size';e={[int64]$_.Size}}
$o.os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,@{n='Boot';e={$_.LastBootUpTime.ToString('o')}}
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


def read_all() -> dict:
    d = powershell_json(SCRIPT, timeout=120) or {}
    for k in ("cpu", "ram", "gpu", "disks", "av"):
        d[k] = [x for x in as_list(d.get(k)) if x]
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
