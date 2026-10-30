#!/bin/bash
set -euo pipefail
source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
target=${VMM_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/Tentacle/WebsiteManager}
command -v docker >/dev/null || { printf '%s\n' 'Docker Engine mit Compose-Plugin fehlt. Bitte Docker nach Herstelleranleitung fuer diese Linux-Distribution installieren und dann erneut starten.' >&2; exit 1; }
if [ "$source_dir" != "$target" ]; then
    [ -d "$source_dir/payload" ] || { printf '%s\n' 'ZIP bitte vollstaendig entpacken.' >&2; exit 1; }
    if [ -e "$target" ] && [ ! -f "$target/.tentacle-installer" ]; then printf 'Zielordner bereits belegt: %s\n' "$target" >&2; exit 1; fi
    mkdir -p "$target";cp -R "$source_dir/payload/." "$target/";cp "$source_dir/"*.sh "$target/";printf '1\n' > "$target/.tentacle-installer"
    exec /bin/bash "$target/Installieren.sh"
fi
cd "$target";umask 077
if [ ! -f .env ]; then printf 'VMM_HOST_DATA=%s/data\nVMM_BIND=127.0.0.1\n' "$target" > .env;fi
/bin/bash "$PWD/app/installer_assets/register-folders.sh" "$PWD" || printf '%s\n' 'Projektordner-Anbindung konnte nicht eingerichtet werden.' >&2
DOCKER=$(command -v docker)
source "$target/app/installer_assets/docker-environment.sh"
manager_environment "$target"
"$DOCKER" build --build-arg "DOCKER_CLI_IMAGE=$DOCKER_CLI_IMAGE" -t vmm-manager:dev .
"$DOCKER" run --rm --mount "type=bind,source=$target,target=/workspace" --mount "type=bind,source=$DOCKER_SOCKET,target=/var/run/docker.sock" -w /workspace vmm-manager:dev python scripts/installer_config.py --host-data "$target/data" --dns-port 1053 --check-environment --host-platform linux
"$DOCKER" network inspect vmm-gateway >/dev/null 2>&1 || "$DOCKER" network create vmm-gateway
"$DOCKER" compose -p tentacle-gateway -f infra/compose.gateway.yaml up -d
"$DOCKER" compose -p tentacle-manager up -d
printf '\nManager: http://localhost:8090/\n'
printf '%s\n' 'Fuer lokale Projektdomains und HTTPS: sudo bash Systemeinrichtung.sh ausfuehren. Der Helfer unterstuetzt systemd-resolved; andere Resolver werden nicht veraendert.'
