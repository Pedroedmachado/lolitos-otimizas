"""Catálogo de ajustes para Linux. Os valores de memória seguem a página 'Gaming' da Arch Wiki
(seção de parâmetros do kernel para consistência de tempo de resposta)."""
from __future__ import annotations

import os
import shutil

from lolitos.core.tweaks import ADVANCED, CATALOG, CATS, ESSENTIAL, RECOMMENDED, Tweak, register
from lolitos.linux.actions import ConfFile, Package, Sysctl, Sysfs, UserEnv
from lolitos.linux.root import P

LINUX_CATS = {"lx_cpu": "Processador e energia", "lx_mem": "Memória e kernel", "lx_disk": "Disco",
              "lx_net": "Rede", "lx_gpu": "Placa de vídeo", "lx_tools": "Ferramentas de jogo"}
CPU = "/sys/devices/system/cpu/cpu*/cpufreq/"
THP = "/sys/kernel/mm/transparent_hugepage/"


def has_zram() -> bool:
    try:
        return any(ln.split()[0].startswith("/dev/zram") for ln in open(P("/proc/swaps")).read().splitlines()[1:])
    except (OSError, IndexError):
        return False


def has_nvidia() -> bool:
    return os.path.exists(P("/proc/driver/nvidia/version")) or bool(shutil.which("nvidia-smi"))


def load() -> list[Tweak]:
    """Registra os ajustes de Linux (uma vez) e devolve a lista."""
    CATS.update(LINUX_CATS)
    if "lx_governor" in CATALOG:
        return linux_tweaks()
    register(
        # ------------------------------------------------------------ processador e energia
        Tweak("lx_governor", "Processador em modo desempenho",
              "Governador 'performance' em todos os núcleos: o processador não espera a carga subir para "
              "aumentar o clock.",
              "lx_cpu", [Sysfs(CPU + "scaling_governor", "performance", "governor")], ESSENTIAL,
              gain="Menos quedas de FPS quando a carga muda de repente.",
              loss="Mais consumo e calor em repouso. Se o power-profiles-daemon ou o TLP estiverem ativos, "
                   "eles podem trocar o governador de volta."),
        Tweak("lx_epp", "Preferência de energia: desempenho",
              "energy_performance_preference = performance (drivers amd-pstate e intel_pstate): o processador "
              "prioriza clock alto em vez de economia.",
              "lx_cpu", [Sysfs(CPU + "energy_performance_preference", "performance", "epp")], RECOMMENDED,
              gain="Resposta mais rápida do processador.", loss="Mais consumo em repouso."),
        Tweak("lx_split_lock", "Sem punição de split lock",
              "kernel.split_lock_mitigate = 0: o kernel deixa de atrasar de propósito programas que fazem "
              "'split lock', o que alguns jogos Windows fazem pelo Proton.",
              "lx_cpu", [Sysctl("kernel.split_lock_mitigate", 0)], RECOMMENDED,
              gain="Evita travadas fortes nos jogos que disparam essa proteção.",
              loss="Um programa mal comportado pode atrasar os outros núcleos por instantes."),
        Tweak("lx_nmi_watchdog", "Desligar o NMI watchdog",
              "kernel.nmi_watchdog = 0: desliga o vigia que interrompe os núcleos periodicamente para detectar "
              "travamento do kernel.",
              "lx_cpu", [Sysctl("kernel.nmi_watchdog", 0)], ADVANCED,
              gain="Menos interrupções periódicas.",
              loss="Se o kernel travar de verdade, não haverá o relatório automático."),
        # ------------------------------------------------------------ memória e kernel
        Tweak("lx_max_map_count", "Limite de mapas de memória alto",
              "vm.max_map_count = 1048576 (ou mais): jogos pelo Proton abrem muitos mapeamentos de memória e "
              "fecham sozinhos se o limite for o padrão antigo do kernel. O Arch já vem assim.",
              "lx_mem", [Sysctl("vm.max_map_count", 1048576, at_least=True)], ESSENTIAL,
              gain="Evita fechamentos em jogos grandes."),
        Tweak("lx_swappiness", "Usar menos a troca em disco",
              "vm.swappiness = 10: o kernel só manda memória para o swap quando a RAM está realmente no fim.",
              "lx_mem", [Sysctl("vm.swappiness", 10)], RECOMMENDED, when=lambda: not has_zram(),
              gain="Menos engasgos por leitura de swap em disco.",
              loss="Com zram (swap comprimido na RAM), o recomendado é o contrário: valor alto."),
        Tweak("lx_compaction", "Sem compactação proativa de memória",
              "vm.compaction_proactiveness = 0: o kernel deixa de reorganizar a memória em segundo plano.",
              "lx_mem", [Sysctl("vm.compaction_proactiveness", 0)], RECOMMENDED,
              gain="Tempo de quadro mais constante.", loss="Páginas grandes ficam um pouco mais difíceis de alocar."),
        Tweak("lx_watermark_boost", "Menos recuperação de memória em rajada",
              "vm.watermark_boost_factor = 1: reduz a recuperação agressiva de memória depois de fragmentação.",
              "lx_mem", [Sysctl("vm.watermark_boost_factor", 1)], RECOMMENDED,
              gain="Menos picos de latência por recuperação de memória."),
        Tweak("lx_page_lock", "Trava de página mais justa",
              "vm.page_lock_unfairness = 1: reduz a espera de quem aguarda uma página já em uso.",
              "lx_mem", [Sysctl("vm.page_lock_unfairness", 1)], RECOMMENDED,
              gain="Menos latência em disputas de memória."),
        Tweak("lx_zone_reclaim", "Sem recuperação por zona",
              "vm.zone_reclaim_mode = 0: o kernel não tenta recuperar memória zona a zona (já é o padrão na "
              "maioria dos PCs).",
              "lx_mem", [Sysctl("vm.zone_reclaim_mode", 0)], ESSENTIAL),
        Tweak("lx_min_free", "Reserva de 1 GB de memória livre",
              "vm.min_free_kbytes = 1048576 e vm.watermark_scale_factor = 500: o kernel mantém uma folga de "
              "memória livre para alocações não precisarem esperar.",
              "lx_mem", [Sysctl("vm.min_free_kbytes", 1048576), Sysctl("vm.watermark_scale_factor", 500)], ADVANCED,
              gain="Menos travadas quando a memória está cheia.",
              loss="Cerca de 1 GB de RAM fica reservado. Não use com menos de 16 GB."),
        Tweak("lx_thp", "Páginas grandes só para quem pede",
              "Transparent Huge Pages em 'madvise', memória compartilhada em 'advise' e sem desfragmentação "
              "automática: só os programas que pedem páginas grandes recebem.",
              "lx_mem", [Sysfs(THP + "enabled", "madvise", "thp_enabled"),
                         Sysfs(THP + "shmem_enabled", "advise", "thp_shmem"),
                         Sysfs(THP + "defrag", "never", "thp_defrag")], RECOMMENDED,
              gain="Evita travadas da desfragmentação de páginas grandes.",
              loss="Programas que dependiam de páginas grandes automáticas podem usar um pouco mais de CPU."),
        # ------------------------------------------------------------ disco
        Tweak("lx_nvme_sched", "NVMe sem fila do kernel",
              "Agendador 'none' nos discos NVMe: o SSD organiza a própria fila (já é o padrão na maioria das "
              "instalações).",
              "lx_disk", [Sysfs("/sys/block/nvme*/queue/scheduler", "none", "nvme_scheduler")], ESSENTIAL,
              gain="Menos trabalho do processador a cada leitura."),
        # ------------------------------------------------------------ rede
        Tweak("lx_tcp_idle", "TCP sem recomeço lento após pausa",
              "net.ipv4.tcp_slow_start_after_idle = 0: a conexão não volta à velocidade inicial depois de um "
              "instante sem tráfego.",
              "lx_net", [Sysctl("net.ipv4.tcp_slow_start_after_idle", 0)], RECOMMENDED,
              gain="Resposta mais constante em jogos que usam TCP, como o BDO."),
        Tweak("lx_tcp_mtu", "Descoberta de MTU no TCP",
              "net.ipv4.tcp_mtu_probing = 1: o kernel ajusta o tamanho dos pacotes quando a rota descarta os "
              "grandes sem avisar.",
              "lx_net", [Sysctl("net.ipv4.tcp_mtu_probing", 1)], RECOMMENDED,
              gain="Evita conexões que travam em rotas com MTU menor (VPN, alguns provedores)."),
        Tweak("lx_tcp_fastopen", "TCP Fast Open",
              "net.ipv4.tcp_fastopen = 3: permite enviar dados já na abertura da conexão, quando o servidor aceita.",
              "lx_net", [Sysctl("net.ipv4.tcp_fastopen", 3)], RECOMMENDED,
              gain="Conexões novas abrem um pouco mais rápido."),
        Tweak("lx_bbr", "Controle de congestionamento BBR",
              "Carrega o módulo tcp_bbr e usa BBR com a fila 'fq': o envio se ajusta pela banda medida, não só "
              "pela perda de pacotes.",
              "lx_net", [ConfFile("/etc/modules-load.d/chinese-control-bbr.conf", "tcp_bbr\n", modprobe="tcp_bbr"),
                         Sysctl("net.core.default_qdisc", "fq"),
                         Sysctl("net.ipv4.tcp_congestion_control", "bbr")], ADVANCED,
              gain="Envio mais estável em conexões com perda.",
              loss="Afeta principalmente upload; em jogo o efeito costuma ser pequeno. A fila 'fq' só vale "
                   "para as interfaces depois de reiniciar.", restart=True),
        # ------------------------------------------------------------ placa de vídeo
        Tweak("lx_nv_shader_cache", "Cache de shaders da NVIDIA maior e permanente",
              "__GL_SHADER_DISK_CACHE_SIZE = 12 GB e __GL_SHADER_DISK_CACHE_SKIP_CLEANUP = 1: o driver deixa de "
              "apagar shaders já compilados quando o cache passa do limite padrão.",
              "lx_gpu", [UserEnv("__GL_SHADER_DISK_CACHE_SIZE", "12000000000"),
                         UserEnv("__GL_SHADER_DISK_CACHE_SKIP_CLEANUP", "1")], RECOMMENDED, when=has_nvidia,
              gain="Menos travadas de compilação de shader em jogos grandes, de uma sessão para a outra.",
              loss="O cache pode ocupar até 12 GB na sua pasta pessoal. Vale no próximo login.", restart=True),
        # ------------------------------------------------------------ ferramentas
        Tweak("lx_gamemode", "Instalar o GameMode",
              "Pacotes gamemode e lib32-gamemode (precisa do repositório multilib). Com 'gamemoderun' nas opções "
              "de inicialização, o jogo recebe prioridade e o processador vai para desempenho só durante a partida.",
              "lx_tools", [Package("gamemode", "lib32-gamemode")], ESSENTIAL,
              gain="Otimizações aplicadas só enquanto o jogo está aberto."),
        Tweak("lx_mangohud", "Instalar o MangoHud",
              "Pacotes mangohud e lib32-mangohud (precisa do repositório multilib): o contador de FPS, tempo de "
              "quadro e temperaturas por cima do jogo.",
              "lx_tools", [Package("mangohud", "lib32-mangohud")], RECOMMENDED,
              gain="FPS e sensores na tela, configurados na aba MangoHud."),
    )
    return linux_tweaks()


def linux_tweaks() -> list[Tweak]:
    return [t for t in CATALOG.values() if t.cat in LINUX_CATS]


def recommended() -> list[Tweak]:
    """O que o botão 'Aplicar recomendados' aplica: essenciais e recomendados que valem neste PC."""
    return [t for t in linux_tweaks() if t.recommended_here() and t.reversible]
