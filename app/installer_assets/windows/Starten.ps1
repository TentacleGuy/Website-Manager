try {
    . "$PSScriptRoot\Gemeinsam.ps1"
    Wait-Docker
    Start-Manager
    Start-Process 'http://localhost:8090/'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host 'Zum Schliessen Eingabetaste druecken'
    exit 1
}
