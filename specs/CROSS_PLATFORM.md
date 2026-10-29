# Multiplataforma — PFS BatchKit

## Objetivo

Permitir o fluxo **imagem híbrida APA-Jail + PFS + exFAT + OPL** no PC em **Linux, macOS e Windows**, com binários PyInstaller gerados em CI por OS.

## Escopo por plataforma

| Capacidade | Linux | macOS | Windows |
|------------|-------|-------|---------|
| `build-image` (APA + sparse) | Sim | Sim | Sim |
| `init-pfs` (pfsshell) | Sim | Sim (pfsshell nativo) | Sim (pfsshell.exe) |
| `format-exfat` | losetup + mkfs.exfat | hdiutil slice + diskutil/mkfs.exfat | diskpart VHD + format exFAT |
| `scaffold-opl` | mount | mount exfat | letra de unidade |
| `prepare-device` | `/dev/sdX` | `/dev/rdiskN` | `\\.\PhysicalDriveN` |
| `prepare-pfs` | idem | idem | idem — só PFS (FHDB/OSD/OPL), exFAT intacto |
| TUI (Textual) | Sim | Sim | Sim |

## Privilégios

- **Linux/macOS:** root ou `sudo` interativo (não depender só de `sudo -n` na UI).
- **Windows:** terminal **Administrador** (UAC); sem elevação automática.

## Dependências externas

| OS | exFAT | PFS |
|----|-------|-----|
| Linux | `exfatprogs` (`mkfs.exfat`), `losetup`, `mount` | `tools/bin/pfsshell` ou PATH |
| macOS | `brew install exfatprogs` (opcional se usar `diskutil eraseVolume`) | pfsshell compilado ou release |
| Windows | format nativo `fs=exfat` (Win10+) via diskpart | `pfsshell.exe` ao lado do binário ou PATH |

## Variáveis de ambiente

- `PFS_BATCHKIT_PFSSHELL` — caminho do pfsshell
- `PFS_BATCHKIT_ALLOW_WRITE=1` — confirmar gravação em disco físico
- `PFS_BATCHKIT_USE_SUDO=1` — Linux/macOS: prefixo `sudo -n` (CLI); UI preferir sudo interativo

## CI (GitHub Actions)

Matriz `ubuntu-latest`, `macos-latest`, `windows-latest`:

1. `uv venv` + `pip install -e ".[build,ui]"`
2. `pyinstaller` → artefatos `pfs-batchkit`, `pfs-batchkit-ui`
3. Linux: compilar pfsshell e anexar ao artefato
4. macOS/Windows: baixar pfsshell de release ps2homebrew quando disponível (ou compilar em job dedicado)

## Fora de escopo (v1)

- NBD, transferência de jogos, POPS (BatchKit original)
- Imagem &gt; 2 TiB (limite prático MBR LBA32)
- Elevação UAC automática no Windows

## Critérios de aceite

1. `format_exfat_requirements_hint()` descreve deps corretas por OS.
2. `format_exfat_region()` delega para backend sem quebrar Linux existente.
3. `prepare-device` grava só a região APA + metadados e formata exFAT in-place (sem clonar `.img` inteira).
4. README documenta fluxo por OS.
