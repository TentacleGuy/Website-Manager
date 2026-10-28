#!/bin/bash
set -Eeuo pipefail
umask 077
SOURCE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=Gemeinsam.sh
. "$SOURCE_DIR/Gemeinsam.sh"
WORK_DIR=''
MOUNT_DIR=''
LOG=''

finish() {
    local result=$?
    trap - EXIT
    if [ -n "$MOUNT_DIR" ]; then
        if /usr/bin/hdiutil detach "$MOUNT_DIR" -quiet >/dev/null 2>&1; then MOUNT_DIR=''; fi
    fi
    if [ -n "$WORK_DIR" ] && [ -z "$MOUNT_DIR" ]; then /bin/rm -rf "$WORK_DIR"; fi
    if [ "$result" -ne 0 ]; then
        printf '\nEinrichtung nicht abgeschlossen (Fehler %s).\n' "$result" >&2
        [ -z "$LOG" ] || printf 'Protokoll: %s\n' "$LOG" >&2
        printf '%s\n' 'Nach Behebung einfach erneut starten. Vorhandene Projektdaten bleiben erhalten.' >&2
    fi
    if [ -t 0 ]; then read -r -p 'Zum Schliessen Eingabetaste druecken. ' _ || true; fi
    exit "$result"
}
trap finish EXIT

[ "$(/usr/bin/uname -s)" = Darwin ] || { fail 'Dieses Paket ist fuer macOS.'; exit 1; }
[ "$(/usr/bin/id -u)" -ne 0 ] || { fail 'Bitte per Doppelklick als normale Benutzerin starten.'; exit 1; }
architecture=$(mac_architecture)
memory=$(/usr/sbin/sysctl -n hw.memsize)
[ "$memory" -ge 4294967296 ] || { fail 'Docker benoetigt mindestens 4 GB Arbeitsspeicher; empfohlen sind 8 GB oder mehr.'; exit 1; }
case "$INSTALL_DIR" in
    *','*|*'$'*|*'#'*|*$'\n'*) fail 'Dieser Benutzerordner enthaelt ein fuer die Docker-Konfiguration nicht unterstuetztes Zeichen. Bitte die IT kontaktieren.'; exit 1 ;;
esac

if [ "$SOURCE_DIR" != "$INSTALL_DIR" ]; then
    [ -d "$SOURCE_DIR/payload" ] || { fail 'Das Paket ist unvollstaendig. Bitte die ZIP-Datei vollstaendig entpacken.'; exit 1; }
    if [ -e "$INSTALL_DIR" ] && [ ! -f "$INSTALL_DIR/.tentacle-installer" ]; then
        fail "Der Zielordner ist bereits belegt: $INSTALL_DIR. Es wurden keine Dateien ersetzt."
        exit 1
    fi
    available=$(/bin/df -Pk "$HOME" | /usr/bin/awk 'NR==2 { print $4 }')
    [ "$available" -ge 20971520 ] || { fail 'Bitte mindestens 20 GB Speicherplatz freigeben.'; exit 1; }
    /bin/mkdir -p "$INSTALL_DIR"
    /bin/cp -R "$SOURCE_DIR/payload/." "$INSTALL_DIR/"
    for source_file in "$SOURCE_DIR/"*.command "$SOURCE_DIR/"*.sh "$SOURCE_DIR/"*.txt; do
        [ ! -f "$source_file" ] || /bin/cp "$source_file" "$INSTALL_DIR/"
    done
    printf '1\n' > "$INSTALL_DIR/.tentacle-installer"
    /bin/chmod u+x "$INSTALL_DIR/"*.command "$INSTALL_DIR/"*.sh
    trap - EXIT
    exec /bin/bash "$INSTALL_DIR/Installieren.command"
fi

/bin/mkdir -p "$INSTALL_DIR/logs" "$HOME/Applications" "$HOME/Desktop"
LOG="$INSTALL_DIR/logs/Einrichtung-$(/bin/date +%Y%m%d-%H%M%S).txt"
exec > >(/usr/bin/tee -a "$LOG") 2>&1
/bin/cp "$INSTALL_DIR/Einrichtung fortsetzen.command" "$HOME/Desktop/Tentacle Einrichtung fortsetzen.command"
printf '\nTentacle Projektmanager - Einrichtung fuer Mac (%s)\n\n' "$architecture"

if ! find_docker; then
    printf '%s\n' 'Docker Desktop wird direkt vom Hersteller geladen. Das kann einige Minuten dauern.'
    WORK_DIR=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/tentacle-setup.XXXXXX")
    /usr/bin/curl --fail --location --retry 3 --connect-timeout 30 --progress-bar \
        "https://desktop.docker.com/mac/main/$architecture/Docker.dmg" -o "$WORK_DIR/Docker.dmg"
    MOUNT_DIR="$WORK_DIR/mount"
    /bin/mkdir "$MOUNT_DIR"
    /usr/bin/hdiutil attach -quiet -nobrowse -readonly -mountpoint "$MOUNT_DIR" "$WORK_DIR/Docker.dmg"
    DOCKER_APP="$MOUNT_DIR/Docker.app"
    printf '%s\n' 'Herstellersignatur und macOS-Kompatibilitaet werden geprueft ...'
    /usr/bin/codesign --verify --deep --strict \
        -R='anchor apple generic and certificate leaf[subject.OU] = "9BNSXJN65R"' "$DOCKER_APP"
    /usr/sbin/spctl --assess --type execute "$DOCKER_APP"
    check_docker_macos
    printf '%s\n' 'macOS fragt jetzt nach Administratorrechten fuer die Docker-Installation.'
    admin "$DOCKER_APP/Contents/MacOS/install" "--user=$(/usr/bin/id -un)"
    /usr/bin/hdiutil detach "$MOUNT_DIR" -quiet
    MOUNT_DIR=''
    /bin/rm -rf "$WORK_DIR"
    WORK_DIR=''
fi

wait_docker
cd "$INSTALL_DIR"
if [ ! -f .env ]; then
    printf 'VMM_HOST_DATA=%s/data\nVMM_BIND=127.0.0.1\n' "$INSTALL_DIR" > .env
    /bin/chmod 600 .env
fi
printf '%s\n' 'Projektmanager und lokale HTTPS-Zertifikate werden vorbereitet ...'
"$DOCKER" build --tag vmm-manager:dev .
"$DOCKER" run --rm --mount "type=bind,source=$INSTALL_DIR,target=/workspace" --workdir /workspace \
    vmm-manager:dev python scripts/installer_config.py --host-data "$INSTALL_DIR/data" --dns-port 1053
"$DOCKER" compose -p tentacle-manager config --quiet
"$DOCKER" compose -p tentacle-gateway -f infra/compose.gateway.yaml config --quiet
start_manager
printf '%s\n' 'Gemeinsame Datenbank und phpMyAdmin werden vorbereitet ...'
"$DOCKER" pull mariadb:10.11
"$DOCKER" pull phpmyadmin:5.2-apache
"$DOCKER" compose -p tentacle-manager exec -T manager python -c \
    "import shared_operations as s; op,args=s.context(); op.command(args+['up','-d','--wait','--wait-timeout','180','db','phpmyadmin'],timeout=300)"

dns_answer=$(/usr/bin/dig @127.0.0.1 -p 1053 einrichtung.vmm.test A +short +time=3 +tries=1)
[ "$dns_answer" = 127.0.0.1 ] || { fail 'Der lokale DNS-Dienst antwortet nicht richtig.'; exit 1; }
printf '%s\n' 'macOS fragt jetzt nach Administratorrechten fuer lokale Projektadressen und HTTPS.'
admin /bin/bash "$INSTALL_DIR/Systemeinrichtung.sh" "$INSTALL_DIR/data/certs/rootCA.pem"
/usr/bin/dscacheutil -q host -a name einrichtung.vmm.test | /usr/bin/grep -q '127.0.0.1' || {
    fail 'Die macOS-Aufloesung der Projektadressen wurde nicht bestaetigt. Bitte VPN-/Firmen-DNS pruefen lassen.'; exit 1;
}
/usr/bin/security verify-cert -c "$INSTALL_DIR/data/certs/vmm.test.pem" -p ssl -s einrichtung.vmm.test

for launcher in "$HOME/Applications/Tentacle Projektmanager.command" "$HOME/Desktop/Tentacle Projektmanager.command"; do
    /bin/cp "$INSTALL_DIR/Starten.command" "$launcher"
    /bin/chmod u+x "$launcher"
done
/bin/rm -f "$HOME/Desktop/Tentacle Einrichtung fortsetzen.command"
printf '\n%s\n' 'Einrichtung abgeschlossen. Ab jetzt genuegt ein Doppelklick auf Tentacle Projektmanager.'
/usr/bin/open 'http://localhost:8090/'
