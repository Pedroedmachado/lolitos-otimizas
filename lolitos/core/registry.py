"""Acesso ao registro com fallback em memória (para testar fora do Windows)."""
from __future__ import annotations

from lolitos.core.system import IS_WIN

if IS_WIN:
    import winreg

KINDS = ("dword", "qword", "sz", "expand", "multi", "binary")

if IS_WIN:
    _HIVES = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKU": winreg.HKEY_USERS,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
    }
    _KIND_TO_WIN = {
        "dword": winreg.REG_DWORD, "qword": winreg.REG_QWORD, "sz": winreg.REG_SZ,
        "expand": winreg.REG_EXPAND_SZ, "multi": winreg.REG_MULTI_SZ, "binary": winreg.REG_BINARY,
    }
    _WIN_TO_KIND = {v: k for k, v in _KIND_TO_WIN.items()}
    _WOW = winreg.KEY_WOW64_64KEY


class _MemReg:
    """Registro falso: {(hive, path_lower): {"_path": path, name_lower: (name, kind, value)}}"""

    def __init__(self):
        self.keys: dict[tuple[str, str], dict] = {}

    def _k(self, hive, path):
        return hive, path.strip("\\").lower()

    def key_exists(self, hive, path):
        return self._k(hive, path) in self.keys

    def create_key(self, hive, path):
        parts = path.strip("\\").split("\\")
        for i in range(1, len(parts) + 1):
            self.keys.setdefault(self._k(hive, "\\".join(parts[:i])), {})

    def read(self, hive, path, name):
        d = self.keys.get(self._k(hive, path))
        if d is None or name.lower() not in d:
            return None
        _, kind, value = d[name.lower()]
        return kind, value

    def write(self, hive, path, name, kind, value):
        self.create_key(hive, path)
        self.keys[self._k(hive, path)][name.lower()] = (name, kind, value)

    def delete_value(self, hive, path, name):
        d = self.keys.get(self._k(hive, path))
        if d:
            d.pop(name.lower(), None)

    def delete_tree(self, hive, path):
        h, p = self._k(hive, path)
        for key in [k for k in self.keys if k[0] == h and (k[1] == p or k[1].startswith(p + "\\"))]:
            del self.keys[key]

    def subkeys(self, hive, path):
        h, p = self._k(hive, path)
        out = set()
        for kh, kp in self.keys:
            if kh == h and kp.startswith(p + "\\"):
                out.add(kp[len(p) + 1:].split("\\")[0])
        return sorted(out)


MEM = _MemReg()


def _open(hive, path, write=False):
    access = (winreg.KEY_READ | winreg.KEY_WRITE) if write else winreg.KEY_READ
    return winreg.OpenKey(_HIVES[hive], path, 0, access | _WOW)


def key_exists(hive: str, path: str) -> bool:
    if not IS_WIN:
        return MEM.key_exists(hive, path)
    try:
        winreg.CloseKey(_open(hive, path))
        return True
    except OSError:
        return False


def read(hive: str, path: str, name: str):
    """Retorna (kind, value) ou None se o valor não existe."""
    if not IS_WIN:
        return MEM.read(hive, path, name)
    try:
        with _open(hive, path) as k:
            value, t = winreg.QueryValueEx(k, name)
            return _WIN_TO_KIND.get(t, "binary"), value
    except OSError:
        return None


def write(hive: str, path: str, name: str, kind: str, value) -> None:
    if kind == "dword":
        value = int(value) & 0xFFFFFFFF
    elif kind == "qword":
        value = int(value) & 0xFFFFFFFFFFFFFFFF
    elif kind == "binary" and isinstance(value, str):
        value = bytes.fromhex(value)
    if not IS_WIN:
        MEM.write(hive, path, name, kind, value)
        return
    with winreg.CreateKeyEx(_HIVES[hive], path, 0, winreg.KEY_WRITE | _WOW) as k:
        winreg.SetValueEx(k, name, 0, _KIND_TO_WIN[kind], value)


def delete_value(hive: str, path: str, name: str) -> None:
    if not IS_WIN:
        MEM.delete_value(hive, path, name)
        return
    try:
        with _open(hive, path, write=True) as k:
            winreg.DeleteValue(k, name)
    except FileNotFoundError:
        pass


def subkeys(hive: str, path: str) -> list[str]:
    if not IS_WIN:
        return MEM.subkeys(hive, path)
    out = []
    try:
        with _open(hive, path) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(k, i))
                    i += 1
                except OSError:
                    break
    except OSError:
        pass
    return out


def values(hive: str, path: str) -> list[tuple[str, str, object]]:
    if not IS_WIN:
        d = MEM.keys.get(MEM._k(hive, path), {})
        return [(n, k, v) for (n, k, v) in d.values()]
    out = []
    try:
        with _open(hive, path) as k:
            i = 0
            while True:
                try:
                    n, v, t = winreg.EnumValue(k, i)
                    out.append((n, _WIN_TO_KIND.get(t, "binary"), v))
                    i += 1
                except OSError:
                    break
    except OSError:
        pass
    return out


def delete_tree(hive: str, path: str) -> None:
    if not IS_WIN:
        MEM.delete_tree(hive, path)
        return
    for sub in subkeys(hive, path):
        delete_tree(hive, path + "\\" + sub)
    try:
        winreg.DeleteKeyEx(_HIVES[hive], path, _WOW, 0)
    except OSError:
        pass


def tree_empty(hive: str, path: str, depth: int = 0) -> bool:
    """True se a chave e todas as subchaves não têm nenhum valor."""
    if depth > 8 or not key_exists(hive, path):
        return depth <= 8
    if values(hive, path):
        return False
    return all(tree_empty(hive, f"{path}\\{s}", depth + 1) for s in subkeys(hive, path))


def first_missing_parent(hive: str, path: str) -> str | None:
    """Primeira chave (do topo para baixo) que ainda não existe, ou None se já existe."""
    parts = path.strip("\\").split("\\")
    for i in range(1, len(parts) + 1):
        sub = "\\".join(parts[:i])
        if not key_exists(hive, sub):
            return sub
    return None


def to_json(kind: str, value):
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def from_json(kind: str, value):
    if kind == "binary" and isinstance(value, str):
        return bytes.fromhex(value)
    return value
