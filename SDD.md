# Software Design Document (SDD)
## PFS-BatchKit-Manager: Arquitetura Híbrida APA-Jail (exFAT) & Boot Stack PS2

---

### Controle do Documento
* **Projeto:** PFS-BatchKit-Manager
* **Módulo:** Suporte a Boot Híbrido APA-Jail Type-A2, HOSDMenu, FreeHDBoot e Open PS2 Loader (BDM exFAT)
* **Status:** Implementado, Validado e Operacional
* **Data da Última Atualização:** 03/11/2026

---

## 1. Visão Geral e Objetivos do Sistema

### 1.1. Contexto e Problema Original
O formato nativo de disco rígido interno do PlayStation 2 (FAT com Network Adapter) utiliza a especificação proprietária da Sony denominada **APA (Aligned Partition Allocation)** e o sistema de arquivos **PFS (PlayStation File System)**. 

Embora eficiente para o hardware original da época (2001), essa estrutura impõe severas limitações em ambientes modernos:
1. **Incompatibilidade com Sistemas Modernos:** Sistemas operacionais contemporâneos (Windows, Linux, macOS) não montam partições PFS nativamente sem drivers experimentais em espaço de usuário (ex.: `pfsfuse`, `pfsshell`).
2. **Transferências Lentas e Complexas:** O gerenciamento de backups exigia softwares legados lentos e propensos a corrupção de índice (como *WinHIIP* ou *hdl_dump*).
3. **Rigidez de Particionamento:** Cada jogo requer uma partição APA individual alinhada a múltiplos de 128 MiB.

### 1.2. A Solução APA-Jail Type-A2
A especificação **APA-Jail Type-A2** (desenvolvida pela comunidade técnica via Berion e projetos como *PS2 HDD Decryption Helper*) resolve esse dilema combinando dois mundos no mesmo disco físico:
* **Área APA Mínima ("Jail"):** Os primeiros ~2 GiB do disco são reservados exclusivamente para as partições de sistema essenciais da Sony (`__mbr`, `__system`, `__sysconf`, `__common`, `__contents`), garantindo que o módulo de ROM do PS2 (`rom0:HDDLOAD`) reconheça o disco e inicialize o bootloader.
* **Área exFAT de Alta Capacidade (Volume `OPL`):** O restante da capacidade total do disco (até 2 TiB na tabela de partição MBR padrão) é formatado em **exFAT**, permitindo a conexão direta do HD ao computador via USB/SATA e a cópia direta ("arrastar e soltar") de imagens `.iso`, `.zso` e jogos de PS1 em pastas convencionais (`DVD/`, `CD/`, `POPS/`).

---

## 2. Arquitetura de Particionamento e Mapeamento de Setores

A estrutura física do disco rígido é organizada conforme o diagrama a seguir:

```
[ Setor 0 (LBA 0) ] -> Cabeçalho Híbrido: APA __mbr (bytes 0-445) + PC MBR (bytes 446-511)
[ Setores 1-15    ] -> Área reservada APA / LAPA Journal
[ Setores 16-167  ] -> Payload Bootloader KELF (LBA 16, alinhado a 512 bytes)
[ LBA 2048 - 2GB  ] -> Partições PFS mínimas (__system, __sysconf, __common, __contents)
[ ~2GB a 2.03GB   ] -> Partição de Recuperação (RECOVERY, 32 MiB ext2)
[ 2.03GB a Fim    ] -> Partição de Dados exFAT (Volume 'OPL', Cluster de 32K)
```

### 2.1. Estrutura Detalhada do Setor 0 (LBA 0)
O Setor 0 atua simultaneamente como o descritor de partição mestre para a BIOS do PS2 e como Master Boot Record para a tabela de partições do PC:

| Offset (Hex) | Tamanho | Descrição Técnica | Valor Configurado |
|---|---|---|---|
| `0x00–0x03` | 4 bytes | **APA Checksum (uint32)** | Soma acumulada das palavras 1 a 255 (`sum(words[1..255]) & 0xFFFFFFFF`). Validada por `rom0:HDDLOAD`. |
| `0x04–0x07` | 4 bytes | **APA Magic** | Sequência ASCII `APA\0` (`0x41 0x50 0x41 0x00`). |
| `0x08–0x0F` | 8 bytes | Próxima / Anterior LBA | `0x00000000` (cadeia estática inicial). |
| `0x10–0x2F` | 32 bytes | ID da Partição Mestre | `__mbr\0` preenchido com zeros. |
| `0x40–0x43` | 4 bytes | Start LBA da Partição | `0x00000000` (início no LBA 0). |
| `0x44–0x47` | 4 bytes | Tamanho da Partição APA | `0x00040000` (262.144 setores = 128 MiB). |
| `0x48–0x49` | 2 bytes | Tipo da Partição | `0x0001` (APA Master Boot Record). |
| `0x4A–0x4B` | 2 bytes | Flags | `0x0000`. |
| `0xE0–0xE7` | 8 bytes | **Assinatura APA-Jail** | Sequência ASCII `APAJ-A2\0` identificando o formato Type-A2. |
| `0x130–0x133`| 4 bytes | **Ponteiro LBA do KELF** | Inteiro Little-Endian `16` (aponta para o Setor 16). |
| `0x134–0x137`| 4 bytes | **Tamanho em Setores** | Inteiro Little-Endian indicando a quantidade de setores do KELF (ex.: 152 setores para FHDB). |
| `0x1BE–0x1FD`| 64 bytes | **Tabela de Partição PC MBR** | 4 entradas de partição MBR padrão definindo a partição exFAT `OPL`. Preservada integralmente. |
| `0x1FE–0x1FF`| 2 bytes | **Assinatura de Boot PC** | `0x55 0xAA`. |

---

## 3. Cadeia de Inicialização (Boot Chain) e Modos de Operação

### 3.1. Modo 1: FreeHDBoot 1.966 Oficial (Padrão)
Projetado para consoles não modificados fisicamente ou que utilizam exploits puros de software:

```
[ Console Power On ]
        │
        ▼
[ rom0:HDDLOAD ] ──> Valida LBA 0 (APA Checksum + Magic APA)
        │
        ▼
[ Carrega LBA 16 ] ──> Executa MBR.XLF (KELF assinado MagicGate)
        │
        ▼
[ Monta hdd0:__system ] ──> Executa pfs0:/osd/osdmain.elf (FHDB.XLF)
        │
        ▼
[ Exibição da Logo FHDB ] ──> Processa hdd0:__sysconf/FMCB/FREEHDB.CNF
        │
        ▼
[ Menu OSD / HOSDMenu ] ──> Lista atalhos: Open PS2 Loader, LaunchELF, HOSDMenu
```

* **Exibição da Logo do FreeHDBoot:** Garantida através das diretivas `FastBoot = 0` e `OSDSYS_Skip_Logo = 0` no [`FREEHDB.CNF`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/FREEHDB.CNF).
* **Binário Principal:** O arquivo `FHDB.XLF` (127.536 bytes) é copiado para a partição `__system` renomeado como `osd/osdmain.elf` para satisfazer a busca estrita do bootstrap da Sony.

### 3.2. Modo 2: krHACKen Universal MBR (Compatível com Modchips)
Projetado para consoles equipados com chips como Matrix Infinity, Modbo ou clones, cujo firmware intercepta os vetores DEV9/ATAD e pode provocar congelamento de tela com o KELF do FHDB:
* **Executável Injetado:** `BAT\mbr.img` (offset 8192 a 467.968, totalizando 898 setores alinhados).
* **Comportamento:** Inicializa o hardware sem depender de decodificação de `osdmain.elf` em `__system`, executando diretamente o wLaunchELF integrado para manutenção e recuperação do sistema.

---

## 4. Integração com o Open PS2 Loader (OPL) Moderno

### 4.1. Arquitetura BDM (Block Device Media) para HD Interno
Diferente das versões legadas que utilizavam o driver de partição HDL/APA, as versões recentes do OPL incorporam o subsistema unificado **BDM**:
* O driver `ata_bd` acessa o canal ATA interno diretamente no nível de bloco.
* O driver de sistema de arquivos do BDM monta a partição exFAT e efetua a varredura das pastas padrão de mídia.

### 4.2. Rastreamento da Versão Mais Recente (GitHub Releases)
A aplicação mantém o OPL permanentemente sincronizado com o repositório oficial:
* **Script:** [`BAT\__Fetch_Latest_OPL.ps1`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Fetch_Latest_OPL.ps1).
* **Endpoint Consultado:** `https://api.github.com/repos/ps2homebrew/Open-PS2-Loader/releases/tags/latest`.
* **Asset Baixado:** `OPNPS2LD.ELF` (compilação atual: `v1.2.0-Beta-2271-b3a2199`, tamanho: 1.361.812 bytes).
* **Fallback Automático:** Caso a API do GitHub sofra rate limit, o script recorre ao download direto via URL fixa da release ou utiliza a réplica em cache local [`BAT\OPNPS2LD_LATEST.ELF`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/OPNPS2LD_LATEST.ELF).

### 4.3. Especificação do Arquivo `conf_opl.cfg` (HD 720p Widescreen e IGR)
Para que o OPL inicialize imediatamente na partição exFAT e em Alta Definição (HD 720p 16:9), além de retornar diretamente para o próprio OPL quando o In-Game Reset (IGR) for acionado, o arquivo [`conf_opl.cfg`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/HDD-OSD/__common/OPL/conf_opl.cfg) é implantado com os seguintes parâmetros chave:

```ini
# Open PS2 Loader Configuration File
# Otimizado para Partição de Dados exFAT via BDM, Alta Definição HD 720p e IGR
scrolling=1
theme=OPL
language_text=Portuguese_BR
wide_screen=1
vmode=5
autosort=1
autorefresh=1
enable_delete_rename=1
hdd_spindown=20
bdm_cache=1
enable_bdm_hdd=1
enable_mx4sio=1
enable_ilink=0
usb_mode=2
hdd_mode=0
eth_mode=0
app_mode=0
default_device=0
exit_path=mass:/OPL/OPNPS2LD.ELF
```

* `language_text=Portuguese_BR`: Define o idioma padrão da interface gráfica (ou qualquer outro idioma escolhido pelo usuário).
* `wide_screen=1`: Ativa a proporção de tela panorâmica 16:9 Widescreen para TVs modernas.
* `vmode=0`: Define o Modo de Vídeo como **Auto (Automático)**, garantindo que o OPL selecione o modo nativo do console com cores 100% fiéis em cabos vídeo componente e adaptadores HDMI, sem distorção VGA.
* `exit_path=mass:/OPL/OPNPS2LD.ELF`: Configura o In-Game Reset (combinação `L1+L2+R1+R2+SELECT+START`) para recarregar o OPL a partir da partição exFAT (`mass:`), contornando as restrições do driver PFS durante o jogo.
* `enable_bdm_hdd=1`: Ativa o suporte a HD interno via Block Device Media.
* `usb_mode=2`: Configura o modo de inicialização do BDM como `START_MODE_AUTO` (2).
* `default_device=0`: Define a tela inicial padrão do OPL como **BDM Games**.
* `hdd_mode=0`: Desativa o scanner legado APA/HDL para impedir conflitos de identificação.
* `autorefresh=1` e `autosort=1`: Assegura atualização automática da lista de jogos ISO ao inicializar.

### 4.4. Resolução HD nos Jogos (GSM - Graphics Synthesizer Mode Selector)
Para que os jogos do PlayStation 2 também sejam executados em Alta Definição (HD 720p):
1. **Configuração Global de Jogos (`conf_game.cfg`):**
   * Armazenado na raiz do drive exFAT e nas partições PFS (`__common:/OPL/`, `__common:/`, `__sysconf:/FMCB/`), contém o template mestre:
     ```ini
     $EnableGSM=1
     $GSMVMode=10
     $GSMXOffset=0
     $GSMYOffset=0
     $GSMFIELDFix=0
     ```
   * O parâmetro `$GSMVMode=10` força a saída de vídeo em **HDTV 720p @ 60Hz**.
2. **Configuração Individual por Jogo (`CFG/<GameID>.cfg`):**
   * O script automatizado [`__Apply_HD_Gsm_Games.ps1`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Apply_HD_Gsm_Games.ps1) varre a pasta `CFG/` e as ISOs em `DVD/` e `CD/`, aplicando ou atualizando os parâmetros GSM HD em cada jogo.

### 4.5. Arquitetura do Sistema de Idiomas e Injeção Dupla (PFS + exFAT)
Como o OPL inicializado a partir do HDD-OSD / FHDB é carregado da partição `__common` antes que os drivers BDM exFAT estejam ativos, a localização de idiomas opera em arquitetura de espelhamento total:
1. **Injeção Completa na Partição PFS (`pfsshell`):**
   * `__common:/OPL/`: Recebe `OPNPS2LD.ELF`, `conf_opl.cfg`, `conf_hdd.cfg`, `conf_game.cfg`, além do arquivo `.lng` e fonte correspondente do idioma selecionado.
   * `__common:/OPL/LNG/`: Recebe **todos os 34 idiomas e fontes oficiais** do OPL.
   * `__common:/LNG/`: Recebe **todos os 34 idiomas e fontes oficiais** como caminho de fallback nativo do OPL.
   * `__common:/`: Recebe cópia mestre dos arquivos de configuração globais.
   * `__sysconf:/FMCB/`: Recebe `conf_opl.cfg` e `conf_game.cfg` atualizados.
2. **Sincronização no Volume exFAT:**
   * `E:\LNG\`: Recebe todos os idiomas e fontes oficiais.
   * `E:\conf_opl.cfg` e `E:\conf_game.cfg`: Configurações mestras com HD, IGR e idioma selecionado na raiz do volume.
   * **Limpeza de Duplicatas:** Remoção de pastas `OPL\` e `CFG\conf_opl.cfg` órfãs no exFAT.

### 4.5. Matriz de Distribuição dos Arquivos OPL (Volume exFAT sem Duplicações)
O sistema organiza os arquivos no volume exFAT e nas partições PFS segundo a especificação oficial do OPL BDM:

| Localização de Destino | Caminho do Arquivo | Função |
|---|---|---|
| **Volume exFAT (Raiz)** | `E:\conf_opl.cfg` | Configuração mestre global do OPL (única fonte da verdade no drive BDM). |
| **Volume exFAT (CFG)** | `E:\CFG\conf_hdd.cfg` e `<GameID>.cfg` | Configuração de partição de montagem do HDD e configurações individuais de jogos. |
| **Volume exFAT (APPS)** | `E:\APPS\OPNPS2LD.ELF` | Executável atualizado do OPL acessível pelo LaunchELF e menu APPS. |
| **Volume exFAT (LNG)** | `E:\LNG\lang_*.lng` e `font_*` | Todos os pacotes oficiais de idiomas e fontes, organizados sem poluir a raiz. |
| **Volume exFAT (DVD/CD)** | `E:\DVD\` e `E:\CD\` | Imagens de jogos (.iso/.zso) do PS2. |
| **Volume exFAT (POPS)** | `E:\POPS\` | Imagens (.VCD) de jogos de PS1 do POPStarter. |
| **Partição PFS `__common`** | `__common:/OPL/OPNPS2LD.ELF` e `conf_opl.cfg` | Atalho do FreeHDBoot pelo OSDSYS nativo do PS2. |
| **Partição PFS `__common (LNG)`** | `__common:/LNG/` | Fallback de localização carregado pelo OPL em partições PFS. |
| **Partição PFS `__sysconf`** | `__sysconf:/FMCB/conf_opl.cfg` | Fallback de configuração lido pelo inicializador FMCB/FHDB. |

---

## 5. Módulos de Execução e Scripts Desenvolvidos

### 5.1. [`__Inject_Mbr_Bootloader.ps1`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Inject_Mbr_Bootloader.ps1)
* **Objetivo:** Gravar o executável KELF e atualizar os ponteiros APA no disco físico com garantia de integridade.
* **Mecanismo:** Utiliza a ferramenta Win32 de baixo nível [`BAT\rawcopy.exe`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/rawcopy.exe) com as opções `-w` (escrita direta sem cache) e `-l` (acesso sem travamento exclusivo de dispositivo).
* **Passos Executados:**
  1. Alinha o payload KELF (`MBR.XLF` ou `mbr.img`) para múltiplos exatos de 512 bytes em arquivo temporário;
  2. Efetua a leitura de 1024 bytes de LBA 0-1 do disco físico;
  3. Atualiza os campos `0x130` (LBA 16), `0x134` (contagem de setores) e `0xE0` (`APAJ-A2\0`);
  4. Preserva integralmente a faixa de bytes `446..511` (tabela de partições PC MBR do exFAT e assinatura `0x55AA`);
  5. Recalcula o checksum de 32 bits das palavras 1 a 255 e grava na posição `0x00`;
  6. Grava o KELF no Setor 16 (offset 8192) e o novo LBA 0 no Setor 0 (offset 0);
  7. Lê de volta os setores gravados e valida o cabeçalho MagicGate KELF (`01-00-00-04`) e o checksum APA.

### 5.2. [`__Build_BootPackage.ps1`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Build_BootPackage.ps1)
* **Objetivo:** Montar a pasta de preparação temporária `BAT\__BootPackage` com todos os binários validados e com os nomes exigidos pelas ferramentas de injeção.
* **Ações:** Extrai componentes do instalador FMCB 1.966 (`MBR.XLF`, `FHDB.XLF`, `BOOT.ELF`, etc.), invoca o atualizador do OPL para obter o `OPNPS2LD.ELF` mais recente, copia arquivos de configuração (`conf_opl.cfg`, `OSDMENU.CNF`, `OSDMBR.CNF`) e pré-nomeia os executáveis (`osdmain.elf`, `osdsys.elf`, `osd110.elf`).

### 5.3. [`__Install_HOSDMenu.bat`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Install_HOSDMenu.bat)
* **Objetivo:** Orquestrar o processo completo de instalação do boot stack no disco rígido.
* **Comunicação PFS:** Gera script de comandos para o [`pfsshell.exe`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/pfsshell.exe) utilizando comandos `put` de argumento único (sem renomeação em tempo de injeção). Redireciona o log de saída para `TMP\pfsshell_install.log` para auditoria.

### 5.4. [`__Configure_OPL_Language.ps1`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Configure_OPL_Language.ps1)
* **Objetivo:** Gerenciar interativamente a escolha de idioma do OPL, atualizar as configurações em `conf_opl.cfg` e distribuir os arquivos `.lng` e fontes correspondentes.
* **Funcionalidades:**
  * Modo interativo com menu numérico destacando `Portuguese_BR` [Recomendado], principais idiomas internacionais (English, Spanish, French, German, Italian, Japanese) ou lista completa com todos os 32 idiomas suportados.
  * Atualiza automaticamente o parâmetro `language_text` em todos os modelos de configuração locais e no volume exFAT montado.
  * Descompacta e disponibiliza a pasta `LNG/` contendo todos os 32 idiomas no volume exFAT e prepara o diretório `__BootPackage` para injeção PFS.

### 5.5. [`__Update_OPL_Latest.bat`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Update_OPL_Latest.bat)
* **Objetivo:** Fornecer uma rotina de atualização autônoma e rápida para o Open PS2 Loader sem a necessidade de reformatar o HD ou regravar o MBR.
* **Ações:**
  1. Consulta a API do GitHub e baixa as releases mais recentes de `OPNPS2LD.ELF` e `OPNPS2LD-LANGS.7z`.
  2. Apresenta o seletor interativo de idiomas para o usuário escolher o idioma desejado da interface.
  3. Atualiza o executável, o arquivo `conf_opl.cfg` e todos os arquivos de tradução na partição exFAT (volume `OPL`).
  4. Caso o HD do PS2 esteja conectado, atualiza diretamente via `pfsshell` a partição PFS `__common:/OPL/` com o novo ELF, a nova configuração e os arquivos de idioma.

### 5.6. [`__Sync_Exfat_Opl_Config.bat`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Sync_Exfat_Opl_Config.bat)
* **Objetivo:** Identificar a letra de unidade do volume exFAT `OPL` no Windows e assegurar que toda a árvore de diretórios (`DVD`, `CD`, `CFG`, `APPS`, `LNG`, etc.) e os arquivos de configuração e tradução do OPL estejam sincronizados.

### 5.7. [`__Ensure_Opl_Drive_Letter.ps1`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Ensure_Opl_Drive_Letter.ps1)
* **Objetivo:** Detectar partições exFAT rotuladas como `OPL` sem ponto de montagem no Windows e atribuir automaticamente a primeira letra de unidade disponível (de D: a Z:).
* **Mecanismo:** Executa uma resolução em 3 camadas de contingência (`Add-PartitionAccessPath`, `Set-Partition` e script temporário `diskpart assign`), garantindo que o volume `OPL` apareça no Windows Explorer sem requerer o uso manual do `diskmgmt.msc`. É executado automaticamente após a formatação APA-Jail, ao recarregar o cache do disco e antes de sincronizar configurações.

---

## 6. Lições Aprendidas e Resolução de Não-Conformidades

1. **Limitação da Classe `.NET FileStream` em Dispositivos Físicos:**
   * *Falha:* Chamadas a `FileStream.Write` contra `\\.\PhysicalDriveX` disparam `IOException: Operação E/S não funcionará...` devido à tentativa da biblioteca padrão do .NET de verificar limites com `GetFileSizeEx` em dispositivos brutos.
   * *Solução:* Substituição completa por `rawcopy.exe`, que utiliza chamadas diretas de Win32 (`CreateFileW`, `WriteFile`) com buffers alinhados por setor (512 bytes).
2. **Restrição Sintática do `pfsshell`:**
   * *Falha:* Comandos como `put FHDB.XLF osdmain.elf` falham ou ignoram o segundo argumento, resultando em arquivos com nomes incompatíveis dentro da partição PFS.
   * *Solução:* Todos os arquivos são pré-nomeados em disco local antes do comando `put <arquivo_unico>`.
3. **Interpretação de Parênteses em Blocos de Lote (`cmd.exe`):**
   * *Falha:* Parênteses não escapados dentro de blocos condicionais (`if (...) else (...)`) em arquivos `.bat` fazem com que o `cmd.exe` feche a janela instantaneamente com o erro `) foi inesperado neste momento`.
   * *Solução:* Eliminação de parênteses literais dentro de blocos condicionais e sanitização das mensagens de console.
4. **Visibilidade da Logo do FreeHDBoot:**
   * *Falha:* As flags padrão do pacote FMCB (`FastBoot = 1`, `OSDSYS_Skip_Logo = 1`) ocultavam a tela de abertura.
   * *Solução:* Ajuste automatizado para `FastBoot = 0` e `OSDSYS_Skip_Logo = 0` no `FREEHDB.CNF`.
5. **Volume exFAT (OPL) sem Letra de Unidade no Windows:**
   * *Falha:* O Windows não atribuía automaticamente uma letra de unidade à partição exFAT após a formatação no WSL ou após o desmonte via `mountvol /d`, exigindo atribuição manual pelo usuário via Gerenciador de Disco (`diskmgmt.msc`).
   * *Solução:* Implementação do [`__Ensure_Opl_Drive_Letter.ps1`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/BAT/__Ensure_Opl_Drive_Letter.ps1) acionado nativamente em todo o ciclo de vida (formatação, carregamento de cache e sincronização).

---

## 7. Roteiro Operacional para o Usuário

### 7.1. Primeira Instalação / Formatação
1. Iniciar o [`!PFS-BatchKit-Manager.bat`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/!PFS-BatchKit-Manager.bat) como Administrador.
2. Selecionar o HD do PS2.
3. No Menu Principal, acessar **`9` (HDD Management)** -> **`2` (APA-Jail minimal + exFAT)**.
4. Acessar **`8` (OSD/XMB Management)** -> **`6` (Install HOSDMenu + exFAT boot stack)** e escolher o bootloader desejado.

### 7.2. Atualização do Open PS2 Loader e Configuração de Idioma
1. Iniciar o [`!PFS-BatchKit-Manager.bat`](file:///c:/Users/beto/Documents/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/!PFS-BatchKit-Manager.bat).
2. Acessar **`8` (OSD/XMB Management)** -> **`5` (Update Open PS2 Loader & Configure Language)** ou alternativamente **`3` (OPL Management)** -> **`6` (Update OPL to Latest (GitHub) + Configure Language)**.
3. Escolher o idioma de interface desejado (Opção `1` - `Portuguese_BR` [Recomendado] ou outro da lista de 32 idiomas).
4. O script baixa a versão mais recente do GitHub, descompacta os 32 pacotes de tradução, aplica o idioma escolhido no `conf_opl.cfg` e sincroniza automaticamente as partições exFAT (`OPL:\`) e PFS (`__common:/OPL/`).
