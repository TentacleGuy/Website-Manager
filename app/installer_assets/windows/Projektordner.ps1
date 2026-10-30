param([Parameter(Mandatory=$true)][string]$ProjectUrl)
$ErrorActionPreference = 'Stop'
try {
    if ($ProjectUrl -cnotmatch '^tentacle-project://open/([a-z][a-z0-9-]{0,39})/?$') { throw 'Ungueltiger Projektordner-Link.' }
    $projectName = $Matches[1]
    $folder = Invoke-RestMethod -Uri "http://127.0.0.1:8090/api/projects/$projectName/folder" -TimeoutSec 10
    if (-not $folder.available) { throw $folder.reason }
    $path = [string]$folder.path
    if ($path -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+[\\/])' -or $path -match '["\r\n]' -or -not (Test-Path -LiteralPath $path -PathType Container)) { throw 'Projektordner auf diesem Rechner nicht erreichbar.' }
    Start-Process -FilePath "$env:SystemRoot\explorer.exe" -ArgumentList ('"' + $path + '"')
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Tentacle Projektordner') | Out-Null
    exit 1
}
