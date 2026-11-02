import unittest,sys,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import project_service as ps
import extension_service as es

class ManagementTests(unittest.TestCase):
    def test_admin_validation(self):
        with self.assertRaises(ValueError):ps.admin_settings({'username':'admin','email':'test@example.com','password':'weak'})
        self.assertEqual(ps.admin_settings({'username':'admin','email':'test@example.com','password':'a-very-long-secret'})['username'],'admin')

    def test_child_key_inherits_account_but_overrides_key(self):
        root=es.save_license({'provider':'yootheme','label':'Unlimited','username':'my-account','password':'account-pass','key':'global','extra':{'customer':'one'},'owner':'Agency'})
        child=es.save_license({'provider':'yootheme','label':'Customer website','parent':root,'project':'child-site','key':'site-key'})
        value=es.license_value(child,'yootheme','child-site')
        self.assertEqual(value['username'],'my-account');self.assertEqual(value['key'],'site-key');self.assertEqual(value['owner'],'Agency')
        es.save_license({'id':root,'provider':'yootheme','label':'Unlimited','username':'changed-account','password':'account-pass','extra':{'customer':'two'}})
        self.assertEqual(es.license_value(child)['username'],'changed-account');self.assertEqual(es.license_value(child)['extra']['customer'],'two')
        with self.assertRaises(ValueError):es.license_value(child,project_name='wrong-site')

    def test_zip_metadata_without_executing_package(self):
        import tempfile,zipfile
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'extension.zip'
            with zipfile.ZipFile(path,'w') as z:z.writestr('sample/sample.php','<?php\n/*\nPlugin Name: My Sample\nVersion: 2.3.4\n*/')
            info=es.inspect_upload(path);self.assertEqual(info['cms'],'wordpress');self.assertEqual(info['version'],'2.3.4');self.assertEqual(info['element'],'sample')

    def test_single_update_uses_only_selected_installed_extension(self):
        with patch.object(es,'project',return_value={'cms':'wordpress'}), patch.object(es,'installed',return_value=[{'element':'hello-dolly','kind':'plugin'}]), patch('operations.snapshot') as backup, patch('operations.exec_php',return_value=b'Updated') as execute:
            self.assertEqual(es.update_single('demo','hello-dolly'),'Updated')
            backup.assert_called_once_with('demo')
            self.assertEqual(execute.call_args.args[1],['wp','--allow-root','plugin','update','hello-dolly'])
            with self.assertRaises(ValueError):es.update_single('demo','uninstalled')
            self.assertEqual(execute.call_count,1)
