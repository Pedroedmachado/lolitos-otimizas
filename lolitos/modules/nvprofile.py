"""Perfis do driver NVIDIA (o mesmo banco que o Painel de Controle NVIDIA usa), pela NVAPI oficial.

Nada toca no jogo: os valores ficam gravados no perfil do programa dentro do driver, exatamente como se
você tivesse mudado em Painel NVIDIA › Gerenciar configurações 3D › Configurações de programa.

- Lê arquivos .nip (exportados pelo NVIDIA Profile Inspector).
- Aplica guardando o valor anterior de cada configuração; desfazer devolve tudo como estava
  (apaga o perfil e os .exe se fomos nós que criamos).
"""
from __future__ import annotations

import ctypes
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from lolitos.core.system import IS_WIN, data_dir


# ====================================================================== .nip
@dataclass
class NipSetting:
    id: int
    value: int
    name: str = ""
    kind: str = "Dword"


@dataclass
class NipProfile:
    name: str
    exes: list[str] = field(default_factory=list)
    settings: list[NipSetting] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # tipos que não são Dword (texto/binário)

    def to_json(self) -> dict:
        return {"name": self.name, "exes": self.exes,
                "settings": [[s.id, s.value, s.name] for s in self.settings]}

    @classmethod
    def from_json(cls, d: dict) -> "NipProfile":
        return cls(d.get("name", ""), list(d.get("exes", [])),
                   [NipSetting(int(i), int(v), n) for i, v, n in d.get("settings", [])])


def _decode(raw: bytes) -> str:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8")
    if len(raw) > 1 and raw[1:2] == b"\x00":
        return raw.decode("utf-16-le")
    return raw.decode("utf-8", errors="replace")


def _int(txt: str) -> int:
    txt = (txt or "").strip()
    return int(txt, 16) if txt.lower().startswith("0x") else int(txt)


def parse_nip(src: bytes | str | Path) -> list[NipProfile]:
    """Lê um .nip (XML em UTF-16 do NVIDIA Profile Inspector). Levanta ValueError se não for um."""
    if isinstance(src, bytes):
        raw = src
    elif isinstance(src, str) and src.lstrip().startswith("<"):
        raw = src.encode("utf-8")
    else:
        raw = Path(src).read_bytes()
    text = _decode(raw)
    text = text.replace('encoding="utf-16"', "").replace("encoding='utf-16'", "")
    try:
        root = ET.fromstring(text.lstrip("﻿"))
    except ET.ParseError as e:
        raise ValueError(f"arquivo .nip inválido: {e}") from e
    out = []
    for p in root.iter("Profile"):
        prof = NipProfile((p.findtext("ProfileName") or "").strip())
        exes = p.find("Executeables")
        if exes is None:
            exes = p.find("Executables")
        if exes is not None:
            prof.exes = [(s.text or "").strip() for s in exes if (s.text or "").strip()]
        sets = p.find("Settings")
        for s in (sets if sets is not None else []):
            kind = (s.findtext("ValueType") or "Dword").strip()
            name = (s.findtext("SettingNameInfo") or "").strip()
            try:
                sid, val = _int(s.findtext("SettingID")), _int(s.findtext("SettingValue"))
            except (TypeError, ValueError):
                prof.skipped.append(name or "?")
                continue
            if kind.lower() != "dword":
                prof.skipped.append(name or str(sid))
                continue
            prof.settings.append(NipSetting(sid, val & 0xFFFFFFFF, name, kind))
        if prof.name and (prof.settings or prof.exes):
            out.append(prof)
    if not out:
        raise ValueError("nenhum perfil encontrado no arquivo")
    return out


# O que cada configuração faz, para mostrar em português (id: (nome, {valor: texto}))
KNOWN = {
    0x0064B541: ("Taxa de atualização preferida", {0: "controlada pelo app", 1: "a mais alta disponível"}),
    0x1075D972: ("Ansel (captura de fotos da NVIDIA)", {0: "desligado", 1: "ligado"}),
    0x107D639D: ("Antialiasing – correção de gama", {0: "desligada", 1: "só em tela cheia", 2: "sempre ligada"}),
    0x10A879AC: ("G-SYNC neste jogo (pedido)", {0: "permitido", 1: "forçado desligado", 2: "proibido",
                                                3: "ULMB", 4: "taxa fixa"}),
    0x10A879CF: ("G-SYNC neste jogo", {0: "permitido", 1: "forçado desligado", 2: "proibido",
                                       3: "ULMB", 4: "taxa fixa"}),
    0x1194F158: ("Modo G-SYNC do aplicativo", {0: "desligado", 1: "só tela cheia", 2: "tela cheia e janela"}),
    0x20C1221E: ("Otimização encadeada (threaded optimization)", {0: "automática", 1: "ligada", 2: "desligada"}),
    0x0005F543: ("Modo de baixa latência (Painel NVIDIA)", {0: "desligado", 1: "ligado", 2: "ultra"}),
    0x10835000: ("Baixa latência ultra no driver", {0: "desligada", 1: "ligada"}),
    0x007BA09E: ("Máximo de quadros pré-renderizados", {0: "controlado pelo app", 1: "1", 2: "2", 3: "3", 4: "4"}),
    0x10D2BB16: ("Filtragem anisotrópica – modo", {0: "controlada pelo app", 1: "definida pelo usuário"}),
    0x101E61A9: ("Filtragem anisotrópica – nível", {2: "2x", 4: "4x", 8: "8x", 16: "16x"}),
    0x00E73211: ("Filtragem anisotrópica – otimização", {0: "desligada", 1: "ligada"}),
    0x0084CD70: ("Filtragem anisotrópica – otimização de amostra", {0: "desligada", 1: "ligada"}),
    0x0019BB68: ("Filtragem de textura – viés LOD negativo", {0: "permitir", 1: "travar (clamp)"}),
    0x00CE2691: ("Filtragem de textura – qualidade", {0xFFFFFFF6: "alta qualidade", 0: "qualidade",
                                                     10: "desempenho", 20: "alto desempenho"}),
    0x002ECAF2: ("Filtragem de textura – otimização trilinear", {0: "ligada", 1: "desligada"}),
    0x1057EB71: ("Modo de gerenciamento de energia", {0: "adaptável", 1: "desempenho máximo", 5: "normal"}),
    0x00A879CF: ("Sincronização vertical", {0x08416747: "desligada", 0x47814940: "ligada",
                                            0x60925292: "controlada pelo app"}),
}


def describe(s: NipSetting) -> tuple[str, str]:
    name, vals = KNOWN.get(s.id, (s.name or f"0x{s.id:08X}", {}))
    return name, vals.get(s.value, f"{s.value} (0x{s.value:X})")


# Perfil do Black Desert que acompanha o app (BDO.nip + o guia de FPS do BDO)
BDO_DEFAULT = NipProfile(
    "Black Desert",
    ["blackdesert32.exe", "blackdesert64.exe", "blackdesert_launcher.exe"],
    [NipSetting(6600001, 1, "Preferred refresh rate"),
     NipSetting(276158834, 0, "Enable Ansel"),
     NipSetting(276652957, 2, "Antialiasing - Gamma correction"),
     NipSetting(279476652, 1, "G-SYNC"),
     NipSetting(279476687, 1, "G-SYNC"),
     NipSetting(294973784, 0, "Enable G-SYNC globally"),
     NipSetting(549528094, 1, "Threaded optimization"),
     # do guia de FPS do BDO (NVIDIA Profile Inspector), além do BDO.nip:
     NipSetting(0x007BA09E, 1, "Maximum pre-rendered frames"),
     NipSetting(0x0005F543, 2, "Ultra Low Latency - CPL State"),
     NipSetting(0x10835000, 1, "Ultra Low Latency - Enabled"),
     NipSetting(0x00A879CF, 0x08416747, "Vertical Sync"),
     NipSetting(0x1057EB71, 1, "Power management mode"),
     NipSetting(0x00E73211, 0, "Anisotropic filter - Optimization"),
     NipSetting(0x0084CD70, 1, "Anisotropic filter - Sample optimization"),
     NipSetting(0x10D2BB16, 1, "Anisotropic filtering - Mode"),
     NipSetting(0x101E61A9, 8, "Anisotropic filtering - Setting"),
     NipSetting(0x0019BB68, 1, "Texture filtering - Negative LOD bias"),
     NipSetting(0x00CE2691, 20, "Texture filtering - Quality"),
     NipSetting(0x002ECAF2, 0, "Texture filtering - Trilinear optimization")],
)


def custom_file() -> Path:
    return data_dir() / "nvidia_bdo.json"


def bdo_profile() -> NipProfile:
    """O perfil importado pelo usuário, se houver; senão o que acompanha o app."""
    import json
    f = custom_file()
    if f.exists():
        try:
            return NipProfile.from_json(json.loads(f.read_text("utf-8")))
        except (OSError, ValueError, TypeError, KeyError):
            pass
    return BDO_DEFAULT


def save_custom(p: NipProfile | None) -> None:
    import json
    f = custom_file()
    if p is None:
        f.unlink(missing_ok=True)
    else:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(p.to_json(), ensure_ascii=False, indent=1), "utf-8")


# ====================================================================== NVAPI (DRS)
class NvError(Exception):
    pass


NVAPI_OK = 0
SETTING_NOT_FOUND = -160
PROFILE_NOT_FOUND = -163
EXECUTABLE_NOT_FOUND = -166
EXECUTABLE_ALREADY_IN_USE = -167
ERRORS = {-1: "erro genérico", -3: "NVAPI não inicializada", -5: "placa NVIDIA não encontrada",
          -6: "driver NVIDIA não carregado", -137: "precisa de administrador", -160: "configuração não encontrada",
          -163: "perfil não encontrado", -164: "nome de perfil em uso", -166: "programa não encontrado",
          -167: "programa já está em outro perfil", -168: "tipo de valor diferente"}

STR = 2048            # NVAPI_UNICODE_STRING_MAX
CURRENT_PROFILE = 0   # NVDRS_CURRENT_PROFILE_LOCATION


class _Setting(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("settingName", ctypes.c_wchar * STR),
                ("settingId", ctypes.c_uint32), ("settingType", ctypes.c_int32),
                ("settingLocation", ctypes.c_int32), ("isCurrentPredefined", ctypes.c_uint32),
                ("isPredefinedValid", ctypes.c_uint32), ("predefinedValue", ctypes.c_ubyte * 4100),
                ("currentValue", ctypes.c_ubyte * 4100)]


class _Profile(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("profileName", ctypes.c_wchar * STR),
                ("gpuSupport", ctypes.c_uint32), ("isPredefined", ctypes.c_uint32),
                ("numOfApps", ctypes.c_uint32), ("numOfSettings", ctypes.c_uint32)]


class _App(ctypes.Structure):    # NVDRS_APPLICATION_V4
    _fields_ = [("version", ctypes.c_uint32), ("isPredefined", ctypes.c_uint32),
                ("appName", ctypes.c_wchar * STR), ("userFriendlyName", ctypes.c_wchar * STR),
                ("launcher", ctypes.c_wchar * STR), ("fileInFolder", ctypes.c_wchar * STR),
                ("flags", ctypes.c_uint32), ("commandLine", ctypes.c_wchar * STR)]


def _ver(struct, n):
    return ctypes.sizeof(struct) | (n << 16)


SETTING_VER, PROFILE_VER, APP_VER = _ver(_Setting, 1), _ver(_Profile, 1), _ver(_App, 4)

H = ctypes.c_void_p
P = ctypes.POINTER
U = ctypes.c_uint32
_SIGS = {   # nome: (ids, argtypes)
    "Initialize": ((0x0150E828,), ()),
    "CreateSession": ((0x0694D52E,), (P(H),)),
    "DestroySession": ((0xDAD9CFF8,), (H,)),
    "LoadSettings": ((0x375DBD6B,), (H,)),
    "SaveSettings": ((0xFCBC7E14,), (H,)),
    "CreateProfile": ((0xCC176068,), (H, P(_Profile), P(H))),
    "DeleteProfile": ((0x17093206,), (H, H)),
    "GetProfileInfo": ((0x61CD6FD6,), (H, H, P(_Profile))),
    "FindProfileByName": ((0x7E4A9A0B,), (H, ctypes.c_wchar_p, P(H))),
    "CreateApplication": ((0x4347A9DE,), (H, H, P(_App))),
    "DeleteApplication": ((0x2C694BC6,), (H, H, ctypes.c_wchar_p)),
    "FindApplicationByName": ((0xEEE566B2,), (H, ctypes.c_wchar_p, P(H), P(_App))),
    "SetSetting": ((0x8A2CF5F5, 0x577DD202), (H, H, P(_Setting), U, U)),
    "GetSetting": ((0xEA99498D, 0x73BF8338), (H, H, U, P(_Setting), P(U))),
    "DeleteProfileSetting": ((0xD20D29DF, 0xE4A26362), (H, H, U)),
    "RestoreProfileDefaultSetting": ((0x7DD5B261, 0x53F0381E), (H, H, U)),
}

_lock = threading.RLock()
_api: dict | None = None
_api_err = ""


def _load() -> dict:
    global _api, _api_err
    with _lock:
        if _api is not None:
            return _api
        if _api_err:
            raise NvError(_api_err)
        try:
            if not IS_WIN:
                raise OSError("só no Windows")
            dll = ctypes.CDLL("nvapi64.dll" if ctypes.sizeof(ctypes.c_void_p) == 8 else "nvapi.dll")
            qi = dll.nvapi_QueryInterface
            qi.restype, qi.argtypes = ctypes.c_void_p, [ctypes.c_uint32]
        except (OSError, AttributeError):
            _api_err = "driver NVIDIA não encontrado"
            raise NvError(_api_err)
        api = {}
        for name, (ids, args) in _SIGS.items():
            for fid in ids:
                ptr = qi(fid)
                if ptr:
                    api[name] = ctypes.CFUNCTYPE(ctypes.c_int, *args)(ptr)
                    break
        missing = [n for n in _SIGS if n not in api]
        if missing:
            _api_err = "driver NVIDIA antigo demais (faltam funções: " + ", ".join(missing) + ")"
            raise NvError(_api_err)
        r = api["Initialize"]()
        if r != NVAPI_OK:
            _api_err = "NVAPI não iniciou: " + ERRORS.get(r, str(r))
            raise NvError(_api_err)
        _api = api
        return api


def available() -> bool:
    try:
        _load()
        return True
    except NvError:
        return False


def _ok(r: int, what: str):
    if r != NVAPI_OK:
        raise NvError(f"{what}: {ERRORS.get(r, f'código {r}')}")


class Drs:
    """Sessão do banco de perfis do driver (use com `with`)."""

    def __enter__(self):
        self.api = _load()
        _lock.acquire()
        self.h = H()
        try:
            _ok(self.api["CreateSession"](ctypes.byref(self.h)), "abrir sessão")
            _ok(self.api["LoadSettings"](self.h), "carregar perfis")
        except Exception:
            _lock.release()
            raise
        return self

    def __exit__(self, *exc):
        try:
            self.api["DestroySession"](self.h)
        finally:
            _lock.release()

    # --------------------------------------------------------------- perfis e programas
    def find_app(self, exe: str):
        hp, app = H(), _App(version=APP_VER)
        r = self.api["FindApplicationByName"](self.h, exe, ctypes.byref(hp), ctypes.byref(app))
        if r in (EXECUTABLE_NOT_FOUND, PROFILE_NOT_FOUND):
            return None
        _ok(r, f"procurar {exe}")
        return hp.value

    def find_profile(self, name: str):
        hp = H()
        r = self.api["FindProfileByName"](self.h, name, ctypes.byref(hp))
        if r == PROFILE_NOT_FOUND:
            return None
        _ok(r, f"procurar perfil {name}")
        return hp.value

    def profile_name(self, hp) -> str:
        p = _Profile(version=PROFILE_VER)
        _ok(self.api["GetProfileInfo"](self.h, H(hp), ctypes.byref(p)), "ler perfil")
        return p.profileName

    def create_profile(self, name: str):
        p, hp = _Profile(version=PROFILE_VER, profileName=name), H()
        _ok(self.api["CreateProfile"](self.h, ctypes.byref(p), ctypes.byref(hp)), f"criar perfil {name}")
        return hp.value

    def delete_profile(self, hp):
        _ok(self.api["DeleteProfile"](self.h, H(hp)), "apagar perfil")

    def add_app(self, hp, exe: str):
        app = _App(version=APP_VER, appName=exe)
        _ok(self.api["CreateApplication"](self.h, H(hp), ctypes.byref(app)), f"adicionar {exe}")

    def del_app(self, hp, exe: str):
        r = self.api["DeleteApplication"](self.h, H(hp), exe)
        if r not in (NVAPI_OK, EXECUTABLE_NOT_FOUND):
            _ok(r, f"remover {exe}")

    # --------------------------------------------------------------- configurações
    def get(self, hp, sid: int) -> dict | None:
        s, x = _Setting(version=SETTING_VER), U(0)
        r = self.api["GetSetting"](self.h, H(hp), sid, ctypes.byref(s), ctypes.byref(x))
        if r == SETTING_NOT_FOUND:
            return None
        _ok(r, f"ler 0x{sid:08X}")
        val = int.from_bytes(bytes(s.currentValue[:4]), "little")
        own = s.settingLocation == CURRENT_PROFILE
        return {"value": val, "own": own, "user": own and not s.isCurrentPredefined,
                "predef": bool(s.isPredefinedValid)}

    def set(self, hp, sid: int, value: int):
        s = _Setting(version=SETTING_VER, settingId=sid, settingType=0)
        s.currentValue[:4] = list((value & 0xFFFFFFFF).to_bytes(4, "little"))
        _ok(self.api["SetSetting"](self.h, H(hp), ctypes.byref(s), 0, 0), f"gravar 0x{sid:08X}")

    def reset(self, hp, sid: int, predefined: bool):
        fn = "RestoreProfileDefaultSetting" if predefined else "DeleteProfileSetting"
        r = self.api[fn](self.h, H(hp), sid)
        if r not in (NVAPI_OK, SETTING_NOT_FOUND):
            _ok(r, f"voltar 0x{sid:08X}")

    def save(self):
        _ok(self.api["SaveSettings"](self.h), "salvar no driver")


# ====================================================================== lógica (testável com um Drs falso)
def locate(drs, prof: NipProfile):
    """O perfil do driver que vale para esse jogo: o que já contém um dos .exe (como o Painel NVIDIA faz),
    senão um com o mesmo nome. None se não existir."""
    for exe in prof.exes:
        hp = drs.find_app(exe)
        if hp:
            return hp
    return drs.find_profile(prof.name) if prof.name else None


def read_state(drs, prof: NipProfile) -> str:
    """'on' (tudo igual ao arquivo), 'partial' ou 'off'."""
    hp = locate(drs, prof)
    if not hp:
        return "off"
    same = 0
    for s in prof.settings:
        cur = drs.get(hp, s.id)
        same += bool(cur and cur["value"] == s.value)
    if same == len(prof.settings):
        return "on"
    return "partial" if same else "off"


def capture(drs, prof: NipProfile) -> dict:
    """Só lê: como está hoje tudo o que `apply` vai mexer (é o que o desfazer usa)."""
    hp = locate(drs, prof)
    snap = {"profile": drs.profile_name(hp) if hp else prof.name, "created": not hp,
            "apps": [e for e in prof.exes if not drs.find_app(e)], "settings": []}
    for s in prof.settings:
        cur = drs.get(hp, s.id) if hp else None
        snap["settings"].append({"id": s.id, "user": bool(cur and cur["user"]),
                                 "value": cur["value"] if cur else None, "predef": bool(cur and cur["predef"])})
    return snap


def apply(drs, prof: NipProfile) -> None:
    hp = locate(drs, prof) or drs.create_profile(prof.name)
    for exe in prof.exes:
        if not drs.find_app(exe):
            drs.add_app(hp, exe)
    for s in prof.settings:
        drs.set(hp, s.id, s.value)
    drs.save()


def revert(drs, snap: dict) -> None:
    hp = drs.find_profile(snap.get("profile", ""))
    if not hp:
        return
    if snap.get("created"):
        drs.delete_profile(hp)
    else:
        for s in reversed(snap.get("settings", [])):
            if s.get("user") and s.get("value") is not None:
                drs.set(hp, s["id"], s["value"])
            else:
                drs.reset(hp, s["id"], s.get("predef", False))
        for exe in snap.get("apps", []):
            drs.del_app(hp, exe)
    drs.save()


def current_values(prof: NipProfile) -> dict[int, int | None]:
    """Valores que o driver usa hoje para esse jogo (para mostrar na tela)."""
    with Drs() as d:
        hp = locate(d, prof)
        if not hp:
            return {}
        out = {}
        for s in prof.settings:
            cur = d.get(hp, s.id)
            out[s.id] = cur["value"] if cur else None
        return out
