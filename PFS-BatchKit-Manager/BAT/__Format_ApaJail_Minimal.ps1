param(
    [string]$PhysicalDrivePath,
    [Parameter(Mandatory = $true)]
    [string]$RootPath,
    [string]$HdlDevicePath,
    [string]$HdlDumpExe,
    [int]$ExtraApaReserveMiB = 0,
    [switch]$RestoreApaHeaderOnly
)

$ErrorActionPreference = 'Stop'

function Convert-ToWslPath {
    param([Parameter(Mandatory = $true)][string]$WindowsPath)
    $full = [System.IO.Path]::GetFullPath($WindowsPath)
    if ($full -notmatch '^([A-Za-z]):\\(.*)$') {
        throw "Not a Windows path: $WindowsPath"
    }
    $drive = $Matches[1].ToLowerInvariant()
    $rest = ($Matches[2] -replace '\\', '/')
    return "/mnt/$drive/$rest"
}

function Write-WslMergedLine {
    param($Line)
    if ($null -eq $Line) {
        return
    }
    if ($Line -is [System.Management.Automation.ErrorRecord]) {
        $text = $Line.Exception.Message
        if (-not $text) {
            $text = [string]$Line
        }
        if ($text.Length -gt 0) {
            Write-Host $text
        }
        return
    }
    $text = [string]$Line
    if ($text.Length -gt 0) {
        Write-Host $text
    }
}

function Invoke-WslRootBashScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Script,
        [string[]]$BashArgs
    )
    # Do not pipe the script into `bash -s`: sfdisk/dd can consume stdin and truncate the script.
    $scriptLf = ($Script -replace "`r`n", "`n") -replace "`r", "`n"
    if (-not $scriptLf.EndsWith("`n")) {
        $scriptLf += "`n"
    }
    $tempSh = [System.IO.Path]::Combine(
        [System.IO.Path]::GetTempPath(),
        ('pfs-apajail-{0}.sh' -f [Guid]::NewGuid().ToString('N'))
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    try {
        [System.IO.File]::WriteAllText($tempSh, $scriptLf, $utf8NoBom)
        $wslSh = Convert-ToWslPath -WindowsPath $tempSh
        # sfdisk prints signature hints on stderr; with $ErrorActionPreference Stop that becomes NativeCommandError.
        $exitCode = 1
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $wslOut = & wsl.exe -u root bash $wslSh @BashArgs 2>&1
            $exitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prevEap
        }
        foreach ($line in @($wslOut)) {
            Write-WslMergedLine $line
        }
        return [int]$exitCode
    } finally {
        Remove-Item -LiteralPath $tempSh -Force -ErrorAction SilentlyContinue
    }
}

# Batch "%~dp0" trailing backslash breaks quoted -RootPath on cmd.exe; "%~dp0." is normalized here too.
$RootPath = $RootPath.Trim().TrimEnd('.', '\', '/')
if (-not $RootPath) {
    throw 'RootPath is empty.'
}
$RootPath = [System.IO.Path]::GetFullPath($RootPath)

if (-not $HdlDumpExe) {
    $HdlDumpExe = Join-Path $RootPath 'BAT\hdl_dump'
    if (-not (Test-Path -LiteralPath $HdlDumpExe)) {
        $HdlDumpExe = Join-Path $RootPath 'BAT\hdl_dump.exe'
    }
}
function Get-ApaHdrBackupPath {
    param([string]$Root)
    $dir = Join-Path $Root 'BAT\__Cache'
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    return Join-Path $dir 'apa_jail_hdr_backup.bin'
}

function Backup-ApaHeaderLba0_7 {
    param(
        [Parameter(Mandatory = $true)][string]$PhysicalDrivePath,
        [Parameter(Mandatory = $true)][string]$OutPath
    )
    $stream = [System.IO.File]::Open(
        $PhysicalDrivePath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite
    )
    try {
        $buf = New-Object byte[] 4096
        $read = $stream.Read($buf, 0, 4096)
        if ($read -lt 1024) {
            throw "Could not read APA header from $PhysicalDrivePath (read $read bytes)."
        }
        $outDir = Split-Path -Parent $OutPath
        if (-not (Test-Path -LiteralPath $outDir)) {
            New-Item -ItemType Directory -Path $outDir -Force | Out-Null
        }
        [System.IO.File]::WriteAllBytes($OutPath, $buf[0..($read - 1)])
    } finally {
        $stream.Dispose()
    }
}

function Test-ApaBackupBytesLookValid {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 8) {
        return $false
    }
    $magic = [BitConverter]::ToUInt32($bytes, 4)
    return ($magic -eq [uint32]0x00415041)
}

function Repair-ApaMasterChecksumOnDisk {
    param([Parameter(Mandatory = $true)][string]$PhysicalDrivePath)
    $stream = [System.IO.File]::Open(
        $PhysicalDrivePath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::ReadWrite
    )
    try {
        $buf = New-Object byte[] 1024
        $read = $stream.Read($buf, 0, 1024)
        if ($read -lt 1024) {
            throw "Could not read 1024 bytes from LBA 0-1 on $PhysicalDrivePath."
        }
        $sum = [uint64]0
        for ($i = 1; $i -le 255; $i++) {
            $off = $i * 4
            $word = [BitConverter]::ToUInt32($buf, $off)
            $sum = ($sum + $word) -band 0xffffffffL
        }
        [BitConverter]::GetBytes([uint32]$sum).CopyTo($buf, 0)
        $stream.Seek(0, [System.IO.SeekOrigin]::Begin) | Out-Null
        $stream.Write($buf, 0, 1024) | Out-Null
        $stream.Flush()
        Write-Host 'APA master checksum (LBA 0-1) recalculated.'
    } finally {
        $stream.Dispose()
    }
}

function Release-PhysicalDriveForWin32Tools {
    param([Parameter(Mandatory = $true)][string]$PhysicalDrivePath)
    Disable-WslPhysicalDiskAccess -PhysicalDrivePath $PhysicalDrivePath
    $diskNum = Get-DiskNumberFromPhysicalPath -Path $PhysicalDrivePath
    Set-Disk -Number $diskNum -IsOffline $false -ErrorAction SilentlyContinue
    Set-Disk -Number $diskNum -IsReadOnly $false -ErrorAction SilentlyContinue
    Get-Partition -DiskNumber $diskNum -ErrorAction SilentlyContinue | ForEach-Object {
        $vol = Get-Volume -Partition $_ -ErrorAction SilentlyContinue
        if ($vol -and $vol.FileSystemLabel -eq 'OPL' -and $vol.DriveLetter) {
            $letter = '{0}:' -f $vol.DriveLetter
            Write-Host "Dismounting $letter (OPL) for raw HDD access..."
            $prevEap = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try {
                & mountvol.exe $letter /d 2>&1 | Out-Null
            } finally {
                $ErrorActionPreference = $prevEap
            }
        }
    }
    Update-HostStorageCache
    Start-Sleep -Seconds 2
}

function Invoke-PfsshellLines {
    param(
        [Parameter(Mandatory = $true)][string[]]$Lines,
        [Parameter(Mandatory = $true)][string]$Root
    )
    $pfsshell = Get-PfsshellExe -Root $Root
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = @($Lines | & $pfsshell 2>&1)
        foreach ($line in $out) {
            Write-WslMergedLine $line
        }
        return ($out | Out-String)
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

function Test-PfsshellApaChainPresent {
    param(
        [Parameter(Mandatory = $true)][string]$PhysicalDrivePath,
        [Parameter(Mandatory = $true)][string]$Root
    )
    $text = Invoke-PfsshellLines -Root $Root -Lines @(
        "device $PhysicalDrivePath"
        'ls -l'
        'exit'
    )
    return ($text -match '__mbr')
}

function Write-HdlDumpDetectionDiagnostic {
    param([Parameter(Mandatory = $true)][string]$HdlDumpPath)
    Write-Host ''
    Write-Host '--- hdl_dump query ---'
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $q = & $HdlDumpPath query 2>&1
        foreach ($line in @($q)) {
            Write-WslMergedLine $line
        }
    } finally {
        $ErrorActionPreference = $prevEap
    }
    Write-Host '--- end query ---'
    Write-Host ''
}

function Invoke-WslApaHeaderRepair {
    param(
        [Parameter(Mandatory = $true)][string]$PhysicalDrivePath,
        [string]$ApaBackupPath
    )
    $diskNum = Get-DiskNumberFromPhysicalPath -Path $PhysicalDrivePath
    $winDisk = Get-Disk -Number $diskNum
    Set-Disk -Number $diskNum -IsReadOnly $false -ErrorAction SilentlyContinue
    Set-Disk -Number $diskNum -IsOffline $true -ErrorAction SilentlyContinue
    try {
        Enable-WslPhysicalDiskAccess -PhysicalDrivePath $PhysicalDrivePath
        Start-Sleep -Seconds 2
        $linuxDev = Resolve-WslBlockDevice -DiskNumber $diskNum -SizeBytes $winDisk.Size -SerialNumber $winDisk.SerialNumber
        Write-Host "WSL device: $linuxDev"
        $wslBackup = ''
        if ($ApaBackupPath -and (Test-Path -LiteralPath $ApaBackupPath)) {
            $wslBackup = Convert-ToWslPath -WindowsPath $ApaBackupPath
        }
        $bash = @'
set -e
DEVICE="$1"
APA_BACK="$2"
recalc_cs() {
  python3 - "$DEVICE" <<'PY'
import struct, sys
dev = sys.argv[1]
with open(dev, "r+b", buffering=0) as f:
    f.seek(0)
    h = bytearray(f.read(1024))
    if len(h) < 1024:
        h.extend(b"\0" * (1024 - len(h)))
    words = struct.unpack("<256I", bytes(h))
    s = sum(words[1:256]) & 0xFFFFFFFF
    struct.pack_into("<I", h, 0, s)
    f.seek(0)
    f.write(h)
PY
}
dd if="$DEVICE" of=/tmp/mbr_s0.bin bs=512 count=1 status=none
restored=0
if [ -n "$APA_BACK" ] && [ -f "$APA_BACK" ]; then
  dd if="$APA_BACK" of="$DEVICE" bs=512 count=8 conv=notrunc status=none
  restored=1
  echo "Restored APA header from backup file."
else
  python3 - "$DEVICE" <<'PY'
import struct, sys
dev = sys.argv[1]
magic = 0x00415041
with open(dev, "rb") as f:
    blob = f.read(32 * 1024 * 1024)
found = None
for off in range(0, max(0, len(blob) - 1024), 512):
    if struct.unpack_from("<I", blob, off + 4)[0] != magic:
        continue
    h = blob[off:off + 1024]
    if len(h) < 1024:
        continue
    words = struct.unpack("<256I", h.ljust(1024, b"\0")[:1024])
    if (sum(words[1:256]) & 0xFFFFFFFF) == words[0]:
        found = off
        break
if found is None:
    print("No valid APA __mbr copy found in first 32 MiB.", file=sys.stderr)
    sys.exit(3)
with open(dev, "r+b", buffering=0) as f:
    f.seek(found)
    hdr = f.read(1024)
    f.seek(0)
    f.write(hdr.ljust(1024, b"\0")[:1024])
print(f"Copied APA __mbr from disk offset {found} to LBA 0.")
PY
  restored=1
fi
if [ "$restored" -eq 1 ]; then
  dd if=/tmp/mbr_s0.bin of="$DEVICE" bs=1 skip=446 seek=446 count=66 conv=notrunc status=none
  echo '4150414A2D413200' | xxd -r -p | dd of="$DEVICE" bs=8 count=1 seek=28 conv=notrunc status=none
  recalc_cs
  sync
  echo 'APA-Jail header merge + checksum done.'
fi
'@
        Write-Host 'Repairing APA __mbr (backup or scan) + MBR exFAT...'
        $exitCode = Invoke-WslRootBashScript -Script $bash -BashArgs @($linuxDev, $wslBackup)
        if ($exitCode -ne 0) {
            throw "WSL APA header repair failed (exit $exitCode)."
        }
    } finally {
        Disable-WslPhysicalDiskAccess -PhysicalDrivePath $PhysicalDrivePath
        Set-Disk -Number $diskNum -IsOffline $false -ErrorAction SilentlyContinue
        Update-HostStorageCache
    }
    try {
        Repair-ApaMasterChecksumOnDisk -PhysicalDrivePath $PhysicalDrivePath
    } catch {
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    }
}

function Get-PfsshellExe {
    param([Parameter(Mandatory = $true)][string]$Root)
    foreach ($name in @('pfsshell.exe', 'pfsshell')) {
        $candidate = Join-Path $Root ("BAT\{0}" -f $name)
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "pfsshell not found under $(Join-Path $Root 'BAT') (expected pfsshell.exe)."
}

function Resolve-PhysicalDriveFromOplVolume {
    $candidates = @()
    Get-Partition -ErrorAction SilentlyContinue | ForEach-Object {
        $vol = Get-Volume -Partition $_ -ErrorAction SilentlyContinue
        if ($vol -and $vol.FileSystemLabel -eq 'OPL') {
            $candidates += $_
        }
    }
    $part = $candidates | Select-Object -First 1
    if (-not $part) {
        return $null
    }
    return ('\\.\PhysicalDrive{0}' -f $part.DiskNumber)
}

function Get-PhysicalDriveFromHddCache {
    param([Parameter(Mandatory = $true)][string]$Root)
    $cacheBat = Join-Path $Root 'BAT\__Cache\HDD.BAT'
    if (-not (Test-Path -LiteralPath $cacheBat)) {
        return $null
    }
    foreach ($line in Get-Content -LiteralPath $cacheBat -ErrorAction SilentlyContinue) {
        if ($line -notmatch '@pfsshell_path=(.+)') {
            continue
        }
        $path = $Matches[1].Trim().Trim('"')
        if ($path -match 'PhysicalDrive\d+') {
            return $path
        }
    }
    return $null
}

function Resolve-PhysicalDriveFromExfatVolume {
    $byDisk = @{}
    Get-Partition -ErrorAction SilentlyContinue | ForEach-Object {
        $part = $_
        $vol = Get-Volume -Partition $part -ErrorAction SilentlyContinue
        if (-not $vol) {
            return
        }
        if ($vol.FileSystem -ne 'exFAT') {
            return
        }
        $score = 1
        if ($vol.FileSystemLabel -eq 'OPL') {
            $score = 10
        }
        $diskNum = $part.DiskNumber
        if (-not $byDisk.ContainsKey($diskNum) -or $byDisk[$diskNum].Score -lt $score) {
            $byDisk[$diskNum] = @{ Score = $score; Part = $part }
        }
    }
    if ($byDisk.Count -eq 0) {
        return $null
    }
    $bestDisk = ($byDisk.GetEnumerator() | Sort-Object { $_.Value.Score } -Descending | Select-Object -First 1).Key
    return ('\\.\PhysicalDrive{0}' -f $bestDisk)
}

function Resolve-PhysicalDriveForApaJailRepair {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [string]$ExplicitPath
    )
    if ($ExplicitPath -and $ExplicitPath -match 'PhysicalDrive\d+') {
        return $ExplicitPath
    }
    $tryOrder = @(
        { Resolve-PhysicalDriveFromOplVolume }
        { Get-PhysicalDriveFromHddCache -Root $Root }
        { Resolve-PhysicalDriveFromExfatVolume }
    )
    foreach ($resolver in $tryOrder) {
        $path = & $resolver
        if ($path) {
            return $path
        }
    }
    $disks = @(Get-Disk -ErrorAction SilentlyContinue | Where-Object {
            -not $_.IsSystem -and -not $_.IsBoot -and $_.Size -gt 200GB
        })
    if ($disks.Count -eq 1) {
        return ('\\.\PhysicalDrive{0}' -f $disks[0].Number)
    }
    return $null
}

function Invoke-MinimalOsdPartitionsPfsshell {
    param(
        [Parameter(Mandatory = $true)][string]$PhysicalDrivePath,
        [Parameter(Mandatory = $true)][string]$Root
    )
    $Root = [System.IO.Path]::GetFullPath($Root)
    $pfsshell = Get-PfsshellExe -Root $Root
    $tmp = Join-Path $Root 'TMP'
    if (-not (Test-Path -LiteralPath $tmp)) {
        New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    }
    $scriptPath = Join-Path $tmp 'pfs-repair-min-osd.txt'
    @(
        "device $PhysicalDrivePath"
        'initialize yes'
        'mkpart __sysconf 128M PFS'
        'mkpart __system 128M PFS'
        'mkpart __contents 128M PFS'
        'mkpart __common 128M PFS'
        'ls -l'
        'exit'
    ) | Set-Content -LiteralPath $scriptPath -Encoding ASCII
    Write-Host 'Recreating minimal PFS (__sysconf, __system, __contents, __common)...'
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        Get-Content -LiteralPath $scriptPath | & $pfsshell 2>&1 | ForEach-Object { Write-WslMergedLine $_ }
    } finally {
        $ErrorActionPreference = $prevEap
    }
    if ($LASTEXITCODE -ne 0 -and -not (Test-PfsshellApaChainPresent -PhysicalDrivePath $PhysicalDrivePath -Root $Root)) {
        throw "pfsshell minimal OSD failed (exit $LASTEXITCODE)."
    }
}

function Invoke-MergeApaHeaderViaWsl {
    param(
        [Parameter(Mandatory = $true)][string]$PhysicalDrivePath,
        [string]$ApaBackupPath
    )
    Invoke-WslApaHeaderRepair -PhysicalDrivePath $PhysicalDrivePath -ApaBackupPath $ApaBackupPath
}

if (-not $RestoreApaHeaderOnly) {
    if (-not $PhysicalDrivePath) {
        throw 'PhysicalDrivePath is required.'
    }
    if (-not $HdlDevicePath) {
        throw 'HdlDevicePath is required (e.g. hdd3: from hdl_dump query).'
    }
}
if (-not (Test-Path -LiteralPath $HdlDumpExe)) {
    throw "hdl_dump not found: $HdlDumpExe"
}

function Get-WslReadiness {
    $probe = & wsl.exe -e echo 'OK' 2>&1 | Out-String
    $code = $LASTEXITCODE

    if ($code -eq 0 -and $probe -match '\bOK\b') {
        return @{ Ready = $true; Message = $null }
    }

    $msg = @(
        'WSL nao esta pronto para executar comandos Linux.'
        ''
    )

    if ($probe -match 'WSL_E_WSL_OPTIONAL_COMPONENT_REQUIRED|Subsistema do Windows para Linux Opcional') {
        $msg += 'O componente opcional WSL ainda nao esta ativo.'
        $msg += '1) Abra PowerShell como Administrador'
        $msg += '2) wsl --install'
        $msg += '3) Reinicie o PC (obrigatorio apos a primeira instalacao)'
        $msg += '4) wsl --install -d Ubuntu'
        $msg += '5) Dentro do Ubuntu: sudo apt update && sudo apt install -y exfatprogs util-linux'
    } elseif ($probe -match 'no installed distributions|Nenhuma distribuicao') {
        $msg += 'WSL instalado, mas falta uma distribuicao Linux.'
        $msg += 'Execute: wsl --install -d Ubuntu'
    } else {
        $msg += "Saida do WSL: $($probe.Trim())"
        $msg += 'Teste manual: wsl -e echo OK'
    }

    return @{ Ready = $false; Message = ($msg -join [Environment]::NewLine) }
}

function Get-DiskNumberFromPhysicalPath {
    param([string]$Path)
    if ($Path -match 'PhysicalDrive(\d+)$') {
        return [int]$Matches[1]
    }
    throw "Invalid PhysicalDrive path: $Path"
}

function Get-UsedApaMiB {
    $toc = & $HdlDumpExe toc $HdlDevicePath 2>&1 | Out-String
    if ($toc -notmatch 'used:\s*([\d,]+)MB') {
        throw "Could not parse APA used size from hdl_dump toc."
    }
    return [int]($Matches[1] -replace ',', '')
}

function Ensure-WslApaJailPackages {
    $pkgScript = @'
set -e
export DEBIAN_FRONTEND=noninteractive
if command -v mkfs.exfat >/dev/null 2>&1; then
  exit 0
fi
apt-get update -qq
apt-get install -y exfatprogs util-linux fdisk xxd e2fsprogs
command -v mkfs.exfat >/dev/null
'@
    Write-Host 'Installing/checking exfatprogs in WSL (root, may take a minute)...'
    $pkgLf = ($pkgScript -replace "`r`n", "`n") -replace "`r", "`n"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = @($pkgLf | & wsl.exe -u root bash -s 2>&1)
        $pkgExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEap
    }
    if ($pkgExit -ne 0) {
        throw "Could not install exfatprogs in WSL. Run in Ubuntu: sudo apt install -y exfatprogs`n$($out -join "`n")"
    }
}

function Invoke-ApaJailViaWsl {
    param(
        [string]$LinuxDevice,
        [int]$ApaMiB,
        [string]$ApaBackupWslPath,
        [string]$MbrKelfWslPath = ''
    )
    Ensure-WslApaJailPackages
    # Run as root in WSL: piped bash has no TTY, so sudo password prompts hang the BatchKit UI.
    $bash = @'
set -e
DEVICE="$1"
APA_MiB="$2"
partprobe "$DEVICE" 2>/dev/null || blockdev --rereadpt "$DEVICE" 2>/dev/null || true
sleep 1
resolve_exfat_part() {
  if [ -b "${DEVICE}3" ]; then echo "${DEVICE}3"; return 0; fi
  if [ -b "${DEVICE}p3" ]; then echo "${DEVICE}p3"; return 0; fi
  return 1
}
EXFAT_PART=""
if resolve_exfat_part >/dev/null 2>&1; then EXFAT_PART="$(resolve_exfat_part)"; fi
if [ -z "$EXFAT_PART" ] && command -v lsblk >/dev/null 2>&1; then
  EXFAT_PART="$(lsblk -rpno NAME,FSTYPE "$DEVICE" 2>/dev/null | awk '$2 ~ /exfat/i { print $1; exit }')"
fi
if [ -n "$EXFAT_PART" ]; then
  echo "MBR partitions already present on $DEVICE ($EXFAT_PART), skipping sfdisk."
elif [ -z "$EXFAT_PART" ]; then
  SFDISK_IN="$(mktemp)"
  trap 'rm -f "$SFDISK_IN"' EXIT
  {
    printf '%s\n' ",${APA_MiB}MiB,17" ",32MiB,17" ",,07"
  } > "$SFDISK_IN"
  sfdisk --force "$DEVICE" < "$SFDISK_IN"
  rm -f "$SFDISK_IN"
  trap - EXIT
  partprobe "$DEVICE" 2>/dev/null || blockdev --rereadpt "$DEVICE" 2>/dev/null || true
  sleep 2
  if resolve_exfat_part >/dev/null 2>&1; then
    EXFAT_PART="$(resolve_exfat_part)"
  else
    echo 'exFAT partition node not found' >&2
    exit 1
  fi
fi
if ! command -v mkfs.exfat >/dev/null 2>&1 && ! command -v mkexfatfs >/dev/null 2>&1; then
  echo 'mkfs.exfat missing; exfatprogs not installed' >&2
  exit 1
fi
format_exfat_opl() {
  local part="$1"
  if command -v mkfs.exfat >/dev/null 2>&1; then
    # exfatprogs (Ubuntu): -L -c -f; legacy fuse-exfat used -F (invalid on exfatprogs 1.x)
    if mkfs.exfat -h 2>&1 | grep -q 'full-format'; then
      mkfs.exfat -L OPL -c 32K "$part"
    else
      mkfs.exfat -F -c 32K -L OPL "$part" 2>/dev/null || mkfs.exfat -L OPL "$part"
    fi
  else
    mkexfatfs -L OPL "$part"
  fi
}
if blkid "$EXFAT_PART" 2>/dev/null | grep -qi exfat; then
  echo "exFAT already on $EXFAT_PART, skipping mkfs."
else
  format_exfat_opl "$EXFAT_PART"
fi
mkdir -p /mnt/ps2opl
mount "$EXFAT_PART" /mnt/ps2opl
mkdir -p /mnt/ps2opl/{APPS,ART,CFG,CHT,LNG,THM,VMC,CD,DVD,POPS,nhddl}
echo 'hdd_partition=__common' > /mnt/ps2opl/CFG/conf_hdd.cfg
umount /mnt/ps2opl
REC=""
if [ -b "${DEVICE}2" ]; then
  REC="${DEVICE}2"
elif [ -b "${DEVICE}p2" ]; then
  REC="${DEVICE}p2"
fi
if [ -n "$REC" ] && command -v mkfs.ext2 >/dev/null 2>&1; then
  if ! blkid "$REC" 2>/dev/null | grep -qi ext2; then
    mkfs.ext2 -F -L RECOVERY "$REC" >/dev/null 2>&1 || true
  fi
fi
APA_BACK="$3"
MBR_KELF="$4"
if [ -n "$APA_BACK" ] && [ -f "$APA_BACK" ]; then
  dd if="$DEVICE" of=/tmp/mbr_s0.bin bs=512 count=1 status=none
  dd if="$APA_BACK" of="$DEVICE" bs=512 count=8 conv=notrunc status=none
  dd if="/tmp/mbr_s0.bin" of="$DEVICE" bs=1 skip=446 seek=446 count=66 conv=notrunc status=none
  echo '4150414A2D413200' | xxd -r -p | dd of="$DEVICE" bs=8 count=1 seek=28 conv=notrunc status=none
  if [ -n "$MBR_KELF" ] && [ -f "$MBR_KELF" ]; then
    kelf_sz=$(stat -c%s "$MBR_KELF")
    kelf_sec=$(( (kelf_sz + 511) / 512 ))
    dd if="$MBR_KELF" of="$DEVICE" bs=512 seek=16 conv=notrunc status=none
    python3 - "$DEVICE" "$kelf_sec" <<'PY'
import struct, sys
dev = sys.argv[1]
ksec = int(sys.argv[2])
with open(dev, "r+b", buffering=0) as f:
    f.seek(0)
    h = bytearray(f.read(1024))
    struct.pack_into("<I", h, 0x130, 16)
    struct.pack_into("<I", h, 0x134, ksec)
    f.seek(0)
    f.write(h)
PY
    echo "Injected MBR.KELF ($kelf_sec sectors) into sector 16."
  fi
  python3 - "$DEVICE" <<'PY'
import struct, sys
dev = sys.argv[1]
with open(dev, "r+b", buffering=0) as f:
    f.seek(0)
    h = bytearray(f.read(1024))
    if len(h) < 1024:
        h.extend(b"\0" * (1024 - len(h)))
    words = struct.unpack("<256I", bytes(h))
    s = sum(words[1:256]) & 0xFFFFFFFF
    struct.pack_into("<I", h, 0, s)
    f.seek(0)
    f.write(h)
PY
  echo 'APA __mbr merged with MBR partition table (APA-Jail).'
fi
'@
    Write-Host 'Running APA-Jail in WSL as root (no sudo password prompt)...'
    $exitCode = Invoke-WslRootBashScript -Script $bash -BashArgs @($LinuxDevice, "$ApaMiB", $ApaBackupWslPath, $MbrKelfWslPath)
    if ($exitCode -ne 0) {
        throw "WSL APA-Jail step failed (exit $exitCode)."
    }
}

function Enable-WslPhysicalDiskAccess {
    param([string]$PhysicalDrivePath)
    $out = (& wsl.exe --mount $PhysicalDrivePath --bare 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -eq 0) {
        return
    }
    if ($out -match 'already attached|already mounted|já está anexado|WSL_E_DISK_ALREADY_ATTACHED|ERROR_FILE_EXISTS|Sharing violation') {
        return
    }
    if ($out) {
        Write-Host "wsl --mount: $out"
    }
}

function Disable-WslPhysicalDiskAccess {
    param([string]$PhysicalDrivePath)
    & wsl.exe --unmount $PhysicalDrivePath 2>&1 | Out-Null
}

function Resolve-WslBlockDevice {
    param(
        [int]$DiskNumber,
        [uint64]$SizeBytes,
        [string]$SerialNumber
    )
    $serial = if ($SerialNumber) { $SerialNumber.Trim() } else { '' }
    $resolveScript = @'
size_bytes="$1"
serial="$2"
if [ -n "$size_bytes" ]; then
  dev="$(lsblk -dpno NAME,SIZE -b 2>/dev/null | awk -v s="$size_bytes" '$2==s {print $1; exit}')"
  if [ -n "$dev" ]; then
    echo "$dev"
    exit 0
  fi
fi
ns="$(echo "$serial" | tr -d '[:space:]' | tr 'A-Z' 'a-z')"
if [ -n "$ns" ]; then
  while read -r name ser; do
    [ -z "$name" ] && continue
    s="$(echo "$ser" | tr -d '[:space:]' | tr 'A-Z' 'a-z')"
    if [ "$s" = "$ns" ]; then
      echo "$name"
      exit 0
    fi
  done < <(lsblk -dpno NAME,SERIAL 2>/dev/null)
fi
lsblk -dpno NAME,TYPE,SIZE -b 2>/dev/null | awk '$2=="disk" && $3>50000000000 {print $1; exit}'
exit 1
'@
    $resolveLf = ($resolveScript -replace "`r`n", "`n") -replace "`r", "`n"
    $raw = @($resolveLf | & wsl.exe bash -s -- $SizeBytes $serial 2>&1)
    $dev = ($raw | Where-Object {
            $_ -and $_ -match '^/dev/' -and $_ -notmatch 'error|Error'
        } | Select-Object -First 1)

    if (-not $dev) {
        $listing = (& wsl.exe lsblk -dpno NAME,MODEL,SIZE,SERIAL 2>&1 | Out-String).Trim()
        throw @(
            "WSL could not map PhysicalDrive$DiskNumber to /dev/sdX."
            "Serial: $serial | Size bytes: $SizeBytes"
            'Try: wsl --mount (run this tool as Administrator).'
            'lsblk in WSL:'
            $listing
        ) -join [Environment]::NewLine
    }
    return $dev.Trim()
}

function Complete-ApaJailHeaderAfterFormat {
    param(
        [Parameter(Mandatory = $true)][string]$PhysicalDrivePath,
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$HdlDumpExe,
        [Parameter(Mandatory = $true)][string]$BackupPath
    )
    Write-Host ''
    Write-Host 'Finalizing APA __mbr + MBR (hdl_dump detection)...' -ForegroundColor Cyan
    Release-PhysicalDriveForWin32Tools -PhysicalDrivePath $PhysicalDrivePath
    $backupValid = Test-ApaBackupBytesLookValid -Path $BackupPath
    $useBackup = if ($backupValid) { $BackupPath } else { $null }
    if (-not $backupValid) {
        Write-Host 'APA backup pre-sfdisk invalid; using on-disk APA scan fallback.' -ForegroundColor Yellow
    }
    Invoke-WslApaHeaderRepair -PhysicalDrivePath $PhysicalDrivePath -ApaBackupPath $useBackup
    Release-PhysicalDriveForWin32Tools -PhysicalDrivePath $PhysicalDrivePath
    try {
        & (Join-Path $PSScriptRoot '__Inject_Mbr_Bootloader.ps1') -PhysicalDrivePath $PhysicalDrivePath -RootPath $Root
    } catch {
        Write-Host "Aviso MBR KELF: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    Write-HdlDumpDetectionDiagnostic -HdlDumpPath $HdlDumpExe
    $query = & $HdlDumpExe query 2>&1 | Out-String
    if ($query -match 'Playstation 2 HDD') {
        Write-Host 'hdl_dump: Playstation 2 HDD detectado apos formatacao APA-Jail.' -ForegroundColor Green
        return $true
    }
    Write-Host 'hdl_dump ainda nao listou o HDD; use menu [13] ou reinicie o BatchKit.' -ForegroundColor Yellow
    return $false
}

if ($RestoreApaHeaderOnly) {
    $PhysicalDrivePath = Resolve-PhysicalDriveForApaJailRepair -Root $RootPath -ExplicitPath $PhysicalDrivePath
    if (-not $PhysicalDrivePath) {
        throw @(
            'Nao foi possivel localizar o HDD APA-Jail.'
            'Tentado: volume OPL, cache BAT\__Cache\HDD.BAT, particao exFAT, unico disco >200GB.'
            'Conecte o HDD, monte OPL ou informe: -PhysicalDrivePath \\.\PhysicalDriveN'
        ) -join [Environment]::NewLine
    }
    Write-Host "Repair APA header: $PhysicalDrivePath"
    Release-PhysicalDriveForWin32Tools -PhysicalDrivePath $PhysicalDrivePath
    $backupPath = Get-ApaHdrBackupPath -Root $RootPath
    $backupValid = Test-ApaBackupBytesLookValid -Path $backupPath
    if (-not $backupValid) {
        if (Test-Path -LiteralPath $backupPath) {
            Write-Host 'Backup apa_jail_hdr_backup.bin invalido (nao e APA); ignorando.' -ForegroundColor Yellow
            Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
        }
        $chainOk = Test-PfsshellApaChainPresent -PhysicalDrivePath $PhysicalDrivePath -Root $RootPath
        if (-not $chainOk) {
            Write-Host ''
            Write-Host 'Cadeia APA nao visivel — recriando layout PFS minimo (exFAT OPL preservado via MBR).' -ForegroundColor Yellow
            Write-Host ''
            Release-PhysicalDriveForWin32Tools -PhysicalDrivePath $PhysicalDrivePath
            Invoke-MinimalOsdPartitionsPfsshell -PhysicalDrivePath $PhysicalDrivePath -Root $RootPath
            Backup-ApaHeaderLba0_7 -PhysicalDrivePath $PhysicalDrivePath -OutPath $backupPath
            $backupValid = Test-ApaBackupBytesLookValid -Path $backupPath
        } else {
            Write-Host 'Cadeia APA visivel no pfsshell; pulando initialize (evita Bad file descriptor).'
        }
    }
    $wslState = Get-WslReadiness
    if (-not $wslState.Ready) {
        Write-Host $wslState.Message -ForegroundColor Yellow
        exit 2
    }
    $useBackup = if ($backupValid) { $backupPath } else { $null }
    Invoke-WslApaHeaderRepair -PhysicalDrivePath $PhysicalDrivePath -ApaBackupPath $useBackup
    Release-PhysicalDriveForWin32Tools -PhysicalDrivePath $PhysicalDrivePath
    try {
        & (Join-Path $PSScriptRoot '__Inject_Mbr_Bootloader.ps1') -PhysicalDrivePath $PhysicalDrivePath -RootPath $Root
    } catch {
        Write-Host "Aviso MBR KELF: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    Write-HdlDumpDetectionDiagnostic -HdlDumpPath $HdlDumpExe
    $query = & $HdlDumpExe query 2>&1 | Out-String
    if ($query -match 'Playstation 2 HDD') {
        Write-Host 'hdl_dump: Playstation 2 HDD detectado.' -ForegroundColor Green
    } else {
        Write-Host 'Se ainda nao detectar: feche programas que usam OPL, reinicie o BatchKit (scan HDD) ou reinicie o PC.' -ForegroundColor Yellow
    }
    exit 0
}

$diskNum = Get-DiskNumberFromPhysicalPath -Path $PhysicalDrivePath
$diskSizeBytes = (Get-Disk -Number $diskNum).Size
if ($diskSizeBytes -gt 2TB) {
    Write-Warning 'Drive is larger than 2 TiB. Use APA-Jail Type-B (PS2 HDD Decryption Helper).'
}
$usedMiB = Get-UsedApaMiB
$apaMiB = $ExtraApaReserveMiB + $usedMiB + 6400 + 128

Write-Host "APA used: ${usedMiB} MiB | APA-Jail boundary: ${apaMiB} MiB"

$backupPath = Get-ApaHdrBackupPath -Root $RootPath
Write-Host "Backing up APA LBA 0-7 -> $backupPath"
Backup-ApaHeaderLba0_7 -PhysicalDrivePath $PhysicalDrivePath -OutPath $backupPath
$wslBackup = Convert-ToWslPath -WindowsPath $backupPath

$wslState = Get-WslReadiness
if (-not $wslState.Ready) {
    Write-Host ''
    Write-Host $wslState.Message -ForegroundColor Yellow
    Write-Host ''
    Write-Host "APA_MiB planejado para sfdisk: $apaMiB"
    Write-Host 'Alternativa: PS2 HDD Decryption Helper (Linux) - APA-Jail Type-A.'
    Write-Host 'Apos corrigir o WSL, use HDD Management opcao 11 (somente exFAT, mantem APA).'
    exit 2
}

$winDisk = Get-Disk -Number $diskNum
Set-Disk -Number $diskNum -IsReadOnly $false -ErrorAction SilentlyContinue
Set-Disk -Number $diskNum -IsOffline $true -ErrorAction SilentlyContinue

try {
    Enable-WslPhysicalDiskAccess -PhysicalDrivePath $PhysicalDrivePath
    Start-Sleep -Seconds 2
    $linuxDev = Resolve-WslBlockDevice -DiskNumber $diskNum -SizeBytes $winDisk.Size -SerialNumber $winDisk.SerialNumber
    Write-Host "WSL device: $linuxDev"
    $mbrKelfWin = Join-Path $RootPath 'BAT\__BootPackage\MBR.XLF'
    $mbrKelfWsl = ''
    if (Test-Path -LiteralPath $mbrKelfWin) {
        $mbrKelfWsl = Convert-ToWslPath -WindowsPath $mbrKelfWin
    }
    Invoke-ApaJailViaWsl -LinuxDevice $linuxDev -ApaMiB $apaMiB -ApaBackupWslPath $wslBackup -MbrKelfWslPath $mbrKelfWsl
} finally {
    Disable-WslPhysicalDiskAccess -PhysicalDrivePath $PhysicalDrivePath
    Set-Disk -Number $diskNum -IsOffline $false -ErrorAction SilentlyContinue
    Update-HostStorageCache
}

Complete-ApaJailHeaderAfterFormat `
    -PhysicalDrivePath $PhysicalDrivePath `
    -Root $RootPath `
    -HdlDumpExe $HdlDumpExe `
    -BackupPath $backupPath | Out-Null

try {
    $ensureScript = Join-Path $RootPath 'BAT\__Ensure_Opl_Drive_Letter.ps1'
    if (Test-Path -LiteralPath $ensureScript) {
        & $ensureScript -PhysicalDrivePath $PhysicalDrivePath -RootPath $RootPath
    }
} catch {
    Write-Host "[AVISO] Nao foi possivel verificar a letra da unidade OPL: $_" -ForegroundColor Yellow
}

Write-Host 'APA-Jail concluido (PFS boot + exFAT OPL).' -ForegroundColor Green
exit 0
