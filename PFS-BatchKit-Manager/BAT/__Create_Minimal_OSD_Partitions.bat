@echo off
setlocal EnableDelayedExpansion
REM Minimal PFS layout for HDD-OSD / HOSDMenu boot (APA side). Games live on exFAT (APA-Jail).
if not defined @pfsshell_path exit /b 1
set "rootpath=%~1"
if not defined rootpath set "rootpath=%~dp0.."
if not exist "%rootpath%\TMP" mkdir "%rootpath%\TMP" >nul 2>&1

echo device !@pfsshell_path!> "%rootpath%\TMP\pfs-min-osd.txt"
echo initialize yes>> "%rootpath%\TMP\pfs-min-osd.txt"
echo mkpart __sysconf 128M PFS>> "%rootpath%\TMP\pfs-min-osd.txt"
echo mkpart __system 128M PFS>> "%rootpath%\TMP\pfs-min-osd.txt"
echo mkpart __contents 128M PFS>> "%rootpath%\TMP\pfs-min-osd.txt"
echo mkpart __common 128M PFS>> "%rootpath%\TMP\pfs-min-osd.txt"
echo ls -l>> "%rootpath%\TMP\pfs-min-osd.txt"
echo exit>> "%rootpath%\TMP\pfs-min-osd.txt"
type "%rootpath%\TMP\pfs-min-osd.txt" | "%rootpath%\BAT\pfsshell" >nul 2>&1
exit /b %ERRORLEVEL%
