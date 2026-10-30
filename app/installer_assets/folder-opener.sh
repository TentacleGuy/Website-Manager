#!/bin/bash
# Only project slugs are accepted; host paths come from the local manager.
set -euo pipefail
url=${1:-}
if [[ ! "$url" =~ ^tentacle-project://open/([a-z][a-z0-9-]{0,39})/?$ ]]; then
    printf '%s\n' 'Ungueltiger Projektordner-Link.' >&2; exit 1
fi
project=${BASH_REMATCH[1]}
folder=$(curl --noproxy '*' --proto '=http' --fail --silent --show-error --max-time 10 "http://127.0.0.1:8090/api/projects/$project/folder?format=path")
[[ "$folder" = /* && "$folder" != *$'\n'* && "$folder" != *$'\r'* && -d "$folder" ]] || { printf '%s\n' 'Projektordner auf diesem Rechner nicht erreichbar.' >&2; exit 1; }
case $(uname -s) in
    Darwin) /usr/bin/open -a Finder "$folder" ;;
    Linux) command -v xdg-open >/dev/null || { printf '%s\n' 'Ein Desktop mit xdg-open wird benoetigt.' >&2; exit 1; };xdg-open "$folder" ;;
    *) printf '%s\n' 'Nicht unterstuetztes Betriebssystem.' >&2;exit 1 ;;
esac
