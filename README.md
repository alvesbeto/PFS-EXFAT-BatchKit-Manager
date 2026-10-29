# PFS BatchKit (Python)

Ferramenta para preparar um HDD de PS2 em layout **híbrido APA-Jail**: região APA mínima para **FreeHDBoot** (384 MiB) e o restante em **exFAT** com a árvore de pastas do **Open PS2 Loader**.

Inspirado no fluxo do [PFS-BatchKit-Manager](https://github.com/GDX-X/PFS-BatchKit-Manager), mas focado no layout boot + exFAT em vez de formatação APA completa no PC.

## Requisitos

- Python 3.11+
- **Linux:** sudo/root + `exfatprogs` (`losetup`, `mkfs.exfat`, `mount`)
- **macOS:** sudo/admin + `hdiutil`/`diskutil` (opcional: `brew install exfatprogs`)
- **Windows:** terminal **Administrador** + `diskpart` (format exFAT nativo)
- **pfsshell** com `mkfs` em todas as plataformas (`PFS_BATCHKIT_PFSSHELL` ou ao lado do `.exe`)
- **FMCBInstaller.elf** — copiado para `APPS/FreeMcBoot/` se `PFS_BATCHKIT_FMCB_INSTALLER` ou clone do Manager; senão, uma vez no PS2 (ver [specs/FHDB_OPL_BOOT.md](specs/FHDB_OPL_BOOT.md))

Spec completa: [specs/CROSS_PLATFORM.md](specs/CROSS_PLATFORM.md) · Boot FHDB+OPL: [specs/FHDB_OPL_BOOT.md](specs/FHDB_OPL_BOOT.md) · OPL/exFAT: [specs/OPL_EXFAT_COMPAT.md](specs/OPL_EXFAT_COMPAT.md)

## Instalação (desenvolvimento)

```bash
cd "/home/beto/Documentos/dev/Repositorios/PFS BatchKit"
python3 -m pip install -e ".[dev,gui]"
```

## Assistente gráfico (Qt)

Instalador passo a passo (Linux, Windows, macOS) — substitui o menu Textual:

```bash
python3 -m pip install -e ".[gui]"
pfs-batchkit-ui
# ou: pfs-batchkit ui
```

Etapas: escolha a **tarefa** na primeira tela (preparar disco, validar `.img`, modo avançado).

**Linux:** prefira `sudo ./pfs-batchkit-ui` ou informe a senha sudo na etapa de opções.

Detalhes: [specs/GUI_WIZARD.md](specs/GUI_WIZARD.md)

## CLI avançada (imagem .img, validação)

### pfsshell com comando `mkfs`

O upstream do pfsshell não expõe `mkfs`; este repo inclui um patch:

```bash
# pfsshell (uma vez; usa Flatpak SDK se meson não estiver no host)
chmod +x tools/build_pfsshell.sh
./tools/build_pfsshell.sh   # → tools/bin/pfsshell
```

Ou defina `PFS_BATCHKIT_PFSSHELL=/caminho/pfsshell`.

## Fluxo completo (imagem)

```bash
sudo env PYTHONPATH=src python3 -m pfs_batchkit.cli build-image \
  --size-gib 500 \
  --output ps2-hdd.img \
  --reference-mbr /tmp/pfs-batchkit/mbr.img \
  --init-pfs \
  --format-exfat
```

- **`--init-pfs`**: PFS vazio em `__system` e `__sysconf` via `tools/bin/pfsshell` (sem root em arquivos `.img`)
- **`--format-exfat`**: exFAT + pastas OPL (`DVD/`, `CD/`, …)

Comandos separados:

```bash
sudo env PYTHONPATH=src python3 -m pfs_batchkit.cli init-pfs ps2-hdd.img
sudo env PYTHONPATH=src python3 -m pfs_batchkit.cli format-exfat ps2-hdd.img
```

Pastas OPL num exFAT já montado:

```bash
pfs-batchkit scaffold-opl /mnt/PS2OPL
```

Validar imagem antes de gravar no disco (OPL BDM + exFAT):

```bash
pfs-batchkit doctor
pfs-batchkit validate-opl-layout ps2-hdd.img
pfs-batchkit validate-opl-layout ps2-hdd.img --require-exfat --strict
```

Antes de gravar no HDD PS2, rode **`doctor`** (pfsshell, ATA-Assault, HDD-OSD/FMCBInstaller). Após **`prepare-device`**, o fluxo imprime **Verificação dispositivo (PS2)**; opcional:

```bash
pfs-batchkit verify-device /dev/sdX --exfat-mount /mnt/PS2OPL --expect-exfat
```

## Executável (PyInstaller)

Gere binários **no sistema alvo** (Linux, Windows ou macOS):

```bash
./packaging/build.sh
# dist/pfs-batchkit      — CLI
# dist/pfs-batchkit-ui   — assistente Qt
# dist/pfsshell          — copiado se tools/bin/pfsshell existir
```

O script cria `.venv` com `uv` se necessário e instala `[build,gui]`.

**Tempo:** o `pfs-batchkit-ui` puxa **PySide6 inteiro** (`collect_all`) — espere vários minutos na primeira vez. Rebuilds são mais rápidos **sem** `--clean`. Para iterar na UI, use `pip install -e ".[gui]"` e `pfs-batchkit-ui` (sem PyInstaller).

```bash
./packaging/build.sh              # CLI + GUI (incremental)
./packaging/build.sh --cli-only   # só CLI (~rápido)
./packaging/build.sh --fast        # só GUI (quando já tem CLI no venv)
./packaging/build.sh --parallel    # CLI + GUI em paralelo
./packaging/build.sh --clean       # rebuild total (lento; use só se quebrar cache)
```

CI gera binários para Linux, macOS e Windows (ver `.github/workflows/build.yml` e [packaging/BUILD_ALL.md](packaging/BUILD_ALL.md)).

Build local (só o OS atual):

```bash
./packaging/build-native-release.sh
# → dist/releases/linux-x86_64/  (no Linux)
```

## Gravar disco físico

**Fluxo recomendado:** preparar **direto no disco** (`prepare-device`) — o app lê o tamanho real, grava a região APA (384 MiB) com MBR/exFAT até o último setor, e opcionalmente roda PFS + exFAT. A imagem `.img` serve só para **backup** ou **validação offline** (`build-image` + `validate-opl-layout`), não para clonar 500 GiB no disco.

Como no [PFS-BatchKit-Manager](https://github.com/GDX-X/PFS-BatchKit-Manager): liste os discos, confira **modelo/tamanho**, escolha pelo **índice `[N]`**.

```bash
pfs-batchkit list-disks

# Preparar in-place (Linux) — como root OU senha na GUI
sudo ./pfs-batchkit-ui
# ou, no terminal:
sudo pfs-batchkit prepare-device --pick 1 --init-pfs --format-exfat --force
```

**Actualizar menu OSD / FreeHDBoot / OPL (PFS) sem apagar jogos exFAT:**

```bash
sudo pfs-batchkit prepare-pfs --pick 1 --force
```

Na UI: tarefa **«Atualizar só PFS (FHDB/OSD/OPL) — manter exFAT/jogos»**. Requer `HDD-OSD/__system` do clone Manager (ou `PFS_BATCHKIT_FHDB_PAYLOAD`).

Na **TUI**: *Preparar disco físico* (ou tecla correspondente no menu).

Discos com montagem em `/`, `/boot` ou `/home` são **recusados** automaticamente.

## Testes

```bash
PYTHONPATH=src python3 tests/run_manual.py
PYTHONPATH=src python3 tests/test_host.py
PYTHONPATH=src python3 tests/test_opl_validate.py
```

## Limitações (v0.4)

- UI: menu TUI (Textual); não é GUI Windows como o BatchKit original
- PFS: pfsshell com patch `mkfs` (build Linux no repo; Win/mac via release ou build local)
- exFAT: backends por OS (ver spec); teste real em macOS/Windows recomendado antes de produção
- PyInstaller: um binário **por** OS (CI em `.github/workflows/build.yml`)
