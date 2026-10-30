# GUI Wizard (Qt / PySide6)

## Objetivo

Assistente gráfico: **preparar HDD**, validar `.img` e modo avançado — num único `pfs-batchkit-ui`.

## Fluxos (menu na boas-vindas)

| Modo | Páginas |
|------|---------|
| **Preparar HDD** | Disco → Opções → Executar → Resumo |
| **Atualizar só PFS** | Disco → Opções (sem exFAT) → Executar → Resumo — exFAT/jogos intactos |
| **Finalizar FHDB** | Disco → Opções → Executar → Resumo (após Install FHDB no PS2) |
| **Importar jogos** | Raiz OPL + pasta ISOs → Executar → Resumo (`.iso`/`.zso` → CD/DVD) |
| **Validar layout** | Imagem + opções strict/exFAT → Executar → Resumo |
| **Transferir jogos** | Menu «Importar jogos» ou botão no resumo pós-prepare |
| **Modo avançado** | Submenu: criar `.img`, validar, só pastas OPL |

## Pós-preparar (transferir jogos)

- No **Linux**, após formatar exFAT + pastas OPL, `format_exfat_region` **remonta** o volume em `/mnt/PS2OPL` (uid/gid do usuário que invocou sudo) em vez de só desmontar o mount temporário.
- A UI recebe `OPL_MOUNT:/mnt/PS2OPL` no log e preenche `opl_root`; botão **Transferir jogos agora…** abre o fluxo de cópia.
- Desmontar quando terminar: `sudo umount /mnt/PS2OPL` (o loop losetup é liberado ao desmontar em muitos casos; senão `sudo losetup -D`).

## Transferência de jogos

- Módulo: `gui/opl_transfer.py`
- Copia `.iso`/`.zso` para `CD/` ou `DVD/` (auto ≥700 MiB → DVD)
- Exige árvore OPL (`write_opl_tree` / prepare-device)
- Alinhado ao **OPL Manager V24** (`OPL_FOLDER` = raiz exFAT)

## Implementação

- `gui/page_ids.py` — IDs para `QWizard.setPage()`
- `gui/wizard_pages.py` — páginas + `AsyncRunPage` (Avançar só após sucesso)
- `gui/workers.py` — threads (prepare, validate, write, copy, build, scaffold)
- `gui/wizard.py` — `PS2HddWizard`

## Build

```bash
pip install -e ".[gui]"
pfs-batchkit-ui
```

PyInstaller: `packaging/pfs-batchkit-ui.spec` (incluir `gui.wizard_pages`, `gui.opl_transfer`).
