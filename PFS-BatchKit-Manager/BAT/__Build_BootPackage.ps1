$base = "C:\Users\beto\Documents\dev\Repositorios\PFS-BatchKit-Manager\PFS-BatchKit-Manager"
$stage = Join-Path $base "BAT\__BootPackage"
if (-not (Test-Path -LiteralPath $stage)) {
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
}

$exe7z = Join-Path $base "BAT\7-Zip\7z.exe"
$copy7z = Join-Path $base "BAT\!COPY_TO_USB_ROOT.7z"

# Extract FMCB / FHDB components
& $exe7z e $copy7z -o"$stage" "APPS\FreeMcBoot_v1.966_Install_(2019-04-13)\INSTALL\SYSTEM\*" -y | Out-Null
& $exe7z e $copy7z -o"$stage" "APPS\FreeMcBoot_v1.966_Install_(2019-04-13)\INSTALL\SYS-CONF\*" -y | Out-Null
& $exe7z e $copy7z -o"$stage" "APPS\FreeMcBoot_v1.966_Install_(2019-04-13)\INSTALL\BOOT-HDD\BOOT.ELF" -y | Out-Null

# Rename/Prepare ELF binaries for PFS (pfsshell 'put' only takes one argument)
if (Test-Path (Join-Path $stage "FHDB.XLF")) {
    Copy-Item (Join-Path $stage "FHDB.XLF") (Join-Path $stage "osdmain.elf") -Force
}
if (Test-Path (Join-Path $stage "OSDSYS.XLF")) {
    Copy-Item (Join-Path $stage "OSDSYS.XLF") (Join-Path $stage "osdsys.elf") -Force
}
if (Test-Path (Join-Path $stage "OSD110.XLF")) {
    Copy-Item (Join-Path $stage "OSD110.XLF") (Join-Path $stage "osd110.elf") -Force
}

# Fetch Latest OPL from GitHub (https://github.com/ps2homebrew/Open-PS2-Loader/releases/tag/latest)
$fetchOplScript = Join-Path $base "BAT\__Fetch_Latest_OPL.ps1"
if (Test-Path -LiteralPath $fetchOplScript) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $fetchOplScript -RootPath $base | Out-Null
}

if (-not (Test-Path (Join-Path $stage "OPNPS2LD.ELF"))) {
    $cachedLatest = Join-Path $base "BAT\OPNPS2LD_LATEST.ELF"
    if (Test-Path -LiteralPath $cachedLatest) {
        Copy-Item $cachedLatest (Join-Path $stage "OPNPS2LD.ELF") -Force
    } else {
        # Fallback to APPS.zip only if download failed and no cache
        $appsZip = Join-Path $base "BAT\APPS.zip"
        $oplTmp = Join-Path $stage "opl_tmp"
        & $exe7z e $appsZip -o"$oplTmp" "APPS\Open PS2 Loader Stable\*.ELF" -r -y | Out-Null
        $oplElf = Get-ChildItem -Path $oplTmp -Filter "*.ELF" | Select-Object -First 1
        if ($oplElf) {
            Copy-Item $oplElf.FullName (Join-Path $stage "OPNPS2LD.ELF") -Force
        }
        Remove-Item -LiteralPath $oplTmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Copy HOSDMenu
$hosd = Join-Path $base "BAT\OSDMenu\hosdmenu.elf"
if (Test-Path -LiteralPath $hosd) {
    Copy-Item $hosd (Join-Path $stage "hosdmenu.elf") -Force
}

# Copy OSDMenu configs
$osdmenuCnf = Join-Path $base "HDD-OSD\__sysconf\osdmenu\OSDMENU.CNF"
$osdmbrCnf = Join-Path $base "HDD-OSD\__sysconf\osdmenu\OSDMBR.CNF"
if (Test-Path -LiteralPath $osdmenuCnf) { Copy-Item $osdmenuCnf (Join-Path $stage "OSDMENU.CNF") -Force }
if (Test-Path -LiteralPath $osdmbrCnf) { Copy-Item $osdmbrCnf (Join-Path $stage "OSDMBR.CNF") -Force }

$confHdd = Join-Path $base "HDD-OSD\__common\OPL\conf_hdd_apajail_exfat.cfg"
if (Test-Path -LiteralPath $confHdd) { Copy-Item $confHdd (Join-Path $stage "conf_hdd.cfg") -Force }

$confOpl = Join-Path $base "HDD-OSD\__common\OPL\conf_opl.cfg"
if (Test-Path -LiteralPath $confOpl) { Copy-Item $confOpl (Join-Path $stage "conf_opl.cfg") -Force }

# Ensure language files are staged
$configLangScript = Join-Path $base "BAT\__Configure_OPL_Language.ps1"
if (Test-Path -LiteralPath $configLangScript) {
    $selectedLangFile = Join-Path $base "TMP\opl_selected_lang.txt"
    $curLang = "Portuguese_BR"
    if (Test-Path -LiteralPath $selectedLangFile) {
        $curLang = (Get-Content -Path $selectedLangFile -Raw).Trim()
        if ([string]::IsNullOrWhiteSpace($curLang)) { $curLang = "Portuguese_BR" }
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $configLangScript -Language $curLang -RootPath $base | Out-Null
}

Get-ChildItem -LiteralPath $stage | Select-Object Name, Length
