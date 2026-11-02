#!/bin/bash
# Only project slugs are accepted; host paths come from the local manager.
set -euo pipefail
url=${1:-}
if [[ "$url" =~ ^tentacle-project://(choose|repair)/([a-f0-9]{32})/?$ ]]; then
    mode=${BASH_REMATCH[1]};token=${BASH_REMATCH[2]}
    if [[ "$mode" = repair ]]; then
        helper_dir=$(cd "$(dirname "$0")" && pwd -P)
        /bin/bash "$helper_dir/register-folders.sh" "$(cd "$helper_dir/../.." && pwd -P)"
    fi
    folder=''
    case $(uname -s) in
      Darwin) folder=$(/usr/bin/osascript -e 'POSIX path of (choose folder with prompt "Speicherordner für den Projektmanager wählen")' 2>/dev/null) || folder='' ;;
      Linux)
        if command -v zenity >/dev/null; then folder=$(zenity --file-selection --directory --title="Speicherordner wählen") || folder=''
        elif command -v kdialog >/dev/null; then folder=$(kdialog --getexistingdirectory "$HOME" --title "Speicherordner wählen") || folder=''
        else printf '%s\n' 'Die Ordnerauswahl benötigt zenity oder kdialog.' >&2;exit 1;fi ;;
      *) exit 1 ;;
    esac
    if [[ -n "$folder" ]]; then [[ "$folder" = /* && "$folder" != *$'\n'* && "$folder" != *$'\r'* && -d "$folder" ]] || exit 1;fi
    curl --noproxy '*' --proto '=http' --fail --silent --show-error --max-time 10 -H 'X-VMM-Request: 1' -H 'Content-Type: text/plain; charset=utf-8' --data-binary "$folder" "http://127.0.0.1:8090/api/folder-picker/$token/complete"
    exit
fi
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
