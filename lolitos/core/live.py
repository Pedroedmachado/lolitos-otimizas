"""Faz valer na hora o que o Windows só leria do registro no próximo login.

Os ajustes de mouse, teclado e acessibilidade ficam em HKCU\\Control Panel, que o Windows carrega ao entrar na
conta. Gravar só o registro deixava o ajuste "ativo" na tela, mas sem efeito até sair e entrar de novo. Aqui os
valores que estão no registro são repassados ao sistema (SystemParametersInfo), tanto ao aplicar quanto ao desfazer."""
from __future__ import annotations

import ctypes
import logging

from lolitos.core import registry as reg
from lolitos.core.system import IS_WIN

log = logging.getLogger("lolitos.live")
SPIF_SENDCHANGE = 0x02
SPI_SETMOUSE, SPI_GETMOUSE = 0x0004, 0x0003
SPI_SETMOUSESPEED, SPI_SETMOUSETRAILS, SPI_SETMOUSEHOVERTIME = 0x0071, 0x005D, 0x0067
SPI_SETKEYBOARDDELAY, SPI_SETKEYBOARDSPEED = 0x0017, 0x000B
SPI_GETSTICKYKEYS, SPI_SETSTICKYKEYS = 0x003A, 0x003B
SPI_GETTOGGLEKEYS, SPI_SETTOGGLEKEYS = 0x0034, 0x0035
SPI_GETFILTERKEYS, SPI_SETFILTERKEYS = 0x0032, 0x0033
SPI_SETMENUSHOWDELAY, SPI_SETWINARRANGING = 0x006B, 0x0083
MOUSE, KEYB, DESK = r"Control Panel\Mouse", r"Control Panel\Keyboard", r"Control Panel\Desktop"
ACC = r"Control Panel\Accessibility"


def _int(path: str, name: str) -> int | None:
    r = reg.read("HKCU", path, name)
    if r is None:
        return None
    try:
        return int(str(r[1]).strip())
    except (TypeError, ValueError):
        return None


class _Flags(ctypes.Structure):          # STICKYKEYS e TOGGLEKEYS têm o mesmo formato
    _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint)]


class _Filter(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint), ("iWaitMSec", ctypes.c_uint),
                ("iDelayMSec", ctypes.c_uint), ("iRepeatMSec", ctypes.c_uint), ("iBounceMSec", ctypes.c_uint)]


def plan() -> list[tuple]:
    """O que seria repassado ao Windows agora: [(nome, código SPI, valor)], só para o que existe no registro."""
    out = []
    spd, t1, t2 = _int(MOUSE, "MouseSpeed"), _int(MOUSE, "MouseThreshold1"), _int(MOUSE, "MouseThreshold2")
    if None not in (spd, t1, t2):
        out.append(("mouse", SPI_SETMOUSE, (t1, t2, spd)))
    for name, path, key, spi, lo, hi in (
            ("mouse_speed", MOUSE, "MouseSensitivity", SPI_SETMOUSESPEED, 1, 20),
            ("mouse_trails", MOUSE, "MouseTrails", SPI_SETMOUSETRAILS, 0, 16),
            ("mouse_hover", MOUSE, "MouseHoverTime", SPI_SETMOUSEHOVERTIME, 1, 5000),
            ("key_delay", KEYB, "KeyboardDelay", SPI_SETKEYBOARDDELAY, 0, 3),
            ("key_speed", KEYB, "KeyboardSpeed", SPI_SETKEYBOARDSPEED, 0, 31),
            ("menu_delay", DESK, "MenuShowDelay", SPI_SETMENUSHOWDELAY, 0, 4000),
            ("snap", DESK, "WindowArrangementActive", SPI_SETWINARRANGING, 0, 1)):
        v = _int(path, key)
        if v is not None and lo <= v <= hi:
            out.append((name, spi, v))
    for name, sub, spi in (("sticky", "StickyKeys", SPI_SETSTICKYKEYS), ("toggle", "ToggleKeys", SPI_SETTOGGLEKEYS),
                           ("filter", "Keyboard Response", SPI_SETFILTERKEYS)):
        v = _int(f"{ACC}\\{sub}", "Flags")
        if v is not None:
            out.append((name, spi, v))
    return out


def sync_input() -> None:
    """Repassa ao Windows os valores de mouse, teclado e acessibilidade que estão no registro. Nunca levanta erro."""
    if not IS_WIN:
        return
    try:
        spi = ctypes.windll.user32.SystemParametersInfoW
        for name, code, v in plan():
            try:
                if code == SPI_SETMOUSE:
                    arr = (ctypes.c_int * 3)(*v)
                    ok = spi(code, 0, arr, SPIF_SENDCHANGE)
                elif code == SPI_SETMOUSESPEED:
                    ok = spi(code, 0, ctypes.c_void_p(v), SPIF_SENDCHANGE)
                elif code in (SPI_SETSTICKYKEYS, SPI_SETTOGGLEKEYS):
                    s = _Flags(ctypes.sizeof(_Flags), v)
                    ok = spi(code, s.cbSize, ctypes.byref(s), SPIF_SENDCHANGE)
                elif code == SPI_SETFILTERKEYS:
                    f = _Filter()
                    f.cbSize = ctypes.sizeof(_Filter)
                    spi(SPI_GETFILTERKEYS, f.cbSize, ctypes.byref(f), 0)      # mantém os tempos atuais
                    f.dwFlags = v
                    ok = spi(code, f.cbSize, ctypes.byref(f), SPIF_SENDCHANGE)
                else:
                    ok = spi(code, v, None, SPIF_SENDCHANGE)
                if not ok:
                    log.info("SystemParametersInfo %s recusado", name)
            except Exception:  # noqa: BLE001
                log.exception("sync %s", name)
    except Exception:  # noqa: BLE001
        log.exception("sync_input")


def mouse_now() -> tuple[int, int, int] | None:
    """(limite1, limite2, aceleração) que o Windows está usando AGORA (para testes)."""
    if not IS_WIN:
        return None
    arr = (ctypes.c_int * 3)()
    if not ctypes.windll.user32.SystemParametersInfoW(SPI_GETMOUSE, 0, arr, 0):
        return None
    return arr[0], arr[1], arr[2]
