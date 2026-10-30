$ErrorActionPreference = 'Stop'

function Get-DockerPaths {
    $command = Get-Command docker.exe -ErrorAction SilentlyContinue
    $cli = if ($command) { $command.Source } else { $null }
    foreach ($base in @("$env:LOCALAPPDATA\Programs\DockerDesktop", "$env:ProgramFiles\Docker\Docker")) {
        if (Test-Path "$base\Docker Desktop.exe") {
            if (-not $cli) { $cli = "$base\resources\bin\docker.exe" }
            return @{ Desktop = "$base\Docker Desktop.exe"; Cli = $cli }
        }
    }
    if ($cli) { return @{ Desktop = $null; Cli = $cli } }
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
    $ready = $false
    try { $type = & $script:Docker info --format '{{.OSType}}' 2>$null; $ready = $LASTEXITCODE -eq 0 -and $type -eq 'linux' } catch {}
    if (-not $ready) {
        if (-not $paths.Desktop) { throw 'Der gewaehlte Docker-Dienst ist nicht gestartet. Bitte zuerst starten.' }
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

function Register-ProjectFolders {
    $helper = Join-Path $PSScriptRoot 'app\installer_assets\windows\Projektordner.ps1'
    if (-not (Test-Path -LiteralPath $helper)) { throw 'Projektordner-Helfer fehlt.' }
    $key = 'HKCU:\Software\Classes\tentacle-project'
    New-Item -Path "$key\shell\open\command" -Force | Out-Null
    Set-Item -LiteralPath $key -Value 'URL:Tentacle Projektordner'
    New-ItemProperty -LiteralPath $key -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
    $powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $command = '"' + $powershell + '" -NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $helper + '" -ProjectUrl "%1"'
    Set-Item -LiteralPath "$key\shell\open\command" -Value $command
    New-Item -ItemType Directory -Path "$PSScriptRoot\data" -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'data\desktop-integration.json'),'{"platform":"windows","scheme":"tentacle-project","version":1}',(New-Object Text.UTF8Encoding $false))
}

function Start-Manager {
    param([switch]$ForceBuild)
    Set-Location $PSScriptRoot
    try { Register-ProjectFolders } catch { Write-Warning ('Projektordner-Anbindung: ' + $_.Exception.Message) }
    Initialize-ManagerEnvironment $PSScriptRoot
    $actual = ''
    try { $actual = Invoke-Docker image inspect vmm-manager:dev --format '{{index .Config.Labels "vmm.docker.cli.image"}}' } catch {}
    if ($ForceBuild -or $actual -ne $script:DockerCliImage) { Invoke-Docker compose -p tentacle-manager build manager }
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

function Initialize-ManagerEnvironment([string]$Root) {
    $info = (Invoke-Docker info --format '{{json .}}') | ConvertFrom-Json
    $version = (Invoke-Docker version --format '{{json .}}') | ConvertFrom-Json
    $compose = (Invoke-Docker compose version --short).Trim()
    if ($info.OSType -ne 'linux') { throw 'Docker muss Linux-Container verwenden.' }
    if ($info.Architecture -notin @('amd64','x86_64','arm64','aarch64')) { throw ('Nicht unterstuetzte Docker-Architektur: ' + $info.Architecture) }
    if ($version.Server.Version -notmatch '^(\d+)\.') { throw 'Docker-Version nicht erkannt.' }
    $major = [int]$Matches[1]
    if ($major -lt 24) { throw 'Docker Engine ab Version 24 wird benoetigt.' }
    if ($compose -notmatch '^v?(\d+)\.(\d+)' -or ([int]$Matches[1] -lt 2) -or ([int]$Matches[1] -eq 2 -and [int]$Matches[2] -lt 20)) { throw 'Docker Compose ab Version 2.20 wird benoetigt.' }
    $contextName = (Invoke-Docker context show).Trim()
    $context = @((Invoke-Docker context inspect $contextName) | ConvertFrom-Json)[0]
    $endpoint = $context.Endpoints.docker.Host
    if ($env:DOCKER_HOST) { $endpoint = $env:DOCKER_HOST }
    if ($endpoint -notmatch '^(unix://|npipe:)') { throw 'Der gewaehlte Docker-Kontext ist nicht lokal. Lokale Projektdateien benoetigen einen lokalen Docker-Dienst.' }
    $script:DockerSocket = '/var/run/docker.sock'
    if ($endpoint.StartsWith('unix://') -and $info.OperatingSystem -notlike '*Docker Desktop*') { $script:DockerSocket = $endpoint.Substring(7) }
    if ($env:VMM_DOCKER_SOCKET) { $script:DockerSocket = $env:VMM_DOCKER_SOCKET }
    if (-not $script:DockerSocket.StartsWith('/')) { throw 'Ein absoluter Linux-Docker-Socket-Pfad wird benoetigt.' }
    if ($script:DockerSocket.Contains(',') -or $script:DockerSocket.Contains("`n")) { throw 'Nicht unterstuetzter Docker-Socket-Pfad.' }
    $script:DockerCliImage = "docker:$major-cli"
    $envFile = Join-Path $Root '.env'
    $text = if (Test-Path $envFile) { [IO.File]::ReadAllText($envFile) } else { '' }
    foreach ($entry in @(@('VMM_DOCKER_CLI_IMAGE',$script:DockerCliImage),@('VMM_DOCKER_SOCKET',$script:DockerSocket))) {
        $pattern = '(?m)^' + $entry[0] + '=.*$'
        $line = $entry[0] + '=' + $entry[1]
        if ([regex]::IsMatch($text,$pattern)) { $text = [regex]::Replace($text,$pattern,[System.Text.RegularExpressions.MatchEvaluator]{ param($m) $line }) }
        else { $text = $text.TrimEnd("`r","`n") + "`n" + $line + "`n" }
    }
    [IO.File]::WriteAllText($envFile,$text.TrimStart("`r","`n"),(New-Object Text.UTF8Encoding $false))
    New-Item -ItemType Directory -Path (Join-Path $Root 'data') -Force | Out-Null
    $report = @{ status='ok'; platform='windows'; context=$contextName; socket=$script:DockerSocket; docker_version=$version.Server.Version; architecture=$info.Architecture; compose=$compose; cli_image=$script:DockerCliImage }
    [IO.File]::WriteAllText((Join-Path $Root 'data/setup-report.json'),($report | ConvertTo-Json),(New-Object Text.UTF8Encoding $false))
    Write-Host ('Docker ' + $version.Server.Version + ' | ' + $info.Architecture + ' | Compose ' + $compose + ' | Kontext ' + $contextName)
}
