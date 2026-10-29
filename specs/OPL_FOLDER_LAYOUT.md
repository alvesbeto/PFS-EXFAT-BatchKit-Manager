# Layout de pastas OPL (exFAT)

Raiz = partição exFAT após os 384 MiB APA (volume label padrão `PS2OPL`).

## Alinhamento

| Fonte | Pastas |
|--------|--------|
| **OPL Manager V24** (`OplFolders.create`) | `CD`, `DVD`, `CFG` ou `CFG-DEV`, `CHT`, `ART`, `VMC`, `APPS`, `POPS` |
| **Open PS2 Loader** (`sbCreateFolders`, BDM HDD) | `CD`, `DVD`, `VMC`, `CFG`, `ART`, `THM`, `LNG`, `CHT`, `APPS` |
| **PFS BatchKit** `write_opl_tree()` | União acima + `POPS` + `LEIA-ME_OPL.txt` |

Mínimo para o **OPL Manager** escanear biblioteca: **`CD/`**, **`DVD/`**, **`ART/`** (mensagem `MAIN_STRINGS_OPL_FOLDER_LOAD_ERROR` se faltar).

## Uso no OPL Manager V24

1. Monte o exFAT no PC (Linux: `/media/.../PS2OPL`, Windows: letra atribuída, macOS: `/Volumes/PS2OPL`).
2. Defina **`OPL_FOLDER`** = pasta que contém `CD`, `DVD`, `ART` (não um subdiretório).
3. Jogos disco: `.iso` / `.zso` em `DVD/` ou `CD/`.
4. UL: `ul.cfg` + ficheiros `ul.*` na raiz (opcional).
5. APPS: subpastas com `title.cfg` + ELF.

## Uso no PS2 (Open PS2 Loader)

- Settings → **HDD (GPT/MBR)** / BDM HDD.
- Settings → **Enable Write Operations** para VMC/renomear.
- Jogos ISO aparecem via **BDM**, não na lista clássica HDLoader/PFS.

## Implementação

- `src/pfs_batchkit/opl.py` — `write_opl_tree()`, `verify_opl_tree()`
- Chamado após `mkfs.exfat` em `host/exfat_*.py` quando `scaffold_opl=True`
