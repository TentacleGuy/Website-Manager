#!/bin/bash
set -euo pipefail
[ "$(id -u)" = 0 ] || { printf '%s\n' 'Diesen Helfer mit sudo starten.' >&2;exit 1; }
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
certificate="$root/data/certs/rootCA.pem"
[ -f "$certificate" ] || { printf '%s\n' 'Das lokale Stammzertifikat fehlt. Zuerst Installieren.sh als normale Benutzerin ausfuehren.' >&2;exit 1; }
command -v systemctl >/dev/null && systemctl is-active --quiet systemd-resolved || { printf '%s\n' 'Kein aktives systemd-resolved. Bitte vmm.test manuell an 127.0.0.1:1053 weiterleiten. Vorhandene DNS-Einstellungen wurden nicht ersetzt.' >&2;exit 1; }
config=/etc/systemd/resolved.conf.d/90-tentacle.conf
expected=$'[Resolve]\nDNS=127.0.0.1:1053\nDomains=~vmm.test'
if [ -e "$config" ] && [ "$(cat "$config")" != "$expected" ];then printf '%s\n' 'Die Tentacle-DNS-Datei wurde individuell angepasst. Bitte pruefen; sie wurde nicht ersetzt.' >&2;exit 1;fi
if command -v update-ca-certificates >/dev/null;then
    install -m 644 "$certificate" /usr/local/share/ca-certificates/tentacle-local.crt;update-ca-certificates
elif command -v update-ca-trust >/dev/null;then
    install -m 644 "$certificate" /etc/pki/ca-trust/source/anchors/tentacle-local.crt;update-ca-trust
else printf '%s\n' 'Kein unterstuetzter Zertifikatsspeicher gefunden. Bitte das oeffentliche rootCA.pem manuell als vertrauenswuerdig installieren.' >&2;exit 1;fi
mkdir -p /etc/systemd/resolved.conf.d
printf '%s\n' "$expected" > "$config";chmod 644 "$config"
systemctl restart systemd-resolved
printf '%s\n' 'Lokale Projektdomains und Stammzertifikat sind eingerichtet. Browser mit eigenem Zertifikatsspeicher ggf. separat konfigurieren.'
