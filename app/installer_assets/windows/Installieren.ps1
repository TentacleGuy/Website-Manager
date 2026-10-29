$ErrorActionPreference = 'Stop'
try {
    . "$PSScriptRoot\Gemeinsam.ps1"
    $os = Get-CimInstance Win32_OperatingSystem
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    if ($arch -notin @('X64','Arm64')) { throw 'Ein 64-Bit-System mit Intel/AMD oder ARM64 wird benoetigt.' }
    $target = Join-Path $env:LOCALAPPDATA 'Tentacle\WebsiteManager'
    if ($env:VMM_INSTALL_DIR) { $target = $env:VMM_INSTALL_DIR }
    $source = $PSScriptRoot
    if ([IO.Path]::GetFullPath($source).TrimEnd('\') -ne [IO.Path]::GetFullPath($target).TrimEnd('\')) {
        if ((Test-Path $target) -and -not (Test-Path "$target\.tentacle-installer")) {
            throw "Der Zielordner $target ist bereits belegt. Es wurden keine Dateien ersetzt."
        }
        if (Test-Path "$source\payload") {
            $drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($target).Substring(0,1))
            if ($drive.Free -lt 20GB) { throw 'Bitte mindestens 20 GB Speicherplatz auf dem Installationslaufwerk freigeben.' }
            New-Item -ItemType Directory -Path $target -Force | Out-Null
            Copy-Item "$source\payload\*" $target -Recurse -Force
            foreach ($file in Get-ChildItem $source -File) { Copy-Item $file.FullName $target -Force }
            Set-Content "$target\.tentacle-installer" '1' -Encoding ASCII
            & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$target\Installieren.ps1"
            exit $LASTEXITCODE
        }
        throw 'Das Installationspaket ist unvollstaendig. ZIP bitte erneut vollstaendig entpacken.'
    }
    New-Item -ItemType Directory -Path "$target\logs" -Force | Out-Null
    $log = Join-Path $target ('logs\Einrichtung-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt')
    Start-Transcript -Path $log | Out-Null
    $desktop = [Environment]::GetFolderPath('Desktop')
    New-ManagerShortcut $desktop 'Tentacle Einrichtung fortsetzen' 'Installieren.ps1'
    Write-Host 'Tentacle Projektmanager - Einrichtung' -ForegroundColor Cyan
    Write-Host 'Windows-Unterstuetzung, Docker, lokale Projektadressen und HTTPS werden eingerichtet.'
    $dockerReady = $false
    $paths = Get-DockerPaths
    if ($paths) {
        try { $type = & $paths.Cli info --format '{{.OSType}}' 2>$null; $dockerReady = $LASTEXITCODE -eq 0 -and $type -eq 'linux' } catch {}
    }
    if (-not $dockerReady -and -not $paths) {
        if ($os.ProductType -ne 1 -or [int]$os.BuildNumber -lt 19045 -or ($arch -eq 'Arm64' -and [int]$os.BuildNumber -lt 22631)) { throw 'Fuer die Neuinstallation von Docker Desktop wird eine vom Hersteller unterstuetzte Windows-Version benoetigt. Ein vorhandener lokaler Docker-Dienst kann weiterverwendet werden.' }
        if ((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory -lt 8GB) { throw 'Docker Desktop benoetigt fuer die Neuinstallation mindestens 8 GB Arbeitsspeicher.' }
        Write-Host 'Bitte die Windows-Administratorabfrage fuer die Systemeinrichtung bestaetigen.'
        $helper = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + "$target\Systemeinrichtung.ps1" + '"'), '-Step', 'Prerequisites')
        if ($helper.ExitCode -eq 3010) {
            Write-Host 'Bitte Arbeit speichern und Windows neu starten. Danach auf dem Desktop "Tentacle Einrichtung fortsetzen" oeffnen.' -ForegroundColor Yellow
            Stop-Transcript | Out-Null
            Read-Host 'Zum Schliessen Eingabetaste druecken'
            exit 3010
        }
        if ($helper.ExitCode -ne 0) { throw 'Die Systemeinrichtung wurde nicht abgeschlossen.' }
    }
    if (-not (Get-DockerPaths)) {
        Write-Host 'Docker Desktop wird direkt vom Hersteller heruntergeladen. Das kann einige Minuten dauern.'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $download = Join-Path $target 'Docker Desktop Installer.exe'
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -UseBasicParsing -Uri ("https://desktop.docker.com/win/main/" + $(if ($arch -eq 'Arm64') { 'arm64' } else { 'amd64' }) + '/Docker%20Desktop%20Installer.exe') -OutFile $download
        $signature = Get-AuthenticodeSignature $download
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)O="?Docker Inc\.?"?(?:,|$)') {
            Remove-Item $download -Force
            throw 'Die Herstellersignatur des Docker-Installers ist ungueltig. Installation abgebrochen.'
        }
        $process = Start-Process -FilePath $download -Wait -PassThru -ArgumentList @('install', '--user', '--backend=wsl-2')
        if ($process.ExitCode -eq 3010) {
            Write-Host 'Bitte Windows neu starten und danach "Tentacle Einrichtung fortsetzen" oeffnen.'
            Stop-Transcript | Out-Null
            Read-Host 'Zum Schliessen Eingabetaste druecken'
            exit 3010
        }
        if ($process.ExitCode -ne 0) { throw "Docker-Installation fehlgeschlagen (Code $($process.ExitCode))." }
        Remove-Item $download -Force
    }
    Wait-Docker
    Set-Location $target
    $hostData = ($target + '\data').Replace('\', '/')
    if (-not (Test-Path '.env')) {
        [IO.File]::WriteAllText((Join-Path $target '.env'), "VMM_HOST_DATA=$hostData`nVMM_BIND=127.0.0.1`n", (New-Object Text.UTF8Encoding $false))
    }
    Write-Host 'Projektmanager und lokale HTTPS-Zertifikate werden vorbereitet ...'
    Initialize-ManagerEnvironment $target
    Invoke-Docker build --build-arg ('DOCKER_CLI_IMAGE=' + $script:DockerCliImage) --tag vmm-manager:dev .
    Invoke-Docker run --rm --mount "type=bind,source=$target,target=/workspace" --mount ('type=bind,source=' + $script:DockerSocket + ',target=/var/run/docker.sock') --workdir /workspace vmm-manager:dev python scripts/installer_config.py --host-data $hostData --check-environment --host-platform windows
    Invoke-Docker compose -p tentacle-manager config --quiet
    Invoke-Docker compose -p tentacle-gateway -f infra/compose.gateway.yaml config --quiet
    Start-Manager
    Write-Host 'Gemeinsame Datenbank und phpMyAdmin werden vorbereitet ...'
    Invoke-Docker compose -p tentacle-manager exec -T manager python -c "import shared_operations as s; op,args=s.context(); op.command(args+['up','-d','--wait','--wait-timeout','180','phpmyadmin'],timeout=300)"
    # Trust only the newly generated public local CA, in the original user's store.
    Import-Certificate -FilePath "$target\data\certs\rootCA.cer" -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
    Write-Host 'Die Windows-Administratorabfrage richtet jetzt nur die lokalen vmm.test-Adressen ein.'
    $helper = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + "$target\Systemeinrichtung.ps1" + '"'), '-Step', 'Dns')
    if ($helper.ExitCode -ne 0) { throw 'Lokale Projektadressen konnten nicht eingerichtet werden.' }
    $answer = @(Resolve-DnsName 'einrichtung.vmm.test' -Type A -DnsOnly -ErrorAction Stop | Where-Object { $_.IPAddress -eq '127.0.0.1' })
    if (-not $answer.Count) { throw 'Der Test der lokalen Projektadressen ist fehlgeschlagen. Bitte DNS-/VPN-Firmenrichtlinien pruefen lassen.' }
    New-ManagerShortcut $desktop 'Tentacle Projektmanager' 'Starten.ps1'
    New-ManagerShortcut (Join-Path ([Environment]::GetFolderPath('Programs')) 'Tentacle') 'Tentacle Projektmanager' 'Starten.ps1'
    Remove-Item (Join-Path $desktop 'Tentacle Einrichtung fortsetzen.lnk') -ErrorAction SilentlyContinue
    Write-Host 'Einrichtung abgeschlossen. Der Projektmanager wird im Browser geoeffnet.' -ForegroundColor Green
    Stop-Transcript | Out-Null
    Start-Process 'http://localhost:8090/'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Einrichtung nach Behebung erneut starten. Protokolle: %LOCALAPPDATA%\Tentacle\WebsiteManager\logs'
    try { Stop-Transcript | Out-Null } catch {}
    Read-Host 'Zum Schliessen Eingabetaste druecken'
    exit 1
}
