"""Ações de Linux. Mesma interface das do Windows (applicable, is_applied, capture, apply, revert, describe),
então o motor de aplicar/desfazer e o histórico são os mesmos."""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
from pathlib import Path

from lolitos.core.actions import Action, ActionError
from lolitos.linux import root
from lolitos.linux.root import P


def _read(path: str) -> str | None:
    try:
        return " ".join(Path(path).read_text().split())
    except OSError:
        return None


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


class Sysctl(Action):
    """Parâmetro do kernel: vale na hora (/proc/sys) e fica gravado em /etc/sysctl.d para os próximos boots.
    at_least=True: um valor maior que o pedido também conta como aplicado (e não é reduzido)."""

    def __init__(self, key: str, value, at_least: bool = False):
        self.key, self.value, self.at_least = key, str(value), at_least
        self.file = f"/etc/sysctl.d/99-chinese-control-{_slug(key)}.conf"

    def _proc(self) -> str:
        return P("/proc/sys/" + self.key.replace(".", "/"))

    def describe(self):
        return f"sysctl {self.key} = {self.value}" + (" (ou mais)" if self.at_least else "")

    def applicable(self):
        return os.path.exists(self._proc())

    def _ok(self, cur: str | None) -> bool:
        if cur is None:
            return False
        if self.at_least:
            try:
                return int(cur) >= int(self.value)
            except ValueError:
                return False
        return cur == self.value

    def is_applied(self):
        return self._ok(_read(self._proc()))

    def capture(self):
        return {"prev": _read(self._proc()), "file": _read_raw(P(self.file))}

    def apply(self):
        if self._ok(_read(self._proc())) and self.at_least:
            return
        root.call("write_file", path=self.file, content=f"# Chinese Control\n{self.key} = {self.value}\n")
        root.call("sysctl", key=self.key, value=self.value)

    def revert(self, snap):
        if snap.get("file") is None:
            root.call("remove_file", path=self.file)
        else:
            root.call("write_file", path=self.file, content=str(snap["file"]))
        if snap.get("prev") is not None:
            root.call("sysctl", key=self.key, value=str(snap["prev"]))


def _read_raw(path: str) -> str | None:
    try:
        return Path(path).read_text()
    except OSError:
        return None


def _choice(text: str | None) -> str | None:
    """'always [madvise] never' → 'madvise'; 'performance' → 'performance'."""
    if text is None:
        return None
    m = re.search(r"\[([^\]]+)\]", text)
    return m.group(1) if m else text


class Sysfs(Action):
    """Valor em /sys (aceita * no caminho). Vale na hora e fica em /etc/tmpfiles.d para os próximos boots."""

    def __init__(self, pattern: str, value: str, name: str = ""):
        self.pattern, self.value = pattern, value
        self.file = f"/etc/tmpfiles.d/chinese-control-{_slug(name or pattern.replace('/sys/', ''))}.conf"

    def _files(self) -> list[str]:
        return sorted(glob.glob(P(self.pattern)))

    def describe(self):
        return f"{self.pattern} = {self.value}"

    def applicable(self):
        fs = self._files()
        if not fs:
            return False
        first = _read(fs[0]) or ""
        if "[" in first:                       # lista de opções: o valor pedido precisa existir
            return self.value in first.replace("[", "").replace("]", "").split()
        avail = Path(fs[0]).with_name("scaling_available_governors")
        if fs[0].endswith("scaling_governor") and avail.exists():
            return self.value in (_read(str(avail)) or "").split()
        return True

    def is_applied(self):
        fs = self._files()
        return bool(fs) and all(_choice(_read(f)) == self.value for f in fs)

    def capture(self):
        pre = len(root.fake_root() or "")
        return {"prev": {f[pre:]: _choice(_read(f)) for f in self._files()}, "file": _read_raw(P(self.file))}

    def apply(self):
        root.call("write_file", path=self.file, content=f"# Chinese Control\nw {self.pattern} - - - - {self.value}\n")
        root.call("sysfs", path=self.pattern, value=self.value)

    def revert(self, snap):
        if snap.get("file") is None:
            root.call("remove_file", path=self.file)
        else:
            root.call("write_file", path=self.file, content=str(snap["file"]))
        errs = []
        for path, val in (snap.get("prev") or {}).items():
            if val:
                try:
                    root.call("sysfs", path=str(path), value=str(val))
                except ActionError as e:
                    errs.append(str(e))
        if errs:
            raise ActionError("; ".join(errs[:2]))


class ConfFile(Action):
    """Arquivo de configuração do sistema criado pelo app (ex.: carregar um módulo no boot)."""

    def __init__(self, path: str, content: str, modprobe: str = ""):
        self.path, self.content, self.modprobe = path, content, modprobe

    def describe(self):
        return f"{self.path}: {self.content.strip()}"

    def is_applied(self):
        return _read_raw(P(self.path)) == self.content

    def capture(self):
        return {"file": _read_raw(P(self.path))}

    def apply(self):
        root.call("write_file", path=self.path, content=self.content)
        if self.modprobe:
            root.call("modprobe", name=self.modprobe)

    def revert(self, snap):
        if snap.get("file") is None:
            root.call("remove_file", path=self.path)
        else:
            root.call("write_file", path=self.path, content=str(snap["file"]))


def env_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "environment.d" / "90-chinese-control.conf"


class UserEnv(Action):
    """Variável de ambiente da sua sessão (~/.config/environment.d). Não pede senha; vale no próximo login."""

    def __init__(self, name: str, value: str):
        self.name, self.value = name, value

    def describe(self):
        return f"{self.name}={self.value}  (~/.config/environment.d)"

    def _lines(self) -> list[str]:
        try:
            return env_file().read_text().splitlines()
        except OSError:
            return []

    def _get(self) -> str | None:
        for ln in self._lines():
            if ln.startswith(self.name + "="):
                return ln.split("=", 1)[1]
        return None

    def is_applied(self):
        return self._get() == self.value

    def capture(self):
        return {"prev": self._get()}

    def _set(self, value: str | None):
        lines = [ln for ln in self._lines() if not ln.startswith(self.name + "=")]
        if value is not None:
            lines.append(f"{self.name}={value}")
        f = env_file()
        if not [ln for ln in lines if ln.strip() and not ln.startswith("#")]:
            f.unlink(missing_ok=True)
            return
        f.parent.mkdir(parents=True, exist_ok=True)
        if not lines or not lines[0].startswith("#"):
            lines.insert(0, "# Chinese Control")
        f.write_text("\n".join(lines) + "\n")

    def apply(self):
        self._set(self.value)

    def revert(self, snap):
        self._set(snap.get("prev"))


class Package(Action):
    """Pacote do Arch (pacman). Sem desfazer automático: para remover, use 'sudo pacman -Rns <pacote>'."""
    reversible = False

    def __init__(self, *pkgs: str):
        self.pkgs = list(pkgs)

    def describe(self):
        return "pacman -S --needed " + " ".join(self.pkgs)

    def applicable(self):
        return bool(shutil.which("pacman")) or root.fake_root() is not None

    def is_applied(self):
        if root.fake_root() is not None:
            log = _read_raw(P("/pacman.log")) or ""
            return all(p in log.split() for p in self.pkgs)
        r = subprocess.run(["pacman", "-Q", *self.pkgs], capture_output=True, timeout=30)
        return r.returncode == 0

    def capture(self):
        return {}

    def apply(self):
        root.call("pacman", pkgs=self.pkgs)

    def revert(self, snap):
        raise ActionError("sem desfazer automático: remova com 'sudo pacman -Rns " + " ".join(self.pkgs) + "'")
