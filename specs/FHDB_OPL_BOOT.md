# Boot FHDB + OPL (paridade PFS-BatchKit-Manager)

Layout **APA-Jail híbrido** (384 MiB + exFAT), não formatação APA completa no PC como a opção 8 clássica do Manager.

## O que o prepare-device deixa pronto no PC

| Componente | BatchKit Manager (equivalente) | PFS BatchKit |
|------------|-------------------------------|--------------|
| `__mbr` + KELF / wLaunchELF | `BAT/mbr.img` + **`BAT/boot.kelf`** | `mbr.img` + **[wLaunchELF_R3Z](https://github.com/saildot4k/wLaunchELF_R3Z)** `WLE-R3Z-DS34.ELF` → `kelftool encrypt mbr` (defeito; **ata:/ exFAT**). Fallback: Manager `boot.kelf`. `PFS_BATCHKIT_WLAUNCHELF_EXFAT=0` |
| `wLaunchELF no exFAT` | (opcional USB) | `APPS/wLaunchELF/WLE-R3Z-DS34.ELF` + `LAUNCHELF.CNF` + entrada em `conf_apps.cfg` |
| Magic APAJ + MBR 55 AA | Hack / imagem premade | `patch_apaj_and_mbr_entry` |
| `__system` / `__sysconf` PFS | Format no PS2 ou NBD | `--init-pfs` (pfsshell mkfs) |
| exFAT + pastas OPL | Transfer / format | **`format-exfat`** após FHDB (prepare **não** mkfs por defeito) |
| `conf_opl.cfg` BDM HDD | Manual no OPL | exFAT: chaves oficiais OPL (`enable_bdm_hdd`, `hdd_mode=0`, …) |
| `conf_apps.cfg` | USB BatchKit | exFAT: OPL + **wLaunchELF R3Z** + FreeMcBoot (`mass:APPS/…`) |
| `OPNPS2LD.ELF` | Manager / USB | **[Open-PS2-Loader `releases/latest`](https://github.com/ps2homebrew/Open-PS2-Loader/releases/latest)** (rolling dev build) → `APPS/OPL/` |
| `__system/OPL/conf_hdd.cfg` | HDD-OSD Manager | PFS: `hdd_partition=__common` + nota biblioteca exFAT |
| FMCBInstaller | `!COPY_TO_USB_ROOT` | `PFS_BATCHKIT_FMCB_INSTALLER` ou clone Manager |
| FHDB instalado em `__system` | **Install HDD-OSD** no PC (`HDD-OSD/__system` + pfsshell) ou FMCB no PS2 | **Igual ao Manager no PC** se existir pasta `HDD-OSD` do clone; senão FMCBInstaller no PS2 |

## Passo no PS2 (FreeHDBoot)

No **Manager real**, quem instala o menu OSD/FHDB no disco, na maioria dos fluxos, é **OSD/XMB Management → Install HDD-OSD** no **PC**: copia `PFS-BatchKit-Manager/HDD-OSD/__system` (e `__sysconf`) via **pfsshell** — **sem** abrir o PS2. Essa pasta **não vem completa no GitHub** (ficheiros Sony/Browser); fica no teu clone depois de extraíres o HDD-OSD (ex. `hddosd-1.10-u.7z`) ou de um HDD já preparado.

O README do Manager ainda descreve o fluxo **clássico** (format no wLaunchELF + FMCBInstaller no PS2). Muita gente só vê o resultado “pronto” porque o **Install HDD-OSD** no PC já correu (ou o `HDD-OSD/` local já estava populado).

**PFS BatchKit** passa a tentar o **mesmo inject no PC** após `--init-pfs`, se detectar `HDD-OSD/__system` com `osd/osdmain.elf` ou `osd100/hosdsys.elf`:

- `PFS_BATCHKIT_MANAGER_ROOT` — raiz do clone Manager  
- `PFS_BATCHKIT_FHDB_PAYLOAD` — pasta espelho só de `__system`  
- `PFS_BATCHKIT_SKIP_HDD_OSD=1` — não injectar

| Etapa | Manager (opção 8 + README) | PFS BatchKit (`prepare-device`) |
|-------|------------------------------|----------------------------------|
| Hack `mbr.img` / APAJ | Sim (PC) | Sim (PC) |
| PFS `__system` / `__sysconf` | Format no **PS2** (HDD Manager) | **`mkfs` no PC** (`--init-pfs`) |
| APPS + FMCBInstaller | Copiar USB `!COPY_TO_USB_ROOT` | Já no **exFAT** (`APPS/FreeMcBoot/`) se instalador disponível |
| **Menu OSD FHDB no boot** | Só após **Install FHDB (From HDD)** no PS2 | **Igual** — obrigatório uma vez |
| Boot antes do passo FHDB | wLaunchELF (entrada do hack) | wLaunchELF (normal) |

**Atenção:** `--init-pfs` faz **mkfs** e **apaga** FreeHDBoot já instalado em `__system`. Disco que já bootava FHDB no Manager deixa de o fazer até repetir Install FHDB (ou restaurar backup via `PFS_BATCHKIT_FHDB_PAYLOAD`).

Não redistribuímos os binários FHDB/Sony em `__system` (mesma razão do Manager: FMCBInstaller no PS2 ou pasta espelho sua).

Com este projeto, após prepare:

1. Ligue o PS2 com o HDD — boot pela cadeia do `mbr.img` (wLaunchELF R3Z ou Manager `boot.kelf`).
2. wLaunchELF → exFAT BDM → **APPS/FreeMcBoot** → `FMCBInstaller.elf` → **Install FHDB (From HDD)**.
3. Reinicie — menu OSD FreeHDBoot (`__system/osd/osdmain.elf`).
4. No PC: **`pfs-batchkit finalize-fhdb DISCO --force`** (patch `FREEHDB.CNF` + ATA-Assault; paridade Manager).
5. Reinicie o PS2; depois **`pfs-batchkit format-exfat DISCO --force`** para biblioteca ISO em `mass:`.
6. Abra **OPL** — BDM HDD já activo via `conf_opl.cfg` (após exFAT formatado).

**Não** use Format / Expand no HDD Manager do wLaunchELF. **Não** rode `prepare-pfs` / `--init-pfs` depois do FHDB (apaga `__system`).

## FreeHDBoot + exFAT no mesmo disco (APA-Jail)

**Observação (estática + comunidade PS2):** no arranque, o FHDB carrega **ps2atad** para PFS (`hdd0:`). Se a fatia **MBR exFAT** já tiver superblock formatado, módulos BDM podem tentar um **segundo** driver ATA no mesmo barramento → **freeze** no início do boot (mesma classe que [OPL PR #1688](https://github.com/ps2homebrew/Open-PS2-Loader/pull/1688) / APA-Jail CosmicScale).

**PFS BatchKit (prepare-device):**

1. Ordem: PFS → inject FHDB/HDD-OSD → **ATA-Assault** em `__sysconf/FMCB/USBD.IRX` + `USBHDFSD.IRX` → exFAT (se permitido).
2. Por defeito o prepare **não formata exFAT** (partição MBR reservada; superblock ausente até FHDB no PS2).
3. **`pfs-batchkit format-exfat DISCO --force`** só corre com **osdmain.elf + ATA-Assault** (gate em código).
4. Expert: `PFS_BATCHKIT_FORMAT_EXFAT_ON_PREPARE=1` + `--format-exfat` no prepare (ainda exige FHDB+ATA).

**Ordem ATA-Assault (paridade Manager):** o Manager **não** coloca ATA-Assault antes do FMCBInstaller. O prepare **adiar** ATA até existir `osdmain.elf` (inject HDD-OSD no PC ou Install FHDB no PS2). Depois do PS2:

```bash
pfs-batchkit finalize-fhdb /dev/sdX --force   # FREEHDB.CNF + ATA-Assault
# reinicie o PS2 → menu OSD
pfs-batchkit format-exfat /dev/sdX --force    # exFAT + pastas OPL
```

Legacy: `PFS_BATCHKIT_ATA_BEFORE_FHDB=1` volta a injectar ATA no prepare (pode interferir com FMCBInstaller).

Variáveis: `PFS_BATCHKIT_SKIP_ATA_ASSAULT`, `PFS_BATCHKIT_ATA_ASSAULT_DIR`, `PFS_BATCHKIT_DEFER_EXFAT=1`, `PFS_BATCHKIT_ATA_BEFORE_FHDB`.

Análise REA: binários PS2 (MIPS) exigem Ghidra/IDA configurados; a conclusão acima alinha-se com documentação ATA-Assault e commits OPL/POPSLoader (drivers duplicados), não com pseudocódigo FHDB desassemblado neste ambiente.

## Configuração OPL (PFS vs exFAT)

| Ficheiro | Onde | Função |
|----------|------|--------|
| `conf_opl.cfg` | **Raiz exFAT** (`mass:`) | BDM HDD interno, gravação, modos (`hdd_mode=0` = sem HDLoader PFS) |
| `conf_apps.cfg` | Raiz exFAT | Entrada OPL em APPS (README OPL) |
| `conf_hdd.cfg` | **`__system/OPL/`** (PFS) | BatchKit: `hdd_partition=__common` — não criar `+OPL` para ISOs |
| ISO/ZSO | `mass:/DVD`, `mass:/CD` | Biblioteca real (sempre exFAT) |

Referência: [Open PS2 Loader](https://github.com/ps2homebrew/Open-PS2-Loader) — Expansion port HDD MBR+exFAT, `enable_bdm_hdd`.

## Variáveis opcionais

- `PFS_BATCHKIT_FMCB_INSTALLER` — caminho para `FMCBInstaller.elf` (copiado para exFAT).
- `PFS_BATCHKIT_FHDB_PAYLOAD` — pasta espelhando conteúdo de `__system` (instalação via pfsshell `put`, avançado).
- `PFS_BATCHKIT_BOOT_KELF` — KELF pronto (ignora build latest).
- `PFS_BATCHKIT_PS2KEYS` — caminho para `PS2KEYS.dat` (retail; necessário para gerar KELF latest). Com `sudo`, também procura `~/PS2KEYS.dat` do utilizador (`SUDO_USER`).
- `PFS_BATCHKIT_OPL_ELF` — `OPNPS2LD.ELF` local (ignora download).
- `PFS_BATCHKIT_SKIP_OPL_DOWNLOAD=1` — não baixar OPL (usa ficheiro já em `APPS/OPL/` se existir).
- `PFS_BATCHKIT_KELFTOOL` — binário `kelftool` (senão download automático ps2homebrew/kelftool).
- `PFS_BATCHKIT_SKIP_BOOT_KELF=1` — não substituir loader do `mbr.img`.
- `PFS_BATCHKIT_PRESERVE_OPL_CFG=1` — não sobrescrever `conf_opl.cfg` / `conf_apps.cfg` no exFAT (paridade FunTuna upgrade).

Paridade FunTuna-Fork (HDD): [FHDB_FUNTUNA_PARITY.md](FHDB_FUNTUNA_PARITY.md).

## Validação automática

Após prepare, o fluxo verifica:

- Loader __mbr + APAJ + MBR (`boot_ready.verify_boot_ready`)
- PFS montável em `__system` / `__sysconf`
- Layout OPL BDM/exFAT (`validate_opl_layout` no disco bruto)
