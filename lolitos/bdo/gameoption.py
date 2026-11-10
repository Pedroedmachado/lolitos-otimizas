"""Leitura/escrita segura do GameOption.txt do Black Desert, com backups e predefinições.

Regras:
- só altera chaves que JÁ existem no arquivo (nunca inventa chave);
- preserva a ordem e as linhas não tocadas byte a byte;
- mantém o formato numérico (casas decimais) de cada valor;
- sempre faz backup antes de gravar; recusa gravar com o jogo aberto
  (o BDO regrava o arquivo ao fechar)."""
from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from lolitos.core.system import backups_dir, process_running

GAME_PROCS = ("BlackDesert64.exe", "BlackDesertLauncher.exe")
_LINE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*?)(\s*)$")


def default_path() -> Path:
    return Path.home() / "Documents" / "Black Desert" / "GameOption.txt"


def find_gameoption() -> Path | None:
    cands = [default_path()]
    try:  # Documentos redirecionados (OneDrive)
        import os
        od = os.environ.get("OneDrive")
        if od:
            cands += [Path(od) / "Documents" / "Black Desert" / "GameOption.txt",
                      Path(od) / "Documentos" / "Black Desert" / "GameOption.txt"]
    except Exception:
        pass
    return next((p for p in cands if p.exists()), None)


# --------------------------------------------------------------------- chaves conhecidas
# label, tipo ('bool' | 'float' | 'int' | 'raw'), dica
KNOWN: dict[str, tuple[str, str, str]] = {
    "windowed": ("Modo de tela", "raw", "Número usado pelo jogo (janela/sem bordas/tela cheia)."),
    "graphicOption": ("Predefinição gráfica", "raw", "Posição no menu de qualidade do jogo."),
    "dof": ("Profundidade de campo", "bool", "Desfoque de fundo. Desligado = imagem mais limpa e mais FPS."),
    "antiAliasing": ("Anti-aliasing", "bool", ""),
    "SSAO": ("Oclusão de ambiente (SSAO)", "bool", "Sombra de contato. Custa bastante GPU em massa."),
    "Tessellation": ("Tesselação", "bool", "Relevo extra no chão/paredes."),
    "postFilter": ("Filtro de tela", "bool", ""),
    "characterEffect": ("Efeitos de personagem (alta qualidade)", "bool", ""),
    "lensBlood": ("Sangue na lente", "bool", "Atrapalha a visão no PvP."),
    "bloodEffect": ("Efeito de sangue", "bool", ""),
    "textureQuality": ("Qualidade de textura", "raw", "Valor do menu (não altere se não souber)."),
    "gamma": ("Gama", "float", ""),
    "contrast": ("Contraste", "float", ""),
    "fov": ("Campo de visão (FOV)", "float", ""),
    "selfEffectAlpha": ("Opacidade dos SEUS efeitos", "float", "0 a 1. Menos = enxerga melhor o alvo."),
    "effectAlpha": ("Opacidade dos efeitos dos outros", "float", "0 a 1. Menos = menos poluição em massa."),
    "skillPostEffect": ("Pós-efeito de habilidades", "float", "Brilho/flash de tela das skills."),
    "enableOVR": ("Modo VR", "bool", ""),
    "cameraEffectMaster": ("Efeitos de câmera (geral)", "float", ""),
    "cameraShakePower": ("Tremor de câmera", "float", "0 = câmera estável no meio da luta."),
    "cameraFovPower": ("Zoom automático da câmera", "float", ""),
    "cameraTranslatePower": ("Deslocamento automático da câmera", "float", ""),
    "motionBlurPower": ("Desfoque de movimento", "float", "0 = sem borrão ao girar a câmera."),
    "upscaleEnable": ("Upscale (resolução reduzida)", "bool", ""),
    "UpscaleFSREnable": ("AMD FSR", "bool", "Mais FPS com pouca perda de nitidez."),
    "sleepModeEnable": ("Modo de economia (AFK)", "bool", "Reduz o uso de GPU parado. Ótimo para lifeskill/AFK."),
    "cropModeEnable": ("Modo de recorte (cinema)", "bool", ""),
    "useNearestEffectOnly": ("Remover efeitos distantes", "bool", "Grande ganho em Guerra de Nodes."),
    "useSelfPlayerOnlyLantern": ("Remover lanternas dos outros", "bool", ""),
    "useSelfPlayerEffectOnly": ("Remover efeitos dos outros jogadores", "bool", "Maior ganho de FPS em massa."),
    "useNearestInSeizeEffectOnly": ("Só efeitos próximos em Guerra/Cerco", "bool",
                                    "Específico de Node War e Siege."),
    "useOptimizationEffectFrame": ("Otimização de quadros de efeitos", "bool", ""),
    "effectFrameEffectOptimization": ("Intensidade da otimização de efeitos", "float", ""),
    "useFarPlayerOptimization": ("Otimizar jogadores distantes", "bool",
                                 "Atualiza menos os jogadores longe de você."),
    "farPlayerOptimizationLimitDist": ("Distância da otimização de jogadores", "float", ""),
    "useCharacterDistUpdate": ("Atualização de personagens por distância", "bool", ""),
    "HideOtherPlayerTent": ("Esconder tendas dos outros", "bool", ""),
    "isUseDefaultCostumeOtherPlayer": ("Outros jogadores com roupa padrão", "bool",
                                       "Corta muito o custo de renderizar 100 pessoas na Siege."),
    "UseSpawnableNPC": ("NPCs invocáveis visíveis", "bool", ""),
    "enableMusic": ("Música", "bool", ""),
    "enableEnvSound": ("Som ambiente", "bool", ""),
    "otherPlayerVolume": ("Volume dos outros jogadores", "float", ""),
    "RenderOutLine": ("Contorno de personagens", "bool", ""),
    "Sharpness": ("Nitidez", "raw", ""),
    "uiScale": ("Escala da interface", "float", ""),
}

# --------------------------------------------------------------------- predefinições
_CLEAN = {"dof": 0, "lensBlood": 0, "bloodEffect": 0, "motionBlurPower": 0.0, "cameraShakePower": 0.0,
          "cameraEffectMaster": 0.0, "cameraFovPower": 0.0, "cameraTranslatePower": 0.0, "enableOVR": 0}
_MASS = {"useNearestEffectOnly": 1, "useSelfPlayerOnlyLantern": 1, "useSelfPlayerEffectOnly": 1,
         "useNearestInSeizeEffectOnly": 1, "useOptimizationEffectFrame": 1, "useCharacterDistUpdate": 1,
         "HideOtherPlayerTent": 1, "isUseDefaultCostumeOtherPlayer": 1, "UseSpawnableNPC": 0}


@dataclass
class Preset:
    id: str
    name: str
    desc: str
    values: dict


PRESETS = [
    Preset("guerra", "Guerra de Nodes / Cerco — FPS máximo",
           "Corta efeitos dos outros, lanternas, tendas, roupas e tudo que pesa com 100+ jogadores na tela; "
           "transparência de efeitos no mínimo (30%). "
           "Mantém a sua resolução, a sua escala de UI e os seus sons.",
           {**_CLEAN, **_MASS, "SSAO": 0, "Tessellation": 0, "postFilter": 0, "characterEffect": 0,
            "skillPostEffect": 0.0, "effectAlpha": 0.30, "useFarPlayerOptimization": 1, "sleepModeEnable": 0}),
    Preset("pvp", "PvP pequeno / Arena — limpo e responsivo",
           "Tela limpa para ler animação e grab: sem tremor, sem borrão, sem sangue, efeitos dos outros "
           "fora. Jogadores distantes continuam atualizando normalmente.",
           {**_CLEAN, **_MASS, "useFarPlayerOptimization": 0, "SSAO": 0, "sleepModeEnable": 0}),
    Preset("grind", "Grind — equilibrado",
           "Remove poluição visual e efeitos distantes, mas mantém a qualidade do mundo.",
           {**_CLEAN, "useNearestEffectOnly": 1, "useSelfPlayerOnlyLantern": 1, "useSelfPlayerEffectOnly": 1,
            "sleepModeEnable": 0}),
    Preset("afk", "AFK / Lifeskill — PC frio e silencioso",
           "Liga o modo de economia do jogo e desliga música/ambiente. Ideal para deixar pescando ou processando.",
           {**_CLEAN, **_MASS, "sleepModeEnable": 1, "enableMusic": 0, "enableEnvSound": 0,
            "useFarPlayerOptimization": 1}),
]


# --------------------------------------------------------------------- arquivo
class GameOptionFile:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lines: list[str] = []
        self.index: dict[str, int] = {}
        self.reload()

    def reload(self):
        raw = self.path.read_bytes()
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig", errors="replace")
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.lines = text.splitlines()
        self.index = {}
        for i, line in enumerate(self.lines):
            m = _LINE.match(line)
            if m:
                self.index.setdefault(m.group(2), i)

    def keys(self) -> list[str]:
        return list(self.index)

    def get(self, key: str) -> str | None:
        i = self.index.get(key)
        if i is None:
            return None
        return _LINE.match(self.lines[i]).group(4)

    @staticmethod
    def _format(old: str, new) -> str:
        if isinstance(new, bool):
            new = int(new)
        if isinstance(new, (int, float)):
            m = re.fullmatch(r"\s*-?\d+\.(\d+)\s*", old or "")
            if m:
                return f"{float(new):.{len(m.group(1))}f}"
            if isinstance(new, float) and not float(new).is_integer():
                return f"{new:.2f}"
            return str(int(new))
        return str(new)

    def set(self, key: str, value) -> bool:
        """Altera uma chave existente. Retorna True se mudou algo."""
        i = self.index.get(key)
        if i is None:
            return False
        m = _LINE.match(self.lines[i])
        old = m.group(4)
        new = self._format(old, value)
        if new == old.strip():
            return False
        self.lines[i] = f"{m.group(1)}{key}{m.group(3)}{new}"
        return True

    def diff(self, values: dict) -> list[tuple[str, str, str]]:
        out = []
        for k, v in values.items():
            old = self.get(k)
            if old is None:
                continue
            new = self._format(old, v)
            if new != old.strip():
                out.append((k, old.strip(), new))
        return out

    def save(self, reason: str = "") -> Path:
        if process_running(*GAME_PROCS):
            raise RuntimeError("Feche o Black Desert antes: ele regrava o GameOption.txt ao sair.")
        bk = backup(self.path, reason)
        data = self.newline.join(self.lines) + self.newline
        self.path.write_bytes((b"\xef\xbb\xbf" if self.bom else b"") + data.encode("utf-8"))
        return bk


def _bdir() -> Path:
    p = backups_dir() / "bdo"
    p.mkdir(parents=True, exist_ok=True)
    return p


def backup(path: Path, reason: str = "") -> Path:
    tag = re.sub(r"[^a-z0-9]+", "-", reason.lower()).strip("-")[:30]
    dst = _bdir() / f"GameOption-{time.strftime('%Y%m%d-%H%M%S')}{'-' + tag if tag else ''}.txt"
    shutil.copy2(path, dst)
    # guarda a primeira cópia para sempre ("original")
    orig = _bdir() / "GameOption-ORIGINAL.txt"
    if not orig.exists():
        shutil.copy2(path, orig)
    return dst


def list_backups() -> list[Path]:
    return sorted(_bdir().glob("GameOption-*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)


def restore_backup(bk: Path, target: Path) -> None:
    if process_running(*GAME_PROCS):
        raise RuntimeError("Feche o Black Desert antes de restaurar.")
    backup(target, "antes-de-restaurar")
    shutil.copy2(bk, target)


def apply_preset(gof: GameOptionFile, preset: Preset) -> tuple[list, Path | None]:
    changes = gof.diff(preset.values)
    if not changes:
        return [], None
    for k, _, new in changes:
        gof.set(k, new)
    bk = gof.save(preset.id)
    return changes, bk
