# Compatibilidade OPL — HDD interno exFAT (APA-Jail)

Referência: [Open-PS2-Loader](https://github.com/ps2homebrew/Open-PS2-Loader) (análise do código em `master`).

## Dois caminhos distintos no OPL

O OPL **não** usa o mesmo stack para APA/PFS (HDLoader) e para exFAT no HDD interno.

| Modo OPL | Stack | Quando |
|----------|--------|--------|
| **HDD** (ícone HDD clássico) | `ps2hdd.irx` + `ps2fs.irx` → `hdd0:` / `pfs0:` | Disco **APA** Sony (partições `__system`, `+OPL`, jogos HDL em PFS) |
| **BDM + HDD interno** (ícone `hdd_bd`) | `bdm.irx` + `bdmfs_fatfs.irx` + `ata_bd` → `massN:` | Disco **MBR/GPT** com **FAT32 ou exFAT** na partição de dados |

O layout **PFS BatchKit (APA-Jail + exFAT)** deve ser consumido **só pelo caminho BDM**, nunca pelo modo HDD/PFS clássico.

## Detecção no boot (evitar corrupção)

Em `src/hddsupport.c`, `hddDetectNonSonyFileSystem()` lê os **dois primeiros setores** via `xhdd0:` e decide **antes** de carregar APA/PFS:

1. Se `0x55 0xAA` em `0x1FE` do setor 0 → trata como **MBR** (`return 1`).
2. Senão, se `EFI PART` no setor 1 → **GPT**.
3. Senão, se `"APA"` no offset 4 → **APA** (`return 0`).
4. Caso contrário → erro (`-1`).

Se `!= 0` (MBR/GPT), `hddLoadSupportModules()` **não carrega** `ps2hdd`/`ps2fs` — comentário explícito: carregar APA em disco MBR/exFAT **corrompe** o conteúdo.

**Requisito BatchKit:** o setor 0 do `__mbr` deve manter **`55 AA` em `0x1FE`**, magic **`APAJ` em `0xE0`**, e entrada MBR em **`0x1BE`** (já feito em `apa.py` / `patch_apaj_and_mbr_entry`).

> Nota: como a assinatura MBR é verificada **antes** do magic APA, o disco híbrido é classificado como **MBR**, que é o comportamento desejado.

## Como o OPL lê o exFAT (leitura de jogos)

1. **Settings → Block devices:** activar **HDD (GPT/MBR)** / `enable_bdm_hdd` (`CONFIG_OPL_ENABLE_BDMHDD` em `include/config.h`).
2. `bdmLoadModules()` carrega BDM + `bdmfs_fatfs` (`src/bdmsupport.c`).
3. Com `gEnableBdmHDD`, carrega ATAD + `xhdd` e o driver **`ata_bd`** (bloco bruto 512 B/setor, LBA 28/48).
4. O filesystem driver (`bdmfs_fatfs`, do PS2SDK) interpreta a **tabela MBR**, monta a partição primária exFAT como `massN:` (driver `"ata"`).
5. Listagem de jogos: `sbReadList()` em `DVD/`, `CD/`, etc. (`sbCreateFolders(..., 1)` cria pastas em BDM).
6. Arranque: `bdmLaunchGame()` obtém **fragmentos** do ficheiro (`USBMASS_IOCTL_GET_FRAGLIST`) — ISO/ZSO até **64 fragmentos** (README OPL ≥ rev1893).

**Requisito layout:** uma **partição MBR primária** type **`0x07`**, início LBA = fim da região APA (384 MiB), tamanho = resto do disco (`plan_layout()`).

**Requisito pastas:** `CD`, `DVD`, `VMC`, `CFG`, `ART`, `THM`, `LNG`, `CHT`, `APPS` (`write_opl_tree` + `POPS`; ver [OPL_FOLDER_LAYOUT.md](OPL_FOLDER_LAYOUT.md) e OPL Manager V24 `OplFolders`). Mínimo Manager: `CD`, `DVD`, `ART`.

## Gravação no PS2

- Escrita ao HDD interno em modo BDM passa por `ata_bd_write()` → `ata_device_sector_io_internal(..., dir=1)` (`modules/iopcore/cdvdman/atad.c`, `USE_BDM_ATA`).
- No OPL: **Settings → Enable Write Operations** (antigo “delete/rename”) — necessário para apagar/renomear jogos, VMC, `conf_opl.cfg`, etc.
- VMC em exFAT: `bdmsupport.c` valida cadeia de clusters antes de escrever; ficheiros **muito fragmentados** podem ser recusados (risco de corrupção).

**Requisito operacional:** activar gravação no OPL; copiar ISOs **sequencialmente** ou manter **baixa fragmentação** (README OPL: evitar defrag agressivo; copiar ficheiro a ficheiro).

## Formatação no PC (compatível com README OPL)

Do README OPL (secção Expansion port HDD):

- **MBR** + **exFAT** (ou GPT para >2 TB).
- **Allocation unit size = Default** ao formatar no Windows.
- No Linux, `mkfs.exfat` / `exfatprogs` com parâmetros por omissão (evitar cluster size exótico).

BatchKit: `format_exfat_region()` + label `PS2OPL` (só cosmético).

## O que **não** fazer no PS2

- **Format completo** no wLaunchELF HDD Manager no disco híbrido (destrói APA-Jail / exFAT).
- Activar modo **HDD clássico** (PFS/HDLoader) esperando ler `DVD/` no exFAT — jogos ISO no exFAT aparecem em **BDM → dispositivo ATA (`massN:`)**, não na lista “HDD Games” HDL.
- `Expand` no wLaunchELF (README OPL: corrompe disco).

## FreeHDBoot vs OPL

- Região APA 384 MiB (`__mbr`, `__system`, `__sysconf`) + FHDB é independente do mount BDM.
- `__system` / `__sysconf` em PFS (via pfsshell no PC) servem FHDB/OSD; **jogos exFAT** ficam **fora** dessas partições, só na slice MBR.

## NBD / PC

OPL exporta o disco inteiro via NBD (`README`: substitui HDL server). O PC vê o **disco bruto** (MBR + APA + exFAT). Ferramentas APA (`hdl_dump`, `pfsshell`) aplicam-se à região APA; ficheiros exFAT editam-se montando a **partição** no offset correcto (como BatchKit faz com `losetup --offset`).

## Checklist BatchKit → OPL

| Item | BatchKit | OPL |
|------|----------|-----|
| Assinatura MBR `55 AA` @ 0x1FE | Sim | Evita load APA/PFS |
| APAJ @ 0xE0 | Sim | FHDB / APA-Jail |
| Entrada MBR LBA + count | Sim | `bdmfs_fatfs` monta partição |
| Tipo partição 0x07 | `MBR_EXFAT_TYPE` | exFAT MBR |
| exFAT ocupa resto do disco | `plan_layout()` | Sem overlap com APA |
| Pastas OPL na raiz exFAT | `write_opl_tree()` | `sbCreateFolders` |
| Modo correcto no OPL | (utilizador) | BDM HDD + Write Ops |

## Melhorias futuras (opcional)

- Validar pós-`mkfs.exfat` cluster size vs recomendação OPL.
- Documentar na TUI que o menu de jogos é **BDM/ATA**, não “HDD HDLoader”.
- Teste de integração: montar imagem no PC e verificar entrada MBR + first sectors APA inalterados após format exFAT.
- Comando **`pfs-batchkit validate-opl-layout`** (implementado) — verifica MBR/APAJ/LBA/exFAT BPB antes de gravar disco.
