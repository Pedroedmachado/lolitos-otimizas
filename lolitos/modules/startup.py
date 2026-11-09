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


def self_autostart(enable: bool) -> None:
    """Liga/desliga o próprio app na inicialização via tarefa agendada (abre já como admin, sem UAC)."""
    import sys
    from lolitos import APP_ID
    from lolitos.core.system import run
    if enable:
        if getattr(sys, "frozen", False):
            tr = f'"{sys.executable}" --tray'
        else:  # modo desenvolvimento: pythonw + caminho do pacote
            pyw = Path(sys.executable).with_name("pythonw.exe")
            main = Path(__file__).resolve().parents[2] / "run_lolitos.pyw"
            tr = f'"{pyw if pyw.exists() else sys.executable}" "{main}" --tray'
        run(["schtasks", "/Create", "/F", "/RL", "HIGHEST", "/SC", "ONLOGON", "/TN", APP_ID,
             "/TR", tr, "/DELAY", "0000:15"])
    else:
        run(["schtasks", "/Delete", "/F", "/TN", APP_ID])


def migrate_old_autostart() -> None:
    """Tarefa de inicialização da 1.3.x (nome antigo) → recria com o nome e o executável novos."""
    from lolitos import OLD_APP_ID
    from lolitos.core.system import run
    if run(["schtasks", "/Query", "/TN", OLD_APP_ID]).ok:
        run(["schtasks", "/Delete", "/F", "/TN", OLD_APP_ID])
        self_autostart(True)


def self_autostart_enabled() -> bool:
    from lolitos import APP_ID
    from lolitos.core.system import run
    return run(["schtasks", "/Query", "/TN", APP_ID]).ok


