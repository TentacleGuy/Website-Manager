# Only this helper is elevated; Docker Desktop and user files belong to the caller.
param([ValidateSet('Prerequisites', 'Dns')][string]$Step = 'Prerequisites')
$ErrorActionPreference = 'Stop'
try {
    if ($Step -eq 'Dns') {
        $comment = 'Tentacle Website Manager local DNS'
        $own = @(Get-DnsClientNrptRule | Where-Object { $_.Comment -eq $comment })
        $conflicts = @(Get-DnsClientNrptRule | Where-Object {
            $_.Comment -ne $comment -and (@($_.Namespace) -contains '.vmm.test' -or @($_.Namespace) -contains 'vmm.test')
        })
        if ($conflicts.Count) { throw 'Es gibt bereits eine DNS-Regel fuer vmm.test. Bitte die IT pruefen lassen.' }
        foreach ($rule in $own) { Remove-DnsClientNrptRule -Name $rule.Name -Force }
        Add-DnsClientNrptRule -Namespace @('vmm.test', '.vmm.test') -NameServers '127.0.0.1' -Comment $comment | Out-Null
        Clear-DnsClientCache
        exit 0
    }
    $restart = $false
    foreach ($feature in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform')) {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName $feature).State
        if ($state -eq 'EnablePending') { $restart = $true }
        elseif ($state -ne 'Enabled') {
            $result = Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart
            if ($result.RestartNeeded) { $restart = $true }
        }
    }
    if ($restart) { exit 3010 }
    $hasWsl = $false
    try { & wsl.exe --version *> $null; $hasWsl = $LASTEXITCODE -eq 0 } catch {}
    if (-not $hasWsl) {
        & wsl.exe --install --no-distribution
        if ($LASTEXITCODE -eq 3010) { exit 3010 }
        if ($LASTEXITCODE -ne 0) { throw 'WSL konnte nicht installiert werden.' }
    }
    & wsl.exe --update
    if ($LASTEXITCODE -eq 3010) { exit 3010 }
    if ($LASTEXITCODE -ne 0) { throw 'WSL konnte nicht aktualisiert werden. Internetzugang und Firmenrichtlinien pruefen.' }
    & wsl.exe --set-default-version 2
    if ($LASTEXITCODE -ne 0) { throw 'WSL 2 konnte nicht aktiviert werden.' }
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host 'Zum Schliessen Eingabetaste druecken'
    exit 1
}
