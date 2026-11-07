# PFS-BatchKit-Manager (Fork APA-Jail & exFAT BDM)

<img src="https://i.imgur.com/O70NFyn.png" alt="Logo" align="right" width="400"/>

> **Fork mantido por [@alvesbeto](https://github.com/alvesbeto/PFS-EXFAT-BatchKit-Manager)**  
> *Baseado no projeto original de [GDX-X/PFS-BatchKit-Manager](https://github.com/GDX-X/PFS-BatchKit-Manager)*

O **PFS BatchKit Manager** é uma suíte abrangente para gerenciar discos rígidos internos de PlayStation 2 e PSX (DESR). 

Este **Fork** foi desenvolvido para modernizar a utilização do HD interno do PS2, substituindo a necessidade de softwares legados lentos (como `hdl_dump`) pelo revolucionário formato híbrido **APA-Jail + exFAT BDM**, permitindo copiar jogos, traduções, capas e temas simplesmente **arrastando e soltando arquivos pelo Windows Explorer**.

---

## 🌟 O que este Fork faz de diferente do repositório original?

| Recurso | Repositório Original (GDX-X) | Este Fork (@alvesbeto) |
| :--- | :--- | :--- |
| **Formato de Armazenamento** | Apenas partições proprietárias APA/PFS (cada jogo é uma partição individual). | **Híbrido APA-Jail Minimal + exFAT BDM (Type-A2)**: área de boot PFS (~2GB) + partição exFAT (volume `OPL`) para jogos até 2TB. |
| **Transferência de Jogos** | Exige instalação manual via linha de comando ou rede lenta NBD Server. | **Arrastar e Soltar (Drag & Drop)** direto no Windows Explorer para as pastas `DVD/`, `CD/`, `ART/`, `POPS/`. |
| **Versão do Open PS2 Loader** | Versões empacotadas estáticas ou legadas. | **Atualizador Oficial GitHub Automatizado**: baixa dinamicamente a versão mais recente (`latest`) de `ps2homebrew/Open-PS2-Loader`. |
| **Suporte a Idiomas** | Idiomas limitados ou requer cópia manual. | **Instalador com 34 idiomas e detecção automática**: detecta o idioma do Windows e instala Português do Brasil (`Portuguese_BR`) e fontes TTF de fábrica. |
| **In-Game Reset (IGR)** | Costuma falhar no HD interno (`hdd0:`) por ausência de drivers PFS durante os jogos. | **IGR 100% Funcional no HD Interno (`mass:/`)**: instala uma cópia do ELF no exFAT e aponta `exit_path=mass:/OPL/OPNPS2LD.ELF`. Retorna ao OPL via `L1+L2+R1+R2+Select+Start` sem Memory Card! |
| **Modo de Vídeo e Cores** | Forçar modos VGA causava tela roxa/magenta em cabos vídeo componente / HDMI. | **Modo de Vídeo Automático (`vmode=0`)**: cores 100% fiéis sem distorção e suporte nativo a Widescreen 16:9. |
| **Compatibilidade de Jogos** | Forçar GSM globalmente causava travamentos em diversos jogos. | **Resolução Nativa Preservada**: jogos rodam em suas resoluções originais de fábrica sem gerar `conf_game.cfg` defeituoso. |
| **Integração com Bootloader** | Boot legado ou dependente de cartões FMCB. | **FreeHDBoot / OSDMenu Integrado**: inicialização limpa direto do HD sem nenhum Memory Card inserido no console. |
| **Reparo de Partição** | Não possui reparo de tabela APA-Jail. | **Ferramenta de Reparo de Cabeçalho**: regenera o cabeçalho APA LBA 0 e alinhamento do MBR sem perda de dados. |
| **Canal de Atualizações** | Conectado ao upstream do autor original. | **Independente**: consulta e atualiza diretamente deste fork (`alvesbeto/PFS-EXFAT-BatchKit-Manager`), preservando todas as customizações. |

---

## 🚀 Principais Funcionalidades

### 1. Particionamento Híbrido APA-Jail Minimal + exFAT BDM
* O HD do PS2 é formatado com um setor 0 híbrido contendo o cabeçalho APA (para o hardware do PS2) e a tabela MBR (para o Windows).
* Cria partições mínimas de 128MB (`__system`, `__sysconf`, `__common`, `__contents`) para que o FreeHDBoot e o OSDMenu inicializem no PS2.
* Todo o restante do disco (até 2TB) é formatado em **exFAT**, ganhando uma letra de unidade no Windows (ex: `E:\`).
* Você pode copiar jogos ISO, ZSO, pastas de capas (`ART/`), músicas, temas e VMCs na velocidade máxima da sua porta SATA ou USB 3.0!

### 2. Atualizador de OPL & Pacotes de Tradução Integrados
* Consulta automática à release oficial do OPL no GitHub (`ps2homebrew/Open-PS2-Loader`).
* Seletor interativo que detecta o idioma do sistema operacional do host e instala as traduções (`lang_Portuguese_BR.lng`) e fontes compatíveis (`font_Portuguese_BR.ttf`) diretamente na pasta `OPL/` da partição exFAT e na partição PFS.

### 3. In-Game Reset (IGR) sem Memory Card
* Os jogos do PS2, ao rodarem pelo HD interno via driver BDM exFAT, não possuem acesso às partições PFS do disco (`hdd0:`).
* Este fork instala o executável `OPNPS2LD.ELF` tanto no PFS (para o boot inicial pelo OSDMenu) quanto na partição exFAT (`mass:/OPL/OPNPS2LD.ELF`).
* O caminho de saída é configurado para `exit_path=mass:/OPL/OPNPS2LD.ELF`. Ao pressionar o combo de IGR no controle (`L1 + L2 + R1 + R2 + START + SELECT`), o jogo retorna imediatamente para o OPL sem erros!

### 4. Cores Corretas e Resolução de Tela Estável
* Corrige a distorção roxa/magenta que ocorria ao forçar resolução VGA. O OPL é configurado em `vmode=0` (Auto) e `wide_screen=1` (Widescreen 16:9).
* Resolução nativa dos jogos 100% respeitada: nenhum arquivo `conf_game.cfg` com GSM forçado é gerado, eliminando telas pretas e bugs visuais.

---

## 🛠️ Como Utilizar (Passo a Passo)

### Passo 1: Formatar o HD com APA-Jail Minimal + exFAT
1. Execute `!PFS-BatchKit-Manager.bat` como Administrador e selecione o disco rígido do PS2.
2. No menu principal, vá em:  
   `9 (HDD Management)` > `1 (Format HDD)` > **`2 (APA-Jail minimal + exFAT)`**.
3. O script criará as partições de sistema mínimas e formatará todo o espaço restante em exFAT com o rótulo de volume **`OPL`**.

### Passo 2: Instalar o Boot Stack (FreeHDBoot / OSDMenu)
1. Vá em:  
   `8 (OSD/XMB Management)` > **`6 (Install HOSDMenu + exFAT boot stack)`**.
2. Escolha o bootloader adequado para seu console:
   * **Opção 1: FreeHDBoot 1.966 Oficial** (Recomendado para PS2 sem modchip / padrão).
   * **Opção 2: krHACKen Universal MBR** (Recomendado para PS2 com modchip Matrix / Modbo).
3. O script injetará o KELF MagicGate no LBA 16 e configurará as partições PFS para boot direto pelo HD.

### Passo 3: Atualizar o OPL e Configurar Idioma e IGR
1. Vá em:  
   `8 (OSD/XMB Management)` > **`5 (Update OPL, Languages + IGR)`** (ou via menu do OPL).
2. O script fará o download da versão mais recente do OPL e do pacote de traduções.
3. Escolha seu idioma (ex: **`1 [Portuguese_BR]`**).
4. O script instalará o OPL na partição PFS, copiará o executável para a pasta `OPL/` do exFAT e configurará o `exit_path=mass:/OPL/OPNPS2LD.ELF`.

### Passo 4: Adicionar Jogos e Jogar
1. Conecte o HD ao seu PC — o Windows montará a unidade exFAT automaticamente (ex: `E:\`).
2. Copie seus jogos diretamente para as pastas correspondentes:
   * Jogos de PS2 em formato `.iso` ou `.zso` na pasta **`DVD/`** (ou **`CD/`** para jogos em CD).
   * Capas de jogos na pasta **`ART/`**.
   * Jogos de PS1 (VCD) na pasta **`POPS/`**.
3. Conecte o HD de volta no PlayStation 2 e ligue o console. O PS2 inicializará pelo OSDMenu, abrirá o OPL em Português com suporte a widescreen e você poderá jogar direto do HD!

---

## 📁 Estrutura de Arquivos no Volume exFAT (`OPL`)

Ao conectar o HD formatado no computador, o volume exFAT terá a seguinte organização:

```
E:\ (Volume exFAT: OPL)
├── APPS/                       # Aplicativos homebrew do PS2
├── ART/                        # Capas dos jogos (COV, ICO, BG)
├── CD/                         # Imagens ISO/ZSO de jogos PS2 em CD
├── CFG/                        # Arquivos individuais de configuração dos jogos
├── CHT/                        # Cheats e códigos de trapaça
├── DVD/                        # Imagens ISO/ZSO de jogos PS2 em DVD
├── LNG/                        # Arquivos de idioma e fontes do OPL
├── OPL/                        # Arquivos centrais do OPL
│   ├── OPNPS2LD.ELF            # Executável do OPL para In-Game Reset (mass:/)
│   ├── conf_opl.cfg            # Configurações do OPL (vmode=0, widescreen, IGR)
│   ├── conf_hdd.cfg            # Mapeamento do driver BDM para exFAT interno
│   ├── lang_Portuguese_BR.lng  # Arquivo de tradução
│   └── font_Portuguese_BR.ttf  # Fonte com acentuação gráfica
├── POPS/                       # Jogos de PS1 (.VCD) convertidos
├── THM/                        # Temas visuais para a interface do OPL
├── VMC/                        # Memory Cards Virtuais (Virtual Memory Cards)
└── conf_opl.cfg                # Configuração espelhada na raiz para compatibilidade
```

---

## ⚙️ Especificações Técnicas e Arquitetura

Para detalhes completos de engenharia de software, mapeamento de setores LBA, integração KELF e especificações do driver BDM, consulte o documento:
* 📄 **[SDD.md (Software Design Document)](SDD.md)**

---

## 🤝 Créditos e Agradecimentos

* **GDX-X**: Criador do [PFS-BatchKit-Manager original](https://github.com/GDX-X/PFS-BatchKit-Manager).
* **ps2homebrew Team**: Pelo desenvolvimento ativo do [Open PS2 Loader (OPL)](https://github.com/ps2homebrew/Open-PS2-Loader), `pfsshell` e `hdl-dump`.
* **pcm720**: Pelo projeto do [OSDMenu](https://github.com/pcm720/OSDMenu).
* **krHACKen**: Por ferramentas essenciais como `mbr.img`, POPStarter, CUE2POPS e SCEDoormat_NoME.
* **gledson999**: Pela tradução oficial para Português do Brasil do Open PS2 Loader.
* **@alvesbeto**: Autor deste fork, implementando a automação híbrida APA-Jail Minimal + exFAT BDM, atualização dinâmica do OPL, IGR exFAT e correções de vídeo.
