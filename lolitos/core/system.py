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

from lolitos import APP_ID, LEGACY_APP_IDS

IS_WIN = sys.platform == "win32"
CREATE_NO_WINDOW = 0x08000000


# ----------------------------------------------------------------- caminhos
def migrate_old_data() -> None:
    """O app já teve outros nomes: traz histórico, backups e config da pasta antiga para a pasta nova."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    new = Path(base) / APP_ID
    for old_id in LEGACY_APP_IDS:
        old = Path(base) / old_id
        if old.exists() and not new.exists():
            try:
                old.rename(new)
            except OSError:
                import shutil
                shutil.copytree(old, new, dirs_exist_ok=True)


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


def write_atomic(path: Path, text: str) -> None:
    """Grava o arquivo inteiro ou nada: escreve num temporário ao lado e troca. Se o PC desligar no meio, o
    arquivo antigo continua inteiro (config, histórico e perfis não corrompem)."""
    import time
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    for attempt in range(5):          # antivírus/indexador às vezes seguram o arquivo por um instante
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


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


def relaunch_self() -> bool:
    """Abre uma nova cópia do app (com a mesma elevação), que espera esta fechar."""
    args = [a for a in sys.argv[1:] if a not in ("--restarted", "--tray")] + ["--restarted"]
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, *args]
    else:
        cmd = [sys.executable, "-m", "lolitos", *args]
    try:
        flags = (0x00000008 | 0x00000200) if IS_WIN else 0   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parents[2]) if not getattr(sys, "frozen", False)
                         else None, creationflags=flags, close_fds=True)
        return True
    except OSError:
        return False


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


def _kill_tree(pid: int) -> None:
    try:
        subprocess.run([system_tool("taskkill"), "/T", "/F", "/PID", str(pid)], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
                       creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        pass


_SYS_TOOLS: dict[str, str] = {}


def system_tool(name: str) -> str:
    """'reg' → 'C:\\Windows\\System32\\reg.exe'. O app roda como administrador: as ferramentas do Windows são
    chamadas pelo caminho completo, para um arquivo com o mesmo nome na pasta atual ou no PATH nunca entrar no
    lugar. O que não é do Windows (winget, ffmpeg…) volta como veio."""
    if not IS_WIN or os.sep in name or "/" in name or ":" in name:
        return name
    key = name.lower()
    if key not in _SYS_TOOLS:
        exe = key if key.endswith((".exe", ".com", ".msc", ".cpl")) else key + ".exe"
        root = os.environ.get("SystemRoot") or r"C:\Windows"
        found = name
        for folder in (os.path.join(root, "System32"),
                       os.path.join(root, "System32", "WindowsPowerShell", "v1.0"),
                       os.path.join(root, "System32", "wbem"), root):
            c = os.path.join(folder, exe)
            if os.path.isfile(c):
                found = c
                break
        _SYS_TOOLS[key] = found
    return _SYS_TOOLS[key]


def run(cmd, timeout: int = 120, shell: bool = False, input_text: str | None = None) -> CmdResult:
    """Roda um comando sem abrir janela de console e SEMPRE volta.

    O subprocess.run comum pode travar para sempre no Windows: se o comando abre outro programa que continua
    rodando (ex.: 'start explorer.exe'), esse programa herda a saída e o Python fica esperando ela fechar. Aqui a
    saída é lida em threads à parte: quando o comando termina (ou passa do tempo e é encerrado com tudo o que
    abriu), a função volta mesmo que algum programa aberto por ele continue de pé."""
    if not IS_WIN:
        return CmdResult(1, "", "não é Windows")
    import threading
    if not shell and isinstance(cmd, (list, tuple)) and cmd:
        cmd = [system_tool(str(cmd[0])), *cmd[1:]]
    try:
        p = subprocess.Popen(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE if input_text else subprocess.DEVNULL,
                             creationflags=CREATE_NO_WINDOW)
    except FileNotFoundError as e:
        return CmdResult(-2, "", str(e))
    except OSError as e:
        return CmdResult(-3, "", str(e))
    out, err = [], []

    def pump(stream, sink):
        try:
            for chunk in iter(lambda: stream.read1(65536), b""):     # read1: entrega o que já chegou
                sink.append(chunk)
        except (OSError, ValueError):
            pass
    readers = [threading.Thread(target=pump, args=(p.stdout, out), daemon=True),
               threading.Thread(target=pump, args=(p.stderr, err), daemon=True)]
    for t in readers:
        t.start()
    if input_text:
        try:
            p.stdin.write(input_text.encode())
            p.stdin.close()
        except OSError:
            pass
    timed_out = False
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(p.pid)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    for t in readers:            # um programa que o comando deixou aberto pode segurar a saída: não espera por ele
        t.join(timeout=3)
    o, e = _decode(b"".join(out)), _decode(b"".join(err))
    if timed_out:
        return CmdResult(-1, o, (e + "\n" if e else "") + f"tempo esgotado ({timeout}s)")
    return CmdResult(p.returncode if p.returncode is not None else -1, o, e)


def launch(cmd: list[str]) -> bool:
    """Abre um programa e não espera por ele (sem herdar a saída do app)."""
    if not IS_WIN:
        return False
    try:
        cmd = [system_tool(str(cmd[0])), *cmd[1:]]
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         close_fds=True, creationflags=0x00000008 | 0x00000200)   # DETACHED | NEW_PROCESS_GROUP
        return True
    except OSError:
        return False


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


@lru_cache(maxsize=1)
def hibernation_supported() -> bool:
    """O hardware/firmware aceita hibernar (estado S4)? Máquinas virtuais e alguns PCs não aceitam: neles o
    'powercfg /h on' falha, então o ajuste de hibernação não se aplica."""
    if not IS_WIN:
        return True
    try:
        buf = (ctypes.c_ubyte * 128)()          # SYSTEM_POWER_CAPABILITIES: o 7º byte é SystemS4
        if not ctypes.windll.powrprof.GetPwrCapabilities(ctypes.byref(buf)):
            return True
        return bool(buf[6])
    except Exception:
        return True


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
