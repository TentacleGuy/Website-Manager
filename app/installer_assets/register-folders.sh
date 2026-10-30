#!/bin/bash
# Per-user desktop integration; no administrator permissions or background service.
set -euo pipefail
root=${1:?Installationsordner fehlt}
root=$(cd "$root" && pwd -P)
helper="$root/app/installer_assets/folder-opener.sh"
[ -f "$helper" ] || { printf '%s\n' 'Projektordner-Helfer fehlt.' >&2;exit 1; }
[[ "$root" != *$'\n'* && "$root" != *$'\r'* ]] || exit 1
mkdir -p "$root/data"
case $(uname -s) in
    Darwin)
        app="$HOME/Applications/Tentacle Projektordner.app"
        marker="$app/Contents/Resources/handler-path.txt"
        if [ ! -f "$marker" ] || [ "$(cat "$marker")" != "1:$helper" ]; then
            mkdir -p "$HOME/Applications"
            escaped=${helper//\\/\\\\};escaped=${escaped//\"/\\\"}
            /usr/bin/osacompile -o "$app" - <<APPLESCRIPT
on open location projectURL
    do shell script "/bin/bash " & quoted form of "$escaped" & " " & quoted form of projectURL
end open location
APPLESCRIPT
            plist="$app/Contents/Info.plist"
            /usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier com.tentacle.project-folder' "$plist" 2>/dev/null || /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string com.tentacle.project-folder' "$plist"
            /usr/libexec/PlistBuddy -c 'Delete :CFBundleURLTypes' "$plist" 2>/dev/null || true
            /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes array' "$plist"
            /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0 dict' "$plist"
            /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0:CFBundleURLName string Tentacle Projektordner' "$plist"
            /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0:CFBundleURLSchemes array' "$plist"
            /usr/libexec/PlistBuddy -c 'Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string tentacle-project' "$plist"
            printf '1:%s\n' "$helper" > "$marker"
        fi
        /usr/bin/codesign --verify "$app" 2>/dev/null || /usr/bin/codesign --force --sign - "$app"
        /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$app"
        printf '%s\n' '{"platform":"macos","scheme":"tentacle-project","version":1}' > "$root/data/desktop-integration.json"
        ;;
    Linux)
        command -v xdg-mime >/dev/null && command -v xdg-open >/dev/null && command -v curl >/dev/null || { printf '%s\n' 'Projektordner-Anbindung benoetigt curl, xdg-mime und xdg-open in einer Desktop-Sitzung.' >&2;exit 1; }
        applications="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
        mkdir -p "$applications"
        # First escape the quoted Exec argument, then the desktop-entry string.
        escaped=${helper//\\/\\\\};escaped=${escaped//\"/\\\"};escaped=${escaped//\$/\\\$};escaped=${escaped//\`/\\\`};escaped=${escaped//%/%%};escaped=${escaped//\\/\\\\}
        cat > "$applications/tentacle-project-folder.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Tentacle Projektordner
Exec=/bin/bash "$escaped" %u
Terminal=false
NoDisplay=true
MimeType=x-scheme-handler/tentacle-project;
DESKTOP
        xdg-mime default tentacle-project-folder.desktop x-scheme-handler/tentacle-project
        printf '%s\n' '{"platform":"linux","scheme":"tentacle-project","version":1}' > "$root/data/desktop-integration.json"
        ;;
    *) printf '%s\n' 'Betriebssystem wird nicht unterstuetzt.' >&2;exit 1 ;;
esac
