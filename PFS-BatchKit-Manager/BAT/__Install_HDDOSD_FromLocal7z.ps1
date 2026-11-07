param(
    [Parameter(Mandatory = $true)]
    [string]$RootPath,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$RootPath = [System.IO.Path]::GetFullPath($RootPath.Trim().TrimEnd('.', '\', '/'))
$expectedElf = Join-Path $RootPath 'HDD-OSD\__system\osd100\hosdsys.elf'
$md5_7z = '403202a03b910fb6fbd522d6ab5007e7'
$hddOsdDir = Join-Path $RootPath 'HDD-OSD'
$sevenZip = Join-Path $RootPath 'BAT\7-Zip\7z.exe'

if (Test-Path -LiteralPath $expectedElf) {
    if (-not $Quiet) { Write-Host 'hosdsys.elf ja instalado.' -ForegroundColor Green }
    exit 0
}

if (-not (Test-Path -LiteralPath $sevenZip)) {
    if (-not $Quiet) { Write-Host '7z.exe nao encontrado em BAT\7-Zip\' -ForegroundColor Red }
    exit 2
}

$candidateNames = @('HDDOSD-1.10U.7z', 'hddosd-1.10-u.7z', 'HDDOSD-1.10U.7Z')
$searchDirs = @($RootPath, (Join-Path $RootPath 'BAT'), $hddOsdDir)
$archives = @()
foreach ($dir in $searchDirs) {
    if (-not (Test-Path -LiteralPath $dir)) { continue }
    foreach ($name in $candidateNames) {
        $p = Join-Path $dir $name
        if (Test-Path -LiteralPath $p) { $archives += $p }
    }
    $archives += @(Get-ChildItem -LiteralPath $dir -Filter 'HDDOSD*.7z' -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $archives += @(Get-ChildItem -LiteralPath $dir -Filter 'hddosd*.7z' -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
}
$archives = @($archives | Select-Object -Unique)

if ($archives.Count -eq 0) {
    if (-not $Quiet) {
        Write-Host 'Nenhum HDDOSD-1.10U.7z na pasta do BatchKit.' -ForegroundColor Yellow
        Write-Host "Coloque o arquivo aqui e rode de novo: $RootPath"
    }
    exit 3
}

$validArchive = $null
foreach ($a in $archives) {
    try {
        $h = (Get-FileHash -LiteralPath $a -Algorithm MD5).Hash.ToLowerInvariant()
        if ($h -eq $md5_7z) {
            $validArchive = $a
            break
        }
        if (-not $Quiet) {
            Write-Host "Ignorando $a (MD5 $h != $md5_7z)" -ForegroundColor DarkYellow
        }
    } catch {
        if (-not $Quiet) { Write-Host $_.Exception.Message -ForegroundColor Yellow }
    }
}

if (-not $validArchive) {
    if (-not $Quiet) {
        Write-Host 'Arquivo .7z encontrado mas MD5 nao confere com HDD-OSD 1.10U.' -ForegroundColor Red
    }
    exit 4
}

if (-not (Test-Path -LiteralPath $hddOsdDir)) {
    New-Item -ItemType Directory -Path $hddOsdDir -Force | Out-Null
}

if (-not $Quiet) {
    Write-Host "Extraindo $validArchive -> $hddOsdDir ..." -ForegroundColor Cyan
}

& $sevenZip x -y "-o$hddOsdDir" $validArchive | Out-Null
if ($LASTEXITCODE -ne 0) {
    if (-not $Quiet) { Write-Host 'Falha ao extrair 7z.' -ForegroundColor Red }
    exit 5
}

# Some archives nest an extra HDD-OSD folder
if (-not (Test-Path -LiteralPath $expectedElf)) {
    $nested = Join-Path $hddOsdDir 'HDD-OSD\__system\osd100\hosdsys.elf'
    if (Test-Path -LiteralPath $nested) {
        $nestedRoot = Join-Path $hddOsdDir 'HDD-OSD'
        Get-ChildItem -LiteralPath $nestedRoot -Force | ForEach-Object {
            $dest = Join-Path $hddOsdDir $_.Name
            if ($_.PSIsContainer) {
                & $sevenZip x -y "-o$dest" $_.FullName 2>$null
                Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
            } else {
                Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
            }
        }
        # Prefer robocopy-style merge for folders
        & robocopy $nestedRoot $hddOsdDir /E /IS /IT /NFL /NDL /NJH /NJS /nc /ns /np 2>$null | Out-Null
    }
}

# Fallback: any hosdsys.elf under HDD-OSD after extract
if (-not (Test-Path -LiteralPath $expectedElf)) {
    $any = Get-ChildItem -LiteralPath $hddOsdDir -Filter 'hosdsys.elf' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($any) {
        $targetDir = Split-Path -Parent $expectedElf
        if (-not (Test-Path -LiteralPath $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        }
        Copy-Item -LiteralPath $any.FullName -Destination $expectedElf -Force
        if (-not $Quiet) {
            Write-Host "hosdsys.elf copiado de $($any.FullName)" -ForegroundColor Yellow
        }
    }
}

if (Test-Path -LiteralPath $expectedElf) {
    if (-not $Quiet) { Write-Host 'OK: hosdsys.elf instalado.' -ForegroundColor Green }
    exit 0
}

if (-not $Quiet) {
    Write-Host '7z extraido mas hosdsys.elf ainda nao esta em __system\osd100\' -ForegroundColor Red
    Write-Host 'Verifique a estrutura dentro do archive Sony.'
}
exit 6
