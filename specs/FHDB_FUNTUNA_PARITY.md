# FreeHDBoot × FunTuna-Fork (alvesbeto) — paridade

Análise estática do fork [alvesbeto/Funtuna-Fork](https://github.com/alvesbeto/Funtuna-Fork) (specs em `.agents/`, commits pós-israpps). **FunTuna = cartão + OpenTuna**; **FreeHDBoot = HDD PFS** — não há repo FHDB separado; aplicamos só padrões transferíveis.

## Mapa conceitual

| FunTuna (MC) | FreeHDBoot (HDD BatchKit) | Implementado |
|--------------|---------------------------|--------------|
| `mc:/SYS-CONF/USBD*.IRX` BDM **antes** de `mc:/BOOT/` | `__sysconf/FMCB/USBD*.IRX` ATA-Assault | `fhdb_bdm.install_ata_assault_sysconf` |
| IRX PS2SDK FAT em `mc:/BOOT/` | N/A (HDD usa BDM no sysconf) | — |
| `FUNTUNA.CNF` / OSD custom | `osdmain.elf` + HDD-OSD inject | `fhdb_stage` |
| OPL `conf_opl.cfg` seed (`usb_mode=2`, `enable_mx4sio=1`) | `mass:/conf_opl.cfg` | `opl_config.CONF_OPL_EXFAT_LINES` |
| OPL `conf_apps.cfg` (lista Apps) | `mass:/conf_apps.cfg` + `__system/OPL/conf_apps.cfg` | `opl_bootstrap`, `pfs_opl_config` |
| Não sobrescrever OPL existente | `PFS_BATCHKIT_PRESERVE_OPL_CFG=1` | `opl_bootstrap._preserve_opl_cfg` |
| FMCB Configurator USB = mesma ordem IRX | USB pen no boot FHDB via drivers sysconf | documentado |

## Melhorias alvesbeto **não** portadas (escopo MC)

- OpenTuna / `BXEXEC-OPENTUNA/` — Slim 9000x, não FHDB HDD.
- `FreeMcBoot/launcher2.c` SYS-CONF-first — código EE; no HDD o FHDB lê `__sysconf/FMCB/` via SP193, não este fork.
- Instalador EE `installer/main.c` — fluxo memory card.

## REA / Ghidra

Binários EE (`BOOT.ELF`) analisam-se com Ghidra **R5900** (`r5900:LE:32:default`). Evidência de ordem USB: **fonte** `launcher2.c` no fork alvesbeto + `.agents/specs/USB_IRX_MATRIX.md`.

## Referências

- [FHDB_OPL_BOOT.md](FHDB_OPL_BOOT.md)
- [OPL_EXFAT_COMPAT.md](OPL_EXFAT_COMPAT.md)
- Upstream FunTuna: [israpps/Funtuna-Fork](https://github.com/israpps/Funtuna-Fork)
