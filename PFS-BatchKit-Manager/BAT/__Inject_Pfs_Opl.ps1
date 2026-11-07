param(
    [string]$RootPath = "$PSScriptRoot\..",
    [string]$PhysicalDrivePath = '',
    [string]$Language = ''
)

$ErrorActionPreference = 'Stop'
$RootPath = [System.IO.Path]::GetFullPath($RootPath)

# 1. Resolver Caminho do Drive Fisico PS2
if ([string]::IsNullOrWhiteSpace($PhysicalDrivePath)) {
    $envPath = [System.Environment]::GetEnvironmentVariable('@pfsshell_path')
    if (-not [string]::IsNullOrWhiteSpace($envPath)) {
        $PhysicalDrivePath = $envPath
    }
}
if ([string]::IsNullOrWhiteSpace($PhysicalDrivePath)) {
    $diskNumFile = Join-Path $RootPath 'TMP\hdd-disknum.txt'
    if (Test-Path -LiteralPath $diskNumFile) {
        $num = (Get-Content -Path $diskNumFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
        if ($num -match '^\d+$') {
            $PhysicalDrivePath = "\\.\PhysicalDrive$num"
        }
    }
}
if ([string]::IsNullOrWhiteSpace($PhysicalDrivePath)) {
    $hddBat = Join-Path $RootPath 'BAT\__Cache\HDD.BAT'
    if (Test-Path -LiteralPath $hddBat) {
        Get-Content -Path $hddBat -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_ -match '@pfsshell_path=(.+)') {
                $PhysicalDrivePath = $Matches[1].Trim()
            }
        }
    }
}
if ([string]::IsNullOrWhiteSpace($PhysicalDrivePath)) {
    # Tentar autodetectar
    $autoDetectScript = Join-Path $RootPath 'BAT\__AutoDetect_PS2_HDD.ps1'
    if (Test-Path -LiteralPath $autoDetectScript) {
        $detected = & powershell -NoProfile -ExecutionPolicy Bypass -File $autoDetectScript -RootPath $RootPath
        if ($detected -and $detected.PhysicalDrivePath) {
            $PhysicalDrivePath = $detected.PhysicalDrivePath
        }
    }
}

if ([string]::IsNullOrWhiteSpace($PhysicalDrivePath)) {
    Write-Warning "Nenhum disco PS2 HDD detectado para injetar via pfsshell."
    exit 1
}

# 2. Localizar pfsshell.exe
$pfsshellExe = Join-Path $RootPath 'BAT\pfsshell.exe'
if (-not (Test-Path -LiteralPath $pfsshellExe)) {
    $pfsshellExe = Join-Path $RootPath 'BAT\pfsshell'
}
if (-not (Test-Path -LiteralPath $pfsshellExe)) {
    Write-Error "pfsshell.exe nao encontrado em $(Join-Path $RootPath 'BAT')."
    exit 1
}

# 3. Resolver Idioma Selecionado
$selectedLang = $Language
if ([string]::IsNullOrWhiteSpace($selectedLang)) {
    $tmpLang = Join-Path $RootPath 'TMP\opl_selected_lang.txt'
    if (Test-Path -LiteralPath $tmpLang) {
        $selectedLang = (Get-Content -Path $tmpLang -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    }
}
if ([string]::IsNullOrWhiteSpace($selectedLang)) {
    $hostCulture = [System.Globalization.CultureInfo]::CurrentUICulture
    if ($hostCulture.TwoLetterISOLanguageName.ToLowerInvariant() -eq 'pt') {
        $selectedLang = 'Portuguese_BR'
    } else {
        $selectedLang = 'English'
    }
}

Write-Host "Injetando OPL e configuracoes na particao PFS (__common:/OPL/)..." -ForegroundColor Cyan
Write-Host "  Disco Fisico: $PhysicalDrivePath" -ForegroundColor Gray
Write-Host "  Idioma:       $selectedLang" -ForegroundColor Gray

# 4. Preparar arquivos de configuracao
$bootPackage = Join-Path $RootPath 'BAT\__BootPackage'
$oplElf = Join-Path $bootPackage 'OPNPS2LD.ELF'
if (-not (Test-Path -LiteralPath $oplElf)) {
    $latestElf = Join-Path $RootPath 'BAT\OPNPS2LD_LATEST.ELF'
    if (Test-Path -LiteralPath $latestElf) {
        Copy-Item -LiteralPath $latestElf -Destination $oplElf -Force
    }
}
if (-not (Test-Path -LiteralPath $oplElf)) {
    Write-Error "OPNPS2LD.ELF nao encontrado em $bootPackage nem em BAT\."
    exit 1
}

# Atualizar conf_opl.cfg com IGR para PFS (hdd0:/__common/OPL/OPNPS2LD.ELF)
$confOpl = Join-Path $bootPackage 'conf_opl.cfg'
$templateOpl = Join-Path $RootPath 'HDD-OSD\__common\OPL\conf_opl.cfg'
$baseConf = if (Test-Path -LiteralPath $confOpl) { $confOpl } elseif (Test-Path -LiteralPath $templateOpl) { $templateOpl } else { $null }

$confContent = @'
# Open PS2 Loader Configuration File
# Configured for APA-Jail exFAT BDM Support & High Definition
scrolling=1
theme=Pixel-Prime-Top (NoLogo)
language_text=Portuguese_BR
wide_screen=1
vmode=0
autosort=1
autorefresh=1
enable_delete_rename=1
hdd_spindown=20
bdm_cache=1
enable_bdm_hdd=1
enable_mx4sio=1
enable_ilink=0
usb_mode=2
hdd_mode=0
eth_mode=0
app_mode=0
default_device=0
exit_path=mass:/OPL/OPNPS2LD.ELF
bg_color=#28C5F9
text_color=#FFFFFF
ui_text_color=#5868B4
sel_text_color=#00AEFF
enable_notifications=0
enable_coverart=1
xoff=0
yoff=0
overscan=0
disable_debug=0
ps2logo=0
hdd_game_list_cache=1
usb_prefix=
eth_prefix=
remember_last=0
autostart_last=9
hdd_cache=8
smb_cache=16
enable_sfx=0
enable_boot_snd=0
enable_bgm=0
sfx_volume=80
boot_snd_volume=80
bgm_volume=70
default_bgm_path=
x_sensitivity=1
y_sensitivity=1
swap_select_btn=1
'@

if ($baseConf -and (Test-Path -LiteralPath $baseConf)) {
    $existing = [System.IO.File]::ReadAllText($baseConf, [System.Text.Encoding]::ASCII)
    if ($existing.Trim().Length -gt 20) {
        $confContent = $existing
    }
}

# Ajustar chaves essenciais
function Set-ConfKey([ref]$text, [string]$key, [string]$val) {
    if ($text.Value -match "(?m)^$key=.*$") {
        $text.Value = $text.Value -replace "(?m)^$key=.*$", "$key=$val"
    } else {
        $text.Value += "`r`n$key=$val`r`n"
    }
}

Set-ConfKey ([ref]$confContent) "language_text" $selectedLang
Set-ConfKey ([ref]$confContent) "exit_path" "mass:/OPL/OPNPS2LD.ELF"
Set-ConfKey ([ref]$confContent) "wide_screen" "1"
Set-ConfKey ([ref]$confContent) "vmode" "0"
Set-ConfKey ([ref]$confContent) "enable_bdm_hdd" "1"
Set-ConfKey ([ref]$confContent) "bdm_cache" "1"
if ($confContent -notmatch '(?m)^theme=.+') {
    Set-ConfKey ([ref]$confContent) "theme" "Pixel-Prime-Top (NoLogo)"
}
if ($confContent -notmatch '(?m)^bg_color=') {
    Set-ConfKey ([ref]$confContent) "bg_color" "#28C5F9"
    Set-ConfKey ([ref]$confContent) "text_color" "#FFFFFF"
    Set-ConfKey ([ref]$confContent) "ui_text_color" "#5868B4"
    Set-ConfKey ([ref]$confContent) "sel_text_color" "#00AEFF"
}

[System.IO.File]::WriteAllText($confOpl, $confContent, [System.Text.Encoding]::ASCII)
if (Test-Path -LiteralPath (Split-Path $templateOpl)) {
    [System.IO.File]::WriteAllText($templateOpl, $confContent, [System.Text.Encoding]::ASCII)
}

# Garantir conf_hdd.cfg
$confHdd = Join-Path $bootPackage 'conf_hdd.cfg'
if (-not (Test-Path -LiteralPath $confHdd)) {
    $templateHdd = Join-Path $RootPath 'HDD-OSD\__common\OPL\conf_hdd_apajail_exfat.cfg'
    if (Test-Path -LiteralPath $templateHdd) {
        Copy-Item -LiteralPath $templateHdd -Destination $confHdd -Force
    } else {
        [System.IO.File]::WriteAllText($confHdd, "hdd_partition=__common`r`n", [System.Text.Encoding]::ASCII)
    }
}

# Regra para conf_game.cfg: Se ja existir, nao faz nada. NUNCA criar em hipotese alguma.
$confGame = Join-Path $bootPackage 'conf_game.cfg'

# 5. Localizar arquivos do idioma selecionado
$langsDir = Join-Path $bootPackage 'LANGS'
$langSrcDir = Join-Path $langsDir $selectedLang
$lngFile = $null
$fontFile = $null

if ($selectedLang -ne 'English' -and (Test-Path -LiteralPath $langSrcDir)) {
    $lngFile = Get-ChildItem -Path $langSrcDir -Filter "*.lng" | Select-Object -First 1
    $fontFile = Get-ChildItem -Path $langSrcDir -Filter "font_*" | Select-Object -First 1
}
if (-not $lngFile) {
    $lngFile = Get-ChildItem -Path $bootPackage -Filter "*$selectedLang*.lng" | Select-Object -First 1
}
if (-not $fontFile) {
    $fontFile = Get-ChildItem -Path $bootPackage -Filter "font_*$selectedLang*" | Select-Object -First 1
}

# 6. Criar Staging Directory Limpo
$stageOpl = Join-Path $RootPath 'TMP\pfs_stage\OPL'
$stageLng = Join-Path $stageOpl 'LNG'
if (Test-Path -LiteralPath $stageOpl) {
    Remove-Item -LiteralPath $stageOpl -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $stageLng -Force | Out-Null

Copy-Item -LiteralPath $oplElf -Destination (Join-Path $stageOpl 'OPNPS2LD.ELF') -Force
Copy-Item -LiteralPath $confOpl -Destination (Join-Path $stageOpl 'conf_opl.cfg') -Force
Copy-Item -LiteralPath $confHdd -Destination (Join-Path $stageOpl 'conf_hdd.cfg') -Force
if (Test-Path -LiteralPath $confGame) {
    Copy-Item -LiteralPath $confGame -Destination (Join-Path $stageOpl 'conf_game.cfg') -Force
}

if ($lngFile) {
    Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $stageOpl $lngFile.Name) -Force
    Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $stageLng $lngFile.Name) -Force
}
if ($fontFile) {
    Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $stageOpl $fontFile.Name) -Force
    Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $stageLng $fontFile.Name) -Force
}

# 7. Gerar Script pfsshell (comandos limpos, sem aspas no lcd)
$pfsCommands = [System.Collections.Generic.List[string]]::new()
$pfsCommands.Add("device $PhysicalDrivePath")
$pfsCommands.Add("mount __common")
$pfsCommands.Add("mkdir OPL")
$pfsCommands.Add("cd OPL")
$pfsCommands.Add("rm OPNPS2LD.ELF")
$pfsCommands.Add("put OPNPS2LD.ELF")
$pfsCommands.Add("rm conf_opl.cfg")
$pfsCommands.Add("put conf_opl.cfg")
$pfsCommands.Add("rm conf_hdd.cfg")
$pfsCommands.Add("put conf_hdd.cfg")
if (Test-Path -LiteralPath $confGame) {
    $pfsCommands.Add("rm conf_game.cfg")
    $pfsCommands.Add("put conf_game.cfg")
}

if ($lngFile) {
    $pfsCommands.Add("rm $($lngFile.Name)")
    $pfsCommands.Add("put $($lngFile.Name)")
}
if ($fontFile) {
    $pfsCommands.Add("rm $($fontFile.Name)")
    $pfsCommands.Add("put $($fontFile.Name)")
}

$pfsCommands.Add("mkdir LNG")
$pfsCommands.Add("cd LNG")
$pfsCommands.Add("lcd LNG")

if ($lngFile) {
    $pfsCommands.Add("rm $($lngFile.Name)")
    $pfsCommands.Add("put $($lngFile.Name)")
}
if ($fontFile) {
    $pfsCommands.Add("rm $($fontFile.Name)")
    $pfsCommands.Add("put $($fontFile.Name)")
}

$pfsCommands.Add("cd ..")
$pfsCommands.Add("lcd ..")
$pfsCommands.Add("cd ..")
$pfsCommands.Add("umount")

# Injetar tambem em __sysconf:/FMCB/
$pfsCommands.Add("mount __sysconf")
$pfsCommands.Add("cd ..")
$pfsCommands.Add("mkdir FMCB")
$pfsCommands.Add("cd FMCB")
$pfsCommands.Add("rm conf_opl.cfg")
$pfsCommands.Add("put conf_opl.cfg")
if (Test-Path -LiteralPath $confGame) {
    $pfsCommands.Add("rm conf_game.cfg")
    $pfsCommands.Add("put conf_game.cfg")
}
$pfsCommands.Add("cd ..")
$pfsCommands.Add("umount")
$pfsCommands.Add("exit")

$pfsScriptFile = Join-Path $RootPath 'TMP\pfs-inject-opl.txt'
[System.IO.File]::WriteAllLines($pfsScriptFile, $pfsCommands, [System.Text.Encoding]::ASCII)

$logFile = Join-Path $RootPath 'TMP\pfsshell_opl.log'

# 8. Executar pfsshell com cwd = $stageOpl
Push-Location $stageOpl
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $out = @(Get-Content -LiteralPath $pfsScriptFile | & $pfsshellExe 2>&1)
    [System.IO.File]::WriteAllLines($logFile, $out, [System.Text.Encoding]::ASCII)
} finally {
    $ErrorActionPreference = $prevEap
    Pop-Location
}

# 9. Analisar resultado
$logText = [System.IO.File]::ReadAllText($logFile)
if ($logText -match 'Permission denied') {
    Write-Warning "Permissao negada ao acessar $PhysicalDrivePath. Execute como Administrador."
    exit 2
}

if ($logText -match 'No such file or directory') {
    Write-Warning "Algum arquivo nao foi encontrado durante a transferencia. Verifique o log em $logFile."
}

Write-Host "Injecao na particao PFS (__common:/OPL/) realizada com sucesso!" -ForegroundColor Green
Write-Host "  OPNPS2LD.ELF atualizado." -ForegroundColor Green
Write-Host "  conf_opl.cfg configurado com exit_path=mass:/OPL/OPNPS2LD.ELF" -ForegroundColor Green
if ($lngFile) {
    Write-Host "  Idioma $($selectedLang) ($($lngFile.Name)) instalado exclusivamente em __common:/OPL/ e LNG/." -ForegroundColor Green
}

# 10. Sincronizar configuracoes em E:\conf_opl.cfg e idioma na pasta E:\OPL\
$oplVolume = Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.FileSystemLabel -eq 'OPL' -and $_.DriveLetter } | Select-Object -First 1
if ($oplVolume) {
    $letter = "$($oplVolume.DriveLetter):"
    Write-Host "Sincronizando configuracoes em $letter\conf_opl.cfg e idioma na pasta OPL..." -ForegroundColor Cyan
    
    $exfatOpl = Join-Path $letter 'OPL'
    $exfatOplLng = Join-Path $exfatOpl 'LNG'
    $exfatLng = Join-Path $letter 'LNG'
    if (-not (Test-Path -LiteralPath $exfatOpl)) { New-Item -ItemType Directory -Path $exfatOpl -Force | Out-Null }
    if (-not (Test-Path -LiteralPath $exfatOplLng)) { New-Item -ItemType Directory -Path $exfatOplLng -Force | Out-Null }
    if (-not (Test-Path -LiteralPath $exfatLng)) { New-Item -ItemType Directory -Path $exfatLng -Force | Out-Null }

    # Copiar executavel para OPL\
    if (Test-Path -LiteralPath $oplElf) {
        Copy-Item -LiteralPath $oplElf -Destination (Join-Path $exfatOpl 'OPNPS2LD.ELF') -Force
    }

    # Copiar idioma para OPL\ e LNG\
    if ($lngFile) {
        Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $exfatOpl $lngFile.Name) -Force
        Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $exfatOplLng $lngFile.Name) -Force
        Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $exfatLng $lngFile.Name) -Force
    }
    if ($fontFile) {
        Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $exfatOpl $fontFile.Name) -Force
        Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $exfatOplLng $fontFile.Name) -Force
        Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $exfatLng $fontFile.Name) -Force
    }

    # Salvar configuracoes em E:\conf_opl.cfg e E:\OPL\conf_opl.cfg
    $rootConf = Join-Path $letter 'conf_opl.cfg'
    Copy-Item -LiteralPath $confOpl -Destination $rootConf -Force
    Copy-Item -LiteralPath $confOpl -Destination (Join-Path $exfatOpl 'conf_opl.cfg') -Force

    # Copiar conf_hdd.cfg para OPL\
    if (Test-Path -LiteralPath $confHdd) {
        Copy-Item -LiteralPath $confHdd -Destination (Join-Path $exfatOpl 'conf_hdd.cfg') -Force
    }

    # Limpeza de arquivos soltos de idioma da raiz
    Get-ChildItem -Path $letter -Filter "lang_*.lng" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $letter -Filter "font_*" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    
    # Manter pastas padrao de jogos
    foreach ($dirName in @('CD', 'DVD', 'ART', 'CFG', 'CHT', 'THM', 'VMC', 'POPS')) {
        $p = Join-Path $letter $dirName
        if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
    }
    
    Write-Host "Configuracoes salvas em $rootConf e idioma instalado em $exfatOpl com sucesso!" -ForegroundColor Green
}

exit 0
