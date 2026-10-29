# Compilar para todas as plataformas

PyInstaller **não faz cross-compile**: cada OS precisa do seu próprio build.

## Nesta máquina (Linux)

```bash
./packaging/build-native-release.sh
# ou, mais rápido no dia a dia:
./packaging/build.sh --cli-only          # só CLI
./packaging/build.sh --fast              # só GUI (PySide6 = lento na 1ª vez)
pip install -e ".[gui]" && pfs-batchkit-ui   # dev sem PyInstaller
```

**Por que demora:** PyInstaller + `collect_all(PySide6)` analisa centenas de MB de Qt. Evite `--clean` em rebuilds; UPX está desligado nos `.spec` para acelerar.

Saída:

```text
dist/releases/linux-x86_64/
  pfs-batchkit
  pfs-batchkit-ui
  pfsshell
```

## macOS + Windows (GitHub Actions)

1. Envie o repositório para o GitHub (branch `main` ou `master`).
2. **Actions** → workflow **Build** → **Run workflow** (ou push normal).
3. Baixe os artefactos:
   - `pfs-batchkit-linux-x86_64`
   - `pfs-batchkit-macos-arm64` (`.exe` não — binários macOS)
   - `pfs-batchkit-windows-x86_64` (`pfs-batchkit.exe`, `pfs-batchkit-ui.exe`)
   - `pfs-batchkit-all-platforms` (dispatch/tag — pasta com os três)

No Windows, os executáveis têm sufixo `.exe`. Coloque `pfsshell.exe` manualmente ao lado (release ps2homebrew) até existir build automático no CI para Win/mac.

## Por que não dá só no Linux?

| Alvo | Motivo |
|------|--------|
| macOS | Binário Mach-O; linker/SDK Apple |
| Windows | PE `.exe`; PyInstaller usa bootloader Windows |

Imagens Docker Wine (ex. `cdrx/pyinstaller-windows`) usam Python 3.7 — este projeto exige **3.11+**.
