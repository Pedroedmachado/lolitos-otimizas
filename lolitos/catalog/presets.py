"""Pacotes prontos de ajustes e perfis do usuário."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lolitos.core.system import data_dir
from lolitos.core.tweaks import ADVANCED, CATALOG, ESSENTIAL, RECOMMENDED

PERF_CATS = ("desempenho", "jogos", "entrada", "gpu", "rede", "bdo")



def _ids(pred) -> list[str]:
    return [t.id for t in CATALOG.values() if pred(t)]


# O Boost (Painel e Formatação) aplica exatamente esta lista, na mesma ordem do Boost do app de referência.
# Itens que não valem para o PC (ex.: Windows 10, notebook) ficam de fora pela condição 'when' de cada ajuste.
# Os outros ajustes essenciais e recomendados continuam nas telas deles e na Otimização Completa.
BOOST = [
    "activity_off", "consumer_features_off", "end_task", "hibernation_off", "telemetry_min", "input_collect_off",
    "track_progs_off", "ps_telemetry_off", "tailored_off", "ad_id_off", "wer_off", "wpbt_off", "background_apps_off",
    "reserved_storage_off", "storage_sense_off", "copilot_off", "recall_off", "remove_recall_feature",
    "clicktodo_off", "paint_ai_off", "notepad_ai_off", "edge_copilot_off", "menu_delay", "edge_background_off",
    "widgets_off", "chat_meetnow_off", "telemetry_tasks", "data_collect_tasks", "appcompat_telemetry_off",
    "delivery_p2p_off", "search_local", "speech_models_off", "settings_agent_off", "push_install_off",
    "motion_bg_off", "no_outlook_devhome", "notepad_no_ad", "game_dvr_off", "clipboard_cloud_off", "memcomp_off",
    "foreground_boost", "core_parking", "pcie_aspm", "sysmain_off", "ntfs_lastaccess", "fast_startup_off",
    "game_mode", "mmcss_games", "system_responsiveness", "mouse_accel_off", "refresh_max", "hags_on",
    "net_throttling_off", "wifi_max", "visual_light", "show_ext", "ads_start", "spotlight_off", "sync_ads_off",
    "device_metadata_off", "ceip_off", "mrt_report_off", "scoobe_off", "autoplay_off", "narrator_hotkey_off",
    "services_manual", "feedback_off", "remove_copilot_apps", "power_plan", "boot_menu_name", "sticky_keys_off",
    "mouse_no_delay", "explorer_cloud_off", "diag_collector_manual", "pca_off", "edge_clean",
    "office_telemetry_off", "experiments_off", "wu_no_reboot", "remote_assist_off",
]
# Black Desert: entram no fim do Boost. Sem o jogo instalado, ficam de fora sozinhos (estado "não se aplica").
BOOST_BDO = ["bdo_priority", "bdo_gpu_high", "bdo_postfilter_xml", "bdo_nvidia_profile"]
# Limpeza que o Boost faz depois dos ajustes (alvos de lolitos.modules.cleanup)
BOOST_CLEAN = ["user_temp", "win_temp", "wu_cache", "delivery", "wer", "thumbs"]


def bdo_here() -> bool:
    """Black Desert neste PC (pasta do jogo ou GameOption.txt nos Documentos)."""
    try:
        from lolitos.bdo import game, gameoption
        return bool(game.install_dir() or gameoption.find_gameoption())
    except Exception:  # noqa: BLE001
        return False


def boost_ids() -> list[str]:
    """O que o 'Boost agora' aplica neste PC: a lista BOOST e a do Black Desert, menos o que não se aplica aqui."""
    out = []
    for i in BOOST + (BOOST_BDO if bdo_here() else []):
        t = CATALOG.get(i)
        if t is not None and (t.when() if t.when else True):
            out.append(i)
    return out


@dataclass
class Preset:
    id: str
    name: str
    desc: str
    ids: Callable[[], list[str]]


def _competitivo():
    return _ids(lambda t: t.cat in PERF_CATS and t.level in (ESSENTIAL, RECOMMENDED) and t.recommended_here()
                and t.reversible)


PRESETS = [
    Preset("online", "Jogos online competitivos",
           "Tudo de desempenho, entrada, GPU e rede recomendado para este PC, mais TCP sem espera, tarefas de "
           "telemetria desligadas e Windows Update sem reiniciar no meio da partida. Vale para qualquer jogo.",
           lambda: sorted(set([i for i in _competitivo() if not i.startswith("bdo_")]
                              + ["nagle_off", "telemetry_tasks", "wu_no_reboot", "net_throttling_off"]))),
    Preset("bdo_guerra", "Black Desert — Guerra de Nodes e Cerco",
           "Tudo de desempenho, entrada e rede recomendado para este PC + prioridade, GPU dedicada e TCP sem "
           "espera para o BlackDesert64.exe. Combine com a predefinição 'Guerra' do GameOption.",
           lambda: sorted(set(_competitivo() + ["bdo_priority", "bdo_gpu_high", "bdo_postfilter_xml", "nagle_off",
                                                "telemetry_tasks", "wu_no_reboot"]))),
    Preset("competitivo", "Competitivo",
           "FPS máximo e latência mínima: abre mão de economia de energia e efeitos visuais.",
           lambda: _competitivo() + _ids(lambda t: t.id in ("visual_light", "transparency_off"))),
    Preset("equilibrado", "Equilibrado",
           "O essencial para jogar melhor sem mudar a cara do Windows. Bom ponto de partida.",
           lambda: _ids(lambda t: t.level == ESSENTIAL and t.cat in PERF_CATS + ("atualizacoes",)
                        and t.reversible and t.recommended_here())),
    Preset("modesto", "PC modesto",
           "Pouca RAM ou GPU fraca: corta peso visual e o que roda em segundo plano.",
           lambda: _competitivo() + ["visual_light", "transparency_off", "background_apps_off",
                                     "sysmain_off", "widgets_off", "edge_background_off"]),
    Preset("privacidade", "Privacidade",
           "Telemetria no mínimo, sem anúncios, sem histórico na nuvem.",
           lambda: _ids(lambda t: t.cat in ("privacidade", "ia") and t.level in (ESSENTIAL, RECOMMENDED)
                        and t.reversible)),
    Preset("sem_ia", "Sem IA",
           "Copilot, Recall, Clique para Fazer e a IA do Paint, Bloco de Notas, Edge e pesquisa desligados.",
           lambda: _ids(lambda t: t.cat == "ia" and t.level != ADVANCED)),
]
PRESETS_BY_ID = {p.id: p for p in PRESETS}

BASIC_PACK = Preset(
    "basico", "Pacote Básico",
    "Windows leve sem telemetria nem IA, mouse e teclado sem atraso, plano de energia próprio e prioridade para jogos.",
    lambda: _ids(lambda t: t.level == ESSENTIAL and t.reversible and t.recommended_here()))


# ------------------------------------------------------------------ perfis do usuário
def _pfile() -> Path:
    return data_dir() / "perfis.json"


def user_profiles() -> list[dict]:
    try:
        return json.loads(_pfile().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_profiles(items: list[dict]) -> None:
    _pfile().write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def upsert_profile(name: str, ids: list[str]) -> None:
    items = [p for p in user_profiles() if p["name"] != name]
    items.append({"name": name, "ids": [i for i in ids if i in CATALOG]})
    save_profiles(items)


def delete_profile(name: str) -> None:
    save_profiles([p for p in user_profiles() if p["name"] != name])


def export_profile(name: str, ids: list[str], path: str) -> None:
    Path(path).write_text(json.dumps({"lolitos_profile": 1, "name": name, "ids": ids},
                                     ensure_ascii=False, indent=1), encoding="utf-8")


def import_profile(path: str) -> tuple[str, int, int]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(d, dict) or d.get("lolitos_profile") != 1:
        raise ValueError("Este arquivo não é um perfil do Chinese Control.")
    ids = [i for i in d.get("ids", []) if isinstance(i, str)]
    known = [i for i in ids if i in CATALOG]
    upsert_profile(str(d.get("name") or "Perfil importado")[:60], known)
    return d.get("name", "Perfil importado"), len(known), len(ids) - len(known)
