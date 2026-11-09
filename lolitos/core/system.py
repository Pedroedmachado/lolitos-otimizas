"""Utilitários de sistema: admin, caminhos, execução de comandos sem janela.

Tudo aqui degrada de forma segura fora do Windows (para testes)."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from lolitos import APP_ID

IS_WIN = sys.platform == "win32"
CREATE_NO_WINDOW = 0x08000000


# ----------------------------------------------------------------- caminhos
def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    p = Path(base) / APP_ID
    p.mkdir(parents=True, exist_ok=True)
    return p


def backups_dir() -> Path:
    p = data_dir() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resource_path(*parts: str) -> Path:
    """Arquivo dentro de lolitos/data (funciona empacotado com PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath("lolitos", "data", *parts)


def expand(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(path))


# ----------------------------------------------------------------- admin
def is_admin() -> bool:
    if not IS_WIN:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Reabre o app pedindo elevação. Retorna True se o pedido foi feito."""
    if not IS_WIN:
        return False
    rest = " ".join(f'"{a}"' for a in sys.argv[1:])
    root = str(Path(__file__).resolve().parents[2])
    if getattr(sys, "frozen", False):
        exe, params, cwd = sys.executable, rest, None
    else:
        exe, cwd = sys.executable, root
        script = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
        if script and script.suffix in (".py", ".pyw") and script.name != "__main__.py":
            params = f'"{script}" {rest}'
        else:
            params = f"-m lolitos {rest}"
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1)
    return rc > 32


# ----------------------------------------------------------------- execução
class CmdResult:
    def __init__(self, code: int, out: str, err: str):
        self.code, self.out, self.err = code, out, err

    @property
    def ok(self) -> bool:
        return self.code == 0

    def __repr__(self) -> str:  # pragma: no cover
        return f"CmdResult({self.code}, out={self.out[:80]!r}, err={self.err[:80]!r})"


def _decode(b: bytes) -> str:
    for enc in ("utf-8", "cp850", "cp1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def run(cmd, timeout: int = 120, shell: bool = False, input_text: str | None = None) -> CmdResult:
    """Roda um comando sem abrir janela de console."""
    if not IS_WIN:
        return CmdResult(1, "", "não é Windows")
    try:
        p = subprocess.run(
            cmd, shell=shell, capture_output=True, timeout=timeout,
            input=input_text.encode() if input_text else None,
            creationflags=CREATE_NO_WINDOW,
        )
        return CmdResult(p.returncode, _decode(p.stdout), _decode(p.stderr))
    except subprocess.TimeoutExpired:
        return CmdResult(-1, "", f"tempo esgotado ({timeout}s)")
    except FileNotFoundError as e:
        return CmdResult(-2, "", str(e))


def powershell(script: str, timeout: int = 180) -> CmdResult:
    """Executa um script PowerShell com saída UTF-8."""
    pre = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;$ProgressPreference='SilentlyContinue';$ErrorActionPreference='Stop';"
    return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-Command", pre + script], timeout=timeout)


def powershell_json(script: str, timeout: int = 180):
    r = powershell(f"$__r = & {{ {script} }}; $__r | ConvertTo-Json -Depth 5 -Compress", timeout)
    if not r.ok or not r.out.strip():
        return None
    try:
        return json.loads(r.out.strip())
    except json.JSONDecodeError:
        return None


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


# ----------------------------------------------------------------- hardware rápido
@lru_cache(maxsize=1)
def ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        return 16.0


@lru_cache(maxsize=1)
def is_laptop() -> bool:
    try:
        import psutil
        return psutil.sensors_battery() is not None
    except Exception:
        return False


@lru_cache(maxsize=1)
def cpu_name() -> str:
    if IS_WIN:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    import platform
    return platform.processor() or "Processador"


@lru_cache(maxsize=1)
def windows_build() -> int:
    if not IS_WIN:
        return 0
    return sys.getwindowsversion().build


def is_win11() -> bool:
    return windows_build() >= 22000


def process_running(*names: str) -> bool:
    try:
        import psutil
        wanted = {n.lower() for n in names}
        return any((p.info["name"] or "").lower() in wanted for p in psutil.process_iter(["name"]))
    except Exception:
        return False


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
