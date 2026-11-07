param(
    [Parameter(Mandatory = $true)]
    [string]$RootPath
)

$RootPath = [System.IO.Path]::GetFullPath($RootPath.Trim().TrimEnd('.', '\', '/'))
$expected = Join-Path $RootPath 'HDD-OSD\__system\osd100\hosdsys.elf'
$md5_110u = 'ca9ab553e8b51259ccf1ca4ea2d1bc00'

Write-Host ''
Write-Host '=== Verificacao HDD-OSD (Browser 2.0) ===' -ForegroundColor Cyan
Write-Host "Pasta BatchKit: $RootPath"
Write-Host "Arquivo obrigatorio: $expected"
Write-Host ''

if (Test-Path -LiteralPath $expected) {
    Write-Host 'OK: hosdsys.elf encontrado no caminho esperado.' -ForegroundColor Green
    try {
        $hash = (Get-FileHash -LiteralPath $expected -Algorithm MD5).Hash.ToLowerInvariant()
        if ($hash -eq $md5_110u) {
            Write-Host 'OK: MD5 confere com HDD-OSD 1.10U.' -ForegroundColor Green
        } else {
            Write-Host "AVISO: MD5 do ELF = $hash (esperado 1.10U: $md5_110u)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    }
    exit 0
}

Write-Host 'FALTA: hosdsys.elf nao esta instalado.' -ForegroundColor Red
Write-Host ''
$popsBin = Join-Path $RootPath 'POPS-Binaries\POPSTARTER.ELF'
if (Test-Path -LiteralPath $popsBin) {
    Write-Host 'NOTA: POPS-Binaries (POPStarter) ja esta na pasta do BatchKit.' -ForegroundColor Cyan
    Write-Host '      Isso NAO substitui o HDD-OSD Sony. Voce ainda precisa do HDDOSD-1.10U.7z separado.'
    Write-Host ''
}
Write-Host 'O repositorio PFS-BatchKit-Manager NAO inclui o pacote Sony HDD-OSD.'
Write-Host 'Voce precisa obter o arquivo HDDOSD-1.10U.7z por conta propria.'
Write-Host 'MD5 do .7z: 403202A03B910FB6FBD522D6AB5007E7'
Write-Host ''
Write-Host 'Depois de extrair, copie/mescle para:'
Write-Host "  $(Join-Path $RootPath 'HDD-OSD')"
Write-Host 'Ate existir:'
Write-Host "  HDD-OSD\__system\osd100\hosdsys.elf"
Write-Host ''

$searchRoots = @(
    [Environment]::GetFolderPath('UserProfile') + '\Downloads'
    [Environment]::GetFolderPath('Desktop')
    (Split-Path -Parent $RootPath)
)
Write-Host 'Procurando hosdsys.elf em Downloads, Desktop e pasta do repo...'
$found = @()
foreach ($root in $searchRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $found += @(Get-ChildItem -LiteralPath $root -Filter 'hosdsys.elf' -Recurse -ErrorAction SilentlyContinue -Force | Select-Object -ExpandProperty FullName)
}
if ($found.Count -gt 0) {
    Write-Host ''
    Write-Host 'Encontrado em outro lugar (copie para o caminho esperado acima):' -ForegroundColor Yellow
    $found | Select-Object -Unique | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host 'Nenhum hosdsys.elf no PC (Downloads/Desktop/repo) — baixe/extraia o 7z primeiro.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host 'Proximo passo:' -ForegroundColor Cyan
    Write-Host "  1) Obtenha HDDOSD-1.10U.7z (MD5 do .7z acima)"
    Write-Host "  2) Copie para: $RootPath"
    Write-Host '  3) Rode Install HDD-OSD [1] de novo (extracao automatica) ou:'
    Write-Host "     powershell -File BAT\__Install_HDDOSD_FromLocal7z.ps1 -RootPath ."
}

Write-Host ''
Write-Host 'Detalhes: HDD-OSD\README.txt'
exit 1
