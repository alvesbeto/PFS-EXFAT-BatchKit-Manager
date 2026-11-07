@echo off
setlocal EnableDelayedExpansion

set "rootpath=%~1"
if not defined rootpath set "rootpath=%~dp0.."
if "%rootpath:~-1%"=="\" set "rootpath=%rootpath:~0,-1%"
if "%rootpath:~-1%"=="\" set "rootpath=%rootpath:~0,-1%"
if not exist "%rootpath%\TMP" mkdir "%rootpath%\TMP" >nul 2>&1

echo ========================================================
echo  Atualizando Open PS2 Loader para a ultima release GitHub
echo ========================================================
echo.

echo [1/4] Verificando e baixando versao mais recente (tag: latest) e Traducoes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%rootpath%\BAT\__Fetch_Latest_OPL.ps1" -RootPath "%rootpath%"
if errorlevel 1 (
    echo [AVISO] Falha ao consultar GitHub. Usando versao em cache local se disponivel.
)

set "BOOT_PKG=%rootpath%\BAT\__BootPackage"
set "OPL_ELF=!BOOT_PKG!\OPNPS2LD.ELF"

if not exist "!OPL_ELF!" (
    echo [ERRO] OPNPS2LD.ELF nao encontrado em !BOOT_PKG!
    exit /b 1
)

echo.
echo [2/4] Configuracao e selecao de Idioma do OPL...
powershell -NoProfile -ExecutionPolicy Bypass -File "%rootpath%\BAT\__Configure_OPL_Language.ps1" -Interactive -SkipInject -RootPath "%rootpath%"

set "CHOSEN_LANG=English"
if exist "%rootpath%\TMP\opl_selected_lang.txt" (
    set /p CHOSEN_LANG=<"%rootpath%\TMP\opl_selected_lang.txt"
)

echo.
echo [3/4] Sincronizando particao PFS __common:/OPL/ com executavel e idioma...
powershell -NoProfile -ExecutionPolicy Bypass -File "%rootpath%\BAT\__Inject_Pfs_Opl.ps1" -RootPath "%rootpath%"
if errorlevel 1 (
    echo [AVISO] Falha ao atualizar particao PFS via pfsshell [certifique-se de executar como Administrador].
) else (
    echo Particao PFS __common:/OPL/ atualizada com sucesso.
)

echo.
echo [4/4] Limpando particao exFAT e configurando pastas de jogos...
call "%rootpath%\BAT\__Sync_Exfat_Opl_Config.bat" "%rootpath%"

echo.
echo [5/5] Configurando FreeHDBoot para boot no OSDMenu e retorno IGR...
call "%rootpath%\BAT\__Patch_FreeHDBoot_Exfat.bat" "%rootpath%"

echo.
echo ========================================================
echo  OPL atualizado para a release mais recente do GitHub!
echo  Idioma configurado: !CHOSEN_LANG!
echo  BDM exFAT e pastas de jogos ativadas com sucesso.
echo ========================================================
echo.
echo Dica para o usuario:
echo  1. Copie seus jogos (.iso ou .zso) na pasta DVD ou CD do volume OPL.
echo  2. Conecte o disco no PS2 e ligue o console.
echo  3. O OPL abrira diretamente no modo BDM com idioma !CHOSEN_LANG!.
echo.
exit /b 0
