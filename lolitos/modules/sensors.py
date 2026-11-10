"""Temperatura da CPU: PawnIO (sensor do próprio processador, se instalado), LibreHardwareMonitor (se aberto) ou a
zona térmica ACPI da placa-mãe (aproximada; em muitos PCs fica parada)."""
from __future__ import annotations

import time

from lolitos.core.system import as_list, powershell_json

_cache = {"t": 0.0, "v": None, "src": ""}


def cpu_temp(max_age: float = 5.0) -> tuple[float | None, str]:
    from lolitos.modules import pawnio
    t = pawnio.cpu_temp()            # leitura direta e barata: pode ser chamada a cada segundo
    if t is not None:
        return t, "sensor do processador (PawnIO)"
    # as outras fontes abrem o PowerShell: com nada encontrado, só tenta de novo depois de 1 minuto
    age = max_age if _cache["v"] is not None else max(max_age, 60)
    if time.time() - _cache["t"] < age:
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
