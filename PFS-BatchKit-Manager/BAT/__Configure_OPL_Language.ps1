param(
    [string]$Language = '',
    [switch]$Interactive,
    [switch]$SkipInject,
    [string]$RootPath = "$PSScriptRoot\.."
)

$ErrorActionPreference = 'Stop'
$RootPath = [System.IO.Path]::GetFullPath($RootPath)

$bootPackage = Join-Path $RootPath 'BAT\__BootPackage'
$langsDir = Join-Path $bootPackage 'LANGS'
$templateConf = Join-Path $RootPath 'HDD-OSD\__common\OPL\conf_opl.cfg'
$stagedConf = Join-Path $bootPackage 'conf_opl.cfg'

# Se a pasta de idiomas ainda nao existe, executar o fetch primeiro
if (-not (Test-Path -LiteralPath $langsDir) -or (Get-ChildItem -Path $langsDir -Directory).Count -eq 0) {
    Write-Host "Baixando pacote de idiomas da release mais recente do OPL..." -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RootPath 'BAT\__Fetch_Latest_OPL.ps1') -RootPath $RootPath | Out-Null
}

# Mapear idiomas disponiveis
$availableLangs = @('English')
if (Test-Path -LiteralPath $langsDir) {
    Get-ChildItem -Path $langsDir -Directory | ForEach-Object {
        $availableLangs += $_.Name
    }
}
$availableLangs = $availableLangs | Select-Object -Unique | Sort-Object

# -------------------------------------------------------------------------
# Deteccao Dinamica do Idioma do Sistema Operacional (Host)
# -------------------------------------------------------------------------
$hostCulture = [System.Globalization.CultureInfo]::CurrentUICulture
$hostIso = $hostCulture.TwoLetterISOLanguageName.ToLowerInvariant()
$hostName = $hostCulture.Name.ToLowerInvariant()

# Verificar tambem se o usuario ja escolheu algum idioma nas configuracoes do PFS-BatchKit
$settingsIni = Join-Path $RootPath 'settings.ini'
$settingsLang = ''
if (Test-Path -LiteralPath $settingsIni) {
    Get-Content -Path $settingsIni -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_ -match '^(?:TitlesLang|DBLang)=(.*)$') {
            $val = $Matches[1].Trim().ToLowerInvariant()
            if ($val -in @('portuguese', 'pt', 'pt-br')) { $settingsLang = 'Portuguese_BR' }
            elseif ($val -in @('spanish', 'es')) { $settingsLang = 'Spanish' }
            elseif ($val -in @('french', 'fr')) { $settingsLang = 'French' }
            elseif ($val -in @('german', 'de')) { $settingsLang = 'German' }
            elseif ($val -in @('italian', 'it')) { $settingsLang = 'Italian' }
            elseif ($val -in @('english', 'en')) { $settingsLang = 'English' }
        }
    }
}

# Mapear idioma recomendado com base no Host OS
$recLang = 'English'
$recDesc = 'English (Padrao Oficial)'

if ($hostIso -eq 'pt' -or $settingsLang -eq 'Portuguese_BR') {
    if ($hostName -eq 'pt-pt') {
        $recLang = 'Portuguese'
        $recDesc = 'Portugues de Portugal (Portuguese)'
    } else {
        $recLang = 'Portuguese_BR'
        $recDesc = 'Portugues do Brasil (Portuguese_BR)'
    }
} elseif ($hostIso -eq 'es' -or $settingsLang -eq 'Spanish') {
    $recLang = 'Spanish'
    $recDesc = 'Espanol (Spanish)'
} elseif ($hostIso -eq 'fr' -or $settingsLang -eq 'French') {
    $recLang = 'French'
    $recDesc = 'Francais (French)'
} elseif ($hostIso -eq 'de' -or $settingsLang -eq 'German') {
    $recLang = 'German'
    $recDesc = 'Deutsch (German)'
} elseif ($hostIso -eq 'it' -or $settingsLang -eq 'Italian') {
    $recLang = 'Italian'
    $recDesc = 'Italiano (Italian)'
} elseif ($hostIso -eq 'ja') {
    $recLang = 'Japanese'
    $recDesc = 'Japanese (Japones)'
} elseif ($hostIso -eq 'ru') {
    $recLang = 'Russian'
    $recDesc = 'Russian (Russo)'
}

# Lista rapida de opcoes comuns (garantindo que a recomendada fique na opcao 1)
$quickLangs = [System.Collections.Generic.List[PSObject]]::new()
$quickLangs.Add([PSCustomObject]@{ Id = $recLang; Label = "$recDesc  [Recomendado - Idioma do Sistema]" })

$popularDefaults = @(
    @{ Id = 'English'; Label = 'English (Padrao Oficial do OPL)' },
    @{ Id = 'Portuguese_BR'; Label = 'Portugues do Brasil (Portuguese_BR)' },
    @{ Id = 'Spanish'; Label = 'Espanol (Spanish)' },
    @{ Id = 'French'; Label = 'Francais (French)' },
    @{ Id = 'German'; Label = 'Deutsch (German)' },
    @{ Id = 'Italian'; Label = 'Italiano (Italian)' },
    @{ Id = 'Japanese'; Label = 'Japanese (Japones)' }
)

foreach ($pop in $popularDefaults) {
    if ($pop.Id -ne $recLang -and $quickLangs.Count -lt 7) {
        $quickLangs.Add([PSCustomObject]@{ Id = $pop.Id; Label = $pop.Label })
    }
}

$selectedLang = $Language

if ([string]::IsNullOrWhiteSpace($selectedLang) -or $Interactive) {
    Clear-Host
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "  Configuracao de Idioma do Open PS2 Loader (OPL)" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ("  Idioma detectado no Windows (Host): {0} [{1}]" -f $hostCulture.EnglishName, $hostCulture.Name) -ForegroundColor Gray
    Write-Host ""
    
    for ($i = 0; $i -lt $quickLangs.Count; $i++) {
        $num = $i + 1
        $item = $quickLangs[$i]
        if ($num -eq 1) {
            Write-Host ("  [{0}] {1}" -f $num, $item.Label) -ForegroundColor Green
        } else {
            Write-Host ("  [{0}] {1}" -f $num, $item.Label)
        }
    }
    Write-Host ("  [8] Escolher outro idioma (Listar todos os {0} idiomas)" -f $availableLangs.Count)
    Write-Host ""
    Write-Host "--------------------------------------------------------" -ForegroundColor Gray
    
    $choice = Read-Host ("Selecione o idioma desejado (1-8, padrao: 1 [{0}])" -f $recLang)
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }
    
    $parsedChoice = 0
    if ([int]::TryParse($choice.Trim(), [ref]$parsedChoice)) {
        if ($parsedChoice -ge 1 -and $parsedChoice -le $quickLangs.Count) {
            $selectedLang = $quickLangs[$parsedChoice - 1].Id
        } elseif ($parsedChoice -eq 8) {
            Write-Host ""
            Write-Host "Todos os Idiomas Disponiveis no Pacote OPL:" -ForegroundColor Cyan
            for ($i = 0; $i -lt $availableLangs.Count; $i++) {
                Write-Host ("  [{0,2}] {1}" -f ($i + 1), $availableLangs[$i])
            }
            Write-Host ""
            $numChoice = Read-Host ("Digite o numero do idioma desejado (1-{0}, Enter para {1})" -f $availableLangs.Count, $recLang)
            $parsedNum = 0
            if ([int]::TryParse($numChoice.Trim(), [ref]$parsedNum)) {
                $idx = $parsedNum - 1
                if ($idx -ge 0 -and $idx -lt $availableLangs.Count) {
                    $selectedLang = $availableLangs[$idx]
                } else {
                    $selectedLang = $recLang
                }
            } else {
                $selectedLang = $recLang
            }
        } else {
            $selectedLang = $recLang
        }
    } else {
        if ($availableLangs -contains $choice.Trim()) {
            $selectedLang = $choice.Trim()
        } else {
            $selectedLang = $recLang
        }
    }
}

Write-Host ""
Write-Host "Idioma selecionado para o OPL: $selectedLang" -ForegroundColor Green

# 1. Atualizar conf_opl.cfg nos templates com Idioma, Widescreen 16:9, Video Mode 720p HD e IGR apontando para mass:/OPL/OPNPS2LD.ELF
function Update-OplConfigLang([string]$filePath, [string]$lang) {
    if (-not (Test-Path -LiteralPath $filePath)) { return }
    $content = [System.IO.File]::ReadAllText($filePath, [System.Text.Encoding]::ASCII)

    # Idioma
    if ($content -match '(?m)^language_text=.*$') {
        $content = $content -replace '(?m)^language_text=.*$', "language_text=$lang"
    } else {
        $content += "`r`nlanguage_text=$lang`r`n"
    }

    # Widescreen 16:9 HD
    if ($content -match '(?m)^wide_screen=.*$') {
        $content = $content -replace '(?m)^wide_screen=.*$', 'wide_screen=1'
    } else {
        $content += "`r`nwide_screen=1`r`n"
    }

    # Video Mode Auto (vmode=0)
    if ($content -match '(?m)^vmode=.*$') {
        $content = $content -replace '(?m)^vmode=.*$', 'vmode=0'
    } else {
        $content += "`r`nvmode=0`r`n"
    }

    # In-Game Reset apontando diretamente para o OPL na particao exFAT (mass:/OPL/OPNPS2LD.ELF)
    if ($content -match '(?m)^exit_path=.*$') {
        $content = $content -replace '(?m)^exit_path=.*$', 'exit_path=mass:/OPL/OPNPS2LD.ELF'
    } else {
        $content += "`r`nexit_path=mass:/OPL/OPNPS2LD.ELF`r`n"
    }

    # Garantir BDM exFAT ativo
    if ($content -match '(?m)^enable_bdm_hdd=.*$') {
        $content = $content -replace '(?m)^enable_bdm_hdd=.*$', 'enable_bdm_hdd=1'
    } else {
        $content += "`r`nenable_bdm_hdd=1`r`n"
    }

    if ($content -match '(?m)^bdm_cache=.*$') {
        $content = $content -replace '(?m)^bdm_cache=.*$', 'bdm_cache=1'
    } else {
        $content += "`r`nbdm_cache=1`r`n"
    }

    [System.IO.File]::WriteAllText($filePath, $content, [System.Text.Encoding]::ASCII)
}

Update-OplConfigLang $templateConf $selectedLang
Update-OplConfigLang $stagedConf $selectedLang

# 2. Localizar arquivos do idioma selecionado
$langSrcDir = Join-Path $langsDir $selectedLang
$lngFile = $null
$fontFile = $null

if ($selectedLang -ne 'English' -and (Test-Path -LiteralPath $langSrcDir)) {
    $lngFile = Get-ChildItem -Path $langSrcDir -Filter "*.lng" | Select-Object -First 1
    $fontFile = Get-ChildItem -Path $langSrcDir -Filter "font_*" | Select-Object -First 1
}

# Limpar staging anterior em __BootPackage e LNG_ALL para conter APENAS o idioma selecionado
$lngAllDir = Join-Path $bootPackage 'LNG_ALL'
if (Test-Path -LiteralPath $lngAllDir) {
    Remove-Item -LiteralPath $lngAllDir -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $lngAllDir -Force | Out-Null

Get-ChildItem -Path $bootPackage -Filter "lang_*.lng" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $bootPackage -Filter "font_*" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $langsDir -Recurse -Include '*.zip','*.7z' -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

if ($lngFile) {
    Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $bootPackage $lngFile.Name) -Force
    Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $lngAllDir $lngFile.Name) -Force
}
if ($fontFile) {
    Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $bootPackage $fontFile.Name) -Force
    Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $lngAllDir $fontFile.Name) -Force
}

# Salvar idioma selecionado em arquivo temporario para o BatchKit
$tmpLangFile = Join-Path $RootPath 'TMP\opl_selected_lang.txt'
[System.IO.File]::WriteAllText($tmpLangFile, $selectedLang)

# 4. Sincronizar na Particao exFAT (volume OPL)
# As configuracoes do OPL sao salvas e lidas em E:\conf_opl.cfg e o idioma na pasta E:\OPL\
$oplVolume = Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.FileSystemLabel -eq 'OPL' -and $_.DriveLetter } | Select-Object -First 1
if (-not $oplVolume) {
    try {
        $ensureScript = Join-Path $RootPath 'BAT\__Ensure_Opl_Drive_Letter.ps1'
        if (Test-Path -LiteralPath $ensureScript) {
            & $ensureScript -RootPath $RootPath | Out-Null
            $oplVolume = Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.FileSystemLabel -eq 'OPL' -and $_.DriveLetter } | Select-Object -First 1
        }
    } catch {}
}

if ($oplVolume) {
    $letter = "$($oplVolume.DriveLetter):"
    Write-Host "Configurando pasta OPL e instalando idioma $selectedLang na particao exFAT ($letter)..." -ForegroundColor Cyan
    
    $exfatOplDir = Join-Path $letter 'OPL'
    $exfatOplLngDir = Join-Path $exfatOplDir 'LNG'
    $exfatLngDir = Join-Path $letter 'LNG'
    $exfatCfgDir = Join-Path $letter 'CFG'
    $exfatAppsDir = Join-Path $letter 'APPS'

    if (-not (Test-Path -LiteralPath $exfatOplDir)) { New-Item -ItemType Directory -Path $exfatOplDir -Force | Out-Null }
    if (-not (Test-Path -LiteralPath $exfatOplLngDir)) { New-Item -ItemType Directory -Path $exfatOplLngDir -Force | Out-Null }
    if (-not (Test-Path -LiteralPath $exfatLngDir)) { New-Item -ItemType Directory -Path $exfatLngDir -Force | Out-Null }
    if (-not (Test-Path -LiteralPath $exfatCfgDir)) { New-Item -ItemType Directory -Path $exfatCfgDir -Force | Out-Null }
    if (-not (Test-Path -LiteralPath $exfatAppsDir)) { New-Item -ItemType Directory -Path $exfatAppsDir -Force | Out-Null }
    
    # 4.1. Copiar executavel OPNPS2LD.ELF para dentro de OPL\ e APPS\
    $srcElf = Join-Path $bootPackage 'OPNPS2LD.ELF'
    if (Test-Path -LiteralPath $srcElf) {
        Copy-Item -LiteralPath $srcElf -Destination (Join-Path $exfatOplDir 'OPNPS2LD.ELF') -Force
        Copy-Item -LiteralPath $srcElf -Destination (Join-Path $exfatAppsDir 'OPNPS2LD.ELF') -Force
    }

    # 4.2. LIMPEZA DE OUTROS IDIOMAS E ARQUIVOS RESIDUAIS
    Get-ChildItem -Path $exfatLngDir -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $exfatOplLngDir -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $exfatOplDir -Filter "lang_*.lng" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $exfatOplDir -Filter "font_*" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $letter -Filter "lang_*.lng" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $letter -Filter "font_*" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

    # 4.3. INSTALAR O IDIOMA ESCOLHIDO NA PASTA OPL E LNG
    if ($lngFile) {
        Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $exfatOplDir $lngFile.Name) -Force
        Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $exfatOplLngDir $lngFile.Name) -Force
        Copy-Item -LiteralPath $lngFile.FullName -Destination (Join-Path $exfatLngDir $lngFile.Name) -Force
    }
    if ($fontFile) {
        Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $exfatOplDir $fontFile.Name) -Force
        Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $exfatOplLngDir $fontFile.Name) -Force
        Copy-Item -LiteralPath $fontFile.FullName -Destination (Join-Path $exfatLngDir $fontFile.Name) -Force
    }

    # 4.4. Atualizar arquivos conf_opl.cfg (na raiz E:\conf_opl.cfg e dentro de OPL\)
    $rootConf = Join-Path $letter 'conf_opl.cfg'
    $oplConf = Join-Path $exfatOplDir 'conf_opl.cfg'

    if (-not (Test-Path -LiteralPath $rootConf)) {
        if (Test-Path -LiteralPath $templateConf) {
            Copy-Item -LiteralPath $templateConf -Destination $rootConf -Force
        }
    }
    Update-OplConfigLang $rootConf $selectedLang

    # Garantir chaves principais no conf_opl.cfg da raiz
    $confText = [System.IO.File]::ReadAllText($rootConf, [System.Text.Encoding]::ASCII)
    if ($confText -notmatch '(?m)^enable_bdm_hdd=1') {
        $confText = $confText -replace '(?m)^enable_bdm_hdd=.*$', 'enable_bdm_hdd=1'
    }
    if ($confText -notmatch '(?m)^theme=') {
        $confText += "`r`ntheme=Pixel-Prime-Top (NoLogo)`r`n"
    } elseif ($confText -match '(?m)^theme=<OPL>') {
        $confText = $confText -replace '(?m)^theme=<OPL>', 'theme=Pixel-Prime-Top (NoLogo)'
    }
    [System.IO.File]::WriteAllText($rootConf, $confText, [System.Text.Encoding]::ASCII)

    # Copiar o conf_opl.cfg configurado para dentro da pasta OPL\
    Copy-Item -LiteralPath $rootConf -Destination $oplConf -Force

    # Copiar conf_hdd.cfg para OPL\ e CFG\
    $confHddSrc = Join-Path $RootPath 'HDD-OSD\__common\OPL\conf_hdd_apajail_exfat.cfg'
    if (Test-Path -LiteralPath $confHddSrc) {
        Copy-Item -LiteralPath $confHddSrc -Destination (Join-Path $exfatOplDir 'conf_hdd.cfg') -Force
        Copy-Item -LiteralPath $confHddSrc -Destination (Join-Path $exfatCfgDir 'conf_hdd.cfg') -Force
    }

    # Garantir pastas padrao de jogos no exFAT
    foreach ($dirName in @('CD', 'DVD', 'ART', 'CFG', 'CHT', 'THM', 'VMC', 'POPS')) {
        $p = Join-Path $letter $dirName
        if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
    }

    Write-Host "Configuracoes salvas em $rootConf e idioma instalado na pasta $exfatOplDir com sucesso!" -ForegroundColor Green
}

# 5. Injetar na particao PFS (__common:/OPL/) via pfsshell (se nao solicitado pular)
if (-not $SkipInject) {
    try {
        $injectScript = Join-Path $RootPath 'BAT\__Inject_Pfs_Opl.ps1'
        if (Test-Path -LiteralPath $injectScript) {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $injectScript -RootPath $RootPath -Language $selectedLang
        }
    } catch {
        Write-Warning "Nao foi possivel sincronizar imediatamente com a particao PFS: $_"
    }
}

Write-Host ""
Write-Host "Configuracao de idioma ($selectedLang) e preparacao do OPL concluidas com sucesso!" -ForegroundColor Green
exit 0
