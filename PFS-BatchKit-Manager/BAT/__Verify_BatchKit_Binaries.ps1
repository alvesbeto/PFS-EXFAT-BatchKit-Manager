param(
    [Parameter(Mandatory = $true)]
    [string]$RootPath
)

$RootPath = [System.IO.Path]::GetFullPath($RootPath.Trim().TrimEnd('.', '\', '/'))

function Test-Binary {
    param(
        [string]$Label,
        [string]$RelativePath,
        [string]$ExpectedMd5 = $null,
        [ValidateSet('required', 'optional', 'user')]
        [string]$Kind = 'required'
    )
    $full = Join-Path $RootPath $RelativePath
    $exists = Test-Path -LiteralPath $full
    $hash = $null
    $md5Ok = $null
    if ($exists) {
        try {
            $hash = (Get-FileHash -LiteralPath $full -Algorithm MD5).Hash.ToLowerInvariant()
            if ($ExpectedMd5) { $md5Ok = ($hash -eq $ExpectedMd5.ToLowerInvariant()) }
        } catch {
            $hash = $_.Exception.Message
        }
    }
    [PSCustomObject]@{
        Label        = $Label
        RelativePath = $RelativePath
        Kind         = $Kind
        Exists       = $exists
        Md5          = $hash
        ExpectedMd5  = $ExpectedMd5
        Md5Ok        = $md5Ok
    }
}

Write-Host ''
Write-Host '=== Auditoria de binarios (PFS BatchKit) ===' -ForegroundColor Cyan
Write-Host "Pasta: $RootPath"
Write-Host ''

$rows = @(
    Test-Binary -Label 'POPStarter (repo)' -RelativePath 'POPS-Binaries\POPSTARTER.ELF' -Kind 'optional'
    Test-Binary -Label 'POPS.ELF Sony (PS1)' -RelativePath 'POPS-Binaries\POPS.ELF' -ExpectedMd5 '355a892a8ce4e4a105469d4ef6f39a42' -Kind 'user'
    Test-Binary -Label 'IOPRP252.IMG (PS1)' -RelativePath 'POPS-Binaries\IOPRP252.IMG' -ExpectedMd5 '1db9c6020a2cd445a7bb176a1a3dd418' -Kind 'user'
    Test-Binary -Label 'TROJAN_7.BIN' -RelativePath 'POPS-Binaries\TROJAN_7.BIN' -Kind 'optional'
    Test-Binary -Label 'hosdsys.elf HDD-OSD 1.10U' -RelativePath 'HDD-OSD\__system\osd100\hosdsys.elf' -ExpectedMd5 'ca9ab553e8b51259ccf1ca4ea2d1bc00' -Kind 'user'
    Test-Binary -Label 'HDDOSD-1.10U.7z (antes de extrair)' -RelativePath 'HDDOSD-1.10U.7z' -ExpectedMd5 '403202A03B910FB6FBD522D6AB5007E7' -Kind 'user'
    Test-Binary -Label 'HDDOSD-1.10U.7z (BAT)' -RelativePath 'BAT\HDDOSD-1.10U.7z' -ExpectedMd5 '403202A03B910FB6FBD522D6AB5007E7' -Kind 'user'
    Test-Binary -Label 'hosdmenu.elf (APA-Jail menu)' -RelativePath 'BAT\OSDMenu\hosdmenu.elf' -Kind 'optional'
    Test-Binary -Label 'FreeHDBoot USB pack' -RelativePath 'BAT\!COPY_TO_USB_ROOT.7z' -Kind 'optional'
    Test-Binary -Label 'OPL MOD archive' -RelativePath 'BAT\Open.PS2.Loader.v1-MOD-2024-05-16_PSX2.7z' -Kind 'optional'
)

foreach ($r in $rows) {
    if (-not $r.Exists) {
        $tag = if ($r.Kind -eq 'user') { 'FALTA (voce precisa obter)' } else { 'ausente' }
        Write-Host "[$tag] $($r.Label)" -ForegroundColor $(if ($r.Kind -eq 'user') { 'Red' } else { 'Yellow' })
        Write-Host "       $($r.RelativePath)"
        continue
    }
    if ($r.ExpectedMd5 -and $r.Md5Ok -eq $false) {
        Write-Host "[MD5 DIFERENTE] $($r.Label)" -ForegroundColor Yellow
        Write-Host "       $($r.RelativePath)"
        Write-Host "       MD5: $($r.Md5)  (esperado: $($r.ExpectedMd5))"
        continue
    }
    if ($r.ExpectedMd5 -and $r.Md5Ok) {
        Write-Host "[OK] $($r.Label)" -ForegroundColor Green
    } else {
        Write-Host "[OK presente] $($r.Label)" -ForegroundColor Green
    }
    Write-Host "       $($r.RelativePath)"
    if ($r.Md5) { Write-Host "       MD5: $($r.Md5)" }
}

Write-Host ''
Write-Host '--- Conteudo atual HDD-OSD (sem Sony) ---' -ForegroundColor Cyan
$hdd = Join-Path $RootPath 'HDD-OSD'
if (Test-Path $hdd) {
    Get-ChildItem -LiteralPath $hdd -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName.Substring($hdd.Length).TrimStart('\') } |
        ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host '  (pasta HDD-OSD inexistente)'
}

$sys = Join-Path $RootPath 'HDD-OSD\__system'
if ((Test-Path $sys) -and -not (Get-ChildItem -LiteralPath $sys -Recurse -File -ErrorAction SilentlyContinue)) {
    Write-Host ''
    Write-Host 'AVISO: HDD-OSD\__system existe mas esta VAZIA — extrair HDDOSD-1.10U.7z aqui.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'NOTA: !COPY_TO_USB_ROOT.7z = FreeMcBoot/FHDB (USB), NAO contem hosdsys.elf.' -ForegroundColor DarkGray
Write-Host ''

$missingUser = @($rows | Where-Object { $_.Kind -eq 'user' -and -not $_.Exists })
if ($missingUser.Count -gt 0) { exit 1 }
exit 0
