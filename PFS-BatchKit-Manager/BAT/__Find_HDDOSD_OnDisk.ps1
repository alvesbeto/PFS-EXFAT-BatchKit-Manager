$roots = @(
    [Environment]::GetFolderPath('UserProfile') + '\Downloads'
    [Environment]::GetFolderPath('Desktop')
    'C:\Users\beto\Documents'
    (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)
$names = @('hosdsys.elf', 'HDDOSD-1.10U.7z', 'hddosd-1.10-u.7z')
foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    foreach ($n in $names) {
        Get-ChildItem -LiteralPath $root -Filter $n -Recurse -ErrorAction SilentlyContinue -Force -Depth 10 |
            Select-Object FullName, Length
    }
}
