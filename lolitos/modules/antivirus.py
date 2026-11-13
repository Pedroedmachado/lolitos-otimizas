"""Antivírus: detectar e liberar este app (só ele) no Defender; instruções para os outros."""
from __future__ import annotations

import sys
from pathlib import Path

from lolitos.core.system import as_list, powershell, powershell_json

GUIDES = {
    "kaspersky": "Configurações › Ameaças e exclusões › Gerenciar exclusões › Adicionar a pasta do app.",
    "avast": "Menu › Configurações › Geral › Exceções › Adicionar exceção (pasta do app).",
    "avg": "Menu › Configurações › Geral › Exceções › Adicionar exceção (pasta do app).",
    "norton": "Configurações › Antivírus › Verificações e riscos › Itens a excluir (pasta do app).",
    "eset": "Configuração avançada › Mecanismo de detecção › Exclusões › Exclusões de desempenho.",
    "bitdefender": "Proteção › Antivírus › Configurações › Gerenciar exceções (Antivírus e Advanced Threat Defense).",
    "mcafee": "Minha proteção › Verificação em tempo real › Arquivos excluídos › Adicionar arquivo.",
    "malwarebytes": "Configurações › Lista de permissões › Adicionar › pasta do app.",
    "avira": "Segurança › Proteção em tempo real › Configurações › Exceções.",
}


def app_folder() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]


def installed_protected() -> bool:
    """Só faz sentido liberar no Defender quando instalado em Arquivos de Programas (só admin altera)."""
    p = str(app_folder()).lower()
    return "program files" in p or "arquivos de programas" in p


def products() -> list[dict]:
    rows = powershell_json("Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct |"
                           " Select-Object displayName,productState", timeout=60)
    out = []
    for r in as_list(rows):
        if not r:
            continue
        st = int(r.get("productState") or 0)
        out.append({"name": r.get("displayName", "?"), "realtime": (st >> 12) & 0xF == 1,
                    "updated": (st >> 4) & 0xF == 0})
    return out


def guide_for(name: str) -> str:
    low = name.lower()
    for k, v in GUIDES.items():
        if k in low:
            return v
    return "Procure por Exceções, Exclusões ou Aplicativos confiáveis e adicione a pasta do app."


def _q(p) -> str:
    return "'" + str(p).replace("'", "''") + "'"


def defender_has_app() -> bool | None:
    r = powershell("(Get-MpPreference).ExclusionPath -join '|'", timeout=60)
    if not r.ok:
        return None
    return str(app_folder()).lower() in r.out.lower()


def defender_add_app() -> tuple[bool, str]:
    if not installed_protected():
        return False, ("Só na versão instalada (em Arquivos de Programas). Numa pasta comum qualquer programa "
                       "poderia se esconder ali.")
    r = powershell(f"Add-MpPreference -ExclusionPath {_q(app_folder())}", timeout=60)
    return r.ok, (r.err or "").strip()


def defender_remove_app() -> tuple[bool, str]:
    r = powershell(f"Remove-MpPreference -ExclusionPath {_q(app_folder())}", timeout=60)
    return r.ok, (r.err or "").strip()
