@echo off
setlocal EnableDelayedExpansion
REM Copy OPL APA-Jail hints to the exFAT volume (label OPL) when present.
if not defined @pfsshell_path exit /b 1
set "rootpath=%~1"
if not defined rootpath set "rootpath=%~dp0.."

if exist "%rootpath%\TMP\hdd-disknum.txt" for /f "usebackq delims=" %%N in ("%rootpath%\TMP\hdd-disknum.txt") do set "DISK_NUM=%%N"
if not defined DISK_NUM for /f "usebackq delims=" %%N in (`powershell -NoProfile -Command "if('%@pfsshell_path%' -match 'PhysicalDrive(\d+)'){ $Matches[1] }"`) do set "DISK_NUM=%%N"
if not defined DISK_NUM exit /b 0
REM Garantir que o volume OPL possui uma letra de unidade montada no Windows
powershell -NoProfile -ExecutionPolicy Bypass -File "%rootpath%\BAT\__Ensure_Opl_Drive_Letter.ps1" -PhysicalDrivePath "%@pfsshell_path%" -RootPath "%rootpath%" >nul 2>&1

if exist "%rootpath%\TMP\opl_drive_letter.txt" (
    set /p OPL_LETTER=<"%rootpath%\TMP\opl_drive_letter.txt"
)

if not defined OPL_LETTER for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "$n=[int]'%DISK_NUM%'; Get-Partition -DiskNumber $n -ErrorAction SilentlyContinue | ForEach-Object { $v=Get-Volume -Partition $_ -ErrorAction SilentlyContinue; if($v -and $v.FileSystemLabel -eq 'OPL' -and $v.DriveLetter){ $v.DriveLetter } }"`) do set "OPL_LETTER=%%D"
if not defined OPL_LETTER for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "$v = Get-Volume | Where-Object { $_.FileSystemLabel -eq 'OPL' -and $_.DriveLetter } | Select-Object -First 1; if($v){ $v.DriveLetter }"`) do set "OPL_LETTER=%%D"

if not defined OPL_LETTER (
    echo         [INFO] Volume exFAT 'OPL' nao detectado como letra de unidade no Windows.
    exit /b 0
)

echo         Volume exFAT identificado na unidade: !OPL_LETTER!:\ (Sincronizando...)

REM Criar pastas padroes de jogos e recursos no drive exFAT/BDM
if not exist "!OPL_LETTER!:\OPL"      mkdir "!OPL_LETTER!:\OPL" >nul 2>&1
if not exist "!OPL_LETTER!:\OPL\LNG"  mkdir "!OPL_LETTER!:\OPL\LNG" >nul 2>&1
if not exist "!OPL_LETTER!:\LNG"      mkdir "!OPL_LETTER!:\LNG" >nul 2>&1
if not exist "!OPL_LETTER!:\CFG"      mkdir "!OPL_LETTER!:\CFG" >nul 2>&1
if not exist "!OPL_LETTER!:\DVD"      mkdir "!OPL_LETTER!:\DVD" >nul 2>&1
if not exist "!OPL_LETTER!:\CD"       mkdir "!OPL_LETTER!:\CD" >nul 2>&1
if not exist "!OPL_LETTER!:\POPS"     mkdir "!OPL_LETTER!:\POPS" >nul 2>&1
if not exist "!OPL_LETTER!:\APPS"     mkdir "!OPL_LETTER!:\APPS" >nul 2>&1
if not exist "!OPL_LETTER!:\nhddl"    mkdir "!OPL_LETTER!:\nhddl" >nul 2>&1
if not exist "!OPL_LETTER!:\ART"      mkdir "!OPL_LETTER!:\ART" >nul 2>&1
if not exist "!OPL_LETTER!:\CHT"      mkdir "!OPL_LETTER!:\CHT" >nul 2>&1
if not exist "!OPL_LETTER!:\THM"      mkdir "!OPL_LETTER!:\THM" >nul 2>&1
if not exist "!OPL_LETTER!:\VMC"      mkdir "!OPL_LETTER!:\VMC" >nul 2>&1

REM 1. Configuracao de montagem do HDD para jogos BDM (CFG\conf_hdd.cfg e OPL\conf_hdd.cfg)
copy /Y "%rootpath%\HDD-OSD\__common\OPL\conf_hdd_apajail_exfat.cfg" "!OPL_LETTER!:\CFG\conf_hdd.cfg" >nul 2>&1
copy /Y "%rootpath%\HDD-OSD\__common\OPL\conf_hdd_apajail_exfat.cfg" "!OPL_LETTER!:\OPL\conf_hdd.cfg" >nul 2>&1
if defined OPLPART (
    "%rootpath%\BAT\busybox" sed -i "s/hdd_partition=__common/hdd_partition=!OPLPART!/" "!OPL_LETTER!:\CFG\conf_hdd.cfg" >nul 2>&1
    "%rootpath%\BAT\busybox" sed -i "s/hdd_partition=__common/hdd_partition=!OPLPART!/" "!OPL_LETTER!:\OPL\conf_hdd.cfg" >nul 2>&1
)

REM 2. Sincronizar configuracoes do OPL em E:\conf_opl.cfg e E:\OPL\conf_opl.cfg
if exist "%rootpath%\HDD-OSD\__common\OPL\conf_opl.cfg" (
    copy /Y "%rootpath%\HDD-OSD\__common\OPL\conf_opl.cfg" "!OPL_LETTER!:\conf_opl.cfg" >nul 2>&1
    copy /Y "%rootpath%\HDD-OSD\__common\OPL\conf_opl.cfg" "!OPL_LETTER!:\OPL\conf_opl.cfg" >nul 2>&1
)

REM 3. Copiar executavel OPNPS2LD.ELF para OPL\
if exist "%rootpath%\BAT\__BootPackage\OPNPS2LD.ELF" (
    copy /Y "%rootpath%\BAT\__BootPackage\OPNPS2LD.ELF" "!OPL_LETTER!:\OPL\OPNPS2LD.ELF" >nul 2>&1
    copy /Y "%rootpath%\BAT\__BootPackage\OPNPS2LD.ELF" "!OPL_LETTER!:\APPS\OPNPS2LD.ELF" >nul 2>&1
)

REM 4. Instalar idiomas na pasta OPL e LNG do exFAT
for %%F in ("%rootpath%\BAT\__BootPackage\lang_*.lng") do (
    if exist "%%~fF" (
        copy /Y "%%~fF" "!OPL_LETTER!:\OPL\%%~nxF" >nul 2>&1
        copy /Y "%%~fF" "!OPL_LETTER!:\OPL\LNG\%%~nxF" >nul 2>&1
        copy /Y "%%~fF" "!OPL_LETTER!:\LNG\%%~nxF" >nul 2>&1
    )
)
for %%F in ("%rootpath%\BAT\__BootPackage\font_*") do (
    if exist "%%~fF" (
        copy /Y "%%~fF" "!OPL_LETTER!:\OPL\%%~nxF" >nul 2>&1
        copy /Y "%%~fF" "!OPL_LETTER!:\OPL\LNG\%%~nxF" >nul 2>&1
        copy /Y "%%~fF" "!OPL_LETTER!:\LNG\%%~nxF" >nul 2>&1
    )
)

REM 5. Limpeza de arquivos soltos na raiz (manter raiz limpa)
del /F /Q "!OPL_LETTER!:\lang_*.lng" >nul 2>&1
del /F /Q "!OPL_LETTER!:\font_*" >nul 2>&1
del /F /Q "!OPL_LETTER!:\OPNPS2LD.ELF" >nul 2>&1

exit /b 0

exit /b 0
