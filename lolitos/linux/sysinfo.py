"""Informações do PC lidas do Linux (/proc, /sys, nvidia-smi)."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from pathlib import Path


def _txt(path: str) -> str:
    try:
        return Path(path).read_text(errors="replace").strip()
    except OSError:
        return ""


def distro() -> str:
    for ln in _txt("/etc/os-release").splitlines():
        if ln.startswith("PRETTY_NAME="):
            return ln.split("=", 1)[1].strip('"')
    return platform.system()


def cpu_model() -> str:
    for ln in _txt("/proc/cpuinfo").splitlines():
        if ln.lower().startswith("model name"):
            return ln.split(":", 1)[1].strip()
    return platform.processor() or "—"


def governor() -> str:
    return _txt("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") or "—"


def cpu_driver() -> str:
    return _txt("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver") or "—"


def board() -> str:
    d = "/sys/class/dmi/id/"
    return " ".join(x for x in (_txt(d + "board_vendor"), _txt(d + "board_name")) if x) or "—"


def bios() -> str:
    d = "/sys/class/dmi/id/"
    return " · ".join(x for x in (_txt(d + "bios_version"), _txt(d + "bios_date")) if x) or "—"


def disks() -> list[dict]:
    out = []
    for b in sorted(Path("/sys/block").glob("*")) if Path("/sys/block").exists() else []:
        if b.name.startswith(("loop", "ram", "zram", "dm-", "sr")):
            continue
        try:
            size = int(_txt(str(b / "size")) or 0) * 512
        except ValueError:
            size = 0
        if size <= 0:
            continue
        kind = "NVMe" if b.name.startswith("nvme") else ("HDD" if _txt(str(b / "queue/rotational")) == "1" else "SSD")
        sched = _txt(str(b / "queue/scheduler"))
        if "[" in sched:
            sched = sched.split("[", 1)[1].split("]", 1)[0]
        out.append({"dev": b.name, "model": _txt(str(b / "device/model")) or b.name, "size": size, "kind": kind,
                    "scheduler": sched})
    return out


_GPU: dict = {"t": 0.0, "v": {}}
_Q = "name,driver_version,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw"


def gpu(max_age: float = 0.9) -> dict:
    """Placa NVIDIA pelo nvidia-smi ({} se não houver). Leitura guardada por ~1 s."""
    if time.time() - _GPU["t"] < max_age:
        return _GPU["v"]
    v: dict = {}
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            r = subprocess.run([exe, f"--query-gpu={_Q}", "--format=csv,noheader,nounits"], capture_output=True,
                               text=True, timeout=4)
            v = parse_smi(r.stdout) if r.returncode == 0 else {}
        except (OSError, subprocess.SubprocessError):
            v = {}
    _GPU.update(t=time.time(), v=v)
    return v


def parse_smi(text: str) -> dict:
    line = (text.strip().splitlines() or [""])[0]
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 7:
        return {}

    def num(s):
        try:
            return float(s)
        except ValueError:
            return None
    return {"name": parts[0], "driver": parts[1], "vram_total": num(parts[2]), "vram_used": num(parts[3]),
            "util": num(parts[4]), "temp": num(parts[5]), "power": num(parts[6])}


def gpu_name() -> str:
    g = gpu(30)
    if g.get("name"):
        return g["name"]
    exe = shutil.which("lspci")
    if exe:
        try:
            for ln in subprocess.run([exe], capture_output=True, text=True, timeout=5).stdout.splitlines():
                if "VGA" in ln or "3D controller" in ln:
                    return ln.split(":", 2)[-1].strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return "—"


def cpu_temp() -> float | None:
    try:
        import psutil
        t = psutil.sensors_temperatures()
    except Exception:  # noqa: BLE001
        return None
    for chip in ("k10temp", "zenpower", "coretemp"):
        for e in t.get(chip, []):
            if e.current:
                return float(e.current)
    return None


def session() -> str:
    return " · ".join(x for x in (os.environ.get("XDG_CURRENT_DESKTOP", ""),
                                  os.environ.get("XDG_SESSION_TYPE", "")) if x) or "—"


def uptime_s() -> float:
    try:
        return float(_txt("/proc/uptime").split()[0])
    except (ValueError, IndexError):
        return 0.0


def summary() -> list[tuple[str, str]]:
    import psutil

    from lolitos.core.system import human_size
    up = int(uptime_s())
    g = gpu(30)
    rows = [("Sistema", f"{distro()} · kernel {platform.release()}"), ("Sessão", session()),
            ("Processador", cpu_model()),
            ("Núcleos", f"{psutil.cpu_count(logical=False)} núcleos / {psutil.cpu_count()} threads · "
                        f"{cpu_driver()} · {governor()}"),
            ("Memória RAM", human_size(psutil.virtual_memory().total)),
            ("Placa de vídeo", gpu_name() + (f" · driver {g['driver']}" if g.get("driver") else "")),
            ("Placa-mãe", board()), ("BIOS", bios()),
            ("Discos", " · ".join(f"{d['model']} ({d['kind']}, {human_size(d['size'])})" for d in disks()) or "—"),
            ("Ligado há", f"{up // 3600} h {up % 3600 // 60} min")]
    return rows
