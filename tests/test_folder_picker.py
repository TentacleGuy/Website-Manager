import os,sys,tempfile,unittest,json,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _temp=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_temp.name
import folder_picker as picker
class PickerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'desktop-integration.json').write_text('{"scheme":"tentacle-project"}')
        for p in (patch.object(picker,'DATA',self.root),patch.dict(picker.PENDING,{},clear=True)):
            p.start();self.addCleanup(p.stop)
    def test_native_choice_only_returns_path_without_applying_settings(self):
        value=picker.create();self.assertTrue(value['url'].endswith(value['id']))
        picker.complete(value['id'],'C:/Sites With Spaces')
        self.assertEqual(picker.result(value['id'])['path'],'C:\\Sites With Spaces')
        self.assertFalse((self.root/'storage').exists())
        with self.assertRaises(ValueError):picker.complete(value['id'],'/second')
    def test_repair_request_is_narrow_and_records_callback_without_private_path(self):
        request=picker.create('repair');self.assertEqual(request['url'],'tentacle-project://repair/'+request['id'])
        picker.complete(request['id'],'/private/Selected')
        report=(self.root/'desktop-access.json').read_text()
        self.assertNotIn('/private/Selected',report);self.assertEqual(json.loads(report)['status'],'selected')
        with self.assertRaises(ValueError):picker.create('arbitrary-command')
    def test_cancellation_and_expired_requests(self):
        token=picker.create()['id'];picker.complete(token,'');self.assertEqual(picker.result(token)['status'],'cancelled')
        picker.PENDING[token]['expires']=time.time()-1
        with self.assertRaises(ValueError):picker.result(token)
    def test_newlines_relative_paths_and_unknown_tokens_are_rejected(self):
        token=picker.create()['id']
        for path in ('relative','/tmp\nother','/tmp\x00other'):
            with self.assertRaises(ValueError):picker.complete(token,path)
        with self.assertRaises(ValueError):picker.complete('f'*32,'/tmp')
    def test_storage_paths_return_without_recursive_usage_scan(self):
        import storage_service as storage
        from unittest.mock import MagicMock
        self.addCleanup(storage._USAGE_BUSY.clear)
        with patch.object(storage,'DATA',self.root),patch('storage_service.settings',return_value={}),patch.dict(storage._USAGE,{},clear=True),patch.object(Path,'rglob',side_effect=AssertionError('view must not scan files')),patch.object(storage.threading,'Thread') as thread:
            storage._USAGE_BUSY.clear();value=storage.status();storage.status()
        self.assertEqual(len(value['areas']),5);self.assertTrue(all(x['used'] is None for x in value['areas']));self.assertEqual(thread.call_count,1)
    def test_linux_helper_posts_literal_choice_to_local_callback(self):
        import subprocess
        root=self.root;binary=root/'bin';binary.mkdir();folder=root/'Selected folder';folder.mkdir()
        tools={'uname':'printf "Linux\\n"','zenity':'printf "%s" "$TEST_FOLDER"','curl':'printf "%s\\n" "$@" > "$TEST_CALLBACK"'}
        for name,body in tools.items():
            file=binary/name;file.write_text('#!/bin/bash\n'+body+'\n');file.chmod(0o755)
        env={**os.environ,'PATH':str(binary)+os.pathsep+os.environ['PATH'],'TEST_FOLDER':str(folder),'TEST_CALLBACK':str(root/'callback')}
        helper=Path(__file__).resolve().parents[1]/'app/installer_assets/folder-opener.sh';token='a'*32
        subprocess.run(['bash',str(helper),'tentacle-project://choose/'+token],env=env,capture_output=True,check=True)
        value=(root/'callback').read_text();self.assertIn(str(folder),value);self.assertIn('http://127.0.0.1:8090/api/folder-picker/'+token+'/complete',value)
        self.assertIn('X-VMM-Request: 1',value)
