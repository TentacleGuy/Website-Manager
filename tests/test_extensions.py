"""Source resolution, authentication, isolation and deferred installs without Docker/network."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import extension_service as ext
from store import db

class ExtensionsTests(unittest.TestCase):
    def make_source(self,**overrides):
        return ext.save_source(dict(name='Test extension',cms='wordpress',kind='plugin',provider='test-provider',element='my-plugin',source_type='update_xml',url='https://vendor.example/update.xml',auth_type='query',auth_parameter='dlid',**overrides))

    def test_auth_formats_and_preserve_query(self):
        cred={'key':'abc &=','username':'alice','password':'pw','extra':{'customer':'123'}}
        url,headers=ext.authenticated('https://vendor.example/file?dlid=old&x=1',{'auth_type':'query','auth_parameter':'dlid'},cred)
        self.assertIn('x=1',url);self.assertEqual(url.count('dlid='),1);self.assertIn('customer=123',url)
        self.assertEqual(ext.authenticated('https://vendor.example',{'auth_type':'bearer'},cred)[1]['Authorization'],'Bearer abc &=')
        self.assertEqual(ext.authenticated('https://vendor.example',{'auth_type':'basic'},cred)[1]['Authorization'],'Basic YWxpY2U6cHc=')
        self.assertEqual(ext.authenticated('https://vendor.example',{'auth_type':'headers','auth_parameter':'X-Key'},cred)[1]['X-Key'],'abc &=')
        with self.assertRaises(ValueError):ext.authenticated('https://vendor.example',{'auth_type':'headers'},{'key':'a\nb'})

    def test_xml_selects_compatible_stable_version(self):
        xml=b'<updates><update><version>5.0.0</version><downloads><downloadurl>https://cdn.example/5.zip</downloadurl></downloads><php_minimum>8.4.0</php_minimum><targetplatform name="joomla" version="6.*"/></update><update><version>4.0.0</version><downloads><downloadurl>https://cdn.example/4.zip</downloadurl></downloads><targetplatform name="joomla" version="5.*"/></update></updates>'
        values=ext.parse_updates(xml,'https://vendor.example/update.xml')
        self.assertEqual(values[0]['version'],'5.0.0')
        self.assertTrue(ext.compatible(values[0],{'cms':'joomla','version':'6.2.0','php':'8.4'}))
        self.assertFalse(ext.compatible(values[0],{'cms':'joomla','version':'5.4.0','php':'8.4'}))
        self.assertFalse(ext.compatible(values[0],{'cms':'joomla','version':'6.2.0','php':'8.3'}))

    def test_auth_only_for_metadata_when_requested(self):
        ident=self.make_source();lic=ext.save_license({'provider':'test-provider','label':'Test','key':'my-key'})
        data=b'<updates><update><version>1.2</version><downloads><downloadurl>https://vendor.example/package.zip</downloadurl></downloads></update></updates>'
        with patch('extension_service.remote',return_value=io.BytesIO(data)) as remote:
            ext.check(ident,lic);self.assertIsNone(remote.call_args.args[1])
        s=ext.source(ident);s['auth_metadata']=True;ext.save_source(s)
        with patch('extension_service.remote',return_value=io.BytesIO(data)) as remote:
            ext.check(ident,lic);self.assertEqual(remote.call_args.args[1]['auth_type'],'query')

    def test_version_archive_reused_and_corruption_rejected(self):
        ident=self.make_source(source_type='upload') if False else ext.save_source({'name':'Archive','provider':'test-provider','cms':'wordpress','kind':'plugin','element':'archive','source_type':'upload','auth_type':'none'})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'package.zip'
            with zipfile.ZipFile(path,'w') as z:z.writestr('archive/archive.php','<?php /* Plugin Name: Archive */')
            first=ext.register_package(path,ext.source(ident),'1.0');self.assertEqual(ext.register_package(path,ext.source(ident),'1.0'),first)
            second=ext.register_package(path,ext.source(ident),'2.0');self.assertNotEqual(first,second)
            self.assertEqual(ext.download_package(ident),second)
            with db() as c:filename=c.execute('SELECT filename FROM extensions WHERE id=?',(second,)).fetchone()['filename']
            (ext.DATA/'extensions'/filename).write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError,'Prüfsumme'):ext.download_package(ident)

    def test_wordpress_org_plugin_and_theme(self):
        for kind in ('plugin','theme'):
            ident=ext.save_source({'name':'WP '+kind,'provider':'wordpress.org','cms':'wordpress','kind':kind,'element':'hello-dolly','source_type':'wordpress_org','auth_type':'none'})
            data={'version':'2.0','download_link':'https://downloads.wordpress.org/plugin/hello-dolly.2.0.zip','versions':{'1.0':'https://downloads.wordpress.org/plugin/hello-dolly.1.0.zip','trunk':'https://downloads.wordpress.org/plugin/hello-dolly.zip'},'requires_php':'7.4'}
            with patch('extension_service.remote',return_value=io.BytesIO(json.dumps(data).encode())) as remote:
                ext.check(ident)
                self.assertIn('action='+kind+'_information',remote.call_args.args[0])
                self.assertEqual(ext.source(ident)['available'][0]['version'],'2.0')

    def test_license_provider_mismatch_and_plain_migration(self):
        lic=ext.save_license({'provider':'another','label':'Other','key':'visible-key','username':'alice','password':' plain ','extra':{'site':'x'}})
        with db() as c:raw=c.execute('SELECT secret FROM licenses WHERE id=?',(lic,)).fetchone()['secret']
        self.assertEqual(json.loads(raw)['password'],' plain ')
        with self.assertRaises(ValueError):ext.license_value(lic,'test-provider')
        try:import cryptography
        except ImportError:self.skipTest('Legacy migration requires cryptography in the Docker runtime')
        from store import cipher
        self.assertEqual(ext.decode_secret(cipher().encrypt(b'old-key').decode())['key'],'old-key')
        self.assertEqual(ext.decode_secret(cipher().encrypt(b'123456').decode())['key'],'123456')
        self.assertEqual(ext.decode_secret('123456')['key'],'123456')

    def test_pending_install_failure_is_not_reported_as_success(self):
        with patch('extension_service.db') as mockdb:
            mockdb.return_value.__enter__.return_value.execute.return_value.fetchall.return_value=[{'source':'x'}]
            with patch('extension_service.install_plan',side_effect=ValueError('License invalid')):
                with self.assertRaisesRegex(ValueError,'License invalid'):ext.process_pending('demo')

    def test_reject_wrong_cms_before_project_created(self):
        ident=self.make_source()
        with self.assertRaises(ValueError):ext.validate_plans('joomla',[{'source':ident}])

if __name__=='__main__':unittest.main()

class SiteLicenseTests(unittest.TestCase):
    def test_project_bound_key_cannot_be_used_on_another_project(self):
        ident=ext.save_source({'name':'Site-key plugin','provider':'site-provider','cms':'wordpress','kind':'plugin','element':'site-plugin','source_type':'upload','auth_type':'none'})
        lic=ext.save_license({'provider':'site-provider','label':'Only alpha','key':'site-only-key','project':'alpha','site':'https://alpha.example','source':ident})
        self.assertEqual(ext.validate_plans('wordpress',[{'source':ident,'license':lic}],'alpha')[0]['license'],lic)
        with self.assertRaisesRegex(ValueError,'anderes Projekt'):ext.validate_plans('wordpress',[{'source':ident,'license':lic}],'beta')
        self.assertEqual(ext.validate_plans('wordpress',[{'source':ident}],'alpha')[0]['license'],lic)
        self.assertIsNone(ext.validate_plans('wordpress',[{'source':ident,'license':''}],'alpha')[0]['license'])
        with self.assertRaisesRegex(ValueError,'Standard'):ext.save_source({**ext.source(ident),'license':lic})

    def test_extension_binding_and_project_slug_validation(self):
        first=ext.save_source({'name':'First','provider':'same-provider','cms':'wordpress','kind':'plugin','element':'first','source_type':'upload','auth_type':'none'})
        second=ext.save_source({'name':'Second','provider':'same-provider','cms':'wordpress','kind':'plugin','element':'second','source_type':'upload','auth_type':'none'})
        lic=ext.save_license({'provider':'same-provider','label':'First only','key':'x','source':first})
        with self.assertRaisesRegex(ValueError,'andere Erweiterung'):ext.validate_plans('wordpress',[{'source':second,'license':lic}],'alpha')
        with self.assertRaises(ValueError):ext.save_license({'provider':'same-provider','label':'Invalid','key':'x','project':'../escape'})
