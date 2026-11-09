"""Liberar RAM sem fechar programas: esvazia working sets e a lista de espera (standby)."""
from __future__ import annotations

import ctypes

from lolitos.core.system import IS_WIN

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SET_QUOTA = 0x0100
SystemMemoryListInformation = 80
MemoryEmptyWorkingSets = 2
MemoryFlushModifiedList = 3
MemoryPurgeStandbyList = 4
SE_PRIVILEGE_ENABLED = 0x2
TOKEN_ADJUST_PRIVILEGES = 0x20
TOKEN_QUERY = 0x8


def _enable_privilege(name: str) -> bool:
    from ctypes import wintypes as wt

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", wt.DWORD), ("HighPart", wt.LONG)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", wt.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", wt.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

    adv, k32 = ctypes.windll.advapi32, ctypes.windll.kernel32
    token = wt.HANDLE()
    if not adv.OpenProcessToken(k32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(token)):
        return False
    luid = LUID()
    if not adv.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
        k32.CloseHandle(token)
        return False
    tp = TOKEN_PRIVILEGES(1, (LUID_AND_ATTRIBUTES * 1)(LUID_AND_ATTRIBUTES(luid, SE_PRIVILEGE_ENABLED)))
    ok = adv.AdjustTokenPrivileges(token, False, ctypes.byref(tp), 0, None, None)
    err = k32.GetLastError()
    k32.CloseHandle(token)
    return bool(ok) and err == 0


def _sysinfo(cmd: int) -> int:
    v = ctypes.c_int(cmd)
    return ctypes.windll.ntdll.NtSetSystemInformation(SystemMemoryListInformation, ctypes.byref(v), ctypes.sizeof(v))


def free_ram(exclude_names: tuple[str, ...] = (), standby: bool = True) -> dict:
    """Retorna {'before': bytes_livres, 'after': ..., 'freed': ..., 'processes': n}."""
    import psutil
    before = psutil.virtual_memory().available
    if not IS_WIN:
        return {"before": before, "after": before, "freed": 0, "processes": 0}
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    excl = {n.lower() for n in exclude_names}
    n = 0
    for p in psutil.process_iter(["pid", "name"]):
        if (p.info["name"] or "").lower() in excl or p.info["pid"] in (0, 4):
            continue
        h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, p.info["pid"])
        if h:
            if psapi.EmptyWorkingSet(h):
                n += 1
            k32.CloseHandle(h)
    if standby and _enable_privilege("SeProfileSingleProcessPrivilege"):
        _sysinfo(MemoryFlushModifiedList)
        _sysinfo(MemoryPurgeStandbyList)
    after = psutil.virtual_memory().available
    return {"before": before, "after": after, "freed": max(0, after - before), "processes": n}
