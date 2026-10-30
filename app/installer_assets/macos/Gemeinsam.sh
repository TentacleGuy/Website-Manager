#!/bin/bash
# macOS ships Bash 3.2. No Homebrew or developer tools are required.

INSTALL_DIR="${VMM_INSTALL_DIR:-$HOME/Library/Application Support/Tentacle/WebsiteManager}"
DOCKER_APP=''
DOCKER=''

fail() { printf '\n%s\n' "$*" >&2; return 1; }

mac_architecture() {
    if [ "$(/usr/sbin/sysctl -in hw.optional.arm64 2>/dev/null || true)" = 1 ]; then
        printf 'arm64\n'
    else
        case "$(/usr/bin/uname -m)" in
            arm64) printf 'arm64\n' ;;
            x86_64) printf 'amd64\n' ;;
            *) fail 'Dieser Mac-Prozessortyp wird nicht unterstuetzt.' ;;
        esac
    fi
}

version_at_least() {
    local actual_major actual_minor actual_patch required_major required_minor required_patch
    IFS=. read -r actual_major actual_minor actual_patch <<< "$1"
    IFS=. read -r required_major required_minor required_patch <<< "$2"
    actual_minor=${actual_minor:-0}; actual_patch=${actual_patch:-0}
    required_minor=${required_minor:-0}; required_patch=${required_patch:-0}
    [ "$actual_major" -gt "$required_major" ] || {
        [ "$actual_major" -eq "$required_major" ] && {
            [ "$actual_minor" -gt "$required_minor" ] || {
                [ "$actual_minor" -eq "$required_minor" ] && [ "$actual_patch" -ge "$required_patch" ]
            }
        }
    }
}

find_docker() {
    local candidate
    DOCKER=$(command -v docker || true)
    for candidate in /Applications/Docker.app "$HOME/Applications/Docker.app"; do
        if [ -x "$candidate/Contents/Resources/bin/docker" ]; then
            DOCKER_APP=$candidate
            [ -n "$DOCKER" ] || DOCKER="$candidate/Contents/Resources/bin/docker"
            return 0
        fi
    done
    [ -n "$DOCKER" ]
}

check_docker_macos() {
    local required
    [ -n "$DOCKER_APP" ] || return 0
    required=$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$DOCKER_APP/Contents/Info.plist" 2>/dev/null || true)
    if [ -n "$required" ] && ! version_at_least "$(/usr/bin/sw_vers -productVersion)" "$required"; then
        fail "Docker benoetigt mindestens macOS $required. Bitte macOS zuerst aktualisieren."
    fi
}

wait_docker() {
    find_docker || { fail 'Docker Desktop fehlt. Bitte Installieren.command starten.'; return 1; }
    export PATH="${DOCKER_APP}/Contents/Resources/bin:$PATH"
    if [ "$("$DOCKER" info --format '{{.OSType}}' 2>/dev/null || true)" != linux ]; then
        [ -n "$DOCKER_APP" ] || { fail "Der gewaehlte lokale Docker-Dienst ist nicht gestartet. Bitte zuerst starten."; return 1; }
        check_docker_macos || return 1
        /usr/bin/open -a "$DOCKER_APP"
        printf '%s\n' 'Docker Desktop startet. Bitte dort die Bedingungen bestaetigen und die Einrichtung abschliessen.'
        local attempt
        for ((attempt=0; attempt<150; attempt++)); do
            if [ "$("$DOCKER" info --format '{{.OSType}}' 2>/dev/null || true)" = linux ]; then
                "$DOCKER" compose version
                return
            fi
            /bin/sleep 4
        done
        fail 'Docker ist noch nicht bereit. Docker-Fenster pruefen und die Einrichtung danach erneut starten.'
        return 1
    fi
    "$DOCKER" compose version
}

start_manager() {
    cd "$INSTALL_DIR"
    /bin/bash "$INSTALL_DIR/app/installer_assets/register-folders.sh" "$INSTALL_DIR" || printf '%s\n' 'Projektordner-Anbindung konnte nicht eingerichtet werden.' >&2
    source "$INSTALL_DIR/app/installer_assets/docker-environment.sh"
    manager_environment "$INSTALL_DIR"
    local actual
    actual=$("$DOCKER" image inspect vmm-manager:dev --format '{{index .Config.Labels "vmm.docker.cli.image"}}' 2>/dev/null || true)
    if [ "$actual" != "$DOCKER_CLI_IMAGE" ]; then "$DOCKER" compose -p tentacle-manager build manager;fi
    if ! "$DOCKER" network inspect vmm-gateway >/dev/null 2>&1; then
        "$DOCKER" network create vmm-gateway
    fi
    "$DOCKER" compose -p tentacle-gateway -f infra/compose.gateway.yaml up -d
    "$DOCKER" compose -p tentacle-manager up -d
    local attempt health
    for ((attempt=0; attempt<60; attempt++)); do
        health=$(/usr/bin/curl --noproxy '*' -fsS --max-time 8 'http://localhost:8090/api/health' 2>/dev/null || true)
        if printf '%s' "$health" | /usr/bin/grep -Eq '"docker"[[:space:]]*:[[:space:]]*true' &&
           printf '%s' "$health" | /usr/bin/grep -Eq '"domain"[[:space:]]*:[[:space:]]*"vmm.test"'; then
            return 0
        fi
        /bin/sleep 3
    done
    fail 'Der Projektmanager antwortet noch nicht. Bitte das Einrichtungsprotokoll pruefen.'
}

admin() {
    # Each argument is separately quoted by AppleScript, including spaces and apostrophes.
    /usr/bin/osascript - "$@" <<'APPLESCRIPT'
on run argv
    set commandText to ""
    repeat with argumentValue in argv
        set commandText to commandText & " " & quoted form of (contents of argumentValue)
    end repeat
    do shell script commandText with administrator privileges
end run
APPLESCRIPT
}
