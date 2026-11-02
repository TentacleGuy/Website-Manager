import json,os,secrets,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _temp=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_temp.name
import project_workspace as workspace
from store import db
class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        p=patch.object(workspace,'DATA',self.root);p.start();self.addCleanup(p.stop)
        self.name='workspace-'+secrets.token_hex(4)
        with db() as c:c.execute("INSERT INTO projects(slug,cms,php,status,created,version,storage) VALUES(?,'joomla','8.4','running',0,'5.0','shared')",(self.name,))
    def test_cached_inventory_does_not_execute_php(self):
        root=self.root/'projects'/self.name;root.mkdir(parents=True);(root/'extension-inventory.json').write_text('{"checked":42,"items":[{"name":"Fixture"}]}')
        with patch('operations.exec_php') as execute:self.assertEqual(workspace.cache(self.name)['checked'],42)
        execute.assert_not_called()
    def test_detected_version_replaces_old_metadata(self):
        root=self.root/'projects'/self.name/'site';(root/'administrator/manifests/files').mkdir(parents=True)
        (root/'configuration.php').write_text('<?php');(root/'administrator/manifests/files/joomla.xml').write_text('<version>5.4.10</version>')
        rows=workspace.project_rows();self.assertEqual(next(p for p in rows if p['slug']==self.name)['version'],'5.4.10')
    def test_restore_never_reuses_existing_directory(self):
        (self.root/'projects'/self.name).mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'belegt'):workspace.restore_export('fixture.zip',self.name)
    def test_restore_rejects_unsafe_zip_before_reserving_project(self):
        (self.root/'exports').mkdir();path=self.root/'exports/unsafe.zip'
        with zipfile.ZipFile(path,'w') as z:z.writestr('../outside','unsafe')
        name='restore-'+secrets.token_hex(4)
        with self.assertRaises(ValueError):workspace.restore_export(path.name,name)
        with db() as c:self.assertIsNone(c.execute('SELECT slug FROM projects WHERE slug=?',(name,)).fetchone())
    def test_default_user_is_only_a_manager_setting(self):
        root=self.root/'projects'/self.name;root.mkdir(parents=True)
        with patch('operations.folder',return_value=root),patch('project_service.user_action',return_value=[{'ID':42}]),patch('operations.exec_php') as execute:
            workspace.account(self.name,{'action':'default','id':42})
        execute.assert_not_called();self.assertEqual(workspace.default_user(self.name),42)
    def test_login_token_is_short_lived_and_not_stored_as_plaintext(self):
        root=self.root/'projects'/self.name;(root/'site').mkdir(parents=True)
        with patch('operations.folder',return_value=root),patch('project_service.user_action',return_value=[{'ID':42}]):value=workspace.account(self.name,{'action':'login','id':42})
        token=value['url'].split('token=')[1];file=next((root/'tools').glob('login-*.json'))
        self.assertNotIn(token,file.read_text());self.assertEqual(json.loads(file.read_text())['id'],42)
        self.assertTrue((root/'site/vmm-manager-login.php').exists())
    def test_zip_restore_imports_into_new_project_and_keeps_archive(self):
        name='restored-'+secrets.token_hex(4);root=self.root/'projects'/name
        exports=self.root/'exports';exports.mkdir();source=exports/'fixture.zip'
        with zipfile.ZipFile(source,'w') as z:
            z.writestr('project.json',json.dumps({'cms':'joomla','php':'8.4','version':'5.4.10'}))
            z.writestr('database.sql','CREATE TABLE fixture(id INT);')
            z.writestr('site/configuration.php','<?php class JConfig {}')
            z.writestr('site/index.php','fixture site')
        calls=[]
        def queue(resource,kind,fn):
            self.assertEqual((resource,kind),(name,'restore-export'));fn();return 'test-job'
        with patch.object(workspace,'job',side_effect=queue),patch('operations.folder',return_value=root),patch('operations.write_tools'),patch('shared_operations.ensure_database'),patch('shared_operations.context',return_value=(None,['docker','compose','-p','isolated-fixture'])),patch('operations.command',side_effect=lambda args,**kw:calls.append(args) or b''),patch('operations.exec_php',return_value=b'OK'),patch('operations.transition') as transition:
            result=workspace.restore_export(source.name,name)
        self.assertEqual(result['slug'],name);self.assertTrue(source.exists());self.assertEqual((root/'site/index.php').read_text(),'fixture site')
        self.assertIn('vmm_'+name.replace('-','_'),str(calls));transition.assert_called_once_with(name,'start')
    def test_wordpress_login_claim_is_single_use_and_expired_claim_never_bootstraps(self):
        import shutil,subprocess,hashlib,time
        php=shutil.which('php')
        if not php:self.skipTest('PHP CLI required')
        root=self.root/'login-fixture';(root/'site').mkdir(parents=True);(root/'tools').mkdir()
        helper=Path(__file__).resolve().parents[1]/'app/tools/manager-login.php';shutil.copyfile(helper,root/'site/login.php')
        (root/'site/wp-load.php').write_text("<?php function get_user_by($k,$id){return (object)['ID'=>$id];} function user_can($u,$c){return true;} function wp_set_current_user($id){} function wp_set_auth_cookie($id,$r){echo 'AUTHENTICATED';} function admin_url(){return '/wp-admin/';} function wp_safe_redirect($u){}")
        token='a'*43;file=root/'tools'/('login-'+hashlib.sha256(token.encode()).hexdigest()+'.json')
        runner=root/'site/run.php';runner.write_text("<?php $_GET['token']='"+token+"';require __DIR__.'/login.php';")
        file.write_text(json.dumps({'id':42,'expires':time.time()+60,'cms':'wordpress'}))
        first=subprocess.run([php,str(runner)],capture_output=True,check=True);self.assertIn(b'AUTHENTICATED',first.stdout);self.assertFalse(file.exists())
        second=subprocess.run([php,str(runner)],capture_output=True,check=True);self.assertNotIn(b'AUTHENTICATED',second.stdout)
        file.write_text(json.dumps({'id':42,'expires':time.time()-10,'cms':'wordpress'}))
        expired=subprocess.run([php,str(runner)],capture_output=True,check=True);self.assertNotIn(b'AUTHENTICATED',expired.stdout)
