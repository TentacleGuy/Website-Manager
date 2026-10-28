"""Fresh local desktop installation configuration, executed inside Docker."""
import argparse
import datetime
import json
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from setup import generate


def configure(root, host_data, dns_port=53):
    if not 1 <= dns_port <= 65535:
        raise ValueError('Ungueltiger lokaler DNS-Port.')
    env = root / '.env'
    if not env.is_file() or env.read_text() != 'VMM_HOST_DATA=' + host_data + '\nVMM_BIND=127.0.0.1\n':
        raise ValueError('Die vorhandene .env passt nicht zur lokalen Installation.')
    data = generate(root, '127.0.0.1')
    path = root / 'infra/compose.gateway.yaml'
    gateway = json.loads(path.read_text())
    gateway['name'] = 'tentacle-gateway'
    # Older Traefik Docker providers cannot negotiate the API used by Docker 29+.
    gateway['services']['traefik']['image'] = 'traefik:v3.7.14'
    gateway['services']['dns']['ports'] = [str(dns_port) + ':53/udp', str(dns_port) + ':53/tcp']
    for service in gateway['services'].values():
        service['ports'] = [p if p.startswith('127.0.0.1:') else '127.0.0.1:' + p for p in service['ports']]
    path.write_text(json.dumps(gateway, indent=2) + '\n')
    certs = data / 'certs'
    expected = [certs / name for name in ('rootCA.pem', 'vmm.test.pem', 'vmm.test-key.pem')]
    if any(p.exists() for p in expected) and not all(p.exists() for p in expected):
        raise ValueError('Unvollstaendige Zertifikate in data/certs; bitte pruefen.')
    if not all(p.exists() for p in expected):
        now = datetime.datetime.now(datetime.timezone.utc)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Tentacle Local Projects CA')])
        ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
              .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - datetime.timedelta(minutes=5))
              .not_valid_after(now + datetime.timedelta(days=3650))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
              .add_extension(x509.NameConstraints(permitted_subtrees=[x509.DNSName('vmm.test')], excluded_subtrees=None), critical=True)
              .sign(ca_key, hashes.SHA256()))
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        leaf = (x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'vmm.test')]))
                .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(minutes=5))
                .not_valid_after(now + datetime.timedelta(days=365))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName([x509.DNSName('vmm.test'), x509.DNSName('*.vmm.test')]), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .sign(ca_key, hashes.SHA256()))
        expected[0].write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        expected[1].write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
        expected[2].write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        expected[2].chmod(0o600)
        # The CA private key is deliberately never persisted.
    leaf = x509.load_pem_x509_certificate(expected[1].read_bytes())
    if leaf.not_valid_after_utc <= datetime.datetime.now(datetime.timezone.utc):
        raise ValueError('Das lokale HTTPS-Zertifikat ist abgelaufen. Zertifikate erneuern; siehe Anleitung.')
    ca = x509.load_pem_x509_certificate(expected[0].read_bytes())
    (certs / 'rootCA.cer').write_bytes(ca.public_bytes(serialization.Encoding.DER))
    (root / 'infra/dynamic/tls.yaml').write_text(json.dumps({'tls': {'certificates': [{
        'certFile': '/certs/vmm.test.pem', 'keyFile': '/certs/vmm.test-key.pem'}]}}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-data', required=True)
    parser.add_argument('--dns-port', type=int, default=53)
    args = parser.parse_args()
    configure(Path(__file__).resolve().parents[1], args.host_data, args.dns_port)
