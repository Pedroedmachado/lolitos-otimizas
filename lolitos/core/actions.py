"""Ações primitivas reversíveis: registro, serviços, tarefas, energia, comandos.

Cada ação sabe: ler o estado atual (capture), aplicar, dizer se já está aplicada
e voltar ao estado capturado (revert). Os snapshots são JSON."""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Callable

from lolitos.core import registry as reg
from lolitos.core.system import (IS_WIN, as_list, backups_dir, expand, powershell,
                                 powershell_json, run)


class ActionError(Exception):
    pass


class BlockedError(ActionError):
    """O Windows (ou o antivírus) negou o acesso."""


def _check(res, what: str):
    if res.ok:
        return
    text = (res.err or res.out or "").strip()
    low = text.lower()
    if res.code == 5 or "acesso negado" in low or "access is denied" in low or "access denied" in low:
        raise BlockedError(f"{what}: acesso negado")
    raise ActionError(f"{what}: {text[:300] or f'código {res.code}'}")


class Action:
    reversible = True

    def describe(self) -> str:
        return self.__class__.__name__

    def applicable(self) -> bool:
        return True

    def is_applied(self) -> bool | None:
        return None

    def capture(self) -> dict:
        return {}

    def apply(self) -> None:
        raise NotImplementedError

    def revert(self, snap: dict) -> None:
        pass


# ======================================================================= registro
class Reg(Action):
    def __init__(self, hive: str, path: str, name: str, value=None, kind: str = "dword",
                 delete: bool = False):
        self.hive, self.path, self.name, self.kind = hive, path, name, kind
        self._value, self.delete = value, delete

    @property
    def value(self):
        return self._value() if callable(self._value) else self._value

    def describe(self):
        target = "(apagar)" if self.delete else repr(self.value)
        return f"{self.hive}\\{self.path} [{self.name or '(Padrão)'}] = {target}"

    def is_applied(self):
        cur = reg.read(self.hive, self.path, self.name)
        if self.delete:
            return cur is None
        if cur is None:
            return False
        kind, value = cur
        want = self.value
        if self.kind in ("dword", "qword"):
            try:
                return int(value) == (int(want) & (0xFFFFFFFF if self.kind == "dword" else 0xFFFFFFFFFFFFFFFF))
            except (TypeError, ValueError):
                return False
        if self.kind == "binary":
            want = bytes.fromhex(want) if isinstance(want, str) else want
        return value == want

    def capture(self):
        cur = reg.read(self.hive, self.path, self.name)
        snap = {"exists": cur is not None, "created_key": reg.first_missing_parent(self.hive, self.path)}
        if cur is not None:
            snap["kind"], snap["value"] = cur[0], reg.to_json(cur[0], cur[1])
        return snap

    def apply(self):
        try:
            if self.delete:
                reg.delete_value(self.hive, self.path, self.name)
            else:
                reg.write(self.hive, self.path, self.name, self.kind, self.value)
        except PermissionError as e:
            raise BlockedError(f"{self.describe()}: acesso negado") from e
        except OSError as e:
            raise ActionError(f"{self.describe()}: {e}") from e

    def revert(self, snap):
        try:
            if snap.get("exists"):
                reg.write(self.hive, self.path, self.name, snap["kind"],
                          reg.from_json(snap["kind"], snap["value"]))
            else:
                reg.delete_value(self.hive, self.path, self.name)
                ck = snap.get("created_key")
                # só apaga chave que faz parte do caminho deste ajuste (o histórico é um arquivo comum no disco)
                inside = isinstance(ck, str) and (self.path.lower() + "\\").startswith(ck.strip("\\").lower() + "\\")
                if ck and inside and reg.tree_empty(self.hive, ck):  # chave criada por nós e que ficou vazia
                    reg.delete_tree(self.hive, ck)
        except PermissionError as e:
            raise BlockedError(f"{self.describe()}: acesso negado") from e


def regs(hive: str, path: str, kind: str = "dword", **vals) -> list[Reg]:
    """Atalho: vários valores na mesma chave."""
    return [Reg(hive, path, n, v, kind) for n, v in vals.items()]


class RegKeyDelete(Action):
    """Apaga uma chave inteira, exportando um .reg antes para poder voltar."""

    def __init__(self, hive: str, path: str):
        self.hive, self.path = hive, path

    def describe(self):
        return f"apagar chave {self.hive}\\{self.path}"

    def is_applied(self):
        return not reg.key_exists(self.hive, self.path)

    def capture(self):
        if not reg.key_exists(self.hive, self.path):
            return {"exists": False}
        f = backups_dir() / f"key-{uuid.uuid4().hex[:10]}.reg"
        full = {"HKCU": "HKEY_CURRENT_USER", "HKLM": "HKEY_LOCAL_MACHINE", "HKU": "HKEY_USERS"}[self.hive]
        _check(run(["reg", "export", f"{full}\\{self.path}", str(f), "/y"]), "exportar chave")
        return {"exists": True, "file": str(f)}

    def apply(self):
        reg.delete_tree(self.hive, self.path)

    def revert(self, snap):
        if not (snap.get("exists") and snap.get("file")):
            return
        f = Path(str(snap["file"]))
        # só importa backup criado por esta ação: dentro da pasta de backups e com o nome que ela dá
        if f.parent.resolve() != backups_dir().resolve() or not re.fullmatch(r"key-[0-9a-f]{10}\.reg", f.name):
            raise ActionError("importar chave: o backup registrado no histórico não é desta pasta de backups")
        if f.exists():
            _check(run(["reg", "import", str(f)]), "importar chave")


# ======================================================================= serviços
_START = {"auto": 2, "delayed": 2, "manual": 3, "disabled": 4}
_SC = {"auto": "auto", "delayed": "delayed-auto", "manual": "demand", "disabled": "disabled"}
_SVC = r"SYSTEM\CurrentControlSet\Services"


class Service(Action):
    def __init__(self, name: str, start: str = "manual", stop: bool = True):
        self.name, self.start, self.stop = name, start, stop

    def describe(self):
        return f"serviço {self.name} → {self.start}"

    def applicable(self):
        return reg.key_exists("HKLM", f"{_SVC}\\{self.name}")

    def _state(self):
        r = reg.read("HKLM", f"{_SVC}\\{self.name}", "Start")
        if r is None:
            return None
        start = int(r[1])
        delayed = reg.read("HKLM", f"{_SVC}\\{self.name}", "DelayedAutostart")
        if start == 2 and delayed and int(delayed[1]) == 1:
            return "delayed"
        return {2: "auto", 3: "manual", 4: "disabled"}.get(start, "system")

    def is_applied(self):
        st = self._state()
        if st is None:
            return None
        if self.start == "manual":
            return st in ("manual", "disabled")
        return st == self.start

    def capture(self):
        return {"start": self._state()}

    def apply(self):
        if self.start == "manual" and self._state() == "disabled":
            return   # já está mais restrito do que o pedido: não religa
        _check(run(["sc.exe", "config", self.name, "start=", _SC[self.start]]), f"sc config {self.name}")
        if self.stop and self.start in ("manual", "disabled"):
            run(["sc.exe", "stop", self.name], timeout=30)

    def revert(self, snap):
        old = snap.get("start")
        if old in _SC:
            _check(run(["sc.exe", "config", self.name, "start=", _SC[old]]), f"sc config {self.name}")
            if old in ("auto", "delayed"):
                run(["sc.exe", "start", self.name], timeout=30)


# ======================================================================= tarefas agendadas
class _TaskCache:
    ttl = 20.0

    def __init__(self):
        self.t = 0.0
        self.data: dict[str, str] = {}

    def get(self) -> dict[str, str]:
        if not IS_WIN:
            return self.data
        if time.time() - self.t > self.ttl:
            rows = powershell_json(
                "Get-ScheduledTask | Select-Object @{n='p';e={$_.TaskPath + $_.TaskName}},"
                "@{n='s';e={[string]$_.State}}", timeout=90)
            self.data = {r["p"].lower(): r["s"] for r in as_list(rows) if r and r.get("p")}
            self.t = time.time()
        return self.data

    def invalidate(self):
        self.t = 0.0


TASKS = _TaskCache()


class Task(Action):
    def __init__(self, path: str, enabled: bool = False):
        self.path, self.enabled = path, enabled

    def describe(self):
        return f"tarefa {self.path} → {'ligada' if self.enabled else 'desligada'}"

    def applicable(self):
        return not IS_WIN or self.path.lower() in TASKS.get()

    def _state(self):
        return TASKS.get().get(self.path.lower())

    def is_applied(self):
        st = self._state()
        if st is None:
            return None
        return (st != "Disabled") == self.enabled

    def capture(self):
        return {"state": self._state()}

    def _set(self, enable: bool):
        flag = "/Enable" if enable else "/Disable"
        _check(run(["schtasks.exe", "/Change", "/TN", self.path, flag]), f"schtasks {self.path}")
        TASKS.invalidate()

    def apply(self):
        self._set(self.enabled)

    def revert(self, snap):
        st = snap.get("state")
        if st is not None:
            self._set(st != "Disabled")


# ======================================================================= energia
_HEX = re.compile(r"0x([0-9a-fA-F]{8})")
_GUID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")


def active_scheme() -> str | None:
    r = run(["powercfg", "/getactivescheme"])
    m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", r.out)
    return m.group(1).lower() if m else None


class Power(Action):
    """Configuração do plano de energia ativo (AC e DC)."""

    def __init__(self, sub: str, setting: str, value: int, dc: int | None = None, label: str = ""):
        self.sub, self.setting, self.value = sub, setting, value
        self.dc = value if dc is None else dc
        self.label = label

    def describe(self):
        return f"energia {self.label or self.setting} = {self.value}"

    def _read(self):
        r = run(["powercfg", "/query", "SCHEME_CURRENT", self.sub, self.setting])
        vals = _HEX.findall(r.out)
        if len(vals) < 2:   # configuração oculta (ex.: estacionamento de núcleos)
            r = run(["powercfg", "/qh", "SCHEME_CURRENT", self.sub, self.setting])
            vals = _HEX.findall(r.out)
        if not r.ok or len(vals) < 2:
            return None
        return int(vals[-2], 16), int(vals[-1], 16)

    def applicable(self):
        return not IS_WIN or self._read() is not None

    def is_applied(self):
        cur = self._read()
        return None if cur is None else cur == (self.value, self.dc)

    def capture(self):
        cur = self._read()
        return {"ac": cur[0], "dc": cur[1]} if cur else {}

    def _set(self, ac, dc):
        _check(run(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", self.sub, self.setting, str(ac)]), "powercfg")
        run(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", self.sub, self.setting, str(dc)])
        run(["powercfg", "/setactive", "SCHEME_CURRENT"])

    def apply(self):
        self._set(self.value, self.dc)

    def revert(self, snap):
        if "ac" in snap:
            try:
                self._set(int(snap["ac"]), int(snap.get("dc", snap["ac"])))
            except (TypeError, ValueError):
                raise ActionError(f"{self.describe()}: valor anterior inválido no histórico") from None


ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"


def find_scheme_by_name(name: str) -> str | None:
    r = run(["powercfg", "/list"])
    for line in r.out.splitlines():
        if name.lower() in line.lower():
            m = re.search(r"([0-9a-fA-F-]{36})", line)
            if m:
                return m.group(1).lower()
    return None


def rename_legacy_power_plans() -> None:
    """O plano criado com um nome antigo do app passa a usar o nome novo (o desfazer continua achando)."""
    from lolitos import LEGACY_POWER_PLAN_NAMES, POWER_PLAN_NAME
    if find_scheme_by_name(POWER_PLAN_NAME):
        return
    for old in LEGACY_POWER_PLAN_NAMES:
        guid = find_scheme_by_name(old)
        if guid:
            run(["powercfg", "-changename", guid, POWER_PLAN_NAME, "Criado pelo Chinese Control"])
            return


def ensure_power_plan(name: str) -> str:
    """Cria (se preciso) uma cópia do Desempenho Máximo com o nome dado e devolve o GUID."""
    guid = find_scheme_by_name(name)
    if guid:
        return guid
    r = run(["powercfg", "-duplicatescheme", ULTIMATE])
    m = re.search(r"([0-9a-fA-F-]{36})", r.out)
    if not m:  # edições sem o Desempenho Máximo: usa Alto Desempenho
        r = run(["powercfg", "-duplicatescheme", HIGH_PERF])
        m = re.search(r"([0-9a-fA-F-]{36})", r.out)
    if not m:
        raise ActionError("não foi possível criar o plano de energia")
    guid = m.group(1).lower()
    run(["powercfg", "-changename", guid, name, "Criado pelo Chinese Control"])
    return guid


class PowerPlan(Action):
    def __init__(self, name: str):
        self.name = name

    def describe(self):
        return f"plano de energia '{self.name}' ativo"

    def is_applied(self):
        g = find_scheme_by_name(self.name)
        return bool(g) and g == active_scheme()

    def capture(self):
        return {"previous": active_scheme()}

    def apply(self):
        guid = ensure_power_plan(self.name)
        _check(run(["powercfg", "/setactive", guid]), "ativar plano")

    def revert(self, snap):
        prev = snap.get("previous")
        if not (isinstance(prev, str) and _GUID.fullmatch(prev)):
            prev = None
        mine = find_scheme_by_name(self.name)
        if prev and prev != mine:
            run(["powercfg", "/setactive", prev])
        if mine and mine != prev:
            run(["powercfg", "/delete", mine])


# ======================================================================= comandos
class Cmd(Action):
    """Comando genérico. `check` é função → bool|None; `ps_check` é script PS que imprime 1/0."""

    def __init__(self, apply: str | list, revert: str | list | None = None, *,
                 check: Callable[[], bool | None] | None = None, ps_check: str | None = None,
                 ps: bool = False, label: str = "", timeout: int = 600):
        self.apply_cmd, self.revert_cmd = apply, revert
        self.check, self.ps_check, self.ps = check, ps_check, ps
        self.label, self.timeout = label, timeout
        self.reversible = revert is not None

    def describe(self):
        return self.label or (self.apply_cmd if isinstance(self.apply_cmd, str) else " ".join(self.apply_cmd))

    def _run(self, c):
        if self.ps:
            return powershell(c, timeout=self.timeout)
        return run(c, shell=isinstance(c, str), timeout=self.timeout)

    def is_applied(self):
        if self.check:
            return self.check()
        if self.ps_check and IS_WIN:
            r = powershell(self.ps_check, timeout=60)
            if not r.ok:
                return None
            return r.out.strip().endswith("1")
        return None

    def apply(self):
        _check(self._run(self.apply_cmd), self.describe())

    def revert(self, snap):
        if self.revert_cmd:
            _check(self._run(self.revert_cmd), "desfazer " + self.describe())


class _AppxCache(_TaskCache):
    ttl = 30.0

    def get(self) -> dict[str, str]:
        if not IS_WIN:
            return self.data
        if time.time() - self.t > self.ttl:
            rows = powershell_json("Get-AppxPackage | Select-Object -ExpandProperty Name", timeout=90)
            self.data = {str(n).lower(): n for n in as_list(rows) if n}
            self.t = time.time()
        return self.data


APPX = _AppxCache()


class Appx(Action):
    """Remove um app da Store (sem desfazer: reinstala-se pela Store)."""
    reversible = False

    def __init__(self, package: str, all_users: bool = False):
        self.package, self.all_users = package, all_users

    def describe(self):
        return f"remover app {self.package}"

    def applicable(self):
        return not IS_WIN or self.package.lower() in APPX.get()

    def is_applied(self):
        return self.package.lower() not in APPX.get()

    def apply(self):
        APPX.invalidate()
        au = " -AllUsers" if self.all_users else ""
        script = (f"Get-AppxPackage{au} -Name '{self.package}' | Remove-AppxPackage{au} -ErrorAction SilentlyContinue;"
                  f"Get-AppxProvisionedPackage -Online | Where-Object DisplayName -eq '{self.package}' |"
                  " Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue | Out-Null")
        _check(powershell(script, timeout=300), self.describe())


class _CapCache:
    """Estado de todos os recursos opcionais (Get-WindowsCapability). Uma leitura só, compartilhada: a consulta é
    lenta (10 a 60 s) e a lista do Debloat pede o estado de vários itens ao mesmo tempo."""
    ttl = 300.0

    def __init__(self):
        import threading
        self.t = 0.0
        self.data: dict[str, str] = {}
        self.lock = threading.Lock()

    def get(self) -> dict[str, str]:
        if not IS_WIN:
            return self.data
        with self.lock:
            if time.time() - self.t > self.ttl:
                rows = powershell_json("Get-WindowsCapability -Online | Select-Object Name,"
                                       "@{n='State';e={[string]$_.State}}", timeout=240)
                if rows is not None:
                    self.data = {r["Name"]: r.get("State") or "" for r in as_list(rows) if r and r.get("Name")}
                    self.t = time.time()
            return self.data

    def invalidate(self):
        self.t = 0.0


CAPS = _CapCache()
# estados em que o recurso ainda está no PC (UninstallPending conta como removido: some ao reiniciar)
CAP_PRESENT = ("installed", "installpending", "partiallyinstalled")


def cap_matches(caps: dict[str, str], pattern: str) -> dict[str, str]:
    import fnmatch
    return {n: st for n, st in caps.items() if fnmatch.fnmatchcase(n.lower(), pattern.lower())}


class Capability(Action):
    """Recurso opcional do Windows (Get-WindowsCapability). Remove só o que está instalado e, no Desfazer,
    reinstala pela internet exatamente o que foi removido (não todos os idiomas do mesmo recurso)."""

    def __init__(self, pattern: str, label: str = ""):
        self.pattern, self.label = pattern, label

    def describe(self):
        return f"remover recurso {self.label or self.pattern}"

    def _mine(self) -> dict[str, str]:
        return cap_matches(CAPS.get(), self.pattern)

    def applicable(self):
        return not IS_WIN or bool(self._mine())

    def is_applied(self):
        m = self._mine()
        if not m:
            return None
        return not any(st.lower() in CAP_PRESENT for st in m.values())

    def capture(self):
        return {"removed": sorted(n for n, st in self._mine().items() if st.lower() == "installed")}

    def apply(self):
        names = [n for n, st in self._mine().items() if st.lower() == "installed"]
        if not names:
            return
        lst = ",".join("'" + n.replace("'", "''") + "'" for n in names)
        script = ("$bad=@(); foreach($n in @(" + lst + ")){ try { Remove-WindowsCapability -Online -Name $n "
                  "-ErrorAction Stop | Out-Null } catch { $bad += ($n + ': ' + $_.Exception.Message) } };"
                  "if($bad.Count){ Write-Output ($bad -join ' | '); exit 1 }")
        r = powershell(script, timeout=1200)
        CAPS.invalidate()
        if not r.ok:
            txt = (r.out or r.err or "").strip()
            if "0x800f0825" in txt.lower() or "permanent" in txt.lower() or "permanente" in txt.lower():
                raise ActionError(f"{self.describe()}: o Windows marca este recurso como parte fixa do idioma "
                                  "instalado e não deixa remover.")
            _check(r, self.describe())

    def revert(self, snap):
        if "removed" in snap:
            names = [n for n in (snap["removed"] or []) if isinstance(n, str) and re.fullmatch(r"[\w.~\-]+", n)]
        else:                       # registro de versões antigas (antes da 2.4.1): volta o que foi tirado
            names = [n for n, st in self._mine().items() if st.lower() not in CAP_PRESENT]
        if not names:
            return
        lst = ",".join("'" + n.replace("'", "''") + "'" for n in names)
        r = powershell("foreach($n in @(" + lst + ")){ Add-WindowsCapability -Online -Name $n | Out-Null }",
                       timeout=1800)
        CAPS.invalidate()
        _check(r, "reinstalar " + (self.label or self.pattern))


class JsonKey(Action):
    """Uma chave num arquivo JSON (ex.: settings.json do Discord)."""

    def __init__(self, path: str, key: str, value):
        self.path, self.key, self.value = path, key, value

    def describe(self):
        return f"{self.path}: {self.key} = {self.value!r}"

    def _load(self):
        p = Path(expand(self.path))
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return None

    def applicable(self):
        return Path(expand(self.path)).exists()

    def is_applied(self):
        d = self._load()
        return None if d is None else d.get(self.key) == self.value

    def capture(self):
        d = self._load() or {}
        return {"exists": self.key in d, "value": d.get(self.key)}

    def _save(self, d):
        Path(expand(self.path)).write_text(json.dumps(d, indent=2), encoding="utf-8")

    def apply(self):
        d = self._load()
        if d is None:
            raise ActionError("arquivo não encontrado")
        d[self.key] = self.value
        self._save(d)

    def revert(self, snap):
        d = self._load()
        if d is None:
            return
        if snap.get("exists"):
            d[self.key] = snap.get("value")
        else:
            d.pop(self.key, None)
        self._save(d)


class Interfaces(Action):
    """Valor de registro aplicado em todas as interfaces de rede TCP/IP com IP."""
    BASE = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"

    def __init__(self, name: str, value: int):
        self.name, self.value = name, value

    def describe(self):
        return f"Tcpip\\Interfaces\\* [{self.name}] = {self.value}"

    def _ifaces(self):
        out = []
        for sub in reg.subkeys("HKLM", self.BASE):
            p = f"{self.BASE}\\{sub}"
            ip = reg.read("HKLM", p, "DhcpIPAddress") or reg.read("HKLM", p, "IPAddress")
            if ip and str(ip[1]).strip("[]' ") not in ("", "0.0.0.0"):
                out.append(p)
        return out

    def applicable(self):
        return not IS_WIN or bool(self._ifaces())

    def is_applied(self):
        ifs = self._ifaces()
        if not ifs:
            return None
        return all((reg.read("HKLM", p, self.name) or (None, None))[1] == self.value for p in ifs)

    def capture(self):
        snap = {}
        for p in self._ifaces():
            cur = reg.read("HKLM", p, self.name)
            snap[p] = None if cur is None else cur[1]
        return {"ifaces": snap}

    def apply(self):
        for p in self._ifaces():
            reg.write("HKLM", p, self.name, "dword", self.value)

    def revert(self, snap):
        base = self.BASE.lower() + "\\"
        for p, old in (snap.get("ifaces") or {}).items():
            sub = str(p).lower()[len(base):]
            if not str(p).lower().startswith(base) or not sub or "\\" in sub:
                continue          # só valores dentro de Tcpip\Interfaces\<placa>
            if old is None:
                reg.delete_value("HKLM", p, self.name)
            else:
                reg.write("HKLM", p, self.name, "dword", old)


class Custom(Action):
    """Ação montada com funções (para casos especiais de módulos)."""

    def __init__(self, label: str, apply: Callable[[], None], *, check=None, capture=None,
                 revert=None, applicable=None):
        self.label, self._apply, self._check = label, apply, check
        self._capture, self._revert, self._applicable = capture, revert, applicable
        self.reversible = revert is not None

    def describe(self):
        return self.label

    def applicable(self):
        return self._applicable() if self._applicable else True

    def is_applied(self):
        return self._check() if self._check else None

    def capture(self):
        return self._capture() if self._capture else {}

    def apply(self):
        self._apply()

    def revert(self, snap):
        if self._revert:
            self._revert(snap)
