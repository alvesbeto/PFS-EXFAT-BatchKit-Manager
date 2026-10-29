"""Empty APA partition passwords."""

from __future__ import annotations

# Validated against PFS-BatchKit Manager BAT/mbr.img (rpwd/fpwd).
_KNOWN_EMPTY: dict[str, bytes] = {
    "__mbr": bytes.fromhex("8bbd61617b39ffa5"),
}


def encrypt_empty_password(partition_id: str) -> bytes:
    """Return 8-byte rpwd/fpwd. PS2 IOP often ignores passwords (APA_ENABLE_PASSWORDS off)."""
    if partition_id in _KNOWN_EMPTY:
        return _KNOWN_EMPTY[partition_id]
    return b"\x00" * 8
