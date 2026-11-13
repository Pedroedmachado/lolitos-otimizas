"""Importar este pacote registra todo o catálogo de ajustes."""
from lolitos.catalog import debloat, desempenho, entrada, extras, interface, privacidade, rede_gpu, sem_ia  # noqa: F401
from lolitos.bdo import tweaks as _bdo_tweaks  # noqa: F401  (ajustes do Black Desert)
from lolitos.catalog.presets import PRESETS, BASIC_PACK  # noqa: F401

from lolitos.modules.game_tweaks import restore_from_history as _rfh  # noqa: E402

_rfh()   # ajustes por jogo aplicados antes continuam desfazíveis


# Ajustes de HKCU\Control Panel: o Windows só lê no login, então o valor é repassado ao sistema na hora.
from lolitos.core import live as _live  # noqa: E402
from lolitos.core.tweaks import CATALOG as _CATALOG  # noqa: E402

LIVE_INPUT = ("mouse_accel_off", "mouse_sensitivity_default", "mouse_trails_off", "mouse_no_delay",
              "sticky_keys_off", "keyboard_repeat", "menu_delay", "snap_off")
for _id in LIVE_INPUT:
    _CATALOG[_id].live = _live.sync_input
