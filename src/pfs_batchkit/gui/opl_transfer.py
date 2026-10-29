"""Copy disc images into OPL CD/DVD folders (OPL Manager / OPL compatible names)."""

from __future__ import annotations

import shutil
from pathlib import Path

DISC_EXTENSIONS = frozenset({".iso", ".zso"})
DVD_SIZE_THRESHOLD = 700_000_000


def pick_medium(size_bytes: int) -> str:
    return "DVD" if size_bytes >= DVD_SIZE_THRESHOLD else "CD"


def iter_disc_files(source_dir: Path) -> list[Path]:
    source_dir = source_dir.expanduser().resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Pasta não encontrada: {source_dir}")
    files: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in DISC_EXTENSIONS:
            files.append(path)
    return files


def copy_games_to_opl_library(
    opl_root: Path,
    source_dir: Path,
    *,
    medium: str | None = None,
    flat_names: bool = True,
) -> tuple[int, list[str]]:
    """
    Copy .iso/.zso into OPL_ROOT/CD or DVD.

    ``opl_root`` must contain CD/ and DVD/ (use after prepare or write_opl_tree).
    """
    from ..opl import OPL_MANAGER_REQUIRED, verify_opl_tree

    opl_root = opl_root.expanduser().resolve()
    ok, missing = verify_opl_tree(opl_root)
    if not ok:
        need = ", ".join(OPL_MANAGER_REQUIRED)
        return 2, [
            f"Raiz OPL inválida: {opl_root}",
            f"Faltam pastas (mínimo Manager): {missing}",
            f"Esperado pelo menos: {need}",
        ]

    try:
        sources = iter_disc_files(source_dir)
    except OSError as exc:
        return 2, [str(exc)]

    if not sources:
        return 2, [f"Nenhum .iso/.zso em {source_dir}"]

    lines: list[str] = []
    copied = 0
    for src in sources:
        med = medium or pick_medium(src.stat().st_size)
        dest_dir = opl_root / med
        dest_dir.mkdir(exist_ok=True)
        dest_name = src.name if flat_names else f"{src.stem}{src.suffix.lower()}"
        dest = dest_dir / dest_name
        if dest.exists() and dest.stat().st_size == src.stat().st_size:
            lines.append(f"Pulado (já existe): {med}/{dest_name}")
            continue
        shutil.copy2(src, dest)
        copied += 1
        lines.append(f"Copiado → {med}/{dest_name} ({src.stat().st_size} bytes)")

    lines.insert(0, f"Origem: {source_dir}")
    lines.insert(1, f"Biblioteca OPL: {opl_root}")
    lines.append(f"Total copiados: {copied} de {len(sources)}")
    return 0, lines
