"""Jogos conhecidos: executável real, anti-cheat e observações. Ajuda a achar o processo certo
e a avisar o que cada anti-cheat aceita."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Known:
    name: str
    exes: list[str]
    anticheat: str = ""
    net: str = ""          # 'tcp' (dá para medir o servidor) ou 'udp'
    notes: list[str] = field(default_factory=list)
    match: list[str] = field(default_factory=list)   # trechos do nome/pasta para reconhecer


HVCI_NOTE = "Se o anti-cheat reclamar, desfaça 'Desligar a Integridade da Memória (HVCI)' em Ajustes › Desempenho."
PROTECTED = "O anti-cheat protege o processo: prioridade/afinidade em tempo real podem ser recusadas — use " \
            "'Prioridade alta sempre' (vale pelo Windows, sem tocar no jogo)."

KNOWN: list[Known] = [
    Known("Black Desert", ["BlackDesert64.exe"], "", "tcp",
          ["Tem módulo próprio no app (tela Black Desert): predefinições do GameOption.txt, servidor e travamentos."],
          ["black desert", "blackdesert"]),
    Known("VALORANT", ["VALORANT-Win64-Shipping.exe"], "Riot Vanguard", "udp",
          ["No Windows 11 o Vanguard exige TPM 2.0 e Secure Boot ligados.", HVCI_NOTE, PROTECTED],
          ["valorant"]),
    Known("League of Legends", ["League of Legends.exe"], "Riot Vanguard", "tcp",
          ["No Windows 11 o Vanguard exige TPM 2.0 e Secure Boot ligados.", HVCI_NOTE], ["league of legends"]),
    Known("Counter-Strike 2", ["cs2.exe"], "VAC", "udp",
          ["Para FACEIT: " + HVCI_NOTE], ["counter-strike 2", "counter-strike global offensive"]),
    Known("Dota 2", ["dota2.exe"], "VAC", "udp", [], ["dota 2"]),
    Known("Fortnite", ["FortniteClient-Win64-Shipping.exe"], "Easy Anti-Cheat / BattlEye", "udp", [PROTECTED],
          ["fortnite"]),
    Known("Apex Legends", ["r5apex.exe", "r5apex_dx12.exe"], "Easy Anti-Cheat", "udp", [PROTECTED], ["apex legends"]),
    Known("PUBG: BATTLEGROUNDS", ["TslGame.exe"], "BattlEye / Uncheater", "udp", [PROTECTED], ["pubg"]),
    Known("Call of Duty", ["cod.exe", "ModernWarfare.exe"], "RICOCHET", "udp", [PROTECTED, HVCI_NOTE],
          ["call of duty", "warzone"]),
    Known("Grand Theft Auto V", ["GTA5.exe", "GTA5_Enhanced.exe"], "BattlEye", "udp",
          ["Servidores de RP (FiveM) podem exigir a Integridade da Memória ligada: " + HVCI_NOTE],
          ["grand theft auto v", "gtav"]),
    Known("Battlefield 1", ["bf1.exe"], "", "udp", [], ["battlefield 1"]),
    Known("Battlefield 2042", ["BF2042.exe"], "EA Javelin", "udp", [PROTECTED], ["battlefield 2042"]),
    Known("Battlefield 6", ["bf6.exe"], "EA Javelin", "udp", [PROTECTED, "Exige Secure Boot ligado."],
          ["battlefield 6"]),
    Known("Rocket League", ["RocketLeague.exe"], "", "udp", [], ["rocket league"]),
    Known("Overwatch 2", ["Overwatch.exe"], "", "udp", [], ["overwatch"]),
    Known("Rainbow Six Siege", ["RainbowSix.exe", "RainbowSix_Vulkan.exe"], "BattlEye", "udp", [PROTECTED],
          ["rainbow six"]),
    Known("Lost Ark", ["LOSTARK.exe"], "Easy Anti-Cheat", "tcp", [PROTECTED], ["lost ark"]),
    Known("Throne and Liberty", ["TL.exe"], "Easy Anti-Cheat", "tcp", [PROTECTED], ["throne and liberty"]),
    Known("Albion Online", ["Albion-Online.exe"], "", "udp", [], ["albion"]),
    Known("Path of Exile 2", ["PathOfExile_x64Steam.exe", "PathOfExileSteam.exe", "PathOfExile.exe"], "", "tcp", [],
          ["path of exile"]),
    Known("World of Warcraft", ["Wow.exe", "WowClassic.exe"], "Warden", "tcp", [], ["world of warcraft"]),
    Known("Diablo IV", ["Diablo IV.exe"], "Warden", "tcp", [], ["diablo iv"]),
    Known("Marvel Rivals", ["Marvel-Win64-Shipping.exe"], "NetEase ACE", "udp", [PROTECTED], ["marvel rivals"]),
    Known("Deadlock", ["deadlock.exe"], "VAC", "udp", [], ["deadlock"]),
    Known("The Finals", ["Discovery.exe"], "Easy Anti-Cheat", "udp", [PROTECTED], ["the finals"]),
    Known("Crossfire", ["crossfire.exe"], "", "tcp", [], ["crossfire"]),
    Known("Tibia", ["client.exe"], "BattlEye", "tcp", [], ["tibia"]),
    Known("Roblox", ["RobloxPlayerBeta.exe"], "Hyperion", "udp", [PROTECTED], ["roblox"]),
    Known("Minecraft", ["javaw.exe", "Minecraft.Windows.exe"], "", "tcp", [], ["minecraft"]),
    Known("Genshin Impact", ["GenshinImpact.exe"], "mhyprot", "udp", [PROTECTED], ["genshin"]),
    Known("Elden Ring", ["eldenring.exe"], "Easy Anti-Cheat", "udp", [], ["elden ring"]),
    Known("Escape from Tarkov", ["EscapeFromTarkov.exe"], "BattlEye", "udp", [PROTECTED], ["tarkov"]),
]


def lookup(name: str = "", folder: str = "", exes: list[str] | None = None) -> Known | None:
    low_exes = {e.lower() for e in (exes or [])}
    text = f"{name} {folder}".lower()
    for k in KNOWN:
        if low_exes & {e.lower() for e in k.exes}:
            return k
    for k in KNOWN:
        if any(m in text for m in k.match):
            return k
    return None
