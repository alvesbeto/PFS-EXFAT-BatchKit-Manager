@echo off
setlocal EnableDelayedExpansion
REM FreeHDBoot (FMCB) menu entries for HOSDMenu boot + OPL on APA — community layout.
if not defined @pfsshell_path exit /b 1
set "rootpath=%~1"
if not defined rootpath set "rootpath=%~dp0.."
if not exist "%rootpath%\TMP" mkdir "%rootpath%\TMP" >nul 2>&1

echo device !@pfsshell_path!> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo mount __sysconf>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo cd FMCB>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo get FREEHDB.CNF>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo umount>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo exit>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
type "%rootpath%\TMP\pfs-fhdb-exfat.txt" | "%rootpath%\BAT\pfsshell" >nul 2>&1

if not exist "%rootpath%\TMP\FREEHDB.CNF" (
    if exist "%rootpath%\TMP\FREEHDB_DEFAULT.CNF" (
        copy /Y "%rootpath%\TMP\FREEHDB_DEFAULT.CNF" "%rootpath%\TMP\FREEHDB.CNF" >nul
    ) else if exist "%rootpath%\BAT\FreeHDBootCFG.zip" (
        "%rootpath%\BAT\7-Zip\7z" e -bso0 "%rootpath%\BAT\FreeHDBootCFG.zip" FREEHDB_DEFAULT.CNF -o"%rootpath%\TMP" -y >nul 2>&1
        if exist "%rootpath%\TMP\FREEHDB_DEFAULT.CNF" copy /Y "%rootpath%\TMP\FREEHDB_DEFAULT.CNF" "%rootpath%\TMP\FREEHDB.CNF" >nul
    )
)
if not exist "%rootpath%\TMP\FREEHDB.CNF" exit /b 1

REM Boot padrao pelo OSDMenu / Browser (HOSDMenu), nao direto no OPL
"%rootpath%\BAT\busybox" sed -i "s|^LK_Auto_E1 = .*|LK_Auto_E1 = OSDSYS|g" "%rootpath%\TMP\FREEHDB.CNF"
"%rootpath%\BAT\busybox" sed -i "s|^FastBoot = .*|FastBoot = 0|g" "%rootpath%\TMP\FREEHDB.CNF"
"%rootpath%\BAT\busybox" sed -i "s|^OSDSYS_Skip_Logo = .*|OSDSYS_Skip_Logo = 0|g" "%rootpath%\TMP\FREEHDB.CNF"


"%rootpath%\BAT\busybox" grep -q "name_OSDSYS_ITEM_6 = HOSDMenu" "%rootpath%\TMP\FREEHDB.CNF" >nul 2>&1
if errorlevel 1 (
    echo.>> "%rootpath%\TMP\FREEHDB.CNF"
    echo name_OSDSYS_ITEM_6 = HOSDMenu>> "%rootpath%\TMP\FREEHDB.CNF"
    echo path1_OSDSYS_ITEM_6 = hdd0:__system:pfs:/osdmenu/hosdmenu.elf>> "%rootpath%\TMP\FREEHDB.CNF"
)
"%rootpath%\BAT\busybox" grep -q "name_OSDSYS_ITEM_7 = Open PS2 Loader" "%rootpath%\TMP\FREEHDB.CNF" >nul 2>&1
if errorlevel 1 (
    echo name_OSDSYS_ITEM_7 = Open PS2 Loader>> "%rootpath%\TMP\FREEHDB.CNF"
    echo path1_OSDSYS_ITEM_7 = hdd0:__common:pfs:/OPL/OPNPS2LD.ELF>> "%rootpath%\TMP\FREEHDB.CNF"
)

echo device !@pfsshell_path!> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo mount __sysconf>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo cd FMCB>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo rm FREEHDB.CNF>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo put FREEHDB.CNF>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo umount>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
echo exit>> "%rootpath%\TMP\pfs-fhdb-exfat.txt"
pushd "%rootpath%\TMP"
type "%rootpath%\TMP\pfs-fhdb-exfat.txt" | "%rootpath%\BAT\pfsshell" >nul 2>&1
popd
exit /b 0
