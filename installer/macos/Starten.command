#!/bin/bash
set -Eeuo pipefail
finish() {
    local result=$?
    trap - EXIT
    if [ "$result" -ne 0 ]; then
        printf '\nStart fehlgeschlagen. Docker pruefen und erneut starten.\n' >&2
        if [ -t 0 ]; then read -r -p 'Zum Schliessen Eingabetaste druecken. ' _ || true; fi
    fi
    exit "$result"
}
trap finish EXIT
root="$HOME/Library/Application Support/Tentacle/WebsiteManager"
. "$root/Gemeinsam.sh"
wait_docker
start_manager
/usr/bin/open 'http://localhost:8090/'
