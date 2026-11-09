"""Check-up do PC: cada item é medido e comparado com um limite. Nada é alterado aqui."""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass

from lolitos.core import registry as reg
from lolitos.core.system import as_list, is_admin, powershell_json, ram_gb

OK, WARN, BAD, INFO = "ok", "atencao", "corrigir", "info"


@dataclass
class Check:
    id: str
    title: str
    state: str
    detail: str
    fix: str = ""       # id de ajuste/ferramenta/página que resolve
    value: str = ""     # o que foi medido (coluna da direita)


def _pending_reboot() -> bool:
    return any(reg.key_exists("HKLM", p) for p in (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"))


_WIN_FACTS = r"""
$o = [ordered]@{}
try { $o.fw = @(Get-NetFirewallProfile -EA Stop | ForEach-Object { [bool]$_.Enabled }) } catch {}
try { $o.act = (Get-CimInstance SoftwareLicensingProduct -Filter "PartialProductKey IS NOT NULL AND ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f'" -EA Stop | Select-Object -First 1 -ExpandProperty LicenseStatus) } catch {}
try { $o.pnp = @(Get-PnpDevice -PresentOnly -Status ERROR -EA Stop | Select-Object -ExpandProperty FriendlyName) } catch { $o.pnp = @() }
$o.crash = @(Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000;StartTime=(Get-Date).AddDays(-7)} -EA SilentlyContinue).Count
$o.k41 = @(Get-WinEvent -FilterHashtable @{LogName='System';Id=41;StartTime=(Get-Date).AddDays(-30)} -EA SilentlyContinue).Count
try { $o.bat = @(Get-CimInstance Win32_Battery -EA Stop | ForEach-Object { $_.EstimatedChargeRemaining }) } catch { $o.bat = @() }
[pscustomobject]$o
"""


def _firmware_uefi() -> bool | None:
    try:
        import ctypes
        t = ctypes.c_ulong(0)
        if ctypes.windll.kernel32.GetFirmwareType(ctypes.byref(t)):
            return t.value == 2
    except (AttributeError, OSError):
        pass
    return None


def _days(n: float) -> str:
    return f"{n:.1f} dias".replace(".", ",") if n < 10 else f"{n:.0f} dias"


def run_checkup(hw: dict | None = None) -> list[Check]:
    import os

    import psutil
    from lolitos.core import restore
    from lolitos.core.system import human_size
    from lolitos.modules import cleanup, display, hwinfo, netdiag, startup
    out: list[Check] = []
    add = out.append
    facts = powershell_json(_WIN_FACTS, timeout=90) or {}
    hw = hw or hwinfo.read_all()

    add(Check("admin", "Rodando como administrador", OK if is_admin() else BAD,
              "" if is_admin() else "Sem admin: ajustes, reparos e limpeza vão falhar.",
              "relaunch_admin", "Sim" if is_admin() else "Não"))

    # espaço livre em cada unidade
    seen, worst, vals = set(), OK, []
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
        st = OK if free >= 15 else WARN if free >= 7 else BAD
        worst = st if {OK: 0, WARN: 1, BAD: 2}[st] > {OK: 0, WARN: 1, BAD: 2}[worst] else worst
        vals.append(f"{part.device.rstrip(chr(92))} {human_size(u.free)} livres de {human_size(u.total)} ({free:.0f}%)")
    if vals:
        add(Check("disk_free", "Espaço livre", worst, "Mantenha pelo menos 15% livres em cada unidade.", "cleanup",
                  " · ".join(vals)))

    tmp = 0
    for tid in ("user_temp", "win_temp"):
        try:
            tmp += cleanup.measure(cleanup.TARGETS_BY_ID[tid])[1]
        except Exception:  # noqa: BLE001
            pass
    add(Check("temp", "Arquivos temporários", OK if tmp < 1024 ** 3 else WARN, "Limite: 1 GB.", "cleanup",
              human_size(tmp)))
    rb_n, rb_b = cleanup.recycle_bin_size()
    add(Check("recycle", "Lixeira", OK if rb_b < 2 * 1024 ** 3 else WARN, "Limite: 2 GB.", "cleanup",
              f"{human_size(rb_b)} em {rb_n} item(ns)"))
    wold = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "Windows.old")
    has_old = os.path.isdir(wold)
    add(Check("windows_old", "Windows.old", WARN if has_old else OK,
              "Cópia da versão anterior do Windows: dá para apagar pela Limpeza de Disco do Windows."
              if has_old else "", "", "Existe" if has_old else "Não existe"))

    pend = _pending_reboot()
    add(Check("reboot", "Reinicialização pendente", WARN if pend else OK,
              "O Windows está esperando reiniciar para concluir atualizações." if pend else "", "reboot",
              "Sim" if pend else "Não"))

    vm = psutil.virtual_memory()
    add(Check("mem", "Memória em uso", OK if vm.percent < 85 else WARN,
              f"{human_size(vm.used)} em uso de {human_size(vm.total)}. Limite: 85%.", "", f"{vm.percent:.0f}%"))
    gb = ram_gb()
    add(Check("ram_amount", "Quantidade de RAM", OK if gb >= 15 else WARN,
              "" if gb >= 15 else "Jogos atuais (e o BDO em Guerra/Cerco) pedem 16 GB ou mais.", "", f"{gb:.0f} GB"))
    rs = hwinfo.ram_summary(hw)
    if rs:
        add(Check("xmp", "Memória na velocidade máxima", BAD if rs["xmp_off"] else OK,
                  f"Os pentes suportam {rs['rated']} MT/s. Ative o XMP/EXPO na BIOS." if rs["xmp_off"] else "",
                  "bios" if rs["xmp_off"] else "", f"{rs['kind']} {rs['running']} MT/s"))
        if rs["count"] == 1:
            add(Check("dual", "Dual channel", BAD, "Um pente só: a memória perde até metade da banda.", "bios",
                      "1 pente"))
        elif rs["dual"] is False:
            add(Check("dual", "Dual channel", WARN, "Os pentes parecem estar no mesmo canal (use A2 e B2).", "",
                      f"{rs['count']} pentes"))
        else:
            add(Check("dual", "Dual channel", OK, "", "", f"{rs['count']} pentes"))

    days = (time.time() - psutil.boot_time()) / 86400
    add(Check("uptime", "Tempo ligado", OK if days < 7 else WARN,
              "Reiniciar ao menos uma vez por semana aplica atualizações e libera memória.", "", _days(days)))

    pts = []
    try:
        pts = restore.list_points()
    except Exception:  # noqa: BLE001
        pass
    if pts:
        lastp = pts[-1]
        try:
            age = (time.time() - time.mktime(time.strptime(lastp.get("When", ""), "%d/%m/%Y %H:%M"))) / 86400
        except ValueError:
            age = 0
        add(Check("restore", "Último ponto de restauração", OK if age < 30 else WARN, lastp.get("Description", ""),
                  "restore_point", f"Há {age:.0f} dia(s)"))
    else:
        add(Check("restore", "Último ponto de restauração", WARN, "Nenhum ponto de restauração no Windows.",
                  "restore_point", "Nenhum"))

    avs = hw.get("av", [])
    names = [a.get("displayName", "") for a in avs]
    add(Check("av", "Antivírus", OK if names else WARN,
              "Proteção em tempo real ligada." if names else "Nenhum antivírus registrado na Central de Segurança.",
              "antivirus", names[0] if names else "Nenhum"))

    fw = facts.get("fw")
    if fw is not None:
        fw = as_list(fw)
        on = sum(1 for x in fw if x)
        add(Check("firewall", "Firewall", OK if fw and on == len(fw) else WARN,
              "" if on == len(fw) else "Algum perfil (domínio, privado ou público) está com o firewall desligado.", "",
              "Ativado em todos os perfis" if fw and on == len(fw) else f"{on} de {len(fw)} perfis"))
    lua = reg.read("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA")
    uac_on = lua is None or int(lua[1] or 0) == 1
    add(Check("uac", "Controle de Conta de Usuário (UAC)", OK if uac_on else WARN,
              "" if uac_on else "Desligado: qualquer programa roda como administrador sem perguntar.", "",
              "Ativado" if uac_on else "Desativado"))

    sb = hw.get("secureboot")
    uefi = _firmware_uefi()
    if sb is not None:
        add(Check("secureboot", "Secure Boot", OK if sb else WARN,
                  "" if sb else "Firmware UEFI. Ative o Secure Boot na configuração da UEFI (BIOS) para proteger a "
                  "inicialização. Alguns jogos com anti-cheat (ex.: Valorant, Battlefield) exigem.", "",
                  "Ativado" if sb else "Desativado"))
    tpm = hw.get("tpm") or {}
    if tpm:
        add(Check("tpm", "TPM (chip de segurança)", OK if tpm.get("ready") else WARN,
                  "" if tpm.get("ready") else "Ausente ou desligado na BIOS (fTPM/PTT).", "",
                  "TPM 2.0 (ativo)" if tpm.get("ready") else "Desligado"))
    if uefi is not None:
        w11 = uefi and sb is not None and bool(tpm.get("ready"))
        add(Check("win11", "Plataforma para Windows 11", OK if w11 else INFO,
                  "UEFI, suporte a Secure Boot e TPM 2.0 presentes." if w11 else
                  "Falta UEFI, Secure Boot ou TPM 2.0.", "", "Atende" if w11 else "Não atende"))

    act = facts.get("act")
    if act is not None:
        add(Check("activation", "Ativação do Windows", OK if int(act) == 1 else WARN,
                  "" if int(act) == 1 else "O Windows não está ativado.", "",
                  "Ativado" if int(act) == 1 else "Não ativado"))

    st, rtt, _ = netdiag.ping_once("1.1.1.1", 1500)
    add(Check("internet", "Internet", OK if st == 0 else BAD, "" if st == 0 else "Sem resposta da internet.", "",
              f"Conectado ({rtt:.0f} ms)" if st == 0 and rtt is not None else "Sem conexão"))

    try:
        n_start = sum(1 for e in startup.list_entries() if e.enabled)
        add(Check("startup", "Programas na inicialização", OK if n_start <= 12 else WARN,
                  "Muitos programas na inicialização deixam o Windows lento para ligar. Limite: 12.", "startup",
                  f"{n_start} programa(s)"))
    except OSError:
        pass

    disks = hw.get("disks", [])
    bad = [d for d in disks if (d.get("HealthStatus") or "").lower() not in ("", "healthy")]
    if disks:
        add(Check("disk_health", "Saúde dos discos", BAD if bad else OK,
                  ("Problema em: " + ", ".join(d.get("FriendlyName", "") for d in bad) + ". Faça backup agora.")
                  if bad else "", "", f"{len(disks) - len(bad)} disco(s) saudável(is)"))
    for d in disks:
        if (d.get("MediaType") or "") == "HDD":
            add(Check("hdd", f"{d.get('FriendlyName')} é um HD", WARN,
                      "Instale os jogos num SSD: carregamentos ficam muito mais rápidos.", "", "HD"))

    pnp = [x for x in as_list(facts.get("pnp")) if x]
    if "pnp" in facts:
        add(Check("devices", "Dispositivos com problema", WARN if pnp else OK,
                  ", ".join(pnp[:4]) + (" — veja o Gerenciador de Dispositivos." if pnp else ""), "",
                  f"{len(pnp)}" if pnp else "Nenhum"))

    try:
        mons = display.monitors()
        low = [m for m in mons if m["hz"] < m["max_hz"]]
        add(Check("refresh", "Monitor na taxa máxima", OK if not low else BAD,
                  "" if not low else "; ".join(f"{m['name']}: {m['hz']} Hz (aceita {m['max_hz']} Hz)" for m in low),
                  "refresh_max", "Todos no máximo" if not low else f"{len(low)} abaixo"))
    except Exception:  # noqa: BLE001
        pass

    n41 = int(facts.get("k41") or 0)
    add(Check("kernel41", "Desligamentos inesperados", OK if n41 == 0 else WARN if n41 < 3 else BAD,
              "" if n41 == 0 else "Desligamentos sem aviso: queda de energia, travamento ou superaquecimento.", "",
              "Nenhum em 30 dias" if n41 == 0 else f"{n41} em 30 dias"))
    nc = int(facts.get("crash") or 0)
    add(Check("crashes", "Falhas de programas", OK if nc < 5 else WARN,
              "" if nc < 5 else "Programas fechando sozinhos com frequência (Visualizador de Eventos › Aplicativo).",
              "", "Nenhuma em 7 dias" if nc == 0 else f"{nc} em 7 dias"))
    bat = [b for b in as_list(facts.get("bat")) if b is not None]
    add(Check("battery", "Bateria", INFO, "", "", f"{bat[0]}%" if bat else "Sem bateria"))
    return out


def score(checks: list[Check], tweak_ratio: float) -> int:
    """0–100: 60% ajustes recomendados ativos + 40% check-up."""
    if not checks:
        return int(tweak_ratio * 100)
    pts = sum({OK: 1.0, INFO: 1.0, WARN: 0.5, BAD: 0.0}[c.state] for c in checks) / len(checks)
    return int(round(60 * tweak_ratio + 40 * pts))
