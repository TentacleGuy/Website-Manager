#!/bin/bash
set -euo pipefail
cd "${VMM_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/Tentacle/WebsiteManager}"
DOCKER=$(command -v docker)
source app/installer_assets/docker-environment.sh
manager_environment "$PWD"
actual=$("$DOCKER" image inspect vmm-manager:dev --format '{{index .Config.Labels "vmm.docker.cli.image"}}' 2>/dev/null || true)
if [ "$actual" != "$DOCKER_CLI_IMAGE" ]; then "$DOCKER" compose -p tentacle-manager build manager;fi
"$DOCKER" compose -p tentacle-gateway -f infra/compose.gateway.yaml up -d
"$DOCKER" compose -p tentacle-manager up -d
printf '%s\n' 'Manager: http://localhost:8090/'
