# Dispositivo PS2 — dependências e verificação

## Antes do prepare

```bash
pfs-batchkit doctor
```

| Item | Obrigatório | Função |
|------|-------------|--------|
| pfsshell | sim (com `--init-pfs`) | mkfs/inject PFS |
| ATA-Assault IRX | sim | `__sysconf/FMCB/` — exFAT + FHDB |
| mkfs.exfat / losetup | Linux + `--format-exfat` | Partição jogos |
| HDD-OSD `__system` | recomendado | `osdmain.elf` sem PS2 |
| FMCBInstaller.elf | alternativa | Install FHDB no PS2 |
| boot KELF + mbr.img | prepare completo | **R3Z** KELF (`PS2KEYS` + kelftool) ou `PFS_BATCHKIT_BOOT_KELF`; wLaunchELF R3Z em `APPS/wLaunchELF/` |

## Durante `prepare-device`

Ordem garantida no código:

1. Região APA-Jail + loader __mbr  
2. PFS mkfs (`__system`, `__sysconf`)  
3. Inject HDD-OSD / FHDB payload  
4. OPL PFS (`conf_hdd.cfg`, `conf_apps.cfg`)  
5. **ATA-Assault** em `__sysconf/FMCB/`  
6. Validação FHDB + ATA antes de formatar exFAT (evita tela preta)  
7. exFAT + `write_opl_tree` (`conf_opl.cfg`, `conf_apps.cfg`, APPS)  
8. Boot/layout + **Verificação dispositivo (PS2)**

## Depois do prepare

```bash
pfs-batchkit verify-device /dev/sdX --exfat-mount /mnt/PS2OPL --expect-exfat
```

No volume exFAT: `LEIA-ME_PS2_BOOT.txt` e `LEIA-ME_FHDB.txt`.

Paridade configs FunTuna: [FHDB_FUNTUNA_PARITY.md](FHDB_FUNTUNA_PARITY.md).
