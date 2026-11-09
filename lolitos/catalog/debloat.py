"""Apps pré-instalados do Windows que dá para remover."""
from pathlib import Path

from lolitos.core.actions import Appx, Cmd
from lolitos.core.system import expand
from lolitos.core.tweaks import ADVANCED, RECOMMENDED, Tweak, register


def _onedrive_installed() -> bool:
    return any(Path(expand(p)).exists() for p in (
        r"%LOCALAPPDATA%\Microsoft\OneDrive\OneDrive.exe",
        r"%ProgramFiles%\Microsoft OneDrive\OneDrive.exe",
        r"%ProgramFiles(x86)%\Microsoft OneDrive\OneDrive.exe"))

# (pacote, nome, aviso) — aviso não vazio = começa desmarcado
APPS = [
    ("Microsoft.BingNews", "Notícias (Microsoft News)", ""),
    ("Microsoft.BingWeather", "Clima (MSN)", ""),
    ("Microsoft.BingSearch", "Pesquisa do Bing", ""),
    ("Microsoft.GetHelp", "Obter Ajuda", ""),
    ("Microsoft.Getstarted", "Dicas", ""),
    ("Microsoft.MicrosoftSolitaireCollection", "Paciência (Solitaire)", ""),
    ("Microsoft.People", "Pessoas", ""),
    ("Microsoft.PowerAutomateDesktop", "Power Automate", ""),
    ("Microsoft.Todos", "Microsoft To Do", ""),
    ("Microsoft.WindowsFeedbackHub", "Hub de Comentários", ""),
    ("Microsoft.WindowsMaps", "Mapas", ""),
    ("Microsoft.WindowsAlarms", "Alarmes e Relógio", "Tem cronômetro e timer — útil para buffs/spawns."),
    ("Microsoft.WindowsSoundRecorder", "Gravador de Som", ""),
    ("Microsoft.ZuneVideo", "Filmes e TV", ""),
    ("Microsoft.ZuneMusic", "Media Player", "É o player de música/vídeo padrão do Windows 11."),
    ("Clipchamp.Clipchamp", "Clipchamp (editor de vídeo)", ""),
    ("Microsoft.549981C3F5F10", "Cortana", ""),
    ("Microsoft.MixedReality.Portal", "Portal de Realidade Misturada", ""),
    ("Microsoft.Microsoft3DViewer", "Visualizador 3D", ""),
    ("Microsoft.SkypeApp", "Skype", ""),
    ("MicrosoftTeams", "Microsoft Teams (pessoal)", ""),
    ("MSTeams", "Microsoft Teams (novo)", "Não remova se usa Teams no trabalho/escola."),
    ("Microsoft.OutlookForWindows", "Outlook (novo)", "Não remova se usa o Outlook novo."),
    ("microsoft.windowscommunicationsapps", "Email e Calendário (antigo)", ""),
    ("Microsoft.Office.OneNote", "OneNote (versão da Store)", "Não remova se usa o OneNote."),
    ("Microsoft.MicrosoftStickyNotes", "Notas Autoadesivas", "Remova só se não usa notas na área de trabalho."),
    ("Microsoft.Wallet", "Carteira (Microsoft Pay)", ""),
    ("Microsoft.Windows.DevHome", "Dev Home", ""),
    ("Microsoft.YourPhone", "Vincular ao Celular", "Necessário para usar o celular pelo PC."),
    ("SpotifyAB.SpotifyMusic", "Spotify (versão da Store)", "Não remova se usa o Spotify da Store."),
    ("Microsoft.XboxSpeechToTextOverlay", "Xbox — legenda de voz", ""),
    ("Microsoft.GamingApp", "Xbox (app)", "Não remova se usa Game Pass."),
    ("Microsoft.XboxGamingOverlay", "Xbox Game Bar", "Usada para gravar e para o Modo de Jogo em alguns jogos."),
    ("Microsoft.WindowsCamera", "Câmera", "Não remova se usa a webcam pelo app Câmera."),
    ("MicrosoftCorporationII.QuickAssist", "Assistência Rápida", "Não remova se alguém dá suporte a este PC por ela."),
    ("Microsoft.MicrosoftOfficeHub", "Microsoft 365 (Office) — atalho da loja", ""),
]

DEBLOAT_TWEAKS = []
for pkg, name, warn in APPS:
    t = Tweak("appx_" + pkg.lower().replace(".", "_"), name, f"Pacote {pkg}. Sem desfazer: volta pela Microsoft Store.",
              "debloat", [Appx(pkg)], ADVANCED if warn else RECOMMENDED, loss=warn)
    DEBLOAT_TWEAKS.append(t)

ONEDRIVE = Tweak(
    "onedrive_remove", "Remover o OneDrive",
    "Desinstala o OneDrive. Arquivos já baixados continuam na sua pasta; os da nuvem continuam na conta.",
    "debloat",
    [Cmd("taskkill /f /im OneDrive.exe >nul 2>&1 & winget uninstall --id Microsoft.OneDrive -e --silent "
         "--accept-source-agreements",
         "winget install --id Microsoft.OneDrive -e --silent --accept-package-agreements --accept-source-agreements",
         check=lambda: not _onedrive_installed(), label="desinstalar OneDrive")],
    ADVANCED, loss="Ruim se você usa o OneDrive para backup ou sincronizar arquivos.")

register(*DEBLOAT_TWEAKS, ONEDRIVE)
