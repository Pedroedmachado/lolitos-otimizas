"""Ajustes do Windows para o executável de QUALQUER jogo, criados sob demanda e registrados no catálogo
(assim entram no histórico e no Desfazer como os outros)."""
from __future__ import annotations

from pathlib import Path

from lolitos.core import history
from lolitos.core import registry as reg
from lolitos.core.actions import Action, ActionError, Reg
from lolitos.core.system import powershell
from lolitos.core.tweaks import ADVANCED, CATALOG, ESSENTIAL, Tweak, register

IFEO = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
GPU_PREF = r"Software\Microsoft\DirectX\UserGpuPreferences"
LAYERS = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
FSO_FLAG = "DISABLEDXMAXIMIZEDWINDOWEDMODE"


class LayerFlag(Action):
    """Adiciona uma flag de compatibilidade ao exe SEM apagar as que já existem (ex.: RUNASADMIN)."""

    def __init__(self, exe_path: str, flag: str):
        self.path, self.flag = exe_path, flag

    def describe(self):
        return f"compatibilidade de {Path(self.path).name}: {self.flag}"

    def _cur(self) -> str | None:
        r = reg.read("HKCU", LAYERS, self.path)
        return None if r is None else str(r[1])

    def applicable(self):
        return Path(self.path).exists()

    def is_applied(self):
        return self.flag in (self._cur() or "").split()

    def capture(self):
        return {"value": self._cur()}

    def apply(self):
        parts = [p for p in (self._cur() or "").split() if p and p != "~"]
        if self.flag not in parts:
            parts.append(self.flag)
        reg.write("HKCU", LAYERS, self.path, "sz", "~ " + " ".join(parts))

    def revert(self, snap):
        if snap.get("value") is None:
            reg.delete_value("HKCU", LAYERS, self.path)
        else:
            reg.write("HKCU", LAYERS, self.path, "sz", snap["value"])


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


class DefenderFolder(Action):
    def __init__(self, folder: str):
        self.folder = folder

    def describe(self):
        return f"exclusão do Defender: {self.folder}"

    def applicable(self):
        return Path(self.folder).exists()

    def is_applied(self):
        r = powershell("(Get-MpPreference).ExclusionPath -join '|'", timeout=60)
        if not r.ok:
            return None
        return self.folder.lower().rstrip("\\") in [x.lower().rstrip("\\") for x in r.out.strip().split("|")]

    def apply(self):
        r = powershell(f"Add-MpPreference -ExclusionPath {_q(self.folder)}", timeout=60)
        if not r.ok:
            raise ActionError((r.err or r.out).strip()[:300] or "o Defender recusou")

    def revert(self, snap):
        powershell(f"Remove-MpPreference -ExclusionPath {_q(self.folder)}", timeout=60)


# ------------------------------------------------------------------ fábrica
def _prio(exe: str, game: str) -> Tweak:
    return Tweak(f"g_prio:{exe.lower()}", "Prioridade alta sempre",
                 f"O Windows abre o {exe} com prioridade de CPU alta (IFEO › PerfOptions) — vale mesmo com o app "
                 "fechado e funciona com anti-cheat que bloqueia mudar a prioridade depois.",
                 "jogo", [Reg("HKLM", IFEO + f"\\{exe}\\PerfOptions", "CpuPriorityClass", 3)], ESSENTIAL,
                 gain="O jogo ganha a frente de navegador, Discord e afins quando a CPU aperta.")


def _gpu(path: str, game: str) -> Tweak:
    return Tweak(f"g_gpu:{path.lower()}", "Placa de vídeo de alto desempenho",
                 "Define nas Configurações de gráficos do Windows que este jogo usa a GPU dedicada.",
                 "jogo", [Reg("HKCU", GPU_PREF, path, "GpuPreference=2;", "sz")], ESSENTIAL, admin=False,
                 gain="Garante a GPU dedicada (crítico em notebook e PCs com vídeo integrado).")


def _fso(path: str, game: str) -> Tweak:
    return Tweak(f"g_fso:{path.lower()}", "Tela cheia sem 'otimizações de tela cheia'",
                 "Marca o executável para usar tela cheia exclusiva de verdade (mantém outras flags que já existam).",
                 "jogo", [LayerFlag(path, FSO_FLAG)], ADVANCED, admin=False,
                 gain="Menos input lag em jogos que rodam em Tela cheia.",
                 loss="Em janela/sem bordas não muda nada. Em tela cheia, overlays (Discord, Game Bar, o deste app) "
                      "não aparecem por cima.")


def _def(folder: str, game: str) -> Tweak:
    return Tweak(f"g_def:{folder.lower()}", "Excluir a pasta do jogo do Microsoft Defender",
                 f"O Defender para de escanear em tempo real os arquivos em {folder}.",
                 "jogo", [DefenderFolder(folder)], ADVANCED,
                 gain="Atualizações mais rápidas e menos travadas ao carregar mapas/regiões.",
                 loss="Arquivos nessa pasta deixam de ser verificados. O resto do PC continua protegido.")


def _get_or_register(t: Tweak) -> Tweak:
    if t.id in CATALOG:
        return CATALOG[t.id]
    register(t)
    return t


def tweaks_for(game_name: str, exe_name: str | None, exe_path: str | None, folder: str | None) -> list[Tweak]:
    out = []
    if exe_name:
        out.append(_get_or_register(_prio(exe_name, game_name)))
    if exe_path:
        out.append(_get_or_register(_gpu(exe_path, game_name)))
        out.append(_get_or_register(_fso(exe_path, game_name)))
    if folder and Path(folder).exists() and len(Path(folder).parts) > 2:   # nunca a raiz de um disco
        out.append(_get_or_register(_def(folder, game_name)))
    return out


def restore_from_history() -> None:
    """Recria no catálogo os ajustes por jogo que estão no histórico (para o Desfazer funcionar sempre)."""
    builders = {"g_prio": _prio, "g_gpu": _gpu, "g_fso": _fso, "g_def": _def}
    for e in history.load():
        tid = e.get("tweak_id", "")
        kind, _, arg = tid.partition(":")
        if kind in builders and arg and tid not in CATALOG:
            try:
                register(builders[kind](arg, ""))
            except ValueError:
                pass
