#!/bin/bash
set -euo pipefail

bundle=${1:?Pfad für Helfer.app fehlt.}
[[ "$bundle" == /*/Helfer.app && -d "${bundle%/*}" ]] || exit 1
helpers=$(cd "$(/usr/bin/dirname "$0")" && pwd -P)
assets=${helpers%/*}
identifier=com.tentacle.helfer

if [[ -e "$bundle" || -L "$bundle" ]]; then
    if [[ -L "$bundle" || ! -d "$bundle" ]] ||
       [ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$bundle/Contents/Info.plist" 2>/dev/null)" != "$identifier" ]; then
        printf '%s\n' 'Helfer.app kann an diesem Speicherort nicht installiert werden.' >&2
        exit 1
    fi
    if /usr/bin/cmp -s "$helpers/Helfer-Info.plist" "$bundle/Contents/Info.plist" &&
       /usr/bin/cmp -s "$helpers/helfer-entrypoint.sh" "$bundle/Contents/MacOS/Helfer" &&
       /usr/bin/cmp -s "$assets/safari-alarm.js" "$bundle/Contents/Resources/safari-alarm.js" &&
       /usr/bin/cmp -s "$assets/safari-alarm.wav" "$bundle/Contents/Resources/safari-alarm.wav" &&
       [[ -x "$bundle/Contents/MacOS/Helfer" ]] &&
       /usr/bin/codesign --verify --strict "$bundle"; then
        exit 0
    fi
fi

stage=$(/usr/bin/mktemp -d "${bundle%/*}/.helfer.XXXXXX")
trap '/bin/rm -rf -- "$stage"' EXIT
built="$stage/Helfer.app"
previous="$stage/previous.app"
/bin/mkdir -p "$built/Contents/MacOS" "$built/Contents/Resources"
/bin/cp -X "$helpers/Helfer-Info.plist" "$built/Contents/Info.plist"
/bin/cp -X "$helpers/helfer-entrypoint.sh" "$built/Contents/MacOS/Helfer"
/bin/cp -X "$assets/safari-alarm.js" "$assets/safari-alarm.wav" "$built/Contents/Resources/"
/bin/chmod u+x "$built/Contents/MacOS/Helfer"
/usr/bin/codesign --sign - "$built"
/usr/bin/codesign --verify --strict "$built"

if [ -d "$bundle" ]; then /bin/mv "$bundle" "$previous"; fi
if ! /bin/mv "$built" "$bundle"; then
    if [ -d "$previous" ] && ! /bin/mv "$previous" "$bundle"; then
        trap - EXIT
        printf 'Die bisherige Helfer.app liegt unter %s.\n' "$previous" >&2
    fi
    exit 1
fi
