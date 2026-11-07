param(
    [string]$PhysicalDrivePath = '',
    [string]$RootPath = "$PSScriptRoot\.."
)

$ErrorActionPreference = 'Continue'
$RootPath = [System.IO.Path]::GetFullPath($RootPath)

function Get-FirstFreeDriveLetter {
    $usedLetters = @()
    Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.DriveLetter } | ForEach-Object {
        $usedLetters += [string]$_.DriveLetter
    }
    # Checar tambem via Get-PSDrive
    Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name.Length -eq 1) { $usedLetters += $_.Name }
    }
    $usedLetters = $usedLetters | Select-Object -Unique

    $candidates = [char[]]([int][char]'D'..[int][char]'Z')
    foreach ($cand in $candidates) {
        $cStr = [string]$cand
        if ($usedLetters -notcontains $cStr) {
            return $cStr
        }
    }
    return $null
}

function Assign-LetterToPartition([int]$DiskNum, [int]$PartNum, [string]$Letter) {
    Write-Host "Atribuindo letra $Letter`: ao Disco $DiskNum, Particao $PartNum..." -ForegroundColor Cyan
    
    # Metodo 1: PowerShell Add-PartitionAccessPath
    try {
        Add-PartitionAccessPath -DiskNumber $DiskNum -PartitionNumber $PartNum -AccessPath "$($Letter):" -ErrorAction Stop
        Start-Sleep -Milliseconds 500
        $check = Get-Partition -DiskNumber $DiskNum -PartitionNumber $PartNum -ErrorAction SilentlyContinue
        if ($check -and $check.DriveLetter -eq [char]$Letter) {
            return $true
        }
    } catch {}

    # Metodo 2: PowerShell Set-Partition
    try {
        Set-Partition -DiskNumber $DiskNum -PartitionNumber $PartNum -NewDriveLetter $Letter -ErrorAction Stop
        Start-Sleep -Milliseconds 500
        $check = Get-Partition -DiskNumber $DiskNum -PartitionNumber $PartNum -ErrorAction SilentlyContinue
        if ($check -and $check.DriveLetter -eq [char]$Letter) {
            return $true
        }
    } catch {}

    # Metodo 3: Diskpart script
    try {
        $dpScript = @"
select disk $DiskNum
select partition $PartNum
assign letter=$Letter
"@
        $dpFile = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "dp_assign_$([Guid]::NewGuid().ToString('N')).txt")
        [System.IO.File]::WriteAllText($dpFile, $dpScript)
        & diskpart.exe /s $dpFile | Out-Null
        Remove-Item -LiteralPath $dpFile -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 800
        $check = Get-Partition -DiskNumber $DiskNum -PartitionNumber $PartNum -ErrorAction SilentlyContinue
        if ($check -and $check.DriveLetter -eq [char]$Letter) {
            return $true
        }
    } catch {}

    return $false
}

# 1. Verificar se ja existe volume 'OPL' com letra montada
$existingVol = Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.FileSystemLabel -eq 'OPL' -and $_.DriveLetter } | Select-Object -First 1
if ($existingVol) {
    $assignedLetter = "$($existingVol.DriveLetter)"
    Write-Host "Volume OPL ja esta montado na unidade $assignedLetter`:" -ForegroundColor Green
    $tmpFile = Join-Path $RootPath 'TMP\opl_drive_letter.txt'
    [System.IO.File]::WriteAllText($tmpFile, $assignedLetter)
    exit 0
}

# 2. Habilitar montagem automatica no Windows se estiver desativada
try {
    & mountvol.exe /e | Out-Null
} catch {}

# 3. Tentar descobrir o numero do disco físico
$targetDiskNum = -1
if ($PhysicalDrivePath -match 'PhysicalDrive(\d+)') {
    $targetDiskNum = [int]$Matches[1]
} elseif (Test-Path -LiteralPath (Join-Path $RootPath 'TMP\hdd-disknum.txt')) {
    $rawNum = (Get-Content -Path (Join-Path $RootPath 'TMP\hdd-disknum.txt') -Raw).Trim()
    if ($rawNum -match '^\d+$') {
        $targetDiskNum = [int]$rawNum
    }
}

# 4. Procurar particao OPL sem letra atribuida
$targetPart = $null

# A. Procurar via Get-Partition / Get-Volume
$allParts = Get-Partition -ErrorAction SilentlyContinue
foreach ($p in $allParts) {
    if ($targetDiskNum -ge 0 -and $p.DiskNumber -ne $targetDiskNum) {
        continue
    }
    $v = Get-Volume -Partition $p -ErrorAction SilentlyContinue
    if ($v -and $v.FileSystemLabel -eq 'OPL') {
        $targetPart = $p
        break
    }
}

# B. Se nao encontrou pelo volume, mas temos o disco alvo, procurar a particao de dados (exFAT / Basic Data / maior particao)
if (-not $targetPart -and $targetDiskNum -ge 0) {
    $diskParts = Get-Partition -DiskNumber $targetDiskNum -ErrorAction SilentlyContinue | Where-Object { -not $_.DriveLetter -and $_.Type -ne 'Reserved' }
    if ($diskParts) {
        # Selecionar a maior particao sem letra (que corresponde a area de dados exFAT)
        $targetPart = $diskParts | Sort-Object -Property Size -Descending | Select-Object -First 1
    }
}

# 5. Atribuir letra se a particao foi localizada
if ($targetPart) {
    $freeLetter = Get-FirstFreeDriveLetter
    if ($freeLetter) {
        $success = Assign-LetterToPartition -DiskNum $targetPart.DiskNumber -PartNum $targetPart.PartitionNumber -Letter $freeLetter
        if ($success) {
            Write-Host "Sucesso! Volume OPL atribuido a unidade $freeLetter`:" -ForegroundColor Green
            $tmpFile = Join-Path $RootPath 'TMP\opl_drive_letter.txt'
            [System.IO.File]::WriteAllText($tmpFile, $freeLetter)
            exit 0
        } else {
            Write-Host "[AVISO] Nao foi possivel atribuir automaticamente a letra de unidade ao volume OPL." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[AVISO] Nenhuma letra de unidade livre encontrada no Windows (D-Z)." -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] Particao OPL nao detectada para atribuicao de letra no momento." -ForegroundColor Gray
}

exit 0
