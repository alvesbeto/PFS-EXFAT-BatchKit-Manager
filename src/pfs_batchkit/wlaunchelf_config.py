"""LAUNCHELF.CNF for exFAT/ata BDM (wLaunchELF R3Z on APA-Jail HDD)."""

from __future__ import annotations

# saildot4k/wLaunchELF_R3Z — ata:/ exFAT internal + usb:/ BDM exFAT
WLE_R3Z_DS34_FILENAME = "WLE-R3Z-DS34.ELF"
WLE_APPS_SUBDIR = "wLaunchELF"


def render_launchelf_cnf(*, cnf_dir: str = "mass:/APPS/wLaunchELF/") -> str:
    """
    Minimal CNF for BatchKit hybrid HDD.

    ``CNF_Path`` keeps settings on the exFAT volume (see PSBBN/wLE mass0 notes —
    R3Z handles ata:/; path is explicit under APPS/wLaunchELF/).
    """
    return (
        f"CNF_version = 3\n"
        f"CNF_Path = {cnf_dir}\n"
        "Menu_Title = wLaunchELF R3Z (PFS BatchKit)\n"
        "Menu_Hide_Paths = 0\n"
        "GUI_Swap_Keys = 1\n"
        "Screen_Interlace = 1\n"
        "Init_Delay = 0\n"
        "LK_Circle_E1 = MISC/FileBrowser\n"
        "Misc_FileBrowser = FileBrowser\n"
        "Misc_HddManager = HddManager\n"
        "Misc_PS2PowerOff = PS2PowerOff\n"
        "Misc_Configure = Configure\n"
        "Misc_Load_CNF = Load CNF\n"
        "Misc_Set_CNF_Path = Set CNF_Path\n"
    )
