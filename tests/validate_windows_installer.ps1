$ErrorActionPreference = 'Stop'
$failed = $false
foreach ($file in Get-ChildItem (Join-Path $PSScriptRoot '../installer/windows') -Filter '*.ps1') {
    $parseErrors = $null
    $tokens = $null
    [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count) {
        $failed = $true
        foreach ($problem in $parseErrors) { Write-Host "$($file.Name): $problem" }
    } else { Write-Host "PASS $($file.Name)" }
}
if ($failed) { exit 1 }
