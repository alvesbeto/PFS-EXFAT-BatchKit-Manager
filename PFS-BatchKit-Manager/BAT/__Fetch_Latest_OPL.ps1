param(
    [string]$RootPath = "$PSScriptRoot\.."
)

$ErrorActionPreference = 'Stop'
$RootPath = [System.IO.Path]::GetFullPath($RootPath)

$bootPackage = Join-Path $RootPath 'BAT\__BootPackage'
$langsDest = Join-Path $bootPackage 'LANGS'
$tmpDir = Join-Path $RootPath 'TMP'
if (-not (Test-Path -LiteralPath $bootPackage)) { New-Item -ItemType Directory -Path $bootPackage -Force | Out-Null }
if (-not (Test-Path -LiteralPath $tmpDir)) { New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null }
if (-not (Test-Path -LiteralPath $langsDest)) { New-Item -ItemType Directory -Path $langsDest -Force | Out-Null }

$destElf = Join-Path $bootPackage 'OPNPS2LD.ELF'
$cacheElf = Join-Path $RootPath 'BAT\OPNPS2LD_LATEST.ELF'
$cacheLangs7z = Join-Path $RootPath 'BAT\OPNPS2LD-LANGS_LATEST.7z'
$7z = Join-Path $RootPath 'BAT\7-Zip\7z.exe'

Write-Host "Verificando ultima release do Open PS2 Loader e Traducoes no GitHub..." -ForegroundColor Cyan

$elfDownloaded = $false
$langsDownloaded = $false
$langsAssetUrl = $null

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $apiUrl = 'https://api.github.com/repos/ps2homebrew/Open-PS2-Loader/releases/tags/latest'
    $webClient = New-Object System.Net.WebClient
    $webClient.Headers.Add('User-Agent', 'PFS-BatchKit-Manager-PS2')
    
    $json = $webClient.DownloadString($apiUrl)
    $release = $json | ConvertFrom-Json
    Write-Host "Release encontrada: $($release.name) ($($release.tag_name))" -ForegroundColor Green
    
    # 1. Procurar asset OPNPS2LD.ELF
    $elfAsset = $release.assets | Where-Object { $_.name -eq 'OPNPS2LD.ELF' } | Select-Object -First 1
    if (-not $elfAsset) {
        $elfAsset = $release.assets | Where-Object { $_.name -like 'OPNPS2LD*.7z' -and $_.name -notlike '*LANG*' -and $_.name -notlike '*VARIANTS*' } | Select-Object -First 1
    }
    
    if ($elfAsset) {
        Write-Host "Baixando asset OPL: $($elfAsset.name) ($($elfAsset.size) bytes)..." -ForegroundColor Cyan
        $tmpDown = Join-Path $tmpDir "$($elfAsset.name)"
        $webClient.DownloadFile($elfAsset.browser_download_url, $tmpDown)
        
        if ($elfAsset.name -like '*.7z') {
            & $7z e $tmpDown -o"$bootPackage" 'OPNPS2LD.ELF' -r -y | Out-Null
            Remove-Item -LiteralPath $tmpDown -Force -ErrorAction SilentlyContinue
        } else {
            Move-Item -LiteralPath $tmpDown -Destination $destElf -Force
        }
        $elfDownloaded = $true
    }

    # 2. Procurar asset de Idiomas (OPNPS2LD-LANGS.7z)
    $langsAsset = $release.assets | Where-Object { $_.name -like 'OPNPS2LD-LANGS*.7z' } | Select-Object -First 1
    if ($langsAsset) {
        $langsAssetUrl = $langsAsset.browser_download_url
        Write-Host "Baixando pacote de idiomas: $($langsAsset.name) ($($langsAsset.size) bytes)..." -ForegroundColor Cyan
        $tmpLangs7z = Join-Path $tmpDir 'OPNPS2LD-LANGS.7z'
        $webClient.DownloadFile($langsAssetUrl, $tmpLangs7z)
        Copy-Item -LiteralPath $tmpLangs7z -Destination $cacheLangs7z -Force
        $langsDownloaded = $true
    }
} catch {
    Write-Host "Aviso ao consultar API do GitHub: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Fallbacks diretos se necessario
if (-not $elfDownloaded -and -not (Test-Path -LiteralPath $destElf)) {
    try {
        Write-Host "Tentando download direto de OPNPS2LD.ELF..." -ForegroundColor Cyan
        $webClient = New-Object System.Net.WebClient
        $webClient.Headers.Add('User-Agent', 'PFS-BatchKit-Manager-PS2')
        $webClient.DownloadFile('https://github.com/ps2homebrew/Open-PS2-Loader/releases/download/latest/OPNPS2LD.ELF', $destElf)
        $elfDownloaded = $true
    } catch {
        if (Test-Path -LiteralPath $cacheElf) {
            Copy-Item -LiteralPath $cacheElf -Destination $destElf -Force
            Write-Host "Usando OPNPS2LD.ELF em cache local." -ForegroundColor Yellow
        }
    }
}

if (-not $langsDownloaded) {
    $tmpLangs7z = Join-Path $tmpDir 'OPNPS2LD-LANGS.7z'
    if (Test-Path -LiteralPath $cacheLangs7z) {
        Copy-Item -LiteralPath $cacheLangs7z -Destination $tmpLangs7z -Force
        $langsDownloaded = $true
    } else {
        try {
            Write-Host "Tentando download direto de OPNPS2LD-LANGS.7z..." -ForegroundColor Cyan
            $webClient = New-Object System.Net.WebClient
            $webClient.Headers.Add('User-Agent', 'PFS-BatchKit-Manager-PS2')
            $webClient.DownloadFile('https://github.com/ps2homebrew/Open-PS2-Loader/releases/download/latest/OPNPS2LD-LANGS.7z', $tmpLangs7z)
            Copy-Item -LiteralPath $tmpLangs7z -Destination $cacheLangs7z -Force
            $langsDownloaded = $true
        } catch {
            Write-Warning "Falha ao baixar pacote de idiomas: $($_.Exception.Message)"
        }
    }
}

# Extrair e organizar idiomas em BAT\__BootPackage\LANGS\<Nome_Idioma>\
$tmpLangs7z = Join-Path $tmpDir 'OPNPS2LD-LANGS.7z'
if (Test-Path -LiteralPath $tmpLangs7z) {
    Write-Host "Descompactando idiomas oficiais do OPL..." -ForegroundColor Gray
    $tmpExtract = Join-Path $tmpDir 'opl_langs_stage'
    if (Test-Path -LiteralPath $tmpExtract) { Remove-Item -LiteralPath $tmpExtract -Recurse -Force }
    New-Item -ItemType Directory -Path $tmpExtract -Force | Out-Null
    
    & $7z x $tmpLangs7z "-o$tmpExtract" -y | Out-Null
    
    # Descompactar zip interno se houver
    $innerZips = Get-ChildItem -Path $tmpExtract -Recurse -Filter '*.zip'
    foreach ($z in $innerZips) {
        & $7z x $z.FullName "-o$tmpExtract" -y | Out-Null
    }
    
    # Mover pastas limpas de idiomas (ex.: Portuguese_BR)
    Get-ChildItem -Path $tmpExtract -Directory | ForEach-Object {
        if ($_.Name -match '^([a-zA-Z0-9_]+)-v[0-9]') {
            $cleanName = $Matches[1]
            $langTarget = Join-Path $langsDest $cleanName
            if (-not (Test-Path -LiteralPath $langTarget)) { New-Item -ItemType Directory -Path $langTarget -Force | Out-Null }
            Get-ChildItem -Path $_.FullName -File -Include '*.lng','font_*' | ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $langTarget $_.Name) -Force
            }
        }
    }
    Remove-Item -LiteralPath $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $langsDest -Recurse -Include '*.zip','*.7z' -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath (Join-Path $langsDest 'OPNPS2LD')) { Remove-Item -LiteralPath (Join-Path $langsDest 'OPNPS2LD') -Recurse -Force -ErrorAction SilentlyContinue }
    Write-Host "Idiomas organizados com sucesso ($((Get-ChildItem -Path $langsDest -Directory).Count) idiomas disponíveis)." -ForegroundColor Green
}

if (Test-Path -LiteralPath $destElf) {
    Copy-Item -LiteralPath $destElf -Destination $cacheElf -Force
    $info = Get-Item -LiteralPath $destElf
    Write-Host "OPNPS2LD.ELF pronto: $($info.Length) bytes ($($info.FullName))" -ForegroundColor Green
    exit 0
} else {
    Write-Warning "Nao foi possivel obter o OPNPS2LD.ELF mais recente."
    exit 1
}
