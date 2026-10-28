"""Opt-in isolated Mac smoke check; never changes DNS or the system keychain."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen
import uuid

from build_macos_installer import NAME, ROOT, build


def run(*args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError(' '.join(map(str, args[:3])) + ':\n' + result.stdout[-2500:] + result.stderr[-2500:])
    return result.stdout


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    ident = 'tentacle-install-check-' + uuid.uuid4().hex[:10]
    image = ident + ':test'
    network = ident + '-network'
    build()
    with tempfile.TemporaryDirectory(prefix='mac-check-', dir=ROOT / 'dist') as temp:
        temp = Path(temp)
        run('/usr/bin/ditto', '-x', '-k', str(ROOT / 'dist' / (NAME + '.zip')), str(temp))
        root = temp / NAME / 'payload'
        # Exercise the spaces in the real macOS installation location.
        target = temp / 'Library/Application Support/Tentacle/WebsiteManager'
        target.parent.mkdir(parents=True)
        shutil.move(root, target)
        (target / '.env').write_text('VMM_HOST_DATA=' + str(target / 'data') + '\nVMM_BIND=127.0.0.1\n')
        compose = temp / 'smoke.json'
        network_created = False
        try:
            run('docker', 'build', '-t', image, str(target))
            run('docker', 'run', '--rm', '--mount', 'type=bind,source=' + str(target) + ',target=/workspace',
                '-w', '/workspace', image, 'python', 'scripts/installer_config.py',
                '--host-data', str(target / 'data'), '--dns-port', '1053')
            print('PASS packaged image and container-based configuration', flush=True)
            certs = target / 'data/certs'
            run('/usr/bin/security', 'verify-cert', '-N', '-L', '-c', str(certs / 'vmm.test.pem'),
                '-r', str(certs / 'rootCA.pem'), '-p', 'ssl', '-n', 'einrichtung.vmm.test')
            print('PASS native macOS HTTPS verification with explicit test root', flush=True)
            for file in (target / 'compose.yaml', target / 'infra/compose.gateway.yaml'):
                run('docker', 'compose', '--env-file', str(target / '.env'), '-f', str(file), 'config', '--quiet')
            config = json.loads((target / 'infra/compose.gateway.yaml').read_text())
            config['name'] = ident
            config['networks']['gateway']['name'] = network
            config['services']['traefik']['command'].append('--providers.docker.constraints=Label(`tentacle.install-check`, `' + ident + '`)')
            manager_port, http_port, tls_port, dns_port = [free_port() for _ in range(4)]
            config['services']['traefik']['ports'] = [f'127.0.0.1:{http_port}:8084', f'127.0.0.1:{tls_port}:8184']
            config['services']['traefik']['volumes'] = [
                '/var/run/docker.sock:/var/run/docker.sock:ro',
                str(target / 'infra/dynamic') + ':/etc/traefik/dynamic:ro', str(certs) + ':/certs:ro']
            config['services']['dns']['ports'] = [f'127.0.0.1:{dns_port}:53/udp', f'127.0.0.1:{dns_port}:53/tcp']
            config['services']['dns']['volumes'] = [str(target / 'infra/Corefile') + ':/etc/coredns/Corefile:ro']
            config['services']['manager'] = {
                'image': image, 'ports': [f'127.0.0.1:{manager_port}:8090'],
                'environment': {'VMM_LISTEN': '0.0.0.0', 'VMM_DATA': '/data', 'VMM_HOST_DATA': str(target / 'data')},
                'volumes': [str(target / 'data') + ':/data', '/var/run/docker.sock:/var/run/docker.sock'],
                'networks': ['gateway']}
            compose.write_text(json.dumps(config))
            run('docker', 'network', 'create', network)
            network_created = True
            run('docker', 'compose', '-p', ident, '-f', str(compose), 'up', '-d')
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    with urlopen(f'http://127.0.0.1:{manager_port}/api/health', timeout=5) as response:
                        assert json.load(response)['docker'] is True
                    break
                except Exception:
                    time.sleep(1)
            else:
                raise RuntimeError('The isolated manager did not start.')
            with urlopen(f'http://127.0.0.1:{manager_port}/assets/tentacle-logo.png', timeout=5) as response:
                assert hashlib.sha256(response.read()).digest() == hashlib.sha256((target / 'app/static/assets/tentacle-logo.png').read_bytes()).digest()
            print('PASS manager health and packaged branding', flush=True)
            assert run('/usr/bin/dig', '@127.0.0.1', '-p', str(dns_port), 'einrichtung.vmm.test', 'A', '+short', '+time=3', '+tries=5').strip() == '127.0.0.1'
            assert run('/usr/bin/dig', '+tcp', '@127.0.0.1', '-p', str(dns_port), 'einrichtung.vmm.test', 'A', '+short', '+time=3', '+tries=5').strip() == '127.0.0.1'
            print('PASS wildcard DNS over UDP and TCP', flush=True)
            # HTTP errors for an unknown project are expected; TLS must verify.
            tls_code = run('/usr/bin/curl', '--noproxy', '*', '-sS', '--retry', '2', '--retry-connrefused', '--connect-timeout', '3', '--max-time', '10',
                           '--cacert', str(certs / 'rootCA.pem'), '--resolve', f'einrichtung.vmm.test:{tls_port}:127.0.0.1',
                           '-o', '/dev/null', '-w', '%{http_code}', f'https://einrichtung.vmm.test:{tls_port}/')
            assert tls_code in ('404', '503'), tls_code
            print('PASS HTTPS through current Traefik with full certificate validation', flush=True)
        except Exception:
            if compose.exists():
                print(run('docker', 'compose', '-p', ident, '-f', str(compose), 'logs', '--tail', '30', 'traefik'), flush=True)
            raise
        finally:
            if compose.exists():
                run('docker', 'compose', '-p', ident, '-f', str(compose), 'down')
            if network_created:
                run('docker', 'network', 'rm', network)
            run('docker', 'image', 'rm', image)


if __name__ == '__main__':
    main()
