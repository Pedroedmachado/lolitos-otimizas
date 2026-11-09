# Lolitos Control

Otimizador de Windows **para jogos** — com otimização por jogo para tudo que estiver instalado e um módulo especial
para **Black Desert Online** (Guerra de Nodes e Cerco). Feito em Python + PySide6. Versão 1.7.0. Interface em português, inglês e espanhol.
Reimplementação limpa das funções de um otimizador comercial: código, textos e valores próprios, sem
reaproveitar nada do programa original.

## Como usar

**Rodar direto do código** (precisa do Python 3.11+): dê dois cliques em `rodar.bat`. Na primeira vez ele cria
um ambiente virtual e instala as dependências. O app pede administrador ao abrir.

**Baixar o instalador pronto:** aba [Releases](https://github.com/Pedroedmachado/lolitos-otimizas/releases) — cada push na `main` gera o `Setup.exe` pelo GitHub Actions.

**Gerar o instalador no seu PC (Setup.exe):** dê dois cliques em `gerar-instalador.bat`. Ele instala sozinho pelo winget o
que faltar (Python 3.12 e Inno Setup 6), gera o programa e monta `dist\LolitosControl-1.7.0-Setup.exe`.
O instalador tem assistente em português, inglês ou espanhol (o app abre no idioma escolhido), termos de uso, atalhos, opção de iniciar com o Windows, fecha o app
antes de atualizar e desinstalador (que pergunta se apaga histórico e backups).

Dados do app (histórico, backups, perfis, config): `%LOCALAPPDATA%\LolitosControl`.

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
