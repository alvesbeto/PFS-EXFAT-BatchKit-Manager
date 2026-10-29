"""QWizard page identifiers for branching flows."""

from __future__ import annotations

from enum import IntEnum


class PageId(IntEnum):
    WELCOME = 0
    DISK = 1
    PREPARE_OPTIONS = 2
    PREPARE_RUN = 3
    PREPARE_DONE = 4

    VALIDATE_INPUT = 10
    VALIDATE_RUN = 11
    VALIDATE_DONE = 12

    GAMES_INPUT = 30
    GAMES_RUN = 31
    GAMES_DONE = 32

    ADVANCED = 40
    BUILD_INPUT = 41
    BUILD_RUN = 42
    BUILD_DONE = 43
    SCAFFOLD_INPUT = 44
    SCAFFOLD_RUN = 45
    SCAFFOLD_DONE = 46
