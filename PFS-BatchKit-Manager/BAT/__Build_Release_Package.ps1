param(
    [string]$RootPath = "$PSScriptRoot\..\..",
    [string]$Version = "1.3.0"
)

$ErrorActionPreference = 'Stop'
$RootPath = [System.IO.Path]::GetFullPath($RootPath)
$sourceDir = Join-Path $RootPath 'PFS-BatchKit-Manager'
$7z = Join-Path $sourceDir 'BAT\7-Zip\7z.exe'

if (-not (Test-Path -LiteralPath $7z)) {
    throw "7-Zip executavel nao encontrado em: $7z"
}

$outArchiveName = "PFS-BatchKit-Manager-v$Version.7z"
$outArchive = Join-Path $RootPath $outArchiveName
$genericArchive = Join-Path $RootPath "PFS-BatchKit-Manager.7z"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Building PFS-BatchKit-Manager v$Version Release Package" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Preparar staging limpo
$tempRoot = Join-Path $RootPath "TMP_RELEASE_BUILD"
$stageDir = Join-Path $tempRoot "PFS-BatchKit-Manager"

if (Test-Path -LiteralPath $tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

Write-Host "Copiando arquivos essenciais para staging..." -ForegroundColor Yellow

# Lista de pastas e arquivos a ignorar (build artifacts / caches)
$excludeDirs = @('TMP', 'pfs_stage', '__Cache', 'LANGS', 'LNG_ALL')
$excludeFiles = @('.wget-hsts', 'OPNPS2LD-LANGS_LATEST.7z', 'OPNPS2LD_LATEST.ELF', '*.tmp', '*.log', '*.bak', 'CheckUPDATE.txt', 'CheckOriginal.txt', 'hdd-disknum.txt', 'opl_drive_letter.txt', 'opl_selected_lang.txt', '!PFS-BatchKit-Manager2.bat')

# Copiar recursivamente via robocopy
$roboArgs = @(
    $sourceDir,
    $stageDir,
    '/E',
    '/XD'
) + $excludeDirs + @('/XF') + $excludeFiles + @('/NJH', '/NJS', '/NDL', '/NC', '/NS')

& robocopy.exe @roboArgs | Out-Null

# 2. Gerar hash e metadados de build
$hashFile = Join-Path $stageDir 'BAT\hash.txt'
$buildTime = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$buildInfo = @"
----PFS-BatchKit-Manager----
Version: $Version
Build Date: $buildTime
Fork: https://github.com/alvesbeto/PFS-BatchKit-Manager
Features: APA-Jail Minimal + exFAT BDM + OPL GitHub Updater + Portuguese_BR + IGR on exFAT
"@
[System.IO.File]::WriteAllText($hashFile, $buildInfo, [System.Text.Encoding]::ASCII)

# 3. Remover arquivos compactados antigos se existirem
if (Test-Path -LiteralPath $outArchive) { Remove-Item -LiteralPath $outArchive -Force }
if (Test-Path -LiteralPath $genericArchive) { Remove-Item -LiteralPath $genericArchive -Force }

Write-Host "Compactando pacote limpo com 7-Zip (LZMA2 Ultra)..." -ForegroundColor Yellow

$itemsToCompress = Join-Path $tempRoot '*'
& $7z a -t7z -m0=lzma2 -mx=9 -mfb=64 -md=32m -ms=on -r $outArchive $itemsToCompress | Out-Null

# Gerar tambem a copia generica esperada pela release
Copy-Item -LiteralPath $outArchive -Destination $genericArchive -Force

# 4. Limpar staging
Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue

# 5. Relatorio
$item1 = Get-Item $outArchive
$sizeMb = [math]::Round($item1.Length / 1MB, 2)

Write-Host "========================================================" -ForegroundColor Green
Write-Host " Build concluido com sucesso!" -ForegroundColor Green
Write-Host " Arquivo: $($item1.Name) ($sizeMb MB)" -ForegroundColor Green
Write-Host " Localizacao: $($item1.FullName)" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
