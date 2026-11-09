"""Ferramentas de reparo e manutenção do próprio Windows (o comando é mostrado antes)."""
from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass
from typing import Callable

from lolitos.core.system import IS_WIN, powershell, run


@dataclass
class Tool:
    id: str
    name: str
    desc: str
    cmd: str                 # o que é mostrado (e executado em cmd.exe, se fn for None)
    group: str
    minutes: str = ""
    fn: Callable[[], tuple[bool, str]] | None = None
    restart: bool = False
    ps: bool = False


def _gpu_reset() -> tuple[bool, str]:
    """Win+Ctrl+Shift+B: reinicia o driver de vídeo (a tela pisca e soa um bipe)."""
    if not IS_WIN:
        return False, "só no Windows"
    u = ctypes.windll.user32
    keys = [0x5B, 0x11, 0x10, 0x42]  # LWIN, CTRL, SHIFT, B
    for k in keys:
        u.keybd_event(k, 0, 0, 0)
    time.sleep(0.05)
    for k in reversed(keys):
        u.keybd_event(k, 0, 2, 0)
    return True, "driver de vídeo reiniciado"


TOOLS = [
    # saúde do sistema
    Tool("sfc", "Verificar arquivos do sistema (SFC)", "Procura arquivos do Windows corrompidos e os troca por cópias boas.",
         "sfc /scannow", "Saúde", "10–20 min"),
    Tool("dism", "Reparar a imagem do Windows (DISM)",
         "Corrige o repositório de componentes que o SFC usa. Precisa de internet.",
         "DISM /Online /Cleanup-Image /RestoreHealth", "Saúde", "10–30 min"),
    Tool("full_repair", "Reparo completo (DISM + SFC)", "Repara a imagem e depois verifica todos os arquivos. "
         "Recomendado se o BDO ou o Windows travam sem motivo.",
         "DISM /Online /Cleanup-Image /RestoreHealth & sfc /scannow", "Saúde", "20–40 min"),
    Tool("chkdsk", "Verificar o disco C: (CHKDSK)", "Verifica o sistema de arquivos sem reiniciar.",
         "chkdsk C: /scan", "Saúde", "5–15 min"),
    Tool("component_cleanup", "Limpar componentes antigos do Windows",
         "Remove versões substituídas de atualizações (WinSxS).", "DISM /Online /Cleanup-Image /StartComponentCleanup",
         "Saúde", "5–15 min"),
    # rede
    Tool("flushdns", "Limpar o cache de DNS", "Resolve sites/servidores que não abrem depois de mudarem de IP.",
         "ipconfig /flushdns", "Rede"),
    Tool("renew_ip", "Renovar o endereço IP", "Pede um IP novo ao roteador. A conexão cai por alguns segundos.",
         "ipconfig /release & ipconfig /renew", "Rede"),
    Tool("reset_net", "Redefinir Winsock e TCP/IP",
         "Volta a rede aos padrões. Corrige internet quebrada depois de VPN, vírus ou 'otimizadores'.",
         "netsh winsock reset & netsh int ip reset & ipconfig /flushdns", "Rede", restart=True),
    # Windows
    Tool("wu_reset", "Redefinir o Windows Update", "Para os serviços, renomeia as pastas de cache e reinicia. "
         "Corrige atualizações que falham ou travam.",
         "net stop wuauserv /y & net stop bits /y & net stop cryptsvc /y & "
         "ren %SystemRoot%\\SoftwareDistribution SoftwareDistribution.old%RANDOM% & "
         "ren %SystemRoot%\\System32\\catroot2 catroot2.old%RANDOM% & "
         "net start cryptsvc & net start bits & net start wuauserv", "Windows"),
    Tool("explorer", "Reiniciar o Explorer", "Resolve barra de tarefas ou menu Iniciar travados.",
         "taskkill /f /im explorer.exe & start explorer.exe", "Windows"),
    Tool("audio", "Reiniciar o áudio do Windows", "Resolve som que sumiu, chiado ou travado (inclusive no BDO).",
         "net stop audiosrv /y & net stop AudioEndpointBuilder /y & net start AudioEndpointBuilder & net start audiosrv",
         "Windows"),
    Tool("bluetooth", "Reiniciar o Bluetooth", "Resolve fone/controle que não conecta.",
         "net stop bthserv /y & net start bthserv", "Windows"),
    Tool("spooler", "Destravar a impressora", "Limpa a fila de impressão e reinicia o spooler.",
         "net stop spooler /y & del /q /f %SystemRoot%\\System32\\spool\\PRINTERS\\* & net start spooler", "Windows"),
    Tool("icons", "Reconstruir o cache de ícones", "Corrige ícones em branco ou errados.",
         "ie4uinit.exe -show & taskkill /f /im explorer.exe & "
         "del /a /q %LOCALAPPDATA%\\IconCache.db & del /a /f /q %LOCALAPPDATA%\\Microsoft\\Windows\\Explorer\\iconcache* & "
         "start explorer.exe", "Windows"),
    Tool("store_repair", "Reparar Microsoft Store e menu Iniciar",
         "Registra de novo os apps essenciais quando a Store ou o Iniciar não abrem.",
         "Get-AppxPackage -AllUsers Microsoft.WindowsStore,Microsoft.Windows.StartMenuExperienceHost,"
         "Microsoft.Windows.ShellExperienceHost | ForEach-Object { Add-AppxPackage -DisableDevelopmentMode "
         "-Register (Join-Path $_.InstallLocation 'AppXManifest.xml') -ErrorAction SilentlyContinue }", "Windows",
         ps=True),
    Tool("hw_rescan", "Procurar alterações de hardware",
         "Faz o Windows detectar de novo pendrives, monitores e webcams que não aparecem.", "pnputil /scan-devices",
         "Windows"),
    Tool("gpu_reset", "Reiniciar o driver de vídeo", "Atalho Win+Ctrl+Shift+B: para tela preta/congelada. "
         "Os programas continuam abertos.", "Win+Ctrl+Shift+B", "Windows", fn=_gpu_reset),
    Tool("netfx3", "Ativar o .NET Framework 3.5", "Muitos jogos e programas antigos precisam dele.",
         "DISM /Online /Enable-Feature /FeatureName:NetFx3 /All /NoRestart", "Windows", "2–10 min"),
    Tool("winget_upgrade", "Atualizar todos os apps instalados (winget)",
         "Atualiza pelo winget todos os programas que têm versão nova.",
         "winget upgrade --all --silent --accept-package-agreements --accept-source-agreements --include-unknown",
         "Windows", "varia"),
]
TOOLS_BY_ID = {t.id: t for t in TOOLS}


def run_tool(t: Tool) -> tuple[bool, str]:
    if t.fn:
        return t.fn()
    if t.ps:
        r = powershell(t.cmd, timeout=3600)
    else:
        r = run(t.cmd, shell=True, timeout=3600)
    text = (r.out + "\n" + r.err).strip()
    # SFC/DISM escrevem com \x00 entre letras em alguns consoles
    text = text.replace("\x00", "")
    return r.ok, text[-4000:]
