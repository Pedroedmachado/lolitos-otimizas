"""Check-up do PC: cada item é medido e comparado com um limite. Nada é alterado aqui."""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass

from lolitos.core import registry as reg
from lolitos.core.system import as_list, is_admin, powershell_json, ram_gb

OK, WARN, BAD = "ok", "atencao", "corrigir"


@dataclass
class Check:
    id: str
    title: str
    state: str
    detail: str
    fix: str = ""       # id de ajuste/ferramenta/página que resolve


def _pending_reboot() -> bool:
    return any(reg.key_exists("HKLM", p) for p in (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"))


def run_checkup(hw: dict | None = None) -> list[Check]:
    import psutil
    from lolitos.core import restore
    from lolitos.modules import display, hwinfo, startup
    out: list[Check] = []
    add = out.append

    add(Check("admin", "Rodando como administrador", OK if is_admin() else BAD,
              "Ajustes do sistema funcionam." if is_admin() else "Sem admin: ajustes, reparos e limpeza vão falhar.",
              "relaunch_admin"))

    last = restore.last_own_point()
    if last:
        days = (time.time() - last) / 86400
        add(Check("restore", "Ponto de restauração", OK if days < 30 else WARN,
                  f"Último criado por este app há {days:.0f} dia(s).", "restore_point"))
    else:
        add(Check("restore", "Ponto de restauração", WARN, "Nenhum criado por este app ainda.", "restore_point"))

    seen = set()
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype or part.mountpoint in seen:
            continue
        seen.add(part.mountpoint)
        try:
            u = shutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        if u.total < 1024 ** 3:   # partições minúsculas (recuperação/EFI)
            continue
        free = u.free / u.total * 100
        add(Check(f"disk_{part.device}", f"Espaço livre em {part.device}",
                  OK if free >= 15 else WARN if free >= 7 else BAD,
                  f"{u.free / 1024**3:.0f} GB livres de {u.total / 1024**3:.0f} GB ({free:.0f}%). Mantenha 15%+.",
                  "cleanup"))

    gb = ram_gb()
    add(Check("ram_amount", "Quantidade de RAM", OK if gb >= 15 else WARN,
              f"{gb:.0f} GB. " + ("Suficiente para BDO (Siege pede 16 GB+)." if gb >= 15
                                   else "O BDO em Guerra/Cerco pede 16 GB ou mais."), ""))

    hw = hw or hwinfo.read_all()
    rs = hwinfo.ram_summary(hw)
    if rs:
        if rs["xmp_off"]:
            add(Check("xmp", "Memória na velocidade máxima", BAD,
                      f"Os pentes suportam {rs['rated']} MT/s mas rodam a {rs['running']} MT/s. "
                      "Ative o XMP/EXPO na BIOS — ganho real de FPS mínimo no BDO.", "bios"))
        else:
            add(Check("xmp", "Memória na velocidade máxima", OK,
                      f"{rs['kind']} a {rs['running']} MT/s.", ""))
        if rs["count"] == 1:
            add(Check("dual", "Dual channel", BAD,
                      "Um pente só: a memória roda em single channel e perde até metade da banda.", "bios"))
        elif rs["dual"] is False:
            add(Check("dual", "Dual channel", WARN,
                      "Os pentes parecem estar no mesmo canal. Com 2 pentes numa placa de 4 slots, use A2 e B2.", ""))
        else:
            add(Check("dual", "Dual channel", OK, f"{rs['count']} pentes" +
                      (f" (canais {', '.join(rs['channels'])})" if rs["channels"] else ""), ""))
        if not rs["same_model"]:
            add(Check("same_ram", "Pentes iguais", WARN,
                      "Modelos ou tamanhos diferentes podem impedir o XMP/EXPO e causar instabilidade/crash.", ""))

    for d in hw.get("disks", []):
        h = (d.get("HealthStatus") or "").lower()
        if h and h != "healthy":
            add(Check("disk_health", f"Saúde do disco {d.get('FriendlyName')}", BAD,
                      "O Windows reporta problema neste disco. Faça backup agora.", ""))
        if (d.get("MediaType") or "") == "HDD":
            add(Check("hdd", f"{d.get('FriendlyName')} é um HD", WARN,
                      "Instale o BDO num SSD: carregamento de Siege e de regiões fica muito mais rápido.", ""))

    sb = hw.get("secureboot")
    if sb is not None:
        add(Check("secureboot", "Secure Boot", OK if sb else WARN,
                  "Ligado." if sb else "Desligado. Alguns anti-cheats e o Windows 11 exigem.", ""))
    tpm = hw.get("tpm") or {}
    if tpm:
        add(Check("tpm", "TPM 2.0", OK if tpm.get("ready") else WARN,
                  "Presente e pronto." if tpm.get("ready") else "Ausente ou desligado na BIOS (fTPM/PTT).", ""))

    avs = [a.get("displayName", "") for a in hw.get("av", [])]
    add(Check("av", "Antivírus", OK if avs else WARN,
              ", ".join(avs) if avs else "Nenhum antivírus registrado na Central de Segurança.", "antivirus"))

    if _pending_reboot():
        add(Check("reboot", "Reinicialização pendente", WARN,
                  "O Windows está esperando reiniciar para concluir atualizações.", "reboot"))

    boot = psutil.boot_time()
    days = (time.time() - boot) / 86400
    add(Check("uptime", "Tempo ligado", OK if days < 7 else WARN,
              f"Ligado há {days:.1f} dia(s). Reiniciar 1x por semana aplica atualizações e limpa a memória.", ""))

    try:
        n_start = sum(1 for e in startup.list_entries() if e.enabled)
        add(Check("startup", "Programas na inicialização", OK if n_start <= 12 else WARN,
                  f"{n_start} abrem com o Windows. Limite sugerido: 12.", "startup"))
    except OSError:
        pass

    try:
        mons = display.monitors()
        low = [m for m in mons if m["hz"] < m["max_hz"]]
        add(Check("refresh", "Monitor na taxa máxima", OK if not low else BAD,
                  "Todos no máximo." if not low else
                  "; ".join(f"{m['name']}: {m['hz']} Hz (aceita {m['max_hz']} Hz)" for m in low), "refresh_max"))
    except Exception:  # noqa: BLE001
        pass

    ev = powershell_json("Get-WinEvent -FilterHashtable @{LogName='System';Id=41;StartTime=(Get-Date).AddDays(-30)}"
                         " -ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count",
                         timeout=60)
    n41 = int(ev or 0) if not isinstance(ev, list) else len(as_list(ev))
    add(Check("kernel41", "Desligamentos inesperados (30 dias)", OK if n41 == 0 else WARN if n41 < 3 else BAD,
              "Nenhum." if n41 == 0 else f"{n41} desligamento(s) sem aviso: queda de energia, travamento, "
              "superaquecimento ou overclock/EXPO instável.", ""))
    return out


def score(checks: list[Check], tweak_ratio: float) -> int:
    """0–100: 60% ajustes recomendados ativos + 40% check-up."""
    if not checks:
        return int(tweak_ratio * 100)
    pts = sum({OK: 1.0, WARN: 0.5, BAD: 0.0}[c.state] for c in checks) / len(checks)
    return int(round(60 * tweak_ratio + 40 * pts))
