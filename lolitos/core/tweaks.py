"""Modelo de ajuste (tweak) e registro global do catálogo."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from lolitos.core.actions import Action

# Níveis
ESSENTIAL = "essencial"      # seguro em qualquer PC
RECOMMENDED = "recomendado"  # leve, com uma contrapartida pequena (mostrada)
ADVANCED = "avancado"        # contrapartida visível; pede confirmação

# Categorias (abas)
CATS = {
    "desempenho": "Desempenho",
    "jogos": "Jogos",
    "entrada": "Mouse e teclado",
    "gpu": "Placa de vídeo e monitor",
    "rede": "Rede",
    "privacidade": "Privacidade",
    "interface": "Interface",
    "ia": "Sem IA",
    "atualizacoes": "Atualizações",
    "seguranca": "Segurança",
    "apps": "Apps e navegadores",
    "debloat": "Debloat",
    "bdo": "Black Desert",
    "jogo": "Por jogo",
}


@dataclass
class Tweak:
    id: str
    title: str
    desc: str
    cat: str
    actions: list[Action]
    level: str = RECOMMENDED
    gain: str = ""            # o que melhora
    loss: str = ""            # o que se perde (vazio = nada relevante)
    restart: bool = False     # vale após reiniciar
    explorer: bool = False    # precisa reiniciar o Explorer
    admin: bool = True
    exclusive: str = ""       # grupo de ajustes mutuamente exclusivos
    when: Callable[[], bool] | None = None   # recomendado só se True (ex.: PC sem bateria)
    tags: tuple[str, ...] = field(default_factory=tuple)
    live: Callable[[], None] | None = None   # chamado depois de aplicar/desfazer, para valer sem novo login

    # ---------------------------------------------------------------- estado
    def applicable(self) -> bool:
        try:
            return any(a.applicable() for a in self.actions)
        except Exception:
            return False

    def status(self) -> str:
        """'on', 'off', 'partial', 'na' (não se aplica) ou 'unknown'."""
        try:
            acts = [a for a in self.actions if a.applicable()]
        except Exception:
            return "unknown"
        if not acts:
            return "na"
        states = []
        for a in acts:
            try:
                states.append(a.is_applied())
            except Exception:
                states.append(None)
        known = [s for s in states if s is not None]
        if not known:
            return "unknown"
        if all(known) and len(known) == len(states):
            return "on"
        if any(known):
            return "partial"
        return "off"

    @property
    def reversible(self) -> bool:
        return all(a.reversible for a in self.actions)

    def recommended_here(self) -> bool:
        if self.level == ADVANCED:
            return False
        return self.when() if self.when else True


CATALOG: dict[str, Tweak] = {}


def register(*tweaks: Tweak) -> None:
    for t in tweaks:
        if t.id in CATALOG:
            raise ValueError(f"id duplicado no catálogo: {t.id}")
        CATALOG[t.id] = t


def by_cat(cat: str) -> list[Tweak]:
    return [t for t in CATALOG.values() if t.cat == cat]


def get(tid: str) -> Tweak | None:
    return CATALOG.get(tid)
