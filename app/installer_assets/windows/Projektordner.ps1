param([Parameter(Mandatory=$true)][string]$ProjectUrl)
$ErrorActionPreference = 'Stop'
try {
    if ($ProjectUrl -cmatch '^tentacle-project://(choose|repair)/([a-f0-9]{32})/?$') {
        $mode = $Matches[1]
        $token = $Matches[2]
        if ($mode -eq 'repair') {
            $helper = $PSCommandPath
            if ($helper -notmatch '[\r\n"]') {
                $key = 'HKCU:\Software\Classes\tentacle-project'
                New-Item -Path "$key\shell\open\command" -Force | Out-Null
                Set-Item -LiteralPath $key -Value 'URL:Tentacle Projektordner'
                New-ItemProperty -LiteralPath $key -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
                $powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
                $command = '"' + $powershell + '" -NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $helper + '" -ProjectUrl "%1"'
                Set-Item -LiteralPath "$key\shell\open\command" -Value $command
            }
        }
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = 'Speicherordner für den Projektmanager wählen'
        $path = ''
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $path = $dialog.SelectedPath }
        $dialog.Dispose()
        Invoke-RestMethod -Uri "http://127.0.0.1:8090/api/folder-picker/$token/complete" -Method Post -Headers @{'X-VMM-Request'='1'} -ContentType 'text/plain; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($path)) -TimeoutSec 10 | Out-Null
        exit 0
    }
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
