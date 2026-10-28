$ErrorActionPreference = 'Stop'

function Get-DockerPaths {
    foreach ($base in @("$env:LOCALAPPDATA\Programs\DockerDesktop", "$env:ProgramFiles\Docker\Docker")) {
        if (Test-Path "$base\Docker Desktop.exe") {
            return @{ Desktop = "$base\Docker Desktop.exe"; Cli = "$base\resources\bin\docker.exe" }
        }
    }
    return $null
}

function Invoke-Docker {
    & $script:Docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker-Schritt fehlgeschlagen (Code $LASTEXITCODE): $($args -join ' ')" }
}

function Wait-Docker {
    $paths = Get-DockerPaths
    if (-not $paths) { throw 'Docker Desktop fehlt. Bitte Installieren.cmd starten.' }
    $script:Docker = $paths.Cli
    $env:DOCKER_CONTEXT = 'desktop-linux'
    # Ignore inherited remote daemon settings for this local installation.
    Remove-Item Env:DOCKER_HOST -ErrorAction SilentlyContinue
    $ready = $false
    try { $type = & $script:Docker info --format '{{.OSType}}' 2>$null; $ready = $LASTEXITCODE -eq 0 -and $type -eq 'linux' } catch {}
    if (-not $ready) {
        Start-Process -FilePath $paths.Desktop
        Write-Host 'Docker Desktop startet. Bitte dort die Bedingungen bestaetigen und ggf. die Einfuehrung abschliessen.'
        $until = (Get-Date).AddMinutes(10)
        while ((Get-Date) -lt $until) {
            try {
                $type = & $script:Docker info --format '{{.OSType}}' 2>$null
                if ($LASTEXITCODE -eq 0 -and $type -eq 'linux') { $ready = $true; break }
            } catch {}
            Start-Sleep -Seconds 4
        }
    }
    if (-not $ready) { throw 'Docker ist noch nicht bereit. Docker Desktop pruefen, danach erneut starten. Benoetigt: Linux-Container mit WSL 2.' }
    Invoke-Docker compose version
}

function Start-Manager {
    Set-Location $PSScriptRoot
    $networks = @(Invoke-Docker network ls --format '{{.Name}}')
    if ($networks -notcontains 'vmm-gateway') { Invoke-Docker network create vmm-gateway }
    Invoke-Docker compose -p tentacle-gateway -f infra/compose.gateway.yaml up -d
    Invoke-Docker compose -p tentacle-manager up -d
    $until = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $until) {
        try {
            $health = Invoke-RestMethod -Uri 'http://localhost:8090/api/health' -TimeoutSec 10
            if ($health.docker -eq $true -and $health.domain -eq 'vmm.test') { return }
        } catch {}
        Start-Sleep -Seconds 3
    }
    throw 'Der Projektmanager antwortet noch nicht. Protokoll pruefen und erneut starten.'
}

function New-ManagerShortcut([string]$Directory, [string]$Name, [string]$Script) {
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut((Join-Path $Directory "$Name.lnk"))
    $link.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $link.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot $Script) + '"'
    $link.WorkingDirectory = $PSScriptRoot
    $link.Save()
}
