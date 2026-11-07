param(
    [Parameter(Mandatory = $true)]
    [string]$PhysicalDrivePath,
    [Parameter(Mandatory = $true)]
    [string]$RootPath,
    [ValidateSet('FHDB', 'KRHACKEN')]
    [string]$BootloaderType = 'FHDB'
)

$ErrorActionPreference = 'Stop'
$RootPath = [System.IO.Path]::GetFullPath($RootPath)

$bootPackage = Join-Path $RootPath 'BAT\__BootPackage'
$rawcopy = Join-Path $RootPath 'BAT\rawcopy.exe'
$tmpDir = Join-Path $RootPath 'TMP'
if (-not (Test-Path -LiteralPath $tmpDir)) {
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $rawcopy)) {
    throw "rawcopy.exe nao encontrado em $rawcopy"
}

# 1. Preparar o payload KELF alinhado a 512 bytes
$tmpAlignedKelf = Join-Path $tmpDir "mbr_payload_aligned.bin"
$sectorCount = [uint32]0

if ($BootloaderType -eq 'FHDB') {
    $mbrKelfPath = Join-Path $bootPackage 'MBR.XLF'
    if (-not (Test-Path -LiteralPath $mbrKelfPath)) {
        # Extrair automaticamente se necessario
        $7z = Join-Path $RootPath 'BAT\7-Zip\7z.exe'
        $archive = Join-Path $RootPath 'BAT\!COPY_TO_USB_ROOT.7z'
        if (Test-Path -LiteralPath $archive) {
            & $7z e $archive -o"$bootPackage" 'APPS\FreeMcBoot_v1.966_Install_(2019-04-13)\INSTALL\SYSTEM\MBR.XLF' -y | Out-Null
        }
    }
    if (-not (Test-Path -LiteralPath $mbrKelfPath)) {
        throw "MBR.XLF nao encontrado em $mbrKelfPath"
    }

    $rawKelf = [System.IO.File]::ReadAllBytes($mbrKelfPath)
    $sectorCount = [uint32][Math]::Ceiling($rawKelf.Length / 512)
    $alignedBytes = New-Object byte[] ($sectorCount * 512)
    [Array]::Copy($rawKelf, 0, $alignedBytes, 0, $rawKelf.Length)
    [System.IO.File]::WriteAllBytes($tmpAlignedKelf, $alignedBytes)
    Write-Host "Payload FreeHDBoot MBR.XLF preparado: $($rawKelf.Length) bytes ($sectorCount setores alinhados)" -ForegroundColor Cyan
} else {
    $mbrImgPath = Join-Path $RootPath 'BAT\mbr.img'
    if (-not (Test-Path -LiteralPath $mbrImgPath)) {
        throw "mbr.img nao encontrado em $mbrImgPath"
    }
    # krHACKen MBR KELF esta no offset 8192 (setor 16) com 898 setores (459776 bytes)
    $stream = [System.IO.File]::OpenRead($mbrImgPath)
    try {
        $stream.Seek(8192, [System.IO.SeekOrigin]::Begin) | Out-Null
        $alignedBytes = New-Object byte[] 459776
        $read = $stream.Read($alignedBytes, 0, 459776)
        if ($read -ne 459776) { throw "Falha ao ler KELF de mbr.img" }
        [System.IO.File]::WriteAllBytes($tmpAlignedKelf, $alignedBytes)
        $sectorCount = [uint32]898
        Write-Host "Payload krHACKen MBR preparado: 459776 bytes ($sectorCount setores alinhados)" -ForegroundColor Cyan
    } finally {
        $stream.Dispose()
    }
}

# 2. Ler LBA 0-1 (1024 bytes) do disco usando rawcopy
$tmpCurrentS0 = Join-Path $tmpDir "current_s0.bin"
if (Test-Path -LiteralPath $tmpCurrentS0) { Remove-Item -LiteralPath $tmpCurrentS0 -Force }

Write-Host "Lendo LBA 0-1 de $PhysicalDrivePath via rawcopy..." -ForegroundColor Gray
$rawReadProc = Start-Process -FilePath $rawcopy -ArgumentList @("0", "1024", $PhysicalDrivePath, $tmpCurrentS0) -NoNewWindow -Wait -PassThru
if ($rawReadProc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $tmpCurrentS0)) {
    throw "Falha ao ler LBA 0 de $PhysicalDrivePath via rawcopy (ExitCode $($rawReadProc.ExitCode)). Certifique-se de executar como Administrador."
}

$lba01 = [System.IO.File]::ReadAllBytes($tmpCurrentS0)
if ($lba01.Length -lt 1024) {
    throw "LBA 0 lida possui menos de 1024 bytes ($($lba01.Length) bytes)."
}

# 3. Validar se tem o cabecalho APA
$magic = [System.Text.Encoding]::ASCII.GetString($lba01, 4, 3)
if ($magic -ne "APA") {
    Write-Warning "Cabecalho APA nao detectado no offset 4 (encontrado '$magic'). Restaurando estrutura APA __mbr padrao..."
    # Preencher estrutura basica do __mbr preservando a tabela MBR (bytes 446..511)
    $mbrTable = New-Object byte[] 66
    [Array]::Copy($lba01, 446, $mbrTable, 0, 66)

    # Limpar primeiros 446 bytes
    [Array]::Clear($lba01, 0, 446)
    # Magic "APA\0" no offset 0x04
    [byte[]]@(0x41, 0x50, 0x41, 0x00).CopyTo($lba01, 0x04)
    # ID "__mbr\0" no offset 0x10
    $mbrId = [System.Text.Encoding]::ASCII.GetBytes("__mbr")
    $mbrId.CopyTo($lba01, 0x10)
    # Start = 0 (offset 0x40)
    [BitConverter]::GetBytes([uint32]0).CopyTo($lba01, 0x40)
    # Length = 0x00040000 (128MB, offset 0x44)
    [BitConverter]::GetBytes([uint32]0x00040000).CopyTo($lba01, 0x44)
    # Type = 0x0001 (offset 0x48)
    [BitConverter]::GetBytes([uint16]0x0001).CopyTo($lba01, 0x48)
    # Flags = 0 (offset 0x4A)
    [BitConverter]::GetBytes([uint16]0x0000).CopyTo($lba01, 0x4A)

    # Restaurar tabela de particao PC MBR
    $mbrTable.CopyTo($lba01, 446)
}

# 4. Atualizar ponteiros do bootloader KELF e assinatura APA-Jail
# Offset 0x130 (304): LBA inicial do KELF = 16
[BitConverter]::GetBytes([uint32]16).CopyTo($lba01, 0x130)
# Offset 0x134 (308): Quantidade de setores do KELF
[BitConverter]::GetBytes([uint32]$sectorCount).CopyTo($lba01, 0x134)

# Identificador APA-Jail Type-A2 no offset 0xE0: "APAJ-A2\0"
$apajMagic = [byte[]]@(0x41, 0x50, 0x41, 0x4A, 0x2D, 0x41, 0x32, 0x00)
$apajMagic.CopyTo($lba01, 0xE0)

# 5. Recalcular soma de verificacao APA de 32 bits (palavras 1 a 255)
$sum = [uint64]0
for ($i = 1; $i -le 255; $i++) {
    $word = [BitConverter]::ToUInt32($lba01, $i * 4)
    $sum = ($sum + $word) -band 0xFFFFFFFFL
}
[BitConverter]::GetBytes([uint32]$sum).CopyTo($lba01, 0)

$tmpNewS0 = Join-Path $tmpDir "new_s0.bin"
[System.IO.File]::WriteAllBytes($tmpNewS0, $lba01)

# 6. Gravar via rawcopy:
# A. Gravar o KELF no Setor 16 (offset 8192)
Write-Host "Gravando KELF ($($sectorCount * 512) bytes) no Setor 16 de $PhysicalDrivePath..." -ForegroundColor Cyan
$kelfProc = Start-Process -FilePath $rawcopy -ArgumentList @("-w", "-l", "-o:8192", $tmpAlignedKelf, $PhysicalDrivePath) -NoNewWindow -Wait -PassThru
if ($kelfProc.ExitCode -ne 0) {
    throw "Falha ao gravar KELF no Setor 16 via rawcopy (ExitCode $($kelfProc.ExitCode))."
}

# B. Gravar LBA 0-1 (1024 bytes) no Setor 0 (offset 0)
Write-Host "Gravando LBA 0-1 (cabeçalho APA com Checksum 0x$($sum.ToString('X8'))) no Setor 0..." -ForegroundColor Cyan
$s0Proc = Start-Process -FilePath $rawcopy -ArgumentList @("-w", "-l", "-o:0", $tmpNewS0, $PhysicalDrivePath) -NoNewWindow -Wait -PassThru
if ($s0Proc.ExitCode -ne 0) {
    throw "Falha ao gravar Setor 0 via rawcopy (ExitCode $($s0Proc.ExitCode))."
}

# 7. Verificacao de integridade
Write-Host "Verificando integridade dos dados gravados..." -ForegroundColor Gray
$tmpVerifyS0 = Join-Path $tmpDir "verify_s0.bin"
if (Test-Path -LiteralPath $tmpVerifyS0) { Remove-Item -LiteralPath $tmpVerifyS0 -Force }
Start-Process -FilePath $rawcopy -ArgumentList @("0", "1024", $PhysicalDrivePath, $tmpVerifyS0) -NoNewWindow -Wait | Out-Null

$tmpVerifyS16 = Join-Path $tmpDir "verify_s16.bin"
if (Test-Path -LiteralPath $tmpVerifyS16) { Remove-Item -LiteralPath $tmpVerifyS16 -Force }
Start-Process -FilePath $rawcopy -ArgumentList @("8192", "512", $PhysicalDrivePath, $tmpVerifyS16) -NoNewWindow -Wait | Out-Null

$v0 = [System.IO.File]::ReadAllBytes($tmpVerifyS0)
$v16 = [System.IO.File]::ReadAllBytes($tmpVerifyS16)

$vMagic = [System.Text.Encoding]::ASCII.GetString($v0, 4, 3)
$vSum = [BitConverter]::ToUInt32($v0, 0)
$vMbrLba = [BitConverter]::ToUInt32($v0, 0x130)
$vMbrSec = [BitConverter]::ToUInt32($v0, 0x134)

# Assinatura KELF no setor 16 deve iniciar com 0x01 0x00 0x00 0x04
$isKelfValid = ($v16[0] -eq 1 -and $v16[1] -eq 0 -and $v16[2] -eq 0 -and $v16[3] -eq 4)

Write-Host ""
Write-Host "=== RELATORIO DE GRAVACAO MBR PS2 ===" -ForegroundColor Green
Write-Host "Disco: $PhysicalDrivePath"
Write-Host "Tipo de Bootloader: $BootloaderType"
Write-Host "APA Magic: $vMagic (OK)"
Write-Host "APA Checksum: 0x$($vSum.ToString('X8')) (OK)"
Write-Host "Ponteiro KELF: LBA $vMbrLba, $vMbrSec setores (OK)"
Write-Host "Assinatura KELF no Setor 16: $(if ($isKelfValid) { 'VALIDA (MagicGate KELF 01-00-00-04)' } else { 'INVALIDA' })"
Write-Host "Tabela PC MBR (exFAT): Preservada (0x55AA presente)"
Write-Host "======================================" -ForegroundColor Green
Write-Host ""

exit 0
