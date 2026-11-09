# Lolitos Otimizações

Otimizador de Windows **para jogos** — com otimização por jogo para tudo que estiver instalado e um módulo especial
para **Black Desert Online** (Guerra de Nodes e Cerco). Feito em Python + PySide6. Versão 1.3.1.
Reimplementação limpa das funções de um otimizador comercial: código, textos e valores próprios, sem
reaproveitar nada do programa original.

## Como usar

**Rodar direto do código** (precisa do Python 3.11+): dê dois cliques em `rodar.bat`. Na primeira vez ele cria
um ambiente virtual e instala as dependências. O app pede administrador ao abrir.

**Baixar o instalador pronto:** aba [Releases](https://github.com/Pedroedmachado/lolitos-otimizas/releases) — cada push na `main` gera o `Setup.exe` pelo GitHub Actions.

**Gerar o instalador no seu PC (Setup.exe):** dê dois cliques em `gerar-instalador.bat`. Ele instala sozinho pelo winget o
que faltar (Python 3.12 e Inno Setup 6), gera o programa e monta `dist\LolitosOtimizacoes-1.3.1-Setup.exe`.
O instalador tem assistente em português, termos de uso, atalhos, opção de iniciar com o Windows, fecha o app
antes de atualizar e desinstalador (que pergunta se apaga histórico e backups).

Dados do app (histórico, backups, perfis, config): `%LOCALAPPDATA%\LolitosOtimizacoes`.

## O que tem

| Tela | O que faz |
|---|---|
| **Painel** | Pontuação de otimização, **Boost em um clique** (ajustes recomendados pendentes + limpeza + RAM), check-up do PC, uso ao vivo |
| **Black Desert** | Pacote de Windows para Guerra; prioridade alta permanente (IFEO), GPU dedicada, tela cheia sem FSO e exclusão no Defender para o `BlackDesert64.exe`; **predefinições do `GameOption.txt`** (Guerra/Cerco, PvP, Grind, AFK) com prévia, backup e editor; **latência real até o servidor** que o jogo está usando; resumo de **travamentos** (Dump) e limpeza segura de caches; checklist NVIDIA/in-game |
| **Ajustes** | ~145 ajustes em 11 categorias (desempenho, jogos, mouse/teclado, GPU/monitor, rede, privacidade, sem IA, interface, atualizações, segurança, apps), cada um com ganho, contrapartida, estado lido do Windows e Desfazer |
| **Debloat** | Apps pré-instalados, recursos opcionais do Windows e OneDrive |
| **Jogos** | Detecta Steam, Epic, GOG, Ubisoft e jogos de EA app, Riot, Battle.net, Rockstar e outros; **Preparar e jogar** (libera RAM, plano de energia só durante a partida, prioridade/afinidade, overlay); **Otimizar este jogo**: prioridade alta permanente, GPU dedicada, tela cheia sem FSO e exclusão no Defender para o executável, observações do anti-cheat (~30 jogos conhecidos) e latência do servidor (jogos TCP) |
| **Perfis** | Pacotes prontos (Básico, Jogos online competitivos, BDO Guerra, Competitivo, Equilibrado, PC modesto, Privacidade, Sem IA) + perfis próprios com exportar/importar |
| **Limpeza** | Temporários, shaders, Windows Update, entrega, WER, dumps, navegadores, Discord, Lixeira — medindo antes; liberar RAM (working sets + standby) |
| **Rede** | Teste de velocidade (Cloudflare) com bufferbloat, perda de pacotes a 20 pkt/s, **análise de rota salto a salto**, DNS/IP/Winsock |
| **Ferramentas** | SFC, DISM, CHKDSK, reset do Windows Update, Explorer, áudio, Bluetooth, spooler, ícones, Store, driver de vídeo, .NET 3.5; inicialização; instalar apps pelo winget (catálogo WinUtil); teste de polling do mouse; teste de monitor (pixels, vazamento, ghosting) |
| **Hardware** | CPU, RAM (XMP/EXPO, dual channel, slots), placa-mãe/BIOS, GPU (link PCIe via NVML), monitores, discos, TPM/Secure Boot; monitor ao vivo com gravação em CSV |
| **Overlay** | FPS (via PresentMon), CPU/GPU, temperaturas, VRAM, RAM e ping por cima do jogo; tecla global |
| **Restauração** | Histórico com desfazer item a item, reverter tudo, pontos de restauração |

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
