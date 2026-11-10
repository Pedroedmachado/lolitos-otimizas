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


def boost_ids() -> list[str]:
    """O que o 'Boost agora' aplica: essencial + recomendado para este PC (sem remover apps)."""
    return _ids(lambda t: t.level in (ESSENTIAL, RECOMMENDED) and t.cat != "debloat"
                and t.recommended_here() and t.reversible)


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
