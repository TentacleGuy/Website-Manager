#!/bin/bash
set -euo pipefail

bundle=$(cd "$(/usr/bin/dirname "$0")/../.." && pwd -P)
if [ "$#" -eq 0 ] || [[ $# -eq 1 && ${1:-} == -psn_* ]]; then
    exec /bin/bash "${bundle%/*}/app/installer_assets/macos/helpers/start-safari-alarm.sh"
fi

resources="$bundle/Contents/Resources"
exec /usr/bin/osascript -l JavaScript "$resources/safari-alarm.js" "$1" "$resources/safari-alarm.wav"
