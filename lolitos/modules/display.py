"""Monitores: listar modos e colocar cada um na taxa de atualização máxima."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt

from lolitos.core.actions import Action, ActionError
from lolitos.core.system import IS_WIN

ENUM_CURRENT_SETTINGS = -1
DM_DISPLAYFREQUENCY = 0x00400000
CDS_UPDATEREGISTRY = 0x01
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x01
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x04


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wt.WCHAR * 32), ("dmSpecVersion", wt.WORD), ("dmDriverVersion", wt.WORD),
        ("dmSize", wt.WORD), ("dmDriverExtra", wt.WORD), ("dmFields", wt.DWORD),
        ("dmPositionX", wt.LONG), ("dmPositionY", wt.LONG),
        ("dmDisplayOrientation", wt.DWORD), ("dmDisplayFixedOutput", wt.DWORD),
        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short), ("dmFormName", wt.WCHAR * 32),
        ("dmLogPixels", wt.WORD), ("dmBitsPerPel", wt.DWORD), ("dmPelsWidth", wt.DWORD),
        ("dmPelsHeight", wt.DWORD), ("dmDisplayFlags", wt.DWORD), ("dmDisplayFrequency", wt.DWORD),
        ("dmICMMethod", wt.DWORD), ("dmICMIntent", wt.DWORD), ("dmMediaType", wt.DWORD),
        ("dmDitherType", wt.DWORD), ("dmReserved1", wt.DWORD), ("dmReserved2", wt.DWORD),
        ("dmPanningWidth", wt.DWORD), ("dmPanningHeight", wt.DWORD),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("DeviceName", wt.WCHAR * 32), ("DeviceString", wt.WCHAR * 128),
                ("StateFlags", wt.DWORD), ("DeviceID", wt.WCHAR * 128), ("DeviceKey", wt.WCHAR * 128)]


if IS_WIN:  # no Linux WCHAR/DWORD têm outro tamanho
    assert ctypes.sizeof(DEVMODEW) == 220, ctypes.sizeof(DEVMODEW)


def _user32():
    return ctypes.windll.user32


def monitors() -> list[dict]:
    """[{device, name, primary, width, height, hz, max_hz}]"""
    if not IS_WIN:
        return []
    u = _user32()
    out, i = [], 0
    while True:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(dd)
        if not u.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not dd.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP:
            continue
        cur = DEVMODEW()
        cur.dmSize = ctypes.sizeof(cur)
        if not u.EnumDisplaySettingsW(dd.DeviceName, ENUM_CURRENT_SETTINGS, ctypes.byref(cur)):
            continue
        best, m = cur.dmDisplayFrequency, 0
        while True:
            dm = DEVMODEW()
            dm.dmSize = ctypes.sizeof(dm)
            if not u.EnumDisplaySettingsW(dd.DeviceName, m, ctypes.byref(dm)):
                break
            m += 1
            if (dm.dmPelsWidth, dm.dmPelsHeight) == (cur.dmPelsWidth, cur.dmPelsHeight) \
                    and dm.dmBitsPerPel == cur.dmBitsPerPel:
                best = max(best, dm.dmDisplayFrequency)
        mon = DISPLAY_DEVICEW()
        mon.cb = ctypes.sizeof(mon)
        u.EnumDisplayDevicesW(dd.DeviceName, 0, ctypes.byref(mon), 0)
        out.append({"device": dd.DeviceName, "name": mon.DeviceString or dd.DeviceString,
                    "primary": bool(dd.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE),
                    "width": cur.dmPelsWidth, "height": cur.dmPelsHeight,
                    "hz": cur.dmDisplayFrequency, "max_hz": best})
    return out


def set_refresh(device: str, hz: int) -> int:
    u = _user32()
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(dm)
    u.EnumDisplaySettingsW(device, ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
    dm.dmDisplayFrequency = hz
    dm.dmFields = DM_DISPLAYFREQUENCY
    return u.ChangeDisplaySettingsExW(device, ctypes.byref(dm), None, CDS_UPDATEREGISTRY, None)


class MaxRefreshAction(Action):
    def describe(self):
        return "monitores na taxa de atualização máxima"

    def applicable(self):
        return not IS_WIN or bool(monitors())

    def is_applied(self):
        mons = monitors()
        if not mons:
            return None
        return all(m["hz"] >= m["max_hz"] for m in mons)

    def capture(self):
        return {"hz": {m["device"]: m["hz"] for m in monitors()}}

    def apply(self):
        errs = []
        for m in monitors():
            if m["hz"] < m["max_hz"]:
                rc = set_refresh(m["device"], m["max_hz"])
                if rc != 0:
                    errs.append(f"{m['name']}: Windows recusou {m['max_hz']} Hz (código {rc})")
        if errs:
            raise ActionError("; ".join(errs))

    def revert(self, snap):
        for dev, hz in snap.get("hz", {}).items():
            set_refresh(dev, int(hz))
