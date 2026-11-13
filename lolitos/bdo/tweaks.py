"""Ajustes do Windows específicos para o executável do Black Desert."""
from __future__ import annotations

from lolitos.bdo import game
from lolitos.core.actions import Action, ActionError, Cmd, Reg
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
        path = snap.get("path")
        if path and path != "None":
            powershell(f"Remove-MpPreference -ExclusionPath {_ps_quote(str(path))}", timeout=60)


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


class PostFilterOff(Action):
    """PostFilter = 0 em todos os gamevariable.xml (UserCache) — o 'Filtro de tela' não volta sozinho."""

    def describe(self):
        return "gamevariable.xml: PostFilter = 0"

    def applicable(self):
        from lolitos.bdo import usercache
        return bool(usercache.values()) or not IS_WIN

    def is_applied(self):
        from lolitos.bdo import usercache
        v = usercache.values()
        return all(x.strip() == "0" for x in v.values()) if v else None

    def capture(self):
        from lolitos.bdo import usercache
        return {"values": {str(k): x for k, x in usercache.values().items()}}

    def apply(self):
        from lolitos.bdo import usercache
        try:
            usercache.set_value("0")
        except RuntimeError as e:
            raise ActionError(str(e)) from e

    def revert(self, snap):
        from pathlib import Path
        from lolitos.bdo import usercache
        try:
            usercache.set_value({Path(k): v for k, v in (snap.get("values") or {}).items()})
        except RuntimeError as e:
            raise ActionError(str(e)) from e


_HPET_FIND = "Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'ACPI\\PNP0103*' }"


register(
    Tweak("bdo_postfilter_xml", "Filtro de tela desligado de verdade (UserCache)",
          "Coloca PostFilter = 0 nos gamevariable.xml da pasta UserCache (da conta e de cada personagem). Só essa "
          "linha muda; atalhos, barra de skills e chat ficam iguais, e há backup antes. Precisa do jogo fechado.",
          "bdo", [PostFilterOff()],
          RECOMMENDED, admin=False,
          gain="O 'Filtro de tela' para de voltar sozinho, mesmo depois de mexer no GameOption.txt.",
          loss="Se você ligar 'Filtro de tela' no jogo de novo, ele volta para 2: é só aplicar aqui outra vez."),
    Tweak("hpet_device_off", "Desativar o Timer de eventos de alta precisão (HPET)",
          "Desativa no Gerenciador de Dispositivos (Dispositivos de sistema) o 'Timer de eventos de alta precisão'. "
          "O Windows passa a usar só o relógio da CPU (TSC). Dá para ativar de novo aqui mesmo.",
          "bdo", [Cmd(_HPET_FIND + " | Disable-PnpDevice -Confirm:$false",
                      _HPET_FIND + " | Enable-PnpDevice -Confirm:$false", ps=True,
                      ps_check="$d = @(" + _HPET_FIND + "); if (-not $d -or -not ($d | Where-Object Status -eq 'OK')) "
                               "{ '1' } else { '0' }",
                      label="Gerenciador de Dispositivos: Timer de eventos de alta precisão")],
          ADVANCED, restart=True,
          gain="Em alguns PCs o frametime fica mais estável. Comum nos guias de FPS do BDO.",
          loss="O ganho varia de PC para PC e em muitos é zero. Se algo estranhar (som falhando, relógio), "
               "desfaça aqui."),
    Tweak("bdo_nvidia_profile", "Perfil do BDO no Painel de Controle NVIDIA",
          "Grava no driver as configurações 3D do Black Desert (BlackDesert64.exe, 32 bits e launcher): taxa de "
          "atualização mais alta, baixa latência Ultra com 1 quadro pré-renderizado, V-Sync e G-SYNC desligados, "
          "energia em desempenho máximo, otimização encadeada ligada, filtragem anisotrópica 8x, filtragem de "
          "textura em alto desempenho com viés LOD travado e Ansel desligado. Usa a interface oficial do driver; "
          "nada é injetado no jogo.",
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

# Checklist do que não dá (ou não deve) ser mudado por arquivo. (título, texto, quando mostrar: ""|"nvidia"|"amd")
INGAME_TIPS = [
    ("No jogo › Configurar Tela › Modo Janela",
     "Tela Cheia, não 'Tela cheia em janela', se você não precisa de outra coisa aberta por cima do jogo. Ajustar "
     "Tamanho de Interface em 80% (o mínimo): a câmera enxerga mais ao redor e sobra um pouco de FPS.", ""),
    ("No jogo › Configurar Tela › Qualidade Gráfica",
     "Qualidade de textura: Alta (custa pouco FPS se a placa tem 4 GB ou mais e evita a textura borrada que "
     "carrega de novo quando você chega num lugar; com menos de 4 GB, Média). Qualidade gráfica "
     "geral: 'Modo de Otimização', com o Modo Remasterizado desligado. Anti-aliasing: Não aplicado. Desligue SSAO, "
     "Filtro de Tela, Melhorar Distância, Profundidade de Campo, Detalhar NPCs Distantes, Efeitos de Impacto, "
     "Derreter Neve Acumulada, Mostrar Sangue e Sangue na Tela.", ""),
    ("Filtro de Tela: nunca ligue de novo",
     "Se você ligar o 'Filtro de Tela' no jogo, o PostFilter volta para 2 nos arquivos da UserCache e o ajuste se "
     "perde. Se ligou sem querer, feche o jogo e aplique de novo 'Filtro de tela desligado de verdade' na aba "
     "Windows para o BDO.", ""),
    ("No jogo › Qualidade Gráfica › Otimizar",
     "Efeitos de Outros Jogadores: ligado (esconde os efeitos dos outros). Otimização (upscale): Não aplicado; use "
     "AMD FSR 1.0 em Quality só se a placa de vídeo for fraca. Reduzir Consumo de Energia: desligado.", ""),
    ("No jogo › Configurar Tela › Efeito",
     "Transparência de Efeitos no mínimo (30) e Efeitos de Câmera (Combate) em 0: a luta fica mais legível na "
     "Guerra. Filtro de imagem, gama e contraste ficam ao seu gosto (o guia usa Vibrante, gama −25, contraste −50).",
     ""),
    ("No jogo › Configurar Desempenho › Otimizar",
     "Efeito de Decisão de Ataque e Efeito de Julgamento de Falha: ligados (ajudam a ler a luta). Otimização de "
     "Performance: ligada só com 8 GB de RAM ou mais (usa mais memória; reinicie o jogo e espere o primeiro "
     "carregamento, que é mais lento). "
     "Otimizar Efeitos: ligado, com a barra toda em 'Prioridade no Desempenho'. Otimizar Personagens e Ocultar "
     "Outros Personagens: desligados no dia a dia (ligue na Siege se o FPS cair muito).", ""),
    ("Painel NVIDIA › Gerenciar configurações 3D › Programa: BlackDesert64.exe",
     "O perfil do BDO deste app já grava isso no driver (aba Windows para o BDO). Confira também em 'Alterar "
     "resolução' que a taxa de atualização está no máximo do monitor e, em 'Configurar Surround, PhysX', que o "
     "processador PhysX é a sua placa de vídeo (não Automático nem CPU).", "nvidia"),
    ("AMD Software (Adrenalin) › Jogos › BlackDesert64",
     "Radeon Anti-Lag: ativado. Radeon Chill: desativado. Aprimoramento de imagens Radeon: ativado (nitidez ao seu "
     "gosto). Enhanced Sync: ativado (se aparecer tremedeira ou travadinha, desligue). Em Avançado: anti-aliasing "
     "usando as configurações do aplicativo, anti-aliasing morfológico desativado, filtragem anisotrópica ativada em "
     "8x, qualidade da filtragem de textura Alta, otimização de formato de superfície ativada, modo de mosaicos "
     "substituindo o aplicativo com nível máximo desativado e buffer triplo OpenGL desativado. Mantenha o driver em "
     "dia pelo site da AMD.", "amd"),
    ("Windows › Configurações de elementos gráficos",
     "Agendamento de GPU acelerado por hardware: ativado. Taxa de atualização variável: ativada. Em Configurações › "
     "Vídeo › Configurações avançadas de tela, escolha a maior taxa de atualização do monitor. O app já marca o "
     "BlackDesert64.exe como 'Alto desempenho' (aba Windows para o BDO).", ""),
    ("Memória virtual (arquivo de paginação)",
     "Deixe 'Tamanho gerenciado pelo sistema' no disco do Windows. Alguns guias mandam desligar; no BDO isso faz o "
     "jogo fechar sozinho por falta de memória em Guerra e Siege.", ""),
    ("Resizable BAR (BIOS)",
     "Se a placa-mãe e a placa de vídeo suportam (RTX 3000+ ou RX 6000+ com Ryzen 3000+/Intel 10ª+): na BIOS ligue "
     "Above 4G Decoding e Re-Size BAR Support e desligue o CSM. Confira em Meu PC se ficou ativo.", ""),
    ("Núcleos e prioridade (o que o Process Lasso faz)",
     "A prioridade alta já vem no ajuste 'BDO sempre em prioridade alta'. Para escolher os núcleos, use a aba "
     "Núcleos da CPU: o app aplica a regra sozinho toda vez que o jogo abre, sem precisar do Process Lasso.", ""),
    ("Interface e som do jogo",
     "No modo de edição de interface, desligue as janelas que você não usa (menos coisa na tela = menos poluição e "
     "um pouco mais de FPS em massa). No áudio: música e vozes desligadas, efeitos sonoros baixos.", ""),
    ("Limite de FPS",
     "No BDO: Configurações › Exibição › Limite de FPS = Hz do monitor − 3 (ex.: 141 em 144 Hz). "
     "Frametime estável vale mais do que FPS de pico na Siege.", ""),
    ("Shift+F5 e esconder jogadores",
     "Shift+F5 alterna a exibição de outros jogadores — salva o FPS em cidade lotada (Velia/Heidel).", ""),
    ("Rede no roteador",
     "Prefira cabo. Se o ping sobe quando alguém usa a internet (bufferbloat), ative QoS/SQM no roteador.", ""),
    ("Antes da Guerra",
     "Use 'Preparar e jogar' (libera RAM, plano de energia, prioridade) e feche navegador com vídeo.", ""),
]


def tips_for_this_pc() -> list[tuple[str, str]]:
    gv = pc.detect().gpu_vendor
    return [(t, d) for t, d, only in INGAME_TIPS if not only or only == gv]
