param(
    [string]$PhysicalDrivePath,
    [Parameter(Mandatory = $true)]
    [string]$RootPath
)

& (Join-Path $PSScriptRoot '__Format_ApaJail_Minimal.ps1') `
    -RestoreApaHeaderOnly `
    -PhysicalDrivePath $PhysicalDrivePath `
    -RootPath $RootPath

exit $LASTEXITCODE
