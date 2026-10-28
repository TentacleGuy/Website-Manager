import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import installer_config
import build_windows_installer


class WindowsInstallerTests(unittest.TestCase):
    def test_clean_local_config_and_certificate_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            host = 'C:/Users/Test Person/AppData/Local/Tentacle/WebsiteManager/data'
            (root / '.env').write_text('VMM_HOST_DATA=' + host + '\nVMM_BIND=127.0.0.1\n')
            installer_config.configure(root, host)
            gateway = json.loads((root / 'infra/compose.gateway.yaml').read_text())
            self.assertEqual(gateway['services']['traefik']['image'], 'traefik:v3.7.14')
            for service in gateway['services'].values():
                self.assertTrue(all(p.startswith('127.0.0.1:') for p in service['ports']))
            certs = root / 'data/certs'
            ca = x509.load_pem_x509_certificate((certs / 'rootCA.pem').read_bytes())
            self.assertEqual(x509.load_der_x509_certificate((certs / 'rootCA.cer').read_bytes()), ca)
            cert = x509.load_pem_x509_certificate((certs / 'vmm.test.pem').read_bytes())
            ca.public_key().verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
            self.assertEqual(cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName), ['vmm.test', '*.vmm.test'])
            constraints = ca.extensions.get_extension_for_class(x509.NameConstraints)
            self.assertTrue(constraints.critical)
            self.assertEqual(constraints.value.permitted_subtrees, [x509.DNSName('vmm.test')])
            self.assertFalse((certs / 'rootCA-key.pem').exists())
            before = (certs / 'vmm.test.pem').read_bytes()
            (root / 'data/keep.txt').write_text('existing project')
            installer_config.configure(root, host)
            self.assertEqual(before, (certs / 'vmm.test.pem').read_bytes())
            self.assertEqual((root / 'data/keep.txt').read_text(), 'existing project')

    def test_existing_environment_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.env').write_text('VMM_HOST_DATA=/existing\nVMM_BIND=0.0.0.0\n')
            with self.assertRaises(ValueError):
                installer_config.configure(root, 'C:/different/data')
            self.assertIn('/existing', (root / '.env').read_text())
            self.assertFalse((root / 'infra').exists())

    def test_partial_certificates_are_never_silently_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.env').write_text('VMM_HOST_DATA=C:/VMM/data\nVMM_BIND=127.0.0.1\n')
            certs = root / 'data/certs'
            certs.mkdir(parents=True)
            (certs / 'rootCA.pem').write_text('existing CA')
            with self.assertRaises(ValueError):
                installer_config.configure(root, 'C:/VMM/data')
            self.assertEqual((certs / 'rootCA.pem').read_text(), 'existing CA')

    def test_distribution_excludes_local_secrets_and_includes_all_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            output = build_windows_installer.build(output=Path(temp) / 'setup.zip')
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                prefix = build_windows_installer.NAME + '/'
                self.assertIn(prefix + 'Installieren.cmd', names)
                self.assertIn(prefix + 'payload/app/static/assets/tentacle-logo.png', names)
                self.assertIn(prefix + 'payload/scripts/installer_config.py', names)
                self.assertFalse(any('/data/' in n or n.endswith('/.env') or '/.git/' in n or '__pycache__' in n or '/tls.yaml' in n for n in names))
                for name in names:
                    self.assertNotIn('..', Path(name).parts)
            self.assertTrue(output.with_suffix('.zip.sha256').exists())


if __name__ == '__main__':
    unittest.main()
