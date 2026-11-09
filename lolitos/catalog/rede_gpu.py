"""Placa de vídeo, monitor e rede."""
from lolitos.core.actions import Interfaces, Power, Reg
from lolitos.core.tweaks import ADVANCED, ESSENTIAL, RECOMMENDED, Tweak, register
from lolitos.modules import display
from lolitos.modules import pcprofile as pc

HKCU, HKLM = "HKCU", "HKLM"
MM = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
TCP6 = r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters"

register(
    # ------------------------------------------------------------ GPU / monitor
    Tweak("hags_on", "Agendamento de GPU acelerado por hardware",
          "A placa de vídeo gerencia a própria fila de quadros (HAGS).",
          "gpu", [Reg(HKLM, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2)],
          RECOMMENDED, restart=True, gain="Menos latência de quadro; necessário para o DLSS Frame Generation.",
          loss="Em placas antigas (anteriores à GTX 10/RX 5000) pode piorar; desfaça se notar travadas.",
          when=pc.hags_ok),
    Tweak("mpo_off", "Desligar o Multiplane Overlay (MPO)",
          "Correção conhecida para tela piscando, cintilação e travadas com monitores de Hz diferentes.",
          "gpu", [Reg(HKLM, r"SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", 5)],
          ADVANCED, restart=True, gain="Acaba com flicker/stutter em alguns PCs NVIDIA.",
          loss="Gasta um pouco mais de GPU em vídeos em janela. Pode não ter efeito no Windows 11 24H2 ou mais novo."),
    Tweak("refresh_max", "Monitor na taxa de atualização máxima",
          "Coloca cada monitor no maior Hz que ele aceita na resolução atual — muita gente joga a 60 Hz sem saber.",
          "gpu", [display.MaxRefreshAction()], ESSENTIAL, admin=False,
          gain="Imagem mais fluida e menos input lag."),
    Tweak("nvidia_telemetry_off", "Desligar a telemetria do Painel de Controle NVIDIA",
          "O Painel de Controle NVIDIA deixa de enviar dados de uso.",
          "gpu", [Reg(HKCU, r"Software\NVIDIA Corporation\NVControlPanel2\Client", "OptInOrOutPreference", 0)],
          ESSENTIAL, when=pc.nvidia),

    # ------------------------------------------------------------ rede
    Tweak("net_throttling_off", "Sem limite de pacotes de rede para multimídia",
          "Remove o NetworkThrottlingIndex, que limita pacotes por milissegundo enquanto há som tocando.",
          "rede", [Reg(HKLM, MM, "NetworkThrottlingIndex", 0xFFFFFFFF)], ESSENTIAL,
          gain="O jogo não perde vazão de rede porque o Discord está tocando áudio."),
    Tweak("nagle_off", "Pacotes TCP sem espera (Nagle desligado)",
          "TcpAckFrequency=1 nas interfaces de rede: o Windows confirma cada pacote na hora, sem esperar "
          "juntar dois (ACK atrasado). O BDO usa TCP, então isso conta.",
          "rede", [Interfaces("TcpAckFrequency", 1)],
          RECOMMENDED, restart=True, gain="Ações e respostas do servidor chegam sem atraso artificial.",
          loss="Um pouco mais de pacotes na rede; irrelevante para internet doméstica."),
    Tweak("wifi_max", "Wi-Fi sem economia de energia",
          "O adaptador Wi-Fi fica no desempenho máximo do plano ativo.",
          "rede", [Power("19cbb8fa-5279-450e-9fac-8a3d5fedd0c1", "12bbebe6-58d6-4636-95bb-3217ef867c1a", 0,
                         label="economia do Wi-Fi")],
          RECOMMENDED, gain="Ping mais estável no Wi-Fi.", loss="Notebook na bateria gasta mais.",
          when=pc.wifi_desktop),
    Tweak("ipv4_first", "Preferir IPv4 ao IPv6",
          "O Windows usa IPv4 primeiro. Ajuda onde o IPv6 da operadora é mal configurado.",
          "rede", [Reg(HKLM, TCP6, "DisabledComponents", 0x20)], ADVANCED, restart=True,
          exclusive="tcpip6", loss="Não combine com 'Desligar o IPv6'."),
    Tweak("ipv6_off", "Desligar o IPv6",
          "Desativa o IPv6 em todos os adaptadores.",
          "rede", [Reg(HKLM, TCP6, "DisabledComponents", 0xFF)], ADVANCED, restart=True, exclusive="tcpip6",
          loss="Ruim se sua operadora usa só IPv6 (CGNAT) ou algum serviço exige IPv6."),
    Tweak("teredo_off", "Desligar o Teredo",
          "Desativa o túnel Teredo do IPv6, que pode adicionar latência.",
          "rede", [Reg(HKLM, r"SOFTWARE\Policies\Microsoft\Windows\TCPIP\v6Transition", "Teredo_State", "Disabled", "sz")],
          RECOMMENDED, loss="Chat de grupo do Xbox pode reclamar de NAT."),
    Tweak("delivery_p2p_off", "Não enviar atualizações para outros PCs",
          "O Windows para de usar sua internet para distribuir atualizações (Otimização de Entrega P2P).",
          "rede", [Reg(HKLM, r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode", 0)],
          ESSENTIAL, gain="Upload livre para o jogo."),
    Tweak("audio_ducking_off", "Não abaixar o som durante chamadas",
          "Jogo e música continuam no volume normal quando o Windows detecta uma chamada (Discord).",
          "rede", [Reg(HKCU, r"Software\Microsoft\Multimedia\Audio", "UserDuckingPreference", 3)], ESSENTIAL),
)
