#!/bin/sh
# Run with sudo on the macOS Docker host. Only vmm.test uses local CoreDNS.
set -eu
[ "$(uname -s)" = Darwin ] || { echo 'Nur für macOS.' >&2; exit 1; }
mkdir -p /etc/resolver
if [ -e /etc/resolver/vmm.test ]; then
  echo 'DNS-Regel existiert bereits; unverändert:'
  cat /etc/resolver/vmm.test
  exit 0
fi
printf 'nameserver 127.0.0.1\nport 53\n' > /etc/resolver/vmm.test
chmod 644 /etc/resolver/vmm.test
dscacheutil -flushcache
killall -HUP mDNSResponder
printf 'vmm.test wird jetzt über den lokalen VMM-DNS aufgelöst.\n'
