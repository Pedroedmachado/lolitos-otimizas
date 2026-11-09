"""Importar este pacote registra todo o catálogo de ajustes."""
from lolitos.catalog import debloat, desempenho, entrada, interface, privacidade, rede_gpu, sem_ia  # noqa: F401
from lolitos.bdo import tweaks as _bdo_tweaks  # noqa: F401  (ajustes do Black Desert)
from lolitos.catalog.presets import PRESETS, BASIC_PACK  # noqa: F401

from lolitos.modules.game_tweaks import restore_from_history as _rfh  # noqa: E402

_rfh()   # ajustes por jogo aplicados antes continuam desfazíveis
