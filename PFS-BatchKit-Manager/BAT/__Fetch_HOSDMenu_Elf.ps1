# Downloads hosdmenu.elf from pcm720/OSDMenu GitHub releases (open source).
param(
    [Parameter(Mandatory = $true)]
    [string]$RootPath
)

$ErrorActionPreference = 'Stop'
$RootPath = [System.IO.Path]::GetFullPath($RootPath.Trim().TrimEnd('.', '\', '/'))
$outDir = Join-Path $RootPath 'BAT\OSDMenu'
$outElf = Join-Path $outDir 'hosdmenu.elf'
if (-not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}
if (Test-Path -LiteralPath $outElf) {
    Write-Host "hosdmenu.elf already present: $outElf"
    exit 0
}

$zipUrl = 'https://github.com/pcm720/OSDMenu/releases/download/v1.3.0/osdmenu-v1.3.0.zip'
$tempZip = Join-Path ([System.IO.Path]::GetTempPath()) ('osdmenu-{0}.zip' -f [Guid]::NewGuid().ToString('N'))
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ('osdmenu-{0}' -f [Guid]::NewGuid().ToString('N'))
try {
    Write-Host 'Downloading pcm720/OSDMenu v1.3.0...'
    Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip -UseBasicParsing
    Expand-Archive -LiteralPath $tempZip -DestinationPath $tempDir -Force
    $found = Get-ChildItem -LiteralPath $tempDir -Recurse -Filter 'hosdmenu.elf' -File -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $found) {
        throw 'hosdmenu.elf not found inside osdmenu release zip.'
    }
    Copy-Item -LiteralPath $found.FullName -Destination $outElf -Force
    Write-Host "Saved: $outElf"
    exit 0
} finally {
    Remove-Item -LiteralPath $tempZip -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}
