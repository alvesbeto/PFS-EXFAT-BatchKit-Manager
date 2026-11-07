param(
    [string]$RootPath = "$PSScriptRoot\..",
    [string]$DriveLetter = ''
)

$ErrorActionPreference = 'Stop'
$RootPath = [System.IO.Path]::GetFullPath($RootPath)

function Update-OplGuiHd([string]$filePath) {
    if (-not (Test-Path -LiteralPath $filePath)) { return }
    $content = [System.IO.File]::ReadAllText($filePath, [System.Text.Encoding]::ASCII)

    # Widescreen 16:9
    if ($content -match '(?m)^wide_screen=.*$') {
        $content = $content -replace '(?m)^wide_screen=.*$', 'wide_screen=1'
    } else {
        $content += "`r`nwide_screen=1`r`n"
    }

    # Video Mode Auto (vmode=0)
    if ($content -match '(?m)^vmode=.*$') {
        $content = $content -replace '(?m)^vmode=.*$', 'vmode=0'
    } else {
        $content += "`r`nvmode=0`r`n"
    }

    # In-Game Reset direto para o OPL na particao PFS
    if ($content -match '(?m)^exit_path=.*$') {
        $content = $content -replace '(?m)^exit_path=.*$', 'exit_path=mass:/OPL/OPNPS2LD.ELF'
    } else {
        $content += "`r`nexit_path=mass:/OPL/OPNPS2LD.ELF`r`n"
    }

    [System.IO.File]::WriteAllText($filePath, $content, [System.Text.Encoding]::ASCII)
}

# 1. Atualizar nos templates locais
$templateConf = Join-Path $RootPath 'HDD-OSD\__common\OPL\conf_opl.cfg'
$stagedConf = Join-Path $RootPath 'BAT\__BootPackage\conf_opl.cfg'
Update-OplGuiHd $templateConf
Update-OplGuiHd $stagedConf

# Regra para conf_game.cfg: Se ja existir, nao faz nada. NUNCA criar em hipotese alguma.
# Nao gerar conf_game.cfg global para evitar quebra de jogos.

# 2. Localizar volume exFAT
$targetLetter = $DriveLetter
if (-not $targetLetter) {
    $oplVolume = Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.FileSystemLabel -eq 'OPL' -and $_.DriveLetter } | Select-Object -First 1
    if (-not $oplVolume) {
        $ensureScript = Join-Path $RootPath 'BAT\__Ensure_Opl_Drive_Letter.ps1'
        if (Test-Path -LiteralPath $ensureScript) {
            & $ensureScript -RootPath $RootPath | Out-Null
            $oplVolume = Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.FileSystemLabel -eq 'OPL' -and $_.DriveLetter } | Select-Object -First 1
        }
    }
    if ($oplVolume) { $targetLetter = "$($oplVolume.DriveLetter):" }
}

if ($targetLetter) {
    if (-not $targetLetter.EndsWith(':')) { $targetLetter += ':' }
    Write-Host "Configurando OPL e Jogos em HD (720p / 16:9 / GSM) na unidade $targetLetter..." -ForegroundColor Cyan

    # Atualizar conf_opl.cfg na raiz e na pasta OPL\ do exFAT
    $rootConf = Join-Path $targetLetter 'conf_opl.cfg'
    if (Test-Path -LiteralPath $rootConf) {
        Update-OplGuiHd $rootConf
    }
    $oplDirConf = Join-Path $targetLetter 'OPL\conf_opl.cfg'
    if (Test-Path -LiteralPath $oplDirConf) {
        Update-OplGuiHd $oplDirConf
    }

    # Regra para conf_game.cfg na raiz do exFAT:
    # Se ja existir, nao fazer nada. NUNCA criar em hipotese alguma.
    # Nao tocar em $rootGameConf.

    Write-Host "Configuracao HD da interface aplicada com sucesso em conf_opl.cfg (GUI 720p 16:9)." -ForegroundColor Green
} else {
    Write-Host "Templates locais de HD atualizados com sucesso (Drive exFAT nao montado no momento)." -ForegroundColor Yellow
}
