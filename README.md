# PFS-EXFAT BatchKit

Ferramenta em **Python** (Linux, macOS, Windows) para preparar um HDD de PlayStation 2 no layout **híbrido APA-Jail + exFAT**: região APA mínima (~384 MiB) para **FreeHDBoot** / PFS e o restante do disco em **exFAT** com biblioteca **Open PS2 Loader** (BDM HDD), pastas oficiais e configs prontas.

Inspirado no fluxo do [PFS-BatchKit-Manager](https://github.com/GDX-X/PFS-BatchKit-Manager), com foco explícito em **boot FHDB + jogos exFAT no mesmo disco**, sem formatação APA completa no PC como a opção clássica do Manager.

Os comandos instalados mantêm o nome histórico **`pfs-batchkit`** / **`pfs-batchkit-ui`** (pacote Python `pfs-batchkit`).

## O que este projeto faz

| Área | Comportamento |
|------|----------------|
| **Layout** | MBR tipo 0x07 (exFAT), magic APAJ, região APA-Jail + partição de jogos até o último setor |
| **Boot `__mbr`** | `mbr.img` do Manager + KELF MBR; por defeito **[wLaunchELF R3Z](https://github.com/saildot4k/wLaunchELF_R3Z)** (`WLE-R3Z-DS34.ELF`) com suporte **ata:/ exFAT** (requer `PS2KEYS.dat` + `kelftool`) |
| **PFS** | `mkfs` em `__system` / `__sysconf` via **pfsshell** (patch `mkfs` incluído) |
| **FHDB / OSD** | Inject de `HDD-OSD/__system` no PC se existir clone do Manager; senão **FMCBInstaller** no PS2 |
| **exFAT + OPL** | `mkfs.exfat`, árvore `CD/`, `DVD/`, `APPS/`, …, `conf_opl.cfg` (BDM HDD), `conf_apps.cfg`, download de **OPNPS2LD.ELF** |
| **wLaunchELF no volume** | `APPS/wLaunchELF/` + `LAUNCHELF.CNF` no exFAT |
| **Estabilidade FHDB+exFAT** | Drivers **ATA-Assault** em `__sysconf/FMCB/` antes de formatar exFAT (evita freeze no boot) |

Documentação detalhada:

- [specs/FHDB_OPL_BOOT.md](specs/FHDB_OPL_BOOT.md) — boot, FHDB, variáveis  
- [specs/OPL_EXFAT_COMPAT.md](specs/OPL_EXFAT_COMPAT.md) — BDM, APA-Jail, armadilhas  
- [specs/OPL_FOLDER_LAYOUT.md](specs/OPL_FOLDER_LAYOUT.md) — pastas na raiz exFAT  
- [specs/CROSS_PLATFORM.md](specs/CROSS_PLATFORM.md) — requisitos por SO  
- [specs/DEVICE_READINESS.md](specs/DEVICE_READINESS.md) — `doctor` / `verify-device`  
- [specs/GUI_WIZARD.md](specs/GUI_WIZARD.md) — assistente Qt  

## Requisitos

- **Python 3.11+**
- **Linux:** sudo/root + `exfatprogs` (`losetup`, `mkfs.exfat`, `mount`)
- **macOS:** sudo/admin + `hdiutil` / `diskutil` (opcional: `brew install exfatprogs`)
- **Windows:** terminal **Administrador** + `diskpart` (exFAT nativo)
- **pfsshell** com comando `mkfs` — [build local](#pfsshell-com-mkfs) ou `PFS_BATCHKIT_PFSSHELL`
- **PS2KEYS.dat** — KELF MBR R3Z (home ou `PFS_BATCHKIT_PS2KEYS`; também no clone Manager `BAT/`)
- **FMCBInstaller.elf** — opcional no PC (`PFS_BATCHKIT_FMCB_INSTALLER` ou `tools/bundled/`); senão uma vez no PS2 ([FHDB_OPL_BOOT.md](specs/FHDB_OPL_BOOT.md))

## Instalação (desenvolvimento)

```bash
git clone <url-do-repositorio>
cd PFS-EXFAT-BatchKit   # nome da pasta local

# com uv (recomendado)
uv venv .venv
uv pip install -e ".[dev,gui]"

# ou pip
python3 -m pip install -e ".[dev,gui]"
```

## Fluxo recomendado: disco físico

Como no Manager: liste discos, confira **modelo e tamanho**, escolha pelo índice **`[N]`**. Discos com `/`, `/boot` ou `/home` montados são recusados.

```bash
pfs-batchkit list-disks

pfs-batchkit doctor

sudo pfs-batchkit prepare-device --pick 1 --init-pfs --force
# Depois do Install FHDB no PS2:
sudo pfs-batchkit format-exfat /dev/sdX --force
```

Ou assistente gráfico:

```bash
pfs-batchkit-ui
# Linux: sudo pfs-batchkit-ui  (ou senha sudo no wizard)
```

Após o prepare, opcional:

```bash
pfs-batchkit verify-device /dev/sdX --exfat-mount /mnt/PS2OPL --expect-exfat
```

No PS2: leia `LEIA-ME_PS2_BOOT.txt` na raiz exFAT. Primeiro boot pode abrir **wLaunchELF** até instalar FHDB (`APPS/FreeMcBoot/FMCBInstaller.elf` → Install FHDB). **Não** use Format/Expand no HDD Manager do wLaunchELF.

### Atualizar só PFS (manter jogos exFAT)

Reformata `__system` / `__sysconf`, reinjecta FHDB/OPL/ATA-Assault **sem** apagar a partição exFAT:

```bash
sudo pfs-batchkit prepare-pfs --pick 1 --force
```

## CLI — outros comandos

| Comando | Uso |
|---------|-----|
| `build-image` | Imagem `.img` para backup/validação (não clonar 500 GiB no disco) |
| `init-pfs` / `format-exfat` | Passos isolados numa imagem existente |
| `scaffold-opl` | Pastas OPL num exFAT já montado |
| `validate-opl-layout` | MBR/APAJ/exFAT antes de gravar |
| `doctor` | Dependências no PC |
| `verify-device` | Checklist pós-prepare |

Exemplo imagem offline:

```bash
pfs-batchkit build-image --size-gib 500 --output ~/ps2-hdd.img --init-pfs
# exFAT na imagem só após FHDB+ATA no destino: format-exfat
```

## pfsshell com `mkfs`

O upstream do pfsshell não expõe `mkfs`; este repositório inclui `tools/pfsshell-mkfs.patch`:

```bash
chmod +x tools/build_pfsshell.sh
./tools/build_pfsshell.sh   # → tools/bin/pfsshell
```

## Variáveis de ambiente (seleção)

| Variável | Efeito |
|----------|--------|
| `PFS_BATCHKIT_PFSSHELL` | Caminho do pfsshell |
| `PFS_BATCHKIT_MANAGER_ROOT` | Clone [PFS-BatchKit-Manager](https://github.com/GDX-X/PFS-BatchKit-Manager) (`HDD-OSD/`, `BAT/`) |
| `PFS_BATCHKIT_FMCB_INSTALLER` | `FMCBInstaller.elf` |
| `PFS_BATCHKIT_BOOT_KELF` / `PFS_BATCHKIT_SKIP_BOOT_KELF` | KELF MBR custom ou não injectar |
| `PFS_BATCHKIT_WLAUNCHELF_EXFAT=0` | Usar `BAT/boot.kelf` do Manager (sem R3Z ata exFAT) |
| `PFS_BATCHKIT_WLAUNCHELF_LATEST=1` | ps2homebrew latest em vez de R3Z |
| `PFS_BATCHKIT_DEFER_EXFAT=1` | Não formatar exFAT no prepare (FHDB no PS2 antes) |
| `PFS_BATCHKIT_PRESERVE_OPL_CFG` | Não sobrescrever `conf_opl.cfg` / `conf_apps.cfg` no exFAT |

Lista completa: [specs/FHDB_OPL_BOOT.md](specs/FHDB_OPL_BOOT.md).

## Executáveis (PyInstaller)

Gere binários **no sistema alvo**:

```bash
./packaging/build.sh
# dist/pfs-batchkit      — CLI
# dist/pfs-batchkit-ui   — assistente Qt
# dist/pfsshell          — se tools/bin/pfsshell existir
```

Opções: `--cli-only`, `--gui-only`, `--fast`, `--parallel`, `--clean`. CI e releases: [packaging/BUILD_ALL.md](packaging/BUILD_ALL.md), `.github/workflows/build.yml`.

Build local em `dist/releases/<plataforma>/`:

```bash
./packaging/build-native-release.sh
```

## Testes

```bash
uv run pytest
# ou
PYTHONPATH=src python3 -m pytest
```

Testes manuais (referência `mbr.img` em `/tmp/pfs-batchkit/`):

```bash
PYTHONPATH=src python3 tests/run_manual.py
```

## Limitações e avisos

- Binários **Sony/FHDB** não são redistribuídos; use pasta `HDD-OSD` do Manager ou FMCBInstaller no PS2.
- `--init-pfs` **apaga** FHDB já presente em `__system` até repetir install ou restaurar payload.
- exFAT + FHDB no mesmo disco exige ordem correta (PFS → FHDB → ATA-Assault → exFAT); ver [OPL_EXFAT_COMPAT.md](specs/OPL_EXFAT_COMPAT.md).
- Imagens `.img` grandes são artefactos locais (ver `.gitignore`); o fluxo principal é **`prepare-device`**.

## Créditos

- [PFS-BatchKit-Manager](https://github.com/GDX-X/PFS-BatchKit-Manager) — layout e fluxo de referência  
- [Open-PS2-Loader](https://github.com/ps2homebrew/Open-PS2-Loader), [pfsshell](https://github.com/ps2homebrew/pfsshell), [wLaunchELF_R3Z](https://github.com/saildot4k/wLaunchELF_R3Z)  

Licença: ver ficheiros `COPYING` / cabeçalhos dos componentes nativos (pfsshell) e dependências upstream.
