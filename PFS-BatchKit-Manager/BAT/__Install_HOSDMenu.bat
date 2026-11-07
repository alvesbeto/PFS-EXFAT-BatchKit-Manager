@echo off
setlocal EnableDelayedExpansion
REM Installs HOSDMenu + FreeHDBoot boot stack on APA boot partitions (__mbr, __system, __sysconf, __common) per APA-Jail specification.

if not defined @pfsshell_path (
    echo [ERROR] No PS2 HDD selected. Run HDD scan first.
    exit /b 1
)

set "rootpath=%~1"
if not defined rootpath set "rootpath=%~dp0.."
if "%rootpath:~-1%"=="\" set "rootpath=%rootpath:~0,-1%"
if "%rootpath:~-1%"=="\" set "rootpath=%rootpath:~0,-1%"
if not exist "%rootpath%\TMP" mkdir "%rootpath%\TMP" >nul 2>&1

set "BOOT_TYPE=%~2"
if not defined BOOT_TYPE set "BOOT_TYPE=FHDB"

echo [1/4] Ensuring boot package binaries are ready...
powershell -NoProfile -ExecutionPolicy Bypass -File "%rootpath%\BAT\__Build_BootPackage.ps1" >nul 2>&1

set "BOOT_PKG=%rootpath%\BAT\__BootPackage"
if not exist "!BOOT_PKG!\hosdmenu.elf" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%rootpath%\BAT\__Fetch_HOSDMenu_Elf.ps1" -RootPath "%rootpath%" >nul 2>&1
    if exist "%rootpath%\BAT\OSDMenu\hosdmenu.elf" copy /Y "%rootpath%\BAT\OSDMenu\hosdmenu.elf" "!BOOT_PKG!\hosdmenu.elf" >nul 2>&1
)

if not exist "!BOOT_PKG!\hosdmenu.elf" (
    echo [ERROR] hosdmenu.elf not found.
    exit /b 1
)

echo [2/4] Injecting MBR.KELF (!BOOT_TYPE!) into LBA 16 and validating APA header...
powershell -NoProfile -ExecutionPolicy Bypass -File "%rootpath%\BAT\__Inject_Mbr_Bootloader.ps1" -PhysicalDrivePath "!@pfsshell_path!" -RootPath "%rootpath%" -BootloaderType "!BOOT_TYPE!"

echo [3/4] Installing OSD boot stack into PFS partitions (__system, __sysconf, __common)...
set "PFSCMD=%rootpath%\TMP\pfs-boot-stack.txt"

(
echo device !@pfsshell_path!
echo mount __system
echo mkdir osd
echo cd osd
echo lcd "!BOOT_PKG!"
echo put osdmain.elf
echo put osdsys.elf
echo put osd110.elf
echo cd ..
echo mkdir osdmenu
echo cd osdmenu
echo put hosdmenu.elf
echo cd ..
echo umount

echo mount __sysconf
echo mkdir FMCB
echo cd FMCB
echo lcd "!BOOT_PKG!"
echo put FREEHDB.CNF
echo put BOOT.ELF
echo put FMCB_CFG.ELF
echo put FMCB.ICN
echo put USBD.IRX
echo put USBHDFSD.IRX
echo put conf_opl.cfg
echo cd ..
echo mkdir osdmenu
echo cd osdmenu
echo put OSDMENU.CNF
echo put OSDMBR.CNF
echo cd ..
echo umount
echo exit
) >> "!PFSCMD!"

pushd "%rootpath%\BAT\__BootPackage"
type "!PFSCMD!" | "%rootpath%\BAT\pfsshell.exe" > "%rootpath%\TMP\pfsshell_install.log" 2>&1
popd
del "!PFSCMD!" >nul 2>&1

echo [4/4] Injetando OPL, idiomas e configuracoes em __common:/OPL/...
powershell -NoProfile -ExecutionPolicy Bypass -File "%rootpath%\BAT\__Inject_Pfs_Opl.ps1" -RootPath "%rootpath%"

echo [4/4] Updating FreeHDBoot and exFAT OPL configurations...
call "%rootpath%\BAT\__Patch_FreeHDBoot_Exfat.bat" "%rootpath%"
call "%rootpath%\BAT\__Sync_Exfat_Opl_Config.bat" "%rootpath%"

echo.
echo ========================================================
echo  Boot stack APA-Jail (HOSDMenu + FHDB + OPL) instalado!
echo ========================================================
exit /b 0
