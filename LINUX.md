# Chinese Control para Linux

Versão enxuta, feita para uso pessoal em Arch Linux (testada só em ambiente de desenvolvimento, não num Arch real).
Fica no ramo `linux`; o ramo `main` e as versões do Windows não mudam.

## Instalar e abrir (Arch)

```sh
sudo pacman -S --needed python pyside6 python-psutil polkit
git clone -b linux https://github.com/Pedroedmachado/lolitos-otimizas.git
cd lolitos-otimizas
./chinese-control-linux
```

Os ajustes de sistema pedem a senha de administrador pelo `pkexec`, uma vez por sessão. Para o pedido de senha
aparecer, a sessão precisa de um agente polkit rodando. No Niri, por exemplo:

```sh
sudo pacman -S --needed polkit-gnome
# no config.kdl do Niri:
# spawn-at-startup "/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1"
```

## O que tem

* **Painel:** resumo do PC, quantos ajustes estão ativos e o botão "Aplicar recomendados".
* **Desempenho:** gráficos ao vivo de processador, memória, placa de vídeo (pelo `nvidia-smi`), disco e rede.
* **Meu PC:** sistema, processador, memória, placa de vídeo, placa-mãe e discos.
* **Ajustes:** 20 ajustes com aplicar e desfazer (governador e preferência de energia do processador, parâmetros de
  memória do kernel, agendador do NVMe, TCP, cache de shaders da NVIDIA, instalação do GameMode e do MangoHud).
* **Jogos:** biblioteca da Steam e a linha de opções de inicialização pronta para copiar.
* **MangoHud:** escolhe o que aparece na tela e grava o `MangoHud.conf`.
* **Restauração:** histórico com desfazer item a item.

## Como os ajustes são gravados

| Tipo | Vale na hora | Fica para o próximo boot em |
|---|---|---|
| Parâmetro do kernel | `/proc/sys/...` | `/etc/sysctl.d/99-chinese-control-*.conf` |
| Valor em `/sys` (governador, THP, agendador) | o próprio arquivo em `/sys` | `/etc/tmpfiles.d/chinese-control-*.conf` |
| Módulo do kernel (BBR) | `modprobe` | `/etc/modules-load.d/chinese-control-*.conf` |
| Variável de ambiente (NVIDIA) | próximo login | `~/.config/environment.d/90-chinese-control.conf` |

Desfazer apaga o arquivo criado e devolve o valor que estava antes.

O ajudante root (`lolitos/linux/helper.py`) só aceita as operações e os caminhos dessa tabela, mais a instalação
dos pacotes `gamemode`, `lib32-gamemode`, `mangohud` e `lib32-mangohud`.

## Limites conhecidos

* O governador do processador pode ser trocado de volta pelo `power-profiles-daemon` ou pelo TLP, se estiverem ativos.
* Os pacotes `lib32-*` precisam do repositório `multilib` habilitado no `pacman.conf`.
* Não há overlay próprio nem tecla global: no Wayland isso fica com o MangoHud.
* Nada do Black Desert é lido ou alterado no Linux.
* Textos só em português.
