"""Temperatura da CPU sem driver próprio: LibreHardwareMonitor/HWiNFO (se abertos) ou zona térmica ACPI."""
from __future__ import annotations

import time

from lolitos.core.system import as_list, powershell_json

_cache = {"t": 0.0, "v": None, "src": ""}


def cpu_temp(max_age: float = 5.0) -> tuple[float | None, str]:
    if time.time() - _cache["t"] < max_age:
        return _cache["v"], _cache["src"]
    v, src = None, ""
    rows = powershell_json(
        "Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -EA SilentlyContinue |"
        " Where-Object { $_.SensorType -eq 'Temperature' -and $_.Parent -like '*cpu*' } |"
        " Select-Object Name,Value", timeout=15)
    rows = [r for r in as_list(rows) if r and r.get("Value")]
    if rows:
        pref = [r for r in rows if any(k in r["Name"] for k in ("Tctl", "Tdie", "Package", "CCD"))] or rows
        v, src = float(pref[0]["Value"]), "LibreHardwareMonitor"
    else:
        z = powershell_json("Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -EA "
                            "SilentlyContinue | Select-Object -ExpandProperty CurrentTemperature", timeout=15)
        z = [x for x in as_list(z) if x]
        if z:
            c = max(z) / 10 - 273.15
            if 10 < c < 120:
                v, src = c, "ACPI (placa-mãe)"
    _cache.update(t=time.time(), v=v, src=src)
    return v, src
