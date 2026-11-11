"""Programas que abrem com o Windows (Run + pasta Inicializar), ligando/desligando como o Gerenciador de Tarefas."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lolitos.core import history
from lolitos.core import registry as reg
from lolitos.core.system import expand

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN32 = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
ENABLED = bytes([2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
DISABLED = bytes([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

SOURCES = [
    # (hive, run key, approved hive, approved subkey, label)
    ("HKCU", RUN, "HKCU", "Run", "Registro (usuário)"),
    ("HKLM", RUN, "HKLM", "Run", "Registro (todos os usuários)"),
    ("HKLM", RUN32, "HKLM", "Run32", "Registro (todos, 32 bits)"),
]
FOLDERS = [
    (r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup", "HKCU", "Pasta Inicializar (usuário)"),
    (r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\StartUp", "HKLM", "Pasta Inicializar (todos)"),
]


@dataclass
class Entry:
    name: str
    command: str
    source: str
    ahive: str
    akey: str
    enabled: bool

    @property
    def uid(self):
        return f"{self.ahive}|{self.akey}|{self.name}"


def _approved(ahive, akey, name) -> bool:
    r = reg.read(ahive, f"{APPROVED}\\{akey}", name)
    if not r or not isinstance(r[1], (bytes, bytearray)) or not r[1]:
        return True
    return r[1][0] % 2 == 0   # 02/06 ligado, 03/07 desligado


def list_entries() -> list[Entry]:
    out = []
    for hive, key, ahive, akey, label in SOURCES:
        for name, _, value in reg.values(hive, key):
            if not name:
                continue
            out.append(Entry(name, str(value), label, ahive, akey, _approved(ahive, akey, name)))
    for folder, ahive, label in FOLDERS:
        p = Path(expand(folder))
        if p.exists():
            for f in p.iterdir():
                if f.name.lower() == "desktop.ini":
                    continue
                out.append(Entry(f.name, str(f), label, ahive, "StartupFolder",
                                 _approved(ahive, "StartupFolder", f.name)))
    return sorted(out, key=lambda e: e.name.lower())


def set_enabled(e: Entry, enabled: bool) -> None:
    reg.write(e.ahive, f"{APPROVED}\\{e.akey}", e.name, "binary", ENABLED if enabled else DISABLED)
    history.add("startup", (f"{e.name}: vai abrir com o Windows" if enabled else f"{e.name}: não vai mais abrir com o Windows"),
                "Inicialização", success=True, reversible=False)


def _self_command() -> tuple[str, str]:
    import sys
    if getattr(sys, "frozen", False):
        return sys.executable, "--tray"
    pyw = Path(sys.executable).with_name("pythonw.exe")     # modo desenvolvimento
    main = Path(__file__).resolve().parents[2] / "run_lolitos.pyw"
    return str(pyw if pyw.exists() else sys.executable), f'"{main}" --tray'


def autostart_script(exe: str, args: str, task: str) -> str:
    """PowerShell que cria a tarefa de login: abre como admin (sem UAC), também na bateria, e nunca é encerrada
    pelo Windows (o padrão do schtasks para o app depois de 3 dias e não abre no notebook fora da tomada)."""
    def q(s):
        return "'" + s.replace("'", "''") + "'"
    return (f"$a=New-ScheduledTaskAction -Execute {q(exe)} -Argument {q(args)};"
            "$t=New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name);"
            "$t.Delay='PT15S';"
            "$s=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries"
            " -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -Priority 5;"
            "$p=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name)"
            " -LogonType Interactive -RunLevel Highest;"
            f"Register-ScheduledTask -TaskName {q(task)} -Action $a -Trigger $t -Settings $s -Principal $p -Force"
            " | Out-Null")


def self_autostart(enable: bool, user_choice: bool = True) -> bool:
    """Liga/desliga o próprio app na inicialização via tarefa agendada."""
    from lolitos import APP_ID
    from lolitos.core import settings
    from lolitos.core.system import powershell, run
    if user_choice:
        settings.set("autostart_choice", bool(enable))
    if not enable:
        return run(["schtasks", "/Delete", "/F", "/TN", APP_ID]).ok
    exe, args = _self_command()
    if powershell(autostart_script(exe, args, APP_ID), timeout=60).ok:
        return True
    # sem o módulo ScheduledTasks: schtasks (com os limites padrão do Windows)
    return run(["schtasks", "/Create", "/F", "/RL", "HIGHEST", "/SC", "ONLOGON", "/TN", APP_ID,
                "/TR", f'"{exe}" {args}', "/DELAY", "0000:15"]).ok


def ensure_autostart() -> None:
    """Uma vez: recria a tarefa de quem já usa o início com o Windows, para valer também na bateria e sem o
    limite de 3 dias do padrão. Instalações novas já vêm com ela ligada (opção marcada no instalador)."""
    from lolitos.core import settings
    if settings.get("autostart_v2"):
        return
    if not self_autostart_enabled() or self_autostart(True, user_choice=False):
        settings.set("autostart_v2", True)


def migrate_old_autostart() -> None:
    """Tarefa de inicialização com um nome antigo do app → recria com o nome e o executável novos."""
    from lolitos import LEGACY_APP_IDS
    from lolitos.core.system import run
    found = False
    for old_id in LEGACY_APP_IDS:
        if run(["schtasks", "/Query", "/TN", old_id]).ok:
            run(["schtasks", "/Delete", "/F", "/TN", old_id])
            found = True
    if found:
        self_autostart(True, user_choice=False)


def self_autostart_enabled() -> bool:
    from lolitos import APP_ID
    from lolitos.core.system import run
    return run(["schtasks", "/Query", "/TN", APP_ID]).ok




def exe_path(command: str) -> str:
    """'"C:\\...\\Discord\\Update.exe" --processStart Discord.exe' → 'C:\\...\\Update.exe' (para o ícone)."""
    import re
    c = expand((command or "").strip())
    if c.startswith('"'):
        end = c.find('"', 1)
        return c[1:end] if end > 0 else c.strip('"')
    m = re.match(r"(.+?\.(?:exe|lnk|bat|cmd|com))(?:\s|$)", c, re.I)
    return m.group(1) if m else c.split(" ")[0]


def all_users(e: Entry) -> bool:
    return e.ahive == "HKLM"
