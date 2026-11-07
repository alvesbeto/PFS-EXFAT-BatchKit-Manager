param(
    [string]$RootPath = "$PSScriptRoot\.."
)

$ErrorActionPreference = 'Continue'
$RootPath = [System.IO.Path]::GetFullPath($RootPath)

# 1. Tentar detectar via hdl_dump query
$hdlDumpExe = Join-Path $RootPath 'BAT\hdl_dump.exe'
if (-not (Test-Path -LiteralPath $hdlDumpExe)) {
    $hdlDumpExe = Join-Path $RootPath 'BAT\hdl_dump'
}

$detectedHdd = $null

if (Test-Path -LiteralPath $hdlDumpExe) {
    try {
        $queryOut = & $hdlDumpExe query 2>&1
        foreach ($line in $queryOut) {
            if ($line -match 'Playstation 2 HDD' -and $line -match '(hdd\d+:)') {
                $detectedHdd = $Matches[1]
                break
            }
        }
    } catch {}
}

if ($detectedHdd) {
    Write-Output $detectedHdd
    exit 0
}

# 2. Tentar detectar se ha algum disco APA-Jail (volume OPL) conectado
$oplDiskNum = $null
try {
    $vol = Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.FileSystemLabel -eq 'OPL' } | Select-Object -First 1
    if ($vol) {
        $p = Get-Partition -ErrorAction SilentlyContinue | Where-Object { 
            $pv = Get-Volume -Partition $_ -ErrorAction SilentlyContinue
            $pv -and $pv.FileSystemLabel -eq 'OPL'
        } | Select-Object -First 1
        if ($p) {
            $oplDiskNum = $p.DiskNumber
        }
    }
} catch {}

if ($null -ne $oplDiskNum) {
    Write-Output "hdd$oplDiskNum`:"
    exit 0
}

# 3. Nenhum disco detectado
Write-Output "NONE"
exit 0
