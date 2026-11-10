"""Objetivo de cada ajuste (etiquetas e filtro dos cartões): FPS, Input lag, Rede, Limpeza e Privacidade.

A categoria dá o objetivo principal; a lista abaixo acrescenta ou troca nos casos em que o ajuste serve a mais de
um objetivo (por exemplo, prioridade de primeiro plano ajuda o FPS e também a resposta do mouse)."""
from __future__ import annotations

GOALS = [("fps", "FPS"), ("input", "Input lag"), ("rede", "Rede"), ("limpeza", "Limpeza"),
         ("privacidade", "Privacidade")]
GOAL_NAMES = dict(GOALS)
GOAL_HINT = {
    "fps": "Mais quadros por segundo e menos travadas.",
    "input": "Resposta mais rápida do mouse, teclado e tela.",
    "rede": "Ping mais estável e menos perda de pacotes.",
    "limpeza": "Menos coisa rodando, menos propaganda e um Windows mais enxuto.",
    "privacidade": "Menos dados enviados para a Microsoft e terceiros.",
}

BY_CAT = {
    "desempenho": {"fps"}, "jogos": {"fps"}, "gpu": {"fps"}, "rede": {"rede"}, "entrada": {"input"},
    "privacidade": {"privacidade"}, "ia": {"privacidade", "limpeza"}, "debloat": {"limpeza"},
    "interface": {"limpeza"}, "apps": {"limpeza"}, "atualizacoes": {"limpeza"}, "seguranca": {"fps"},
    "bdo": {"fps"},
}

EXTRA = {
    # resposta (input lag)
    "core_parking": {"input"}, "usb_suspend": {"input"}, "mmcss_games": {"input"}, "system_responsiveness":
        {"input"}, "foreground_boost": {"input"}, "game_dvr_off": {"input"}, "fse_global": {"input"},
    "hags_on": {"input"}, "mpo_off": {"input"}, "refresh_max": {"input"}, "nagle_off": {"input"},
    "menu_delay": {"input"}, "power_plan": {"input"}, "hvci_off": {"input"}, "net_throttling_off": {"input"},
    "bdo_priority": {"input"}, "bdo_nvidia_profile": {"input"}, "mouse_no_delay": {"input"},
    # FPS em ajustes de outras categorias
    "visual_light": {"fps"}, "transparency_off": {"fps"}, "nvidia_telemetry_off": {"privacidade"},
    "edge_background_off": {"fps"}, "store_autoupdate_off": {"fps"}, "wu_no_reboot": set(),
    "dynamic_lighting_off": {"fps"},
    # limpeza em desempenho (o que roda em segundo plano)
    "sysmain_off": {"limpeza"}, "search_index_off": {"limpeza"}, "services_manual": {"limpeza"},
    "spooler_manual": {"limpeza"}, "diag_collector_manual": {"limpeza", "privacidade"},
    "startup_delay_off": {"limpeza"}, "reserved_storage_off": {"limpeza"}, "storage_sense_off": set(),
    "delivery_p2p_off": {"privacidade"}, "audio_ducking_off": set(),
    # privacidade em outras categorias
    "sync_ads_off": {"privacidade"}, "start_no_recs": {"privacidade"}, "no_recent": {"privacidade"},
    "explorer_cloud_off": {"privacidade"}, "remote_assist_off": {"privacidade"}, "wpbt_off": {"privacidade"},
    "push_install_off": {"privacidade"}, "edge_clean": {"privacidade"}, "brave_clean": {"privacidade"},
    "wu_drivers_off": set(),
}
# ajustes cuja categoria não diz nada do objetivo (aparência, comodidade): sem etiqueta da categoria
NO_CAT_GOAL = {
    "dark_mode", "show_ext", "show_hidden", "classic_context", "taskbar_left", "end_task", "snap_off",
    "alttab_windows", "explorer_thispc", "compact_explorer", "start_more_pins", "shortcut_suffix_off",
    "copy_details", "scrollbars", "verbose_status", "skip_lockscreen", "login_noblur", "printscreen_classic",
    "new_bat_reg", "utc_clock", "photo_viewer_classic", "jpeg_quality", "boot_menu_name", "multi_invoke_menu",
    "long_paths", "ntfs_lastaccess", "fth_off", "keyboard_repeat", "numlock_on", "lang_hotkey_off",
    "narrator_hotkey_off", "netfx3_on", "ps_remotesigned", "uac_silent", "autoplay_off", "wu_notify",
    "wu_notifs_off", "discord_skip_update", "ipv4_first", "ipv6_off", "teredo_off", "fast_startup_off",
    "fast_shutdown", "hibernation_off", "appcompat_engine_off", "maintenance_nowake",
}


def goals(t) -> list[str]:
    """Objetivos do ajuste, na ordem de GOALS."""
    base = set() if t.id in NO_CAT_GOAL else set(BY_CAT.get(t.cat, set()))
    extra = EXTRA.get(t.id)
    if extra is not None:
        base |= extra
    if t.id in ("ipv4_first", "ipv6_off", "teredo_off"):
        base.add("rede")
    if t.id in ("fast_startup_off", "hibernation_off"):
        base.add("limpeza")
    return [g for g, _ in GOALS if g in base]
