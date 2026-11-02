import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _temp=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_temp.name
import extension_service as ext
class CMSInventoryTests(unittest.TestCase):
    def inventory(self,core):
        def execute(p,args,**kwargs):
            if 'check-update' in args:
                if isinstance(core,Exception):raise core
                return json.dumps(core).encode()
            return b'[{"name":"sample","version":"1.0","status":"active","update":"none"}]'
        with patch.object(ext,'project',return_value={'cms':'wordpress','version':'7.1.3'}),patch('operations.write_tools'),patch('operations.exec_php',side_effect=execute),patch.object(ext,'save_inventory'):
            return ext.installed('fixture')
    def test_core_update_is_separate_and_counted_once(self):
        items=self.inventory([{'version':'7.1.4'}]);core=items[0]
        self.assertTrue(ext.is_core_update(core));self.assertEqual(core['version'],'7.1.3');self.assertEqual(core['available'],'7.1.4')
        self.assertEqual(ext.inventory_counts(items),{'updates':1,'extension_updates':0,'core_updates':1})
    def test_no_available_core_update_is_explicitly_current(self):
        core=self.inventory([])[0];self.assertEqual(core['update'],'none');self.assertEqual(core['available'],'')
    def test_failed_core_check_does_not_claim_current(self):
        core=self.inventory(RuntimeError('network failure'))[0];self.assertEqual(core['update'],'unknown');self.assertIn('network failure',core['check_error'])
    def test_joomla_core_row_is_still_detected_without_explicit_core_flag(self):
        self.assertTrue(ext.is_core_update({'kind':'file','element':'joomla'}))
