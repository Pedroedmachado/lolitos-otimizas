"""Núcleos do processador para o BDO, no estilo de uma regra do Process Lasso.

Você escolhe as threads (por CCD e núcleo) e o método:
- Afinidade de CPU (rígida): o jogo só pode rodar nessas threads.
- CPU Sets (flexível): o Windows prefere essas threads para o jogo, mas pode usar outras se precisar.

Enquanto o app estiver aberto (ou na bandeja), toda vez que o BlackDesert64.exe abrir a regra é aplicada, e é
aplicada de novo se o jogo mudar a afinidade sozinho. Nada é injetado no jogo: é o mesmo ajuste que o Gerenciador
de Tarefas faz em 'Definir afinidade'."""
from __future__ import annotations

import ctypes
import logging
import threading
import time

import psutil

from lolitos.bdo.game import EXE
from lolitos.core import settings
from lolitos.core.system import IS_WIN
from lolitos.modules.cputopo import Topology

log = logging.getLogger("lolitos")
KEY = "bdo_cores"            # {"enabled": bool, "method": "affinity"|"cpusets", "cpus": [int]}
METHODS = [("affinity", "Afinidade de CPU"), ("cpusets", "CPU Sets")]


def rule() -> dict:
    r = dict(settings.get(KEY) or {})
    r.setdefault("enabled", False)
    r.setdefault("method", "affinity")
    r.setdefault("cpus", [])
    return r


def save_rule(**kw) -> dict:
    r = rule()
    r.update(kw)
    settings.set(KEY, r)
    return r


# ---------------------------------------------------------------- predefinições
def presets(t: Topology) -> list[tuple[str, str, list[int], str]]:
    """(chave, nome, threads, explicação) que fazem sentido neste processador."""
    allc = t.threads
    out = [("all", "Todas", allc, "Sem restrição (como o Windows faz por padrão).")]
    if len(t.ccds) > 1:
        v = [c for c in t.ccds if c.vcache]
        if v:
            out.append(("vcache", "Só o CCD com 3D V-Cache", sorted(v[0].cpus),
                        "O BDO roda inteiro no CCD do cache 3D: mais FPS mínimo e menos travadas."))
            others = [c for c in t.ccds if not c.vcache]
            if others:
                out.append(("freq", "Só o CCD de frequência", sorted(others[0].cpus),
                            "O CCD sem cache 3D, com clock mais alto."))
        else:
            out.append(("ccd0", "Só o CCD 0", sorted(t.ccds[0].cpus),
                        "Evita a latência entre CCDs (o jogo não pula de um chiplet para o outro)."))
    if t.smt:
        out.append(("physical", "Um thread por núcleo (sem SMT)", sorted(c.cpus[0] for c in t.cores),
                    "Usa só a primeira thread de cada núcleo físico."))
    if len(t.cores) >= 6:
        out.append(("no0", "Sem o núcleo 0", [c for c in allc if c not in t.cores[0].cpus],
                    "Deixa o núcleo 0 para o Windows, o Discord e os drivers."))
    rec = recommended(t)
    out.insert(1, ("rec", "Recomendado para o BDO", rec, recommended_why(t)))
    return out


def recommended(t: Topology) -> list[int]:
    if len(t.ccds) > 1:
        v = [c for c in t.ccds if c.vcache] or [t.ccds[0]]
        return sorted(v[0].cpus)
    if len(t.cores) >= 6:
        return [c for c in t.threads if c not in t.cores[0].cpus]
    return t.threads


def recommended_why(t: Topology) -> str:
    if len(t.ccds) > 1:
        if any(c.vcache for c in t.ccds):
            return "Ryzen X3D com dois CCDs: o BDO fica só no CCD com o cache 3D."
        return "Dois CCDs: o BDO fica todo no CCD 0, sem pular de chiplet."
    if len(t.cores) >= 6:
        return "Um CCD: o BDO usa tudo menos o núcleo 0, que fica para o Windows."
    return "Poucos núcleos: o melhor é deixar todos."


# ---------------------------------------------------------------- CPU Sets (Windows 10+)
def _cpuset_ids() -> dict[int, int]:
    """Número da thread lógica → Id do CPU Set."""
    if not IS_WIN:
        return {}
    import struct
    k32 = ctypes.windll.kernel32
    need = ctypes.c_ulong(0)
    k32.GetSystemCpuSetInformation(None, 0, ctypes.byref(need), None, 0)
    if not need.value:
        return {}
    buf = ctypes.create_string_buffer(need.value)
    if not k32.GetSystemCpuSetInformation(buf, need, ctypes.byref(need), None, 0):
        return {}
    raw, off, out = buf.raw, 0, {}
    while off + 8 <= need.value:
        size, typ = struct.unpack_from("<II", raw, off)
        if not size:
            break
        if typ == 0:                                             # CpuSetInformation
            cid, group, lp = struct.unpack_from("<IHB", raw, off + 8)
            out[group * 64 + lp] = cid
        off += size
    return out


def _set_cpusets(pid: int, cpus: list[int] | None) -> None:
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    h = k32.OpenProcess(0x2000 | 0x1000, False, pid)            # SET/QUERY_LIMITED_INFORMATION
    if not h:
        raise PermissionError("o processo não deixou mudar (anti-cheat ou permissão)")
    try:
        if cpus:
            ids = _cpuset_ids()
            arr = (ctypes.c_ulong * len(cpus))(*[ids[c] for c in cpus if c in ids])
            ok = k32.SetProcessDefaultCpuSets(ctypes.c_void_p(h), arr, len(arr))
        else:
            ok = k32.SetProcessDefaultCpuSets(ctypes.c_void_p(h), None, 0)
        if not ok:
            raise PermissionError(f"SetProcessDefaultCpuSets falhou ({ctypes.get_last_error() or k32.GetLastError()})")
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


def _get_cpusets(pid: int) -> list[int] | None:
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    h = k32.OpenProcess(0x1000, False, pid)
    if not h:
        return None
    try:
        arr = (ctypes.c_ulong * 256)()
        n = ctypes.c_ulong(0)
        if not k32.GetProcessDefaultCpuSets(ctypes.c_void_p(h), arr, 256, ctypes.byref(n)):
            return None
        back = {v: k for k, v in _cpuset_ids().items()}
        return sorted(back[arr[i]] for i in range(n.value) if arr[i] in back)
    finally:
        k32.CloseHandle(ctypes.c_void_p(h))


# ---------------------------------------------------------------- aplicar
def bdo_pids() -> list[int]:
    out = []
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() == EXE.lower():
            out.append(p.pid)
    return out


def current(pid: int, method: str) -> list[int] | None:
    try:
        if method == "cpusets":
            return _get_cpusets(pid) if IS_WIN else None
        return sorted(psutil.Process(pid).cpu_affinity())
    except (psutil.Error, OSError):
        return None


def apply_pid(pid: int, method: str, cpus: list[int]) -> str:
    """Aplica e devolve '' (ok) ou o motivo da falha."""
    allc = sorted(range(psutil.cpu_count(logical=True) or 1))
    try:
        if method == "cpusets":
            # tira uma afinidade rígida antiga para os CPU Sets valerem
            try:
                if sorted(psutil.Process(pid).cpu_affinity()) != allc:
                    psutil.Process(pid).cpu_affinity(allc)
            except psutil.Error:
                pass
            _set_cpusets(pid, None if sorted(cpus) == allc else cpus)
        else:
            if IS_WIN:
                try:
                    _set_cpusets(pid, None)
                except OSError:
                    pass
            psutil.Process(pid).cpu_affinity(cpus or allc)
        return ""
    except psutil.AccessDenied:
        return "o jogo protege o próprio processo (anti-cheat); rode o app como administrador"
    except psutil.NoSuchProcess:
        return "o jogo fechou"
    except (OSError, ValueError, KeyError) as e:
        return str(e)


def restore_all() -> str:
    allc = list(range(psutil.cpu_count(logical=True) or 1))
    errs = [e for pid in bdo_pids() for e in [apply_pid(pid, "affinity", allc)] if e]
    return errs[0] if errs else ""


class Watcher(threading.Thread):
    """Fica de olho no BlackDesert64.exe e mantém a regra aplicada (como o Process Lasso)."""

    def __init__(self, on_event=None):
        super().__init__(daemon=True)
        self.on_event = on_event or (lambda kind, msg: None)
        self._stop = threading.Event()
        self.last = ""                 # texto do último estado, para a tela
        self._seen: dict[int, float] = {}

    def stop(self):
        self._stop.set()

    def check_now(self) -> str:
        r = rule()
        if not r["enabled"] or not r["cpus"]:
            self.last = "regra desligada"
            return self.last
        pids = bdo_pids()
        if not pids:
            self.last = "esperando o BDO abrir"
            return self.last
        msgs = []
        for pid in pids:
            want = sorted(r["cpus"])
            if current(pid, r["method"]) == want:
                msgs.append(f"aplicado (PID {pid})")
                continue
            err = apply_pid(pid, r["method"], want)
            if err:
                msgs.append(f"PID {pid}: {err}")
                if pid not in self._seen:
                    self.on_event("aviso", f"Núcleos do BDO: {err}")
            else:
                first = pid not in self._seen
                msgs.append(f"aplicado (PID {pid})")
                self.on_event("ok" if first else "reaplicado",
                              f"Núcleos do BDO: {len(want)} de {psutil.cpu_count(logical=True)} threads"
                              + ("" if first else " (o jogo tinha mudado; aplicado de novo)"))
            self._seen.setdefault(pid, time.time())
        self.last = "; ".join(msgs)
        return self.last

    def run(self):
        while not self._stop.wait(3):
            try:
                self.check_now()
            except Exception:  # noqa: BLE001
                log.exception("núcleos do BDO")
