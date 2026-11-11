"""Check-up do hardware (aba do Meu PC): confere memória, placa de vídeo, discos e BIOS com base no que o Windows
informa (SMBIOS, WMI, driver). Nada é alterado: mudanças de slot e de BIOS são feitas por você."""
from __future__ import annotations

import re
from dataclasses import dataclass

OK, WARN, BAD = "ok", "warn", "bad"


@dataclass
class Item:
    level: str        # ok | warn | bad
    title: str
    detail: str
    area: str         # Memória | Placa de vídeo | Armazenamento | Processador


def _slot_pos(loc: str) -> str:
    """'DIMM_A2' / 'Controller0-ChannelA-DIMM1' / 'A2' → 'A2' (ou '')."""
    t = (loc or "").upper()
    m = re.search(r"(?:DIMM|CHANNEL)?[_\s-]*([A-D])[_\s-]*([12])\b", t)
    if m:
        return m.group(1) + m.group(2)
    m = re.search(r"CHANNEL\s*([A-D]).*DIMM\s*([01])", t)
    if m:
        return m.group(1) + str(int(m.group(2)) + 1)
    return ""


def memory(rs: dict) -> list[Item]:
    if not rs:
        return []
    out = []
    n, slots = rs["count"], rs.get("slots") or 0
    if rs.get("dual") is True:
        ch = ", ".join(rs.get("channels") or [])
        out.append(Item(OK, "Dual channel ativado",
                        f"{n} pentes em canais diferentes ({ch}): a largura de banda da memória está dobrada.",
                        "Memória"))
    elif n == 1:
        out.append(Item(WARN, "Só um pente de memória (single channel)",
                        "Com dois pentes iguais, a memória trabalha em dual channel e o FPS mínimo sobe bastante.",
                        "Memória"))
    elif rs.get("dual") is False:
        out.append(Item(BAD, "Pentes no mesmo canal",
                        "Os pentes estão num canal só. Coloque-os nos slots A2 e B2 (veja o manual da placa).",
                        "Memória"))
    if slots >= 4 and n == 2:
        pos = sorted(p for p in (_slot_pos(s.get("DeviceLocator", "") + " " + s.get("BankLabel", ""))
                                 for s in rs["sticks"]) if p)
        if pos == ["A2", "B2"]:
            out.append(Item(OK, "Pentes nos slots certos (A2 e B2)",
                            "Em placas com 4 slots, 2 pentes devem ficar no 2º e no 4º slot a partir do "
                            "processador (A2 e B2). É o que o Windows informa para este PC.", "Memória"))
        elif len(pos) == 2:
            out.append(Item(WARN, f"Pentes em {pos[0]} e {pos[1]}",
                            "Em placas com 4 slots, o recomendado para 2 pentes é A2 e B2 (2º e 4º slot a partir "
                            "do processador): a memória fica mais estável em frequências altas.", "Memória"))
    if n > 1:
        if rs.get("same_model"):
            out.append(Item(OK, "Pentes iguais", "Mesmo modelo e mesmo tamanho: ideal para dual channel e para o "
                                                 "perfil XMP/EXPO.", "Memória"))
        else:
            out.append(Item(WARN, "Pentes diferentes",
                            "Modelos ou tamanhos diferentes podem obrigar a memória a rodar mais devagar ou sem "
                            "XMP/EXPO.", "Memória"))
    xmp = "XMP" if "intel" in str(rs.get("cpu_vendor", "")).lower() else "EXPO" if rs.get("kind") == "DDR5" else "XMP/EXPO"
    if rs.get("xmp_off"):
        out.append(Item(BAD, f"Memória abaixo da velocidade ({rs['running']} de {rs['rated']} MT/s)",
                        f"O perfil {xmp} está desligado na BIOS. Ligar dá FPS de graça, principalmente em Ryzen.",
                        "Memória"))
    elif rs.get("running"):
        out.append(Item(OK, f"Memória na frequência máxima ({rs['running']} MT/s)" +
                        (f" · {xmp} ativado" if rs.get("xmp_on") or rs["running"] >= max(3200, rs["rated"]) else ""),
                        "Os pentes rodam na velocidade nominal deles.", "Memória"))
    gb = round(rs.get("total_gb", 0))
    if gb >= 32:
        out.append(Item(OK, f"{gb} GB de RAM", "Quantidade suficiente para jogos atuais.", "Memória"))
    elif gb >= 16:
        out.append(Item(OK, f"{gb} GB de RAM", "Bom para jogar. Com Discord, navegador e jogo pesado abertos, "
                                               "32 GB ajudam.", "Memória"))
    elif gb:
        out.append(Item(WARN, f"{gb} GB de RAM", "Pouco para jogos atuais: 16 GB é o mínimo confortável.", "Memória"))
    return out


def gpus(names: list[str], nv: dict | None) -> list[Item]:
    out = []
    for name in names:
        if nv and nv.get("pcie_width") and nv.get("pcie_width_max") and nv.get("name") and nv["name"] in name:
            w, wm = nv["pcie_width"], nv["pcie_width_max"]
            g = nv.get("pcie_gen_max") or nv.get("pcie_gen")
            if w >= wm:
                out.append(Item(OK, f"{name}: PCIe {g}.0 x{w}", "A placa usa todas as linhas PCIe que suporta.",
                                "Placa de vídeo"))
            else:
                out.append(Item(WARN, f"{name}: PCIe x{w} de x{wm}",
                                "A placa está usando menos linhas do que suporta: confira se está no 1º slot x16 e "
                                "se um SSD M.2 divide as linhas com ela.", "Placa de vídeo"))
    return out


def disks(items: list[dict]) -> list[Item]:
    out = []
    for x in items:
        name = (x.get("FriendlyName") or "Disco").strip()
        health = str(x.get("HealthStatus") or "")
        wear = x.get("Wear")
        if health and health.lower() not in ("healthy", "0", "saudável"):
            out.append(Item(BAD, f"{name}: {health}", "O Windows indica problema neste disco. Faça backup.",
                            "Armazenamento"))
        elif wear not in (None, "") and int(wear) >= 80:
            out.append(Item(WARN, f"{name}: {wear}% de desgaste", "O SSD está perto do fim da vida útil "
                                                                   "informada pelo fabricante.", "Armazenamento"))
        else:
            kind = " ".join(str(v) for v in (x.get("MediaType"), x.get("BusType")) if v and str(v) != "Unspecified")
            out.append(Item(OK, f"{name}: saudável", kind or "Sem alertas do Windows.", "Armazenamento"))
    return out


def virtualization(cpu: dict) -> list[Item]:
    v = cpu.get("VirtualizationFirmwareEnabled")
    if v is None:
        return []
    if v:
        return [Item(OK, "Virtualização ativada na BIOS", "Pronto para WSL, máquinas virtuais e anti-cheats que a "
                                                          "exigem.", "Processador")]
    return [Item(WARN, "Virtualização desligada na BIOS", "Alguns anti-cheats (Valorant, FACEIT) e o WSL pedem "
                                                          "SVM/VT-x ligado na BIOS.", "Processador")]


def run(d: dict, rs: dict, nv: dict | None) -> list[Item]:
    cpu = (d.get("cpu") or [{}])[0]
    rs = dict(rs or {})
    if rs:
        rs["cpu_vendor"] = cpu.get("Manufacturer", "")
    return [*memory(rs), *gpus([g.get("Name", "") for g in d.get("gpu", [])], nv), *disks(d.get("disks", [])),
            *virtualization(cpu)]
