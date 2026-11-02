import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_macos_installer
import installer_config


class MacInstallerTests(unittest.TestCase):
    def test_mac_paths_and_unprivileged_dns_port(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            host = "/Users/Test Person/Library/Application Support/Tentacle/WebsiteManager/data"
            (root / '.env').write_text('VMM_HOST_DATA=' + host + '\nVMM_BIND=127.0.0.1\n')
            installer_config.configure(root, host, dns_port=1053)
            config = json.loads((root / 'infra/compose.gateway.yaml').read_text())
            self.assertEqual(config['services']['dns']['ports'], ['127.0.0.1:1053:53/udp', '127.0.0.1:1053:53/tcp'])
            self.assertIn('127.0.0.1:8084:8084', config['services']['traefik']['ports'])
            self.assertEqual((root / '.env').read_text(), 'VMM_HOST_DATA=' + host + '\nVMM_BIND=127.0.0.1\n')
            before = (root / 'data/certs/rootCA.pem').read_bytes()
            installer_config.configure(root, host, dns_port=1053)
            self.assertEqual((root / 'data/certs/rootCA.pem').read_bytes(), before)

    def test_mac_distribution_is_executable_and_contains_no_machine_data(self):
        with tempfile.TemporaryDirectory() as temp:
            output = build_macos_installer.build(output=Path(temp) / 'setup.zip')
            prefix = build_macos_installer.NAME + '/'
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                self.assertIn(prefix + 'payload/app/static/assets/tentacle-logo.png', names)
                for name in names:
                    self.assertFalse(any(part in {'data', '.git', '.venv', '__pycache__', '.env', '.DS_Store'} for part in Path(name).parts))
                    self.assertNotIn('..', Path(name).parts)
                    self.assertFalse(name.endswith(('.ps1', '.cmd')))
                for name in ('Installieren.command', 'Starten.command', 'Einrichtung fortsetzen.command', 'Systemeinrichtung.sh'):
                    info = archive.getinfo(prefix + name)
                    self.assertTrue((info.external_attr >> 16) & stat.S_IXUSR)
                    self.assertNotIn(b'\r\n', archive.read(info))

    @unittest.skipUnless(sys.platform == 'darwin', 'Uses macOS system Bash')
    def test_scripts_parse_in_the_macos_system_bash(self):
        for path in (ROOT / 'installer/macos').iterdir():
            if path.suffix in ('.sh', '.command'):
                subprocess.run(['/bin/bash', '-n', str(path)], check=True, capture_output=True)

    @unittest.skipUnless(sys.platform == 'darwin', 'Uses macOS system Bash')
    def test_macos_version_comparison_and_current_hardware(self):
        library = ROOT / 'installer/macos/Gemeinsam.sh'
        script = '''
set -eu
. "$1"
version_at_least 26.2 14.0
version_at_least 14.7.1 14.7
version_at_least 15 15.0.0
! version_at_least 14.9 15
! version_at_least 14.7.1 14.7.2
case "$(mac_architecture)" in arm64|amd64) ;; *) exit 1 ;; esac
'''
        subprocess.run(['/bin/bash', '-c', script, 'test', str(library)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
