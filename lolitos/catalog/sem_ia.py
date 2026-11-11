"""Desligar Copilot, Recall e IA do Windows; pesquisa sem web; widgets."""
from lolitos.core.actions import Appx, Capability, Cmd, Reg, regs
from lolitos.core.system import is_win11
from lolitos.core.tweaks import ADVANCED, ESSENTIAL, RECOMMENDED, Tweak, register

HKCU, HKLM = "HKCU", "HKLM"
AI = r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI"
ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
SEARCH_POL = r"SOFTWARE\Policies\Microsoft\Windows\Windows Search"

register(
    Tweak("copilot_off", "Desligar o Copilot do Windows",
          "Desativa o assistente por política, para o usuário e para o PC.",
          "ia", [Reg(HKCU, r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 1),
                 Reg(HKLM, r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 1),
                 Reg(HKCU, ADV, "ShowCopilotButton", 0)], ESSENTIAL),
    Tweak("recall_off", "Desligar o Recall (capturas da tela)",
          "Impede que o Windows salve e analise capturas periódicas da tela (PCs Copilot+).",
          "ia", [Reg(HKCU, AI.replace("SOFTWARE", "Software"), "DisableAIDataAnalysis", 1),
                 Reg(HKLM, AI, "DisableAIDataAnalysis", 1), Reg(HKLM, AI, "AllowRecallEnablement", 0)],
          ESSENTIAL, when=is_win11),
    Tweak("clicktodo_off", "Desligar o Clique para Fazer",
          "Desativa a sobreposição de IA que analisa a tela para sugerir ações.",
          "ia", [Reg(HKCU, AI.replace("SOFTWARE", "Software"), "DisableClickToDo", 1),
                 Reg(HKLM, AI, "DisableClickToDo", 1)], ESSENTIAL, when=is_win11),
    Tweak("settings_agent_off", "Sem a pesquisa com IA nas Configurações",
          "Desliga o agente que interpreta a pesquisa das Configurações.",
          "ia", [Reg(HKLM, AI, "DisableSettingsAgent", 1)], ESSENTIAL, when=is_win11),
    Tweak("paint_ai_off", "Sem IA no Paint", "Desativa Cocreator, Preenchimento generativo e Criador de imagens.",
          "ia", regs(HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Paint",
                     DisableCocreator=1, DisableGenerativeFill=1, DisableImageCreator=1), ESSENTIAL),
    Tweak("notepad_ai_off", "Sem IA no Bloco de Notas", "Desativa reescrever e resumir com IA.",
          "ia", [Reg(HKLM, r"SOFTWARE\Policies\WindowsNotepad", "DisableAIFeatures", 1)], ESSENTIAL),
    Tweak("edge_copilot_off", "Sem Copilot no Microsoft Edge",
          "Tira a barra lateral do Copilot e impede que ele leia as páginas.",
          "ia", regs(HKLM, r"SOFTWARE\Policies\Microsoft\Edge", HubsSidebarEnabled=0, CopilotPageContext=0,
                     CopilotCDPPageContext=0), ESSENTIAL),
    Tweak("search_local", "Pesquisa do Iniciar só no PC",
          "Sem Bing, sem nuvem e sem destaques: o que você digita no Iniciar não sai do computador.",
          "ia", [Reg(HKCU, r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", 1),
                 *regs(HKCU, r"Software\Microsoft\Windows\CurrentVersion\Search", BingSearchEnabled=0, CortanaConsent=0),
                 *regs(HKCU, r"Software\Microsoft\Windows\CurrentVersion\SearchSettings", IsDynamicSearchBoxEnabled=0,
                       IsAADCloudSearchEnabled=0, IsMSACloudSearchEnabled=0),
                 *regs(HKLM, SEARCH_POL, AllowCloudSearch=0, AllowCortana=0, ConnectedSearchUseWeb=0,
                       DisableWebSearch=1, EnableDynamicContentInWSB=0)],
          ESSENTIAL, gain="Iniciar abre e pesquisa mais rápido."),
    Tweak("widgets_off", "Desligar os Widgets (notícias)",
          "Desativa o painel de Widgets, que fica carregando notícias em segundo plano.",
          "ia", [Reg(HKLM, r"SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", 0),
                 Reg(HKLM, r"SOFTWARE\Policies\Microsoft\Windows\Windows Feeds", "EnableFeeds", 0)], ESSENTIAL,
          gain="Menos um processo WebView rodando."),
    Tweak("chat_meetnow_off", "Sem Chat do Teams e 'Reunir agora' na barra",
          "Remove o botão de chat do Teams pessoal e o ícone do Reunir agora.",
          "ia", [Reg(HKCU, ADV, "TaskbarMn", 0),
                 Reg(HKLM, r"SOFTWARE\Policies\Microsoft\Windows\Windows Chat", "ChatIcon", 3),
                 Reg(HKCU, r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "HideSCAMeetNow", 1)],
          ESSENTIAL),
    Tweak("remove_copilot_apps", "Remover os apps de IA (Copilot e Microsoft 365)",
          "Desinstala o app Copilot e o Microsoft 365 (Office Hub). Voltam pela Microsoft Store.",
          "ia", [Appx("Microsoft.Copilot"), Appx("Microsoft.Windows.Ai.Copilot.Provider"),
                 Appx("Microsoft.MicrosoftOfficeHub")], RECOMMENDED,
          loss="Sem desfazer automático: reinstale pela Store se precisar."),
    Tweak("remove_recall_feature", "Remover o componente Recall",
          "Desinstala o recurso opcional Recall (vale após reiniciar).",
          "ia", [Cmd("Disable-WindowsOptionalFeature -Online -FeatureName Recall -NoRestart | Out-Null",
                     "Enable-WindowsOptionalFeature -Online -FeatureName Recall -NoRestart | Out-Null", ps=True,
                     ps_check="$f=Get-WindowsOptionalFeature -Online -FeatureName Recall -EA SilentlyContinue;"
                              "if(-not $f -or $f.State -ne 'Enabled'){'1'}else{'0'}", label="recurso Recall")],
          ADVANCED, restart=True, when=is_win11),
)

# Recursos opcionais removíveis (Debloat > Recursos do Windows)
CAPABILITIES = [
    ("App.StepsRecorder*", "Gravador de Passos", "A Microsoft já descontinuou."),
    ("App.Support.QuickAssist*", "Assistência Rápida antiga", "Usada em golpes de 'suporte técnico'."),
    ("MathRecognizer*", "Painel de Entrada de Matemática", "Só serve com caneta."),
    ("Language.Handwriting*", "Reconhecimento de escrita à mão", "Só serve em notebook com caneta ou tela de toque."),
    ("Hello.Face*", "Windows Hello facial", "Não remova se entra no Windows pelo rosto."),
    ("Microsoft.Windows.WordPad*", "WordPad", ""),
    ("Print.Fax.Scan*", "Fax e Scanner do Windows", "Não remova se usa scanner pelo app do Windows."),
    ("Language.Speech*", "Reconhecimento de fala", "O ditado por voz para de funcionar."),
    ("Language.TextToSpeech*", "Vozes do Windows (leitura em voz alta)", "O Narrador fica sem voz."),
]
CAPABILITY_TWEAKS = []
for pat, label, warn in CAPABILITIES:
    tid = "cap_" + pat.split("*")[0].lower().replace(".", "_")
    t = Tweak(tid, f"Remover {label}", f"Recurso opcional do Windows ({pat}). Desfazer reinstala pela internet.",
              "debloat", [Capability(pat, label)], ADVANCED, loss=warn, restart=True)
    CAPABILITY_TWEAKS.append(t)
register(*CAPABILITY_TWEAKS)
