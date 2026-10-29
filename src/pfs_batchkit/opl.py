"""Open PS2 Loader directory layout (BDM exFAT root + OPL Manager V24)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# OPL supportbase sbCreateFolders (HDD BDM) + POPS (BatchKit / Manager)
OPL_DIR_NAMES: tuple[str, ...] = (
    "CD",
    "DVD",
    "VMC",
    "ART",
    "THM",
    "LNG",
    "CHT",
    "APPS",
    "POPS",
)

# OPL Manager V24 (OplFolders) minimum to scan library
OPL_MANAGER_REQUIRED: tuple[str, ...] = ("CD", "DVD", "ART")

CFG_DIR_NAME = "CFG"
CFG_DEV_DIR_NAME = "CFG-DEV"

# Backward-compatible alias
OPL_ROOT_DIRS = OPL_DIR_NAMES + (CFG_DIR_NAME,)


@dataclass(frozen=True)
class OplTreeResult:
    root: Path
    created_dirs: tuple[str, ...]
    readme_path: Path | None
    bootstrap_messages: tuple[str, ...] = ()


def opl_cfg_dir_name(*, cfg_dev: bool = False) -> str:
    return CFG_DEV_DIR_NAME if cfg_dev else CFG_DIR_NAME


def write_opl_tree(
    root: Path,
    *,
    cfg_dev: bool = False,
    volume_label: str = "PS2OPL",
    download_opl_elf: bool = True,
) -> OplTreeResult:
    """
    Create OPL + OPL Manager folder tree on the exFAT volume root.

    Aligns with:
    - Open PS2 Loader BDM (CD/DVD/…/APPS)
    - OPL Manager V24 ``OplFolders.create()`` (CD, DVD, CFG, CHT, ART, VMC, APPS, POPS)
    """
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    for name in OPL_DIR_NAMES:
        (root / name).mkdir(exist_ok=True)
        created.append(name)

    cfg_name = opl_cfg_dir_name(cfg_dev=cfg_dev)
    (root / cfg_name).mkdir(exist_ok=True)
    created.append(cfg_name)

    for name in created:
        keep = root / name / ".opl_ready"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")

    readme = root / "LEIA-ME_OPL.txt"
    readme.write_text(_readme_text(root, volume_label=volume_label, cfg_dir=cfg_name), encoding="utf-8")

    from .opl_bootstrap import bootstrap_opl_runtime

    bootstrap = bootstrap_opl_runtime(root, download_opl=download_opl_elf)

    return OplTreeResult(
        root=root,
        created_dirs=tuple(created),
        readme_path=readme,
        bootstrap_messages=bootstrap.messages,
    )


def _readme_text(root: Path, *, volume_label: str, cfg_dir: str) -> str:
    return f"""PFS BatchKit — pastas OPL prontas
Raiz da biblioteca (exFAT): {root}
Volume label sugerido: {volume_label}

=== Open PS2 Loader (PS2) ===
1. Settings → Block devices → ativar HDD (GPT/MBR) / BDM HDD
2. Settings → Enable Write Operations (para VMC, renomear, etc.)
3. Jogos ISO/ZSO: pasta DVD/ (PS2 DVD) ou CD/ (PS2 CD)
4. Homebrew: APPS/<nome>/title.cfg + boot ELF
5. POPS: POPS/ (PS1)

=== OPL Manager V24 (PC) ===
Defina OPL_FOLDER para esta pasta (raiz do exFAT montado):
  {root}

Pastas mínimas para o Manager escanear: CD/, DVD/, ART/
CFG por jogo: {cfg_dir}/
Capas: ART/<ID>_COV.png
UL (opcional): ul.cfg + ul.* na raiz

Formatos de disco: .iso .zso (CD e DVD)

Não use Format/Expand do wLaunchELF no HDD após FHDB.
Referência: https://github.com/ps2homebrew/Open-PS2-Loader
"""


def verify_opl_tree(root: Path, *, cfg_dev: bool = False) -> tuple[bool, list[str]]:
    """Return (ok, missing dir names)."""
    root = Path(root)
    missing: list[str] = []
    for name in OPL_DIR_NAMES:
        if not (root / name).is_dir():
            missing.append(name)
    cfg = opl_cfg_dir_name(cfg_dev=cfg_dev)
    if not (root / cfg).is_dir():
        missing.append(cfg)
    for req in OPL_MANAGER_REQUIRED:
        if req in missing:
            pass  # already listed
    ok = not missing and all((root / r).is_dir() for r in OPL_MANAGER_REQUIRED)
    return ok, missing
