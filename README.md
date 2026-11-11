# Chinese Control

Otimizador de Windows **para jogos** — com otimização por jogo para tudo que estiver instalado e um módulo especial
para **Black Desert Online** (Guerra de Nodes e Cerco). Feito em Python + PySide6. Versão 2.2.0. Interface em português, inglês e espanhol.
Reimplementação limpa das funções de um otimizador comercial: código, textos e valores próprios, sem
reaproveitar nada do programa original.

## Como usar

**Rodar direto do código** (precisa do Python 3.11+): dê dois cliques em `rodar.bat`. Na primeira vez ele cria
um ambiente virtual e instala as dependências. O app pede administrador ao abrir.

**Baixar o instalador pronto:** aba [Releases](https://github.com/Pedroedmachado/lolitos-otimizas/releases) — cada push na `main` gera o `Setup.exe` pelo GitHub Actions.

**Gerar o instalador no seu PC (Setup.exe):** dê dois cliques em `gerar-instalador.bat`. Ele instala sozinho pelo winget o
que faltar (Python 3.12 e Inno Setup 6), gera o programa e monta `dist\ChineseControl-2.2.0-Setup.exe`.
O instalador tem assistente em português, inglês ou espanhol (o app abre no idioma escolhido), termos de uso, atalhos, opção de iniciar com o Windows, fecha o app
antes de atualizar e desinstalador (que pergunta se apaga histórico e backups).

Dados do app (histórico, backups, perfis, config): `%LOCALAPPDATA%\ChineseControl`.

## O que tem

A barra lateral é dividida em quatro seções:

| Seção | Tela | O que faz |
|---|---|---|
| Principal | **Painel** | Pontuação de otimização, **Boost em um clique**, uso ao vivo, atalhos e resumo do check-up |
| | **Manutenção** | SFC, DISM, CHKDSK, reset do Windows Update, Explorer, áudio, Bluetooth, spooler, ícones, Store, driver de vídeo, .NET 3.5, rede |
| | **Desempenho** | CPU, RAM, GPU, VRAM, temperaturas, disco e rede ao vivo, com mín./máx. e gravação em CSV |
| | **Meu PC** | Perfil do PC, CPU, RAM (XMP/EXPO, dual channel), placa-mãe/BIOS, GPU (link PCIe), monitores, discos; **Copiar minha configuração** |
| | **Black Desert** | Pacote de Windows para Guerra, `GameOption.txt` (Guerra/Cerco, PvP, Grind, AFK), latência real até o servidor, travamentos e caches |
| Otimizar | **Formatação** | Windows recém-instalado pronto de uma vez: ponto de restauração, ajustes recomendados, debloat, programas e limpeza |
| | **Debloat** | Apps pré-instalados, recursos opcionais do Windows e OneDrive |
| | **Windows** | Ajustes em abas: desempenho, jogos, rede, privacidade, interface, atualizações, segurança, apps |
| | **Mouse / Teclado / GPU** | Ajustes de cada assunto (aceleração do mouse, atalhos que atrapalham, agendamento da GPU, taxa do monitor) |
| | **Perfis** | Pacotes prontos + perfis próprios com exportar/importar |
| | **Jogos** | Detecta os jogos instalados; Preparar e jogar; Otimizar este jogo |
| | **Instalar apps** | Centenas de programas pelo winget (catálogo WinUtil), por categoria, com atualizar todos |
| | **Limpeza / Inicialização** | Temporários, caches e RAM; programas que abrem com o Windows |
| Ferramentas | **Overlay de jogo** | FPS (PresentMon), CPU/GPU, temperaturas, VRAM, RAM e ping por cima do jogo |
| | **Teste do mouse** | Polling rate real |
| | **Teste de monitor** | Movimento/ghosting com faixas de quadros, cores e pixels, OLED e vazamento de luz |
| | **Teste de velocidade** | Download, upload, ping, variação e bufferbloat (Cloudflare), com histórico |
| | **Perda de pacotes** | Teste de 30 s ou 2 min, rota salto a salto, exportar CSV e reparos rápidos |
| | **Comparar placas** | Índice próprio de desempenho em jogos de ~95 placas, com a sua destacada |
| | **Defender e IA** | Antivírus (liberar o app) e recursos de IA do Windows |
| | **Check-up** | Todos os itens medidos, com Corrigir, exportar relatório e copiar configuração |
| Sistema | **Restauração / Configurações** | Histórico com desfazer, pontos de restauração; idioma, tema, bandeja, atualizações |

## Novidades da 2.5.1

* **Debloat em tabela:** cada item é uma linha com as colunas Nível, Ajuste, O que faz, Estado e Desfazer.
  * O nível aparece em cores: Essencial, Recomendado e Avançado.
  * Nos avançados, o que se perde aparece em amarelo logo abaixo da descrição.
  * Os prós e contras completos aparecem ao passar o mouse.
* **Black Desert de volta ao Boost:** quando o jogo está instalado, o Boost também aplica:
  * prioridade alta para o BDO;
  * placa de vídeo dedicada;
  * Filtro de tela desligado no UserCache;
  * perfil NVIDIA do BDO (só em placa NVIDIA).

  Sem o jogo no PC, esses itens ficam de fora sozinhos e não contam na pontuação.

## Novidades da 2.5.0

* **Troca de tela com efeitos:** a tela anterior se desfoca enquanto some e o título da nova é digitado. No menu, o
  destaque desliza do item antigo até o novo.
* **Desempenho refeito:** um gráfico por componente (processador, memória, placa de vídeo, disco e rede), cada um com
  a sua cor. Embaixo de cada um aparecem os detalhes: modelo, núcleos, clock, temperatura, pentes, VRAM, leitura e
  escrita. A rede mostra o upload numa linha cinza.
* **Painel com Informações do Sistema:** um cartão novo mostra o computador, o Windows, o processador e os núcleos,
  a memória, há quanto tempo o PC está ligado, a placa de vídeo, a placa-mãe, os discos, o Secure Boot e o TPM.
* **Inicialização em lista:** cada programa aparece com o ícone, o caminho, para quem vale ("Usuário" ou "Todos os
  usuários") e uma chave liga/desliga. No topo ficam a contagem de ativos e desativados e o botão Atualizar.
* **Configurações reorganizadas** em seções: Aparência, Inicialização, Atualizações, Segurança, Preparar e jogar,
  Dados do aplicativo e Sobre.
  * O tema se troca com botões (Escuro, Claro, Azul).
  * A seção Atualizações mostra a versão instalada e tem o botão "Procurar agora".
* **Apresentação do app:** na primeira abertura, uma volta guiada destaca o menu, a pontuação, o Boost e as telas
  principais. Para rever, use Configurações › Aparência.
* **Check-up ao vivo:** todos os itens aparecem como "Medindo…" e se preenchem um a um. As consultas lentas do
  Windows começam em paralelo, sem segurar as rápidas.

## Novidades da 2.4.3

* **Boost igual ao do app de referência:**
  * Aplica a mesma lista de 80 ajustes, na mesma ordem. Entraram *Liberar o armazenamento reservado*, *Remover o
    componente Recall*, *Remover os apps de IA* e o *nome no menu de inicialização*.
  * Saíram do Boost itens de aparência e de apps (menu clássico, esconder pesquisa, Nagle, Brave, Discord…); eles
    continuam nas telas deles e na Otimização Completa.
  * Itens que não valem para o seu PC (Windows 10, notebook etc.) ficam de fora sozinhos.
* **Limpeza do Boost mais completa:** temporários do usuário e do Windows, cache do Windows Update, cache de
  Otimização de Entrega, relatórios de erro e cache de miniaturas (apagado com o Explorer fechado e reaberto em
  seguida).
* **Relatório do Boost em seções:** ponto de restauração, *Já aplicados neste PC* com a lista ✓, cada ajuste aplicado
  (*Feito.* ou *Feito. Vale após reiniciar.*), cada limpeza com o quanto liberou e a RAM liberada.

## Novidades da 2.4.2

* **Boost completo não trava mais.** Quando um ajuste pedia para reiniciar o Explorer, a janela do Boost ficava
  esperando para sempre. Os comandos do app agora sempre voltam, mesmo quando abrem outro programa, e quem passa
  do tempo é encerrado junto com o que abriu.
* A janela do Boost (e de qualquer tarefa) mostra há quanto tempo está rodando, avisa quando o Windows está
  demorando num passo e tem *Continuar em segundo plano*.
* Se não der para criar o ponto de restauração, o Boost avisa e segue em vez de esperar 10 minutos.
* **Pontuação de otimização voltou a funcionar.**
  * O ponteiro do velocímetro ficava parado no zero (a animação nova não aceitava a nota inteira).
  * A análise ficou mais leve: a saúde dos discos só é lida no Meu PC, e o hardware fica guardado por
    10 minutos.
  * O check-up do Windows tem tempo máximo e não segura mais a nota.

## Novidades da 2.4.1

* **Debloat avançado corrigido:**
  * Os itens *Remover …* de recursos do Windows (Gravador de Passos, Matemática, escrita à mão, Hello facial, fala,
    vozes, WordPad, Fax e Scanner, sincronização de contas) agora conferem o estado de verdade. Depois de removidos
    aparecem como ativos, e os que não existem na sua versão do Windows aparecem como *não se aplica*.
  * Se o Windows recusar a remoção, o motivo aparece na tela.
  * O *Desfazer* reinstala só o que foi removido, e não os pacotes de todos os idiomas.
  * *Remover o OneDrive* usa o desinstalador do próprio OneDrive (o winget muitas vezes não achava a instalação) e
    confere no fim se ele saiu mesmo.
  * *Liberar o armazenamento reservado* explica o erro quando há atualização em andamento.

## Novidades da 2.4.0

* **Debloat refeito numa tela só:**
  * *Essencial e Recomendado*: Edge, Widgets, Teams, telemetria, Copilot, Recall, propagandas e afins. O que ainda
    não está aplicado já vem marcado; tem *Marcar todos* e *Desmarcar todos*.
  * *Avançados*: SysMain, indexação, hibernação, OneDrive, recursos opcionais do Windows. Nada vem marcado e cada
    item mostra o que se perde; dá para esconder a seção.
  * *Apps pré-instalados*: só os que existem na sua conta, em caixinhas, com *Atualizar lista* e
    *Remover selecionados*.
  * Um botão *Aplicar selecionados (N)* para tudo, com ponto de restauração antes.
  * Novos itens: *Bloquear instalação automática de software de periféricos* e *Remover reconhecimento de escrita
    à mão*.
* **Meu PC em abas:**
  * *Processador*: codinome, arquitetura, família, modelo, stepping, tecnologia, TDP, microcódigo, instruções e
    clocks ao vivo.
  * *Caches* L1, L2 e L3 com vias e linha.
  * *Placa-mãe*: chipset, revisão, BIOS e sistema.
  * *Memória* e *Slots de memória*, incluindo os slots vazios.
  * *Gráficos*: fabricante da placa, arquitetura, núcleos CUDA, TDP, barramento, clocks máximos, VBIOS, PCIe e
    leitura ao vivo.
  * *Armazenamento*: temperatura, desgaste e horas ligado.
  * *Check-up do hardware*: dual channel, pentes em A2/B2, pentes iguais, XMP/EXPO, quantidade de RAM, linhas PCIe
    da placa de vídeo, saúde dos discos e virtualização.
  * Clicar numa peça do desenho da placa abre a aba dela, e o *Exportar relatório…* salva tudo em texto.
* **Efeitos visuais em três níveis** (Configurações ou menu do Tema):
  * *Desligados*.
  * *Básicos*: vidro, brilho ao passar o mouse em qualquer botão, chaves que deslizam, telas que esmaecem e
    velocímetro que sobe até a nota.
  * *Completos*: tudo do básico, mais onda ao clicar, reflexo nos botões principais, luz que segue o mouse,
    cartões que levantam com sombra e telas que entram deslizando.

## Novidades da 2.3.0

* **Núcleos da CPU para o BDO (processadores AMD)**, no estilo do Process Lasso: nova aba no Black Desert com as
  threads por CCD e núcleo (mostra qual CCD tem o 3D V-Cache), escolhas rápidas (recomendado, só o CCD do V-Cache,
  um thread por núcleo, sem o núcleo 0…) e dois métodos: *Afinidade de CPU* (rígida) ou *CPU Sets* (flexível). Com a
  regra ligada, o app aplica sozinho toda vez que o BlackDesert64.exe abre e de novo se o jogo mudar. É o mesmo
  *Definir afinidade* do Gerenciador de Tarefas: nada é injetado no jogo.
* **Black Desert atualizado com o guia de FPS do BDO:**
  * *Filtro de tela desligado de verdade*: coloca PostFilter = 0 nos gamevariable.xml da pasta UserCache (conta e
    personagens), com backup; só essa linha muda.
  * *Perfil NVIDIA do BDO* agora também grava baixa latência Ultra com 1 quadro pré-renderizado, V-Sync desligado,
    energia em desempenho máximo, filtragem anisotrópica 8x e filtragem de textura em alto desempenho com viés LOD
    travado. Quem já aplicou o perfil antigo só precisa clicar em *Aplicar no driver* de novo.
  * Novo ajuste avançado para desativar o *Timer de eventos de alta precisão (HPET)*, com desfazer.
  * Predefinição *Guerra* do GameOption com a transparência de efeitos no mínimo (30%).
  * *Checklist fora do app* refeito: o que ligar e desligar em cada aba de configurações do jogo, Painel NVIDIA ou
    AMD Adrenalin (aparece só o da sua placa), configurações de gráficos do Windows, memória virtual e Resizable BAR.

## Novidades da 2.2.0

* **Temperatura da CPU no overlay**, lida do sensor do próprio processador (Ryzen: Tctl/Tdie; Intel: pacote) pelo
  **PawnIO**, driver assinado e de código aberto (o mesmo do LibreHardwareMonitor). Ele é instalado só quando você
  clica em *Ativar a temperatura do processador* na tela do Overlay; os módulos assinados vêm com o app. Também vale
  para o Hardware Monitor e o Meu PC. Sem o PawnIO, continua o LibreHardwareMonitor (se aberto) ou a placa-mãe.
* O overlay não abre mais o PowerShell a cada poucos segundos quando não acha temperatura (pesava no jogo).

## Novidades da 2.1.0

* **Clipes de novo, no formato completo:**
  * *Componente de gravação*: o gravador é baixado só quando você clica em *Baixar e ativar Clipes*.
  * *Captura*: estado (ligada, desligada, gravando), botões **Ligar captura**, **Salvar clipe** e **Gravar**, e
    **atalhos que você escolhe** (padrão Alt+Home e Alt+End), com aviso quando outro programa já usa o atalho.
  * *Configurações em botões*: quanto guardar (15 s a 5 min), qualidade (Leve, Equilibrada, Alta), 30/60 FPS,
    **tamanho do vídeo** (720p, 1080p, 1440p ou original), **o que capturar** (só a janela do jogo ou a tela
    inteira) e som (só o jogo, todo o PC ou sem som), com quanto o buffer ocupa no disco.
  * **Ligar sozinho quando um jogo abrir**: com isso desligado, nada fica rodando até você ligar a captura.
  * Pasta dos clipes (trocar e abrir) e clipes recentes.

## Novidades da 2.0.1

* **Clipes com áudio limpo:** o som não pipoca nem corta mais. Cada pacote de áudio entra no lugar certo pelo
  horário que o Windows marca (antes o app completava com silêncio quando a leitura atrasava, gerando estalos), a
  captura tem 1 s de folga e não espera o gravador, os pedaços são emendados como um fluxo contínuo e o áudio
  sai em AAC 192 kb/s, 48 kHz.

## Novidades da 2.0.0

* **Visual de vidro com animações**, em três temas: **Escuro**, **Claro** (vidro líquido) e **Azul**. Troque em
  Configurações ou pelo botão *Tema* no fim do menu. O menu recolhido cresce suavemente ao passar o mouse e as
  telas entram com uma animação curta. Em PCs mais fracos, desligue em Configurações › *Efeitos visuais*.
* **Clipes** (Ferramentas): **Alt+Home** salva os últimos segundos do jogo e **Alt+End** começa/para uma
  gravação, com o **som só do jogo** (Windows 11; no Windows 10 antigo, o som do PC). A placa de vídeo codifica
  (NVENC, AMF ou Quick Sync) e o vídeo sai pronto na hora. O gravador (ffmpeg) é baixado pelo winget só quando você
  ativa os Clipes, e só roda com um jogo em primeiro plano.
* **Meu PC:** desenho da placa-mãe com o processador, as memórias nos encaixes, a placa de vídeo, os SSDs e o
  chipset. Passe o mouse em cada peça para ver os detalhes.
* **Ajustes com etiquetas** (FPS, Input lag, Rede, Limpeza, Privacidade) e **filtro por objetivo**. Cada cartão diz
  se foi ativado pelo Chinese Control ou se já estava assim, e o **Saiba mais** mostra exatamente o que muda.
* **Iniciar com o Windows** vem marcado no instalador e fica na bandeja. Agora abre também no notebook na bateria e
  não para depois de dias ligado (a tarefa antiga é recriada sozinha).
* **Atualizações mais confiáveis:** tenta de novo quando a primeira tentativa falha e confere a cada 6 horas
  enquanto o app está na bandeja.
* **Correção:** o Painel podia ficar parado em "Analisando" e o Boost não liberava. Agora a análise sempre termina
  e, se algo falhar, o app tenta de novo sozinho.

## Novidades da 1.9.0

* **Revisão semanal** (Manutenção): disco, imagem do Windows (DISM) e arquivos do sistema (SFC), com botão
  *Rodar agora* e opção de rodar sozinha todo domingo (se o PC estiver desligado, roda no próximo login).
* **Painel:** cartão *Ações recomendadas* com os ajustes que faltam e um botão Aplicar em cada um.
* **Formatação:** *Aplicar também para contas criadas depois neste PC* (os ajustes por usuário vão para o perfil
  padrão do Windows).
* **Perfis:** cartão *Padrão do Windows*, que desfaz tudo que o app aplicou.
* **Jogos:** os núcleos escolhidos são conferidos a cada 10 s e aplicados de novo se o jogo os trocar.
* **Overlay, Painel e Hardware Monitor:** uso e VRAM da placa de vídeo também em AMD e Intel (contadores do
  Windows, escolhendo a placa dedicada).
* **Limpeza:** cache de DNS na lista.
* **Ajustes novos:** Iniciar sem a seção Recomendados, central de notificações e calendário, clique direito completo
  com muitos arquivos, tirar *Transmitir para dispositivo* e *Solucionar problemas de compatibilidade* do clique
  direito, nome no menu de inicialização, .NET 3.5, não registrar apps mais abertos, tarefas de coleta de dados,
  movimento em segundo plano, apps em segundo plano por política, registro do Relatório de Erros, spooler e
  coletor de diagnóstico sob demanda, Mecanismo de Compatibilidade, remover sincronização de Email/Calendário e
  Conexão de Área de Trabalho Remota, **Mouse sem atrasos**. A tela GPU mostra também o PCI Express.
* Menu lateral recolhe sozinho em janela estreita; a janela abre a partir de 800×600.

## Novidades da 1.8.0

* Novo nome: **Chinese Control** (antes Lolitos Control) e novo logo: um **C** azul com um ponto aceso na abertura.
  Quem já usa recebe pela atualização normal: o instalador troca o executável e os atalhos, e o app traz o
  histórico, os backups, as configurações, a tarefa de iniciar com o Windows e o plano de energia do nome antigo.
* **Black Desert:** perfil do BDO no Painel de Controle NVIDIA, gravado direto no driver pela NVAPI (taxa de
  atualização mais alta, otimização encadeada, Ansel desligado, correção de gama, G-SYNC desligado no jogo), com
  desfazer e importação de arquivos `.nip` do NVIDIA Profile Inspector.

## Novidades da 1.7.3

* **Check-up** com o valor medido à direita e itens novos: arquivos temporários, Lixeira, Windows.old, memória em
  uso, último ponto de restauração, firewall, UAC, plataforma para Windows 11, ativação, internet, saúde dos discos,
  dispositivos com problema, falhas de programas e bateria.

## Novidades da 1.7.2

* **Windows, Mouse, Teclado e GPU** em cartões com chave liga/desliga: selos Recomendado/Reinicia/Avançado, aviso
  'Evite se…', estado lido do Windows, contador de ativos, *Aplicar recomendados*, filtros por área e *Salvar perfil*.
* **Limpeza** nova: espaço livre do disco, lixo por categoria em barras com o total selecionado, memória RAM e a
  lista do que limpar com o tamanho de cada item.

## Novidades da 1.7.1

* Corrigidas as janelinhas brancas 'Lolitos Control' que piscavam na tela: blocos de app, capas de jogos e as
  caixas de marcar dos ajustes eram mostrados antes de entrar na tela. Um teste automático agora barra isso.

## Novidades da 1.7.0

* **Interface nova:** barra lateral com logo, bandeiras de idioma, *Recolher menu* e ícones de linha do Windows;
  cada tela com cabeçalho de ícone, blocos de número e chaves liga/desliga.
* **Painel:** saudação, aviso de otimização pendente, velocímetro da pontuação, cartões de pontos de restauração,
  arquivos para limpar e memória, atalho para Windows recém-formatado e monitor em tempo real (CPU, GPU, RAM, disco,
  rede) com gráfico de 60 s.
* **Hardware Monitor (novo):** clock e uso de cada núcleo, temperaturas, clocks e energia da placa de vídeo, memória,
  discos e rede, com mínimo, máximo e gravação em CSV.
* **Otimização Completa (nova):** tudo que é recomendado para o PC, por área, aplicado de uma vez.
* **Formatação e Instalar apps** em grade com ícones, filtros por categoria, instalados, selecionados e código aberto;
  Boost completo, extras (Visualizador de Fotos clássico, remover OneDrive) e *Iniciar configuração*.
* **Ferramentas refeitas:** teste do mouse com Atual/Máximo/Resposta/Amostras; overlay com prévia ao vivo, formato
  vertical ou horizontal, tamanho, tempo de quadro, 1% low, clocks e nome do jogo; teste de monitor com seus monitores,
  taxa máxima e opções do teste de movimento; teste de velocidade com botão INICIAR; perda de pacotes com blocos de
  número; Defender e IA; check-up em lista.

## Novidades da 1.6.2

* **Jogos** em grade de capas (a arte vertical da biblioteca da Steam; jogos de outras lojas são procurados pelo nome
  na loja da Steam). Clique na capa para as opções do jogo, ▶ para Preparar e jogar, botão direito para escolher
  outra capa. Filtro por loja.
* **FPS no overlay corrigido:** o PresentMon 2.6 (Intel, MIT) agora vem no instalador; o overlay mede todos os
  processos e mostra o jogo em primeiro plano, e reinicia a medição sozinho se ela cair. Botão para baixar o
  PresentMon dentro do app, com o arquivo conferido por SHA-256.

## Novidades da 1.6.1

* **Formatação** com 112 programas em 10 categorias (essenciais para jogos — Visual C++ 2005 a 2022, DirectX,
  .NET, XNA, PhysX, Java —, navegadores, comunicação, lojas e launchers, hardware e monitoramento, gravação e
  streaming, música e vídeo, utilitários, documentos, programação), com busca, marcar categoria inteira e aviso dos
  que já estão instalados. IDs conferidos no repositório oficial do winget.

## Novidades da 1.6.0

* Barra lateral reorganizada em **Principal, Otimizar, Ferramentas e Sistema**, com telas separadas por assunto.
* **Idiomas:** português, inglês e espanhol (Configurações › Idioma). O instalador também pergunta o idioma.
* Ferramentas novas ou ampliadas: Formatação, Comparar placas, Check-up com relatório, Teste de velocidade com
  histórico, Perda de pacotes com teste de 2 minutos e CSV, teste de monitor com objetos, cores e faixas de quadros,
  Instalar apps com categorias e "atualizar todos".

## Novidades da 1.5.0

* Botão **Atualizar** na barra lateral, ligado ao GitHub Releases: baixa o instalador novo, confere tamanho e
  SHA-256, instala sem janelas e reabre o app sozinho (histórico, perfis e configurações são mantidos).
* O app procura atualização ao abrir e avisa quando há versão nova (dá para desligar em Configurações).
* Quem está na 1.4.0 ou anterior instala a 1.5.0 manualmente uma vez; daí em diante é pelo botão.

## Novidades da 1.4.0

* Novo nome: **Lolitos Control** (antes Lolitos Otimizações) e novo ícone: um **L azul**.
* Quem tem a versão antiga pode instalar por cima: o instalador remove o executável e os atalhos antigos, e o app
  traz histórico, backups e configurações da pasta antiga.

## Novidades da 1.3.2

* Sem a piscada ao trocar de tela: a janela não é mais reativada a cada clique no menu.
* As telas são montadas em segundo plano logo depois que o app abre, sem desenho pela metade.
* Iniciar com o Windows (`--tray`) volta a abrir só na bandeja.

## Novidades da 1.3.1

* **Fim das travadas ao trocar de tela**: a tecla global do overlay roda numa thread própria (antes cada mensagem
  do Windows passava pelo Python e a janela congelava), as verificações de estado rodam no máximo 2 por vez,
  as abas de Ajustes são montadas só quando abertas e a temperatura da CPU não é mais lida na thread da interface.
* **Barra de rolagem** estilizada por completo, sem rastros ao rolar.
* **Novo visual azul-escuro**, ícone e instalador incluídos.

## Novidades da 1.3.0 — análise do PC

* O app analisa cada máquina (processador, P-cores/E-cores da Intel, Ryzen X3D, placa dedicada ou integrada,
  SSD/HD, RAM, Wi-Fi, notebook) e classifica em **PC modesto, intermediário ou forte**.
* O **Boost** e os pacotes só recomendam o que ajuda naquele hardware. Exemplos: SysMain continua ligado com o
  Windows em HD; HAGS só em placas que suportam; economias de energia mantidas em notebook; compressão de memória
  mantida com pouca RAM; efeitos visuais só cortados em PCs modestos/intermediários; telemetria NVIDIA só com NVIDIA.
* **Na primeira abertura** aparece a análise do PC com dicas e a opção de aplicar o recomendado para ele.
* Card **Seu PC** no Painel mostra o perfil, o que o Boost deixou de fora e por quê.
* **Afinidade inteligente** em Jogos: "Só P-cores" em Intel híbrido e "CCD com 3D V-Cache" em Ryzen X3D de dois CCDs
  (as opções só aparecem quando o processador tem isso).

## Novidades da 1.2.1

* "Preparar e jogar" atualiza o status na tela (antes ficava em "Preparando…" mesmo depois de fechar o jogo).
* Trocar de tela não tira mais a janela do modo maximizado.

## Novidades da 1.2.0

* Foco em todos os jogos: a tela **Jogos** vem logo depois do Painel e cada jogo tem o seu painel de otimização.
* Mais launchers detectados (GOG, Ubisoft e jogos instalados por EA app, Riot, Battle.net, Rockstar, Garena…).
* Banco de ~30 jogos conhecidos: executável certo, anti-cheat e avisos (ex.: Vanguard exige TPM/Secure Boot).
* Pacote **Jogos online competitivos**; overlay mede o FPS de qualquer jogo detectado aberto.
* Tela cheia sem FSO agora **mantém** outras flags de compatibilidade do executável.

## Segurança e anti-cheat

* Nada é injetado no jogo e a memória dele nunca é lida. Prioridade/afinidade usam as mesmas APIs do
  Gerenciador de Tarefas; o servidor do BDO é descoberto pela tabela de conexões do Windows.
* Cada ajuste guarda o valor anterior e volta exatamente a ele. Chaves criadas pelo app são apagadas ao desfazer.
* O `GameOption.txt` só tem alteradas chaves que já existem; sempre há backup (o primeiro fica salvo como
  `GameOption-ORIGINAL.txt`). O app recusa gravar com o jogo aberto.
* A pasta `UserCache` do BDO (atalhos, skills, layout) nunca é tocada.

## O que ficou de fora (e por quê)

* **Assinatura/login/Hotmart e consultoria remota** — não fazem sentido num app seu.
* **Driver PawnIO** (temperatura da CPU direto do sensor e timings de RAM ao vivo) — exige driver de kernel.
  A temperatura da CPU é lida do LibreHardwareMonitor quando ele está aberto.
* **Ranking de placas de vídeo** — dados proprietários do app original.
* **Atualizador automático assinado**, assistente único de "Windows recém-formatado" e revisão semanal
  agendada — dá para adicionar depois (os blocos já existem: perfis, winget e ferramentas).

## Créditos

* Catálogo de apps: [WinUtil](https://github.com/ChrisTitusTech/winutil) de Chris Titus Tech — licença MIT
  (`lolitos/data/WINUTIL_LICENSE.txt`).
* FPS: [PresentMon](https://github.com/GameTechDev/PresentMon) da Intel — licença MIT, baixado à parte.

## Estrutura

```
lolitos/
  core/       registro, ações reversíveis, motor de aplicar/desfazer, histórico, ponto de restauração
  catalog/    todos os ajustes + pacotes/perfis
  bdo/        Black Desert: instalação, GameOption.txt, servidor, travamentos, ajustes do executável
  modules/    limpeza, RAM, reparos, rede, velocidade, winget, jogos, hardware, GPU (NVML), check-up, FPS
  ui/         janela, páginas, overlay, testes de mouse/monitor
tests/        testes que rodam em qualquer sistema (python -m pytest)
```
