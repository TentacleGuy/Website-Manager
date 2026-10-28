import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('setup',Path(__file__).resolve().parents[1]/'scripts'/'setup.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

class SetupTests(unittest.TestCase):
    def test_every_php_has_http_tls_and_wildcard_dns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);setup.generate(root,'192.168.2.123')
            gateway=json.loads((root/'infra'/'compose.gateway.yaml').read_text())
            self.assertEqual(gateway['networks']['gateway'],{'name':'vmm-gateway','external':True})
            ports=gateway['services']['traefik']['ports']
            self.assertIn('127.0.0.1:8091:8091',ports)
            self.assertIn('8082:8082',ports);self.assertIn('8182:8182',ports)
            self.assertEqual(len(ports),2*len(setup.PHP)+1)
            self.assertIn('192.168.2.123',(root/'infra'/'Corefile').read_text())
            dynamic=json.loads((root/'infra'/'dynamic'/'warmup.yaml').read_text())
            self.assertEqual(dynamic['http']['routers']['vmm-warmup-tls']['tls'],{})
            self.assertIn('[.]vmm[.]test',dynamic['http']['routers']['vmm-warmup-php']['rule'])
            self.assertNotIn('PASSWORD',(root/'.env').read_text())

if __name__=='__main__':unittest.main()
