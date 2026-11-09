"""Ajustes do Windows específicos para o executável do Black Desert."""
from __future__ import annotations

from lolitos.bdo import game
from lolitos.core.actions import Action, ActionError, Reg
from lolitos.core.system import IS_WIN
from lolitos.core.tweaks import ADVANCED, ESSENTIAL, RECOMMENDED, Tweak, register
from lolitos.modules import pcprofile as pc

IFEO = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"


class ExeReg(Reg):
    """Valor de registro cujo NOME é o caminho completo do BlackDesert64.exe."""

    def __init__(self, hive, path, value, kind="sz"):
        super().__init__(hive, path, "", value, kind)

    @property
    def name(self):  # type: ignore[override]
        p = game.exe_path()
        return str(p) if p else ""

    @name.setter
    def name(self, _):
        pass

    def applicable(self):
        return bool(self.name) or not IS_WIN


def _defender_has_exclusion() -> bool | None:
    d = game.install_dir()
    if not d:
        return None
    from lolitos.core.system import powershell
    r = powershell("(Get-MpPreference).ExclusionPath -join '|'", timeout=60)
    if not r.ok:
        return None
    return str(d).lower() in r.out.lower()


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


class DefenderExclusion(Action):
    def describe(self):
        return f"exclusão do Defender: {game.install_dir()}"

    def applicable(self):
        return game.install_dir() is not None

    def is_applied(self):
        return _defender_has_exclusion()

    def apply(self):
        from lolitos.core.system import powershell
        r = powershell(f"Add-MpPreference -ExclusionPath {_ps_quote(str(game.install_dir()))}", timeout=60)
        if not r.ok:
            raise ActionError((r.err or r.out).strip()[:300] or "o Defender recusou")

    def capture(self):
        return {"path": str(game.install_dir())}

    def revert(self, snap):
        from lolitos.core.system import powershell
        powershell(f"Remove-MpPreference -ExclusionPath {_ps_quote(snap.get('path', ''))}", timeout=60)


class NvidiaProfile(Action):
    """Grava o perfil do BDO no driver NVIDIA (Painel de Controle NVIDIA › Configurações de programa)."""

    def describe(self):
        from lolitos.modules import nvprofile
        return f"perfil NVIDIA '{nvprofile.bdo_profile().name}'"

    def applicable(self):
        from lolitos.modules import nvprofile
        try:
            if not pc.nvidia():
                return False
        except Exception:  # noqa: BLE001
            pass
        return nvprofile.available()

    def is_applied(self):
        from lolitos.modules import nvprofile
        with nvprofile.Drs() as d:
            return nvprofile.read_state(d, nvprofile.bdo_profile()) == "on"

    def capture(self):
        from lolitos.modules import nvprofile
        try:
            with nvprofile.Drs() as d:
                return nvprofile.capture(d, nvprofile.bdo_profile())
        except nvprofile.NvError as e:
            raise ActionError(str(e)) from e

    def apply(self):
        from lolitos.modules import nvprofile
        try:
            with nvprofile.Drs() as d:
                nvprofile.apply(d, nvprofile.bdo_profile())
        except nvprofile.NvError as e:
            raise ActionError(str(e)) from e

    def revert(self, snap):
        from lolitos.modules import nvprofile
        try:
            with nvprofile.Drs() as d:
                nvprofile.revert(d, snap)
        except nvprofile.NvError as e:
            raise ActionError(str(e)) from e


register(
    Tweak("bdo_nvidia_profile", "Perfil do BDO no Painel de Controle NVIDIA",
          "Grava no driver as configurações 3D do Black Desert (BlackDesert64.exe, 32 bits e launcher): taxa de "
          "atualização mais alta, otimização encadeada ligada, Ansel desligado, correção de gama sempre ligada e "
          "G-SYNC desligado no jogo. Usa a interface oficial do driver; nada é injetado no jogo.",
          "bdo", [NvidiaProfile()],
          RECOMMENDED, when=pc.nvidia, admin=True,
          gain="O driver já abre o BDO com essas opções, sem precisar mexer no Painel NVIDIA. Dá para trocar "
               "pelo seu próprio arquivo .nip na tela do Black Desert.",
          loss="Desliga o G-SYNC só no BDO (o resto do PC continua igual). Se você usa monitor G-SYNC e prefere "
               "ele ligado no jogo, importe um .nip seu ou deixe este ajuste desligado."),
    Tweak("bdo_priority", "BDO sempre em prioridade alta",
          "Registra no Windows (IFEO › PerfOptions) que o BlackDesert64.exe abre com prioridade de CPU alta — vale mesmo com este app fechado. Não injeta nada no jogo.",
          "bdo", [Reg("HKLM", IFEO + r"\BlackDesert64.exe\PerfOptions", "CpuPriorityClass", 3)],
          ESSENTIAL, gain="O jogo ganha a frente do Discord, navegador e afins quando a CPU aperta. "
                          "Usa 'Alta', nunca 'Tempo real' (que pode travar o PC)."),
    Tweak("bdo_gpu_high", "BDO na placa de vídeo de alto desempenho",
          "Define nas Configurações de gráficos do Windows que o BDO usa a GPU dedicada.",
          "bdo", [ExeReg("HKCU", r"Software\Microsoft\DirectX\UserGpuPreferences", "GpuPreference=2;")],
          ESSENTIAL, gain="Garante a RTX/Radeon dedicada (crítico em notebook e PCs com vídeo integrado).",
          admin=False),
    Tweak("bdo_fso_off", "BDO sem 'otimizações de tela cheia'",
          "Marca o BlackDesert64.exe para usar tela cheia exclusiva de verdade.",
          "bdo", [ExeReg("HKCU", r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
                         "~ DISABLEDXMAXIMIZEDWINDOWEDMODE")],
          ADVANCED, admin=False,
          gain="Menos input lag SE você joga em Tela cheia no BDO.",
          loss="Em janela/sem bordas não muda nada. Em tela cheia, overlays não aparecem por cima."),
    Tweak("bdo_defender", "Excluir a pasta do BDO do Microsoft Defender",
          "O Defender para de escanear os arquivos do jogo em tempo real (patches e carregamento de áreas).",
          "bdo", [DefenderExclusion()],
          ADVANCED, gain="Patch mais rápido e menos travadas ao carregar regiões/Siege.",
          loss="Arquivos nessa pasta deixam de ser verificados. O resto do PC continua protegido."),
)

# Checklist do que não dá (ou não deve) ser mudado por arquivo
INGAME_TIPS = [
    ("Painel NVIDIA › Gerenciar configurações 3D › Programa: BlackDesert64.exe",
     "Modo de baixa latência: Ativado (ou Ultra se a GPU estiver em 99%) · Gerenciamento de energia: "
     "Preferir desempenho máximo · Sincronização vertical: Desligada (se usar G-Sync, ligue V-Sync no painel "
     "e limite o FPS 3 abaixo do Hz)."),
    ("Limite de FPS",
     "No BDO: Configurações › Exibição › Limite de FPS = Hz do monitor − 3 (ex.: 141 em 144 Hz). "
     "Frametime estável vale mais do que FPS de pico na Siege."),
    ("Modo de otimização (Configurações › Exibição › Qualidade)",
     "Use 'Otimização' ou 'Muito baixo' nas Guerras. Depois ligue de volta só o que você sente falta."),
    ("Shift+F5 e esconder jogadores",
     "Shift+F5 alterna a exibição de outros jogadores — salva o FPS em cidade lotada (Velia/Heidel)."),
    ("Rede no roteador",
     "Prefira cabo. Se o ping sobe quando alguém usa a internet (bufferbloat), ative QoS/SQM no roteador."),
    ("Antes da Guerra",
     "Use 'Preparar e jogar' (libera RAM, plano de energia, prioridade) e feche navegador com vídeo."),
]
