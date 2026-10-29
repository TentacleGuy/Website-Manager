#!/bin/bash
# This helper alone runs with administrator privileges.
set -euo pipefail
[ "$(/usr/bin/uname -s)" = Darwin ] && [ "$(/usr/bin/id -u)" -eq 0 ] || exit 1
[ "$#" -eq 1 ] && [ -f "$1" ] || { printf '%s\n' 'Lokales Stammzertifikat fehlt.' >&2; exit 1; }
expected=$'# Tentacle Website Manager local DNS\nnameserver 127.0.0.1\nport 1053'
resolver=/etc/resolver/vmm.test
if [ -e "$resolver" ] && [ "$(/bin/cat "$resolver")" != "$expected" ]; then
    printf '%s\n' 'Fuer vmm.test besteht bereits eine andere DNS-Regel. Bitte durch die IT pruefen lassen; sie wurde nicht ersetzt.' >&2
    exit 1
fi
/bin/mkdir -p /etc/resolver
if [ ! -e "$resolver" ]; then
    printf '%s\n' "$expected" > "$resolver"
    /bin/chmod 644 "$resolver"
fi
/usr/bin/security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$1"
/usr/bin/dscacheutil -flushcache
/usr/bin/killall -HUP mDNSResponder
printf '%s\n' 'Lokale Projektadressen und HTTPS sind eingerichtet.'
