"""Ajustes que completam o catálogo: menus do Explorer, Iniciar, coleta de dados, compatibilidade, serviços,
recursos opcionais e o mouse sem atrasos."""
from __future__ import annotations

import time

from lolitos import APP_NAME
from lolitos.core.actions import Action, ActionError, Capability, Reg, Service, Task, _check
from lolitos.core.system import IS_WIN, is_win11, powershell, run
from lolitos.core.tweaks import ADVANCED, ESSENTIAL, RECOMMENDED, Tweak, register

HKCU, HKLM = "HKCU", "HKLM"
POL = r"SOFTWARE\Policies\Microsoft\Windows"
ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
BLOCKED = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Shell Extensions\Blocked"
CAST_MENU = "{7AD84985-87B4-4a16-BE58-8B72A5B390F7}"      # "Transmitir para dispositivo"
COMPAT_MENU = "{1d27f844-3a1f-4410-85ac-14651078412d}"    # "Solucionar problemas de compatibilidade"

# curvas de movimento padrão do Windows (as mesmas de uma instalação limpa)
MOUSE_X = "0000000000000000156e000000000000004001000000000029dc0300000000000000280000000000"
MOUSE_Y = "0000000000000000fd11010000000000002404000000000000fc12000000000000c0bb0100000000"

DATA_TASKS = [
    r"\Microsoft\Windows\Power Efficiency Diagnostics\AnalyzeSystem",
    r"\Microsoft\Windows\Device Information\Device",
    r"\Microsoft\Windows\Device Information\Device User",
    r"\Microsoft\Windows\DiskFootprint\Diagnostics",
    r"\Microsoft\Windows\Maintenance\WinSAT",
    r"\Microsoft\Windows\Flighting\FeatureConfig\UsageDataReporting",
]


# ---------------------------------------------------------------- nome no menu de inicialização
_DESC_KEYS = ("description", "descrição", "descripción", "descricao")


def boot_description() -> str | None:
    """Nome desta instalação no gerenciador de inicialização (bcdedit; os rótulos vêm no idioma do Windows)."""
    r = run(["bcdedit", "/enum", "{current}"], timeout=30)
    if not r.ok:
        return None
    for line in r.out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() in _DESC_KEYS:
            return parts[1].strip()
    return None


class BootName(Action):
    def __init__(self, name: str):
        self.name = name

    def describe(self):
        return f"nome no menu de inicialização = {self.name}"

    def applicable(self):
        return IS_WIN

    def is_applied(self):
        d = boot_description()
        return None if d is None else d == self.name

    def capture(self):
        return {"desc": boot_description()}

    def _set(self, name: str):
        _check(run(["bcdedit", "/set", "{current}", "description", name], timeout=30), "bcdedit")

    def apply(self):
        self._set(self.name)

    def revert(self, snap):
        old = snap.get("desc") or ("Windows 11" if is_win11() else "Windows 10")
        self._set(old)


# ---------------------------------------------------------------- recursos opcionais (DISM)
_FEATURES: dict[str, str] = {}
_FEATURES_T = [0.0]


def feature_state(name: str) -> str | None:
    """'Enabled', 'Disabled'… ou None se o recurso não existe nesta versão do Windows."""
    if not IS_WIN:
        return None
    if time.time() - _FEATURES_T[0] > 60 or name not in _FEATURES:
        r = powershell(f"(Get-WindowsOptionalFeature -Online -FeatureName '{name}' -EA SilentlyContinue).State",
                       timeout=120)
        _FEATURES[name] = r.out.strip() if r.ok else ""
        _FEATURES_T[0] = time.time()
    return _FEATURES.get(name) or None


class Feature(Action):
    """Liga ou desliga um recurso opcional do Windows (Ativar ou desativar recursos do Windows)."""

    def __init__(self, name: str, enable: bool, label: str):
        self.name, self.enable, self.label = name, enable, label

    def describe(self):
        return f"recurso {self.label} → {'ligado' if self.enable else 'desligado'}"

    def applicable(self):
        return feature_state(self.name) is not None

    def is_applied(self):
        st = feature_state(self.name)
        if st is None:
            return None
        return (st.lower() == "enabled") == self.enable

    def capture(self):
        return {"state": feature_state(self.name)}

    def _set(self, on: bool):
        verb = "Enable" if on else "Disable"
        extra = " -All" if on else ""
        r = powershell(f"{verb}-WindowsOptionalFeature -Online -FeatureName '{self.name}'{extra} -NoRestart "
                       "| Out-Null", timeout=1800)
        _FEATURES.pop(self.name, None)
        if not r.ok:
            raise ActionError(f"{self.label}: {(r.err or r.out).strip()[:300] or 'o Windows recusou'}")

    def apply(self):
        self._set(self.enable)

    def revert(self, snap):
        st = (snap.get("state") or "").lower()
        if st:
            self._set(st == "enabled")


register(
    # ============================================================ Explorer, Iniciar e menus
    Tweak("start_hide_recommended", "Iniciar sem a seção Recomendados",
          "Esconde do menu Iniciar a área de arquivos e apps recomendados, deixando só os fixados.",
          "interface", [Reg(HKLM, POL + r"\Explorer", "HideRecommendedSection", 1),
                        Reg(HKLM, r"SOFTWARE\Microsoft\PolicyManager\current\device\Start",
                            "HideRecommendedSection", 1),
                        Reg(HKCU, r"Software\Policies\Microsoft\Windows\Explorer", "HideRecommendedSection", 1)],
          ADVANCED, explorer=True, when=is_win11,
          loss="Em algumas edições e versões do Windows 11 a política é ignorada; nesse caso nada muda."),
    Tweak("notif_center_off", "Desligar a central de notificações e o calendário",
          "Tira a central de notificações e o calendário da bandeja, junto com os balões de notificação.",
          "interface", [Reg(HKCU, r"Software\Policies\Microsoft\Windows\Explorer", "DisableNotificationCenter", 1),
                        Reg(HKCU, r"Software\Microsoft\Windows\CurrentVersion\PushNotifications", "ToastEnabled", 0)],
          ADVANCED, admin=False, explorer=True,
          loss="Lembretes, alarmes e avisos de mensagens deixam de aparecer."),
    Tweak("multi_invoke_menu", "Clique direito completo com muitos arquivos",
          "Com mais de 15 arquivos selecionados, o clique direito continua oferecendo Abrir, Imprimir e o resto.",
          "interface", [Reg(HKCU, r"Software\Microsoft\Windows\CurrentVersion\Explorer",
                            "MultipleInvokePromptMinimum", 1000)], RECOMMENDED, admin=False),
    Tweak("ctx_cast_off", "Tirar 'Transmitir para dispositivo' do clique direito",
          "Remove a opção de mandar mídia para TVs e outros aparelhos do menu de contexto.",
          "interface", [Reg(HKLM, BLOCKED, CAST_MENU, "", "sz")], RECOMMENDED, explorer=True),
    Tweak("ctx_compat_off", "Tirar 'Solucionar problemas de compatibilidade' do clique direito",
          "Remove do menu de contexto dos programas a entrada do solucionador de compatibilidade.",
          "interface", [Reg(HKLM, BLOCKED, COMPAT_MENU, "", "sz")], RECOMMENDED, explorer=True),
    Tweak("boot_menu_name", f"Nome '{APP_NAME}' no menu de inicialização",
          "Dá esse nome a esta instalação do Windows no gerenciador de inicialização (bcdedit). "
          "Desfazer devolve o nome que estava antes.",
          "interface", [BootName(APP_NAME)], ADVANCED,
          gain="Fácil de reconhecer quando há mais de um sistema no PC."),
    Tweak("netfx3_on", "Ativar o .NET Framework 3.5",
          "Instala o .NET 3.5 pelo Windows Update. Muitos jogos e programas antigos não abrem sem ele.",
          "apps", [Feature("NetFx3", True, ".NET Framework 3.5")], ADVANCED,
          loss="Precisa de internet e pode levar alguns minutos."),

    # ============================================================ privacidade e coleta
    Tweak("track_progs_off", "Não registrar os apps que você mais abre",
          "O Windows para de montar a lista de programas mais usados para o Iniciar e a pesquisa.",
          "privacidade", [Reg(HKCU, ADV, "Start_TrackProgs", 0)], ESSENTIAL, admin=False),
    Tweak("data_collect_tasks", "Desligar tarefas de coleta de dados",
          "Diagnóstico de energia, inventário do aparelho, uso de disco e avaliação de desempenho que rodam "
          "sozinhos em segundo plano.",
          "privacidade", [Task(t) for t in DATA_TASKS], ESSENTIAL,
          gain="Menos picos de disco e processador fora de hora."),
    Tweak("motion_bg_off", "Apps sem acesso a movimento em segundo plano",
          "Apps fechados deixam de ler sensores de movimento e de posição.",
          "privacidade", [Reg(HKLM, POL + r"\AppPrivacy", "LetAppsAccessBackgroundSpatialPerception", 2)],
          ESSENTIAL),
    Tweak("bg_apps_policy", "Bloquear apps em segundo plano para todas as contas",
          "Versão por política: nenhum app da Store roda escondido, em nenhuma conta do PC.",
          "privacidade", [Reg(HKLM, POL + r"\AppPrivacy", "LetAppsRunInBackground", 2)], ADVANCED,
          loss="WhatsApp, Spotify, Vincular ao Celular e outros apps da Store só notificam abertos."),
    Tweak("wer_logging_off", "Não gravar o Relatório de Erros no Visualizador de Eventos",
          "Os eventos do Relatório de Erros do Windows deixam de ser registrados.",
          "privacidade", [Reg(HKLM, r"SOFTWARE\Microsoft\Windows\Windows Error Reporting", "LoggingDisabled", 1)],
          ADVANCED, loss="Fica mais difícil descobrir a causa de travamentos (inclusive no Check-up)."),

    # ============================================================ desempenho e compatibilidade
    Tweak("spooler_manual", "Spooler de impressão sob demanda",
          "O serviço de impressão passa a ligar só quando algum programa vai imprimir.",
          "desempenho", [Service("Spooler", "manual", stop=False)], ADVANCED,
          loss="Se você imprime toda hora, a primeira impressão demora um pouco mais."),
    Tweak("diag_collector_manual", "Coletor de diagnóstico sob demanda",
          "O coletor padrão do Hub de Diagnóstico só liga quando alguma ferramenta de diagnóstico pede.",
          "desempenho", [Service("diagnosticshub.standardcollector.service", "manual")], RECOMMENDED),
    Tweak("appcompat_engine_off", "Desligar o Mecanismo de Compatibilidade de Aplicativos",
          "Para as correções automáticas que o Windows aplica em programas antigos (inclui o SwitchBack).",
          "desempenho", [Reg(HKLM, POL + r"\AppCompat", "DisableEngine", 1),
                         Reg(HKLM, POL + r"\AppCompat", "SbEnable", 0)], ADVANCED,
          loss="Jogos e programas antigos podem parar de abrir ou travar; desfaça se acontecer."),

    # ============================================================ recursos opcionais
    Tweak("cap_onesync", "Remover a sincronização de Email, Calendário e Pessoas",
          "Componente que sincroniza contas dos apps antigos de Email e Calendário.",
          "debloat", [Capability("OneCoreUAP.OneSync*", "sincronização de contas")], ADVANCED,
          loss="Os apps antigos de Email e Calendário param de sincronizar. Outlook e navegador não mudam."),
    Tweak("rdp_client_remove", "Remover a Conexão de Área de Trabalho Remota",
          "Desinstala o mstsc, usado para controlar outro PC pela Área de Trabalho Remota.",
          "debloat", [Feature("Microsoft-RemoteDesktopConnection", False, "Conexão de Área de Trabalho Remota")],
          ADVANCED, loss="Evite se você acessa servidores ou o PC do trabalho pela Área de Trabalho Remota."),

    # ============================================================ mouse
    Tweak("mouse_no_delay", "Mouse sem atrasos",
          "Dica do ponteiro em 10 ms e curvas de movimento no padrão do Windows (sem curva personalizada "
          "deixada por outros programas). Combine com 'Desligar a aceleração do mouse'.",
          "entrada", [Reg(HKCU, r"Control Panel\Mouse", "MouseHoverTime", "10", "sz"),
                      Reg(HKCU, r"Control Panel\Mouse", "SmoothMouseXCurve", MOUSE_X, "binary"),
                      Reg(HKCU, r"Control Panel\Mouse", "SmoothMouseYCurve", MOUSE_Y, "binary")],
          RECOMMENDED, admin=False),
)
