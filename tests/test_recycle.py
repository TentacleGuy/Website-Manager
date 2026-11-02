import json,os,secrets,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _tmp=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_tmp.name
import server,cleanup_service as cleanup,recycle_service as recycle,file_service
from store import db

class RecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for directory in ('packages','extensions','backups','exports','projects','trash'):(self.root/directory).mkdir()
        for context in (patch.object(cleanup,'DATA',self.root),patch.object(recycle,'DATA',self.root),patch('storage_service.busy',return_value=False),patch('storage_service.ACTIVE_UPLOADS',0),patch('system_service.SHUTTING_DOWN',False)):
            context.start();self.addCleanup(context.stop)
        recycle.init()
        with db() as c:c.execute('DELETE FROM recycle_entries');c.execute("UPDATE jobs SET status='done' WHERE status IN ('queued','running')")
        self.ident=secrets.token_hex(12)
    def package(self):
        path=self.root/'packages'/(self.ident+'.zip');path.write_bytes(b'original package')
        with db() as c:c.execute('INSERT INTO packages VALUES(?,?,?,?,?,?,?,?)',(self.ident,'joomla','5.4.10',path.name,'0'*64,path.stat().st_size,'fixture',0))
        return path
    def test_cms_package_and_project_reference_round_trip(self):
        path=self.package();name='recycle-'+self.ident[:8];(self.root/'projects'/name/'site').mkdir(parents=True);(self.root/'projects'/name/'site/index.php').write_text('installed')
        with db() as c:c.execute("INSERT INTO projects(slug,cms,php,status,created,package_id) VALUES(?,'joomla','8.4','running',0,?)",(name,self.ident))
        token=cleanup.remove('cms',self.ident)['trash_id'];self.assertFalse(path.exists());self.assertTrue(recycle.listing()['items'])
        with db() as c:self.assertIsNone(c.execute('SELECT package_id FROM projects WHERE slug=?',(name,)).fetchone()[0])
        recycle.restore(token);self.assertEqual(path.read_bytes(),b'original package')
        with db() as c:self.assertEqual(c.execute('SELECT package_id FROM projects WHERE slug=?',(name,)).fetchone()[0],self.ident)
        self.assertEqual(recycle.listing()['items'],[])
    def extension(self):
        source=secrets.token_hex(12);name='ext-'+self.ident[:8];file=self.root/'extensions'/(self.ident+'.zip');file.write_bytes(b'extension')
        with db() as c:
            c.execute('INSERT INTO extension_sources(id,config) VALUES(?,?)',(source,json.dumps({'name':'Fixture','cms':'wordpress'})))
            c.execute("INSERT INTO projects(slug,cms,php,status,created) VALUES(?,'wordpress','8.4','running',0)",(name,))
            c.execute('INSERT INTO extensions(id,name,cms,kind,provider,version,filename,sha256,created,source_id,archived) VALUES(?,?,?,?,?,?,?,?,?,?,1)',(self.ident,'Fixture','wordpress','plugin','custom','1.0',file.name,'0'*64,0,source))
            c.execute("INSERT INTO extension_plans(project,source,status) VALUES(?,?,'installed')",(name,source));c.execute("INSERT INTO project_extensions(project,extension,status) VALUES(?,?,'installed')",(name,self.ident))
        return source,file,name
    def test_removed_library_source_restores_packages_and_assignments(self):
        source,file,name=self.extension();token=cleanup.remove('extension',source)['trash_id'];recycle.restore(token)
        self.assertEqual(file.read_bytes(),b'extension')
        with db() as c:
            self.assertIsNotNone(c.execute('SELECT 1 FROM extension_sources WHERE id=?',(source,)).fetchone());self.assertIsNotNone(c.execute('SELECT 1 FROM extension_plans WHERE project=? AND source=?',(name,source)).fetchone())
    def test_one_package_restores_without_overwriting_edited_source(self):
        source,file,_=self.extension();token=cleanup.remove('extension-package',self.ident)['trash_id']
        with db() as c:c.execute('UPDATE extension_sources SET config=? WHERE id=?',('{"name":"Changed","cms":"wordpress"}',source))
        recycle.restore(token)
        with db() as c:self.assertIn('Changed',c.execute('SELECT config FROM extension_sources WHERE id=?',(source,)).fetchone()[0]);self.assertEqual(c.execute('SELECT archived FROM extensions WHERE id=?',(self.ident,)).fetchone()[0],1)
    def test_all_backup_parts_stay_together(self):
        folder=self.root/'backups'/self.ident;folder.mkdir()
        for name in ('site.jpa','site.j01'):(folder/name).write_bytes(b'part')
        token=cleanup.remove('backup',self.ident)['trash_id'];self.assertFalse(folder.exists());recycle.restore(token)
        self.assertEqual(sorted(p.name for p in folder.iterdir()),['site.j01','site.jpa'])
    def test_restore_never_overwrites_a_new_file(self):
        path=self.package();token=cleanup.remove('cms',self.ident)['trash_id'];path.write_bytes(b'new')
        with self.assertRaisesRegex(ValueError,'nichts überschrieben'):recycle.restore(token)
        self.assertEqual(path.read_bytes(),b'new');self.assertEqual(recycle.listing()['items'][0]['status'],'ready')
    def test_metadata_conflict_rolls_files_back_into_trash(self):
        path=self.package();token=cleanup.remove('cms',self.ident)['trash_id'];self.package()
        path.unlink()
        with self.assertRaises(Exception):recycle.restore(token)
        self.assertFalse(path.exists());self.assertEqual(recycle.listing()['items'][0]['status'],'ready')
    def test_permanent_mode_removes_without_a_recycle_entry(self):
        path=self.package();recycle.save_settings({'mode':'permanent','days':14});cleanup.remove('cms',self.ident)
        self.assertFalse(path.exists());self.assertEqual(recycle.listing()['items'],[])
    def test_new_retention_does_not_silently_shorten_existing_deadlines(self):
        self.package();token=cleanup.remove('cms',self.ident)['trash_id'];old=recycle.listing()['items'][0]['expires'];recycle.save_settings({'mode':'trash','days':1})
        self.assertEqual(recycle.listing()['items'][0]['expires'],old)
        for value in ({'mode':'invalid','days':1},{'mode':'trash','days':0},{'mode':'trash','days':True},{'mode':'trash','days':3651}):
            with self.assertRaises(ValueError):recycle.save_settings(value)
    def test_expiry_only_purges_expired_items_and_creates_an_activity_job(self):
        self.package();token=cleanup.remove('cms',self.ident)['trash_id']
        with db() as c:value=recycle.load(c,token);value['expires']=1;recycle.put(c,value)
        fresh=self.root/'exports/fresh.zip';fresh.write_bytes(b'keep');fresh_id=cleanup.remove('export',fresh.name)['trash_id']
        def job(resource,kind,action):self.assertEqual((resource,kind),('recycle-bin','recycle-purge'));return action()
        with patch.object(recycle,'job',side_effect=job):recycle.tick()
        self.assertEqual([x['id'] for x in recycle.listing()['items']],[fresh_id])
    def test_active_work_and_symlinks_protect_purge(self):
        path=self.package();token=cleanup.remove('cms',self.ident)['trash_id']
        with db() as c:value=recycle.load(c,token);saved=recycle.paths(value)[0][1]
        kept=self.root/'outside';kept.write_bytes(b'keep');saved.unlink();saved.symlink_to(kept)
        with self.assertRaises(ValueError):recycle.purge(token)
        self.assertEqual(kept.read_bytes(),b'keep')
    def test_interrupted_move_and_restore_recover_without_losing_metadata(self):
        path=self.package();token=cleanup.remove('cms',self.ident)['trash_id']
        with db() as c:value=recycle.load(c,token);value['status']='restoring';recycle.put(c,value)
        original,saved=recycle.paths(value)[0];saved.rename(original);recycle.recover();self.assertFalse(original.exists());self.assertTrue(saved.exists())
        # A move which crashed before detaching its metadata must be rolled back.
        with db() as c:recycle.restore_metadata(c,value);value['status']='moving';recycle.put(c,value)
        recycle.recover();self.assertEqual(path.read_bytes(),b'original package');self.assertEqual(recycle.listing()['items'],[])
    def test_file_details_preserve_original_download_name_in_trash(self):
        path=self.package();token=cleanup.remove('cms',self.ident)['trash_id'];item=file_service.entries('recycle',token)['files'][0]
        self.assertEqual(item['name'],path.name);self.assertEqual(file_service.file('recycle',token,item['path']).read_bytes(),b'original package')
        self.assertNotIn('metadata',recycle.listing()['items'][0]);self.assertNotIn('paths',recycle.listing()['items'][0])
    def test_old_project_trash_gets_a_fresh_retention_period_and_restores_stopped(self):
        name='old-'+self.ident[:8];ident=name+'-1-abcdef';folder=self.root/'trash'/ident;(folder/'project/site').mkdir(parents=True);(folder/'project/site/index.php').write_text('site')
        with db() as c:
            c.execute("INSERT INTO projects(slug,cms,php,status,created,storage,database_profile) VALUES(?,'wordpress','8.4','running',0,'shared','existing')",(name,));p=dict(c.execute('SELECT * FROM projects WHERE slug=?',(name,)).fetchone());c.execute('DELETE FROM projects WHERE slug=?',(name,))
        (folder/'metadata.json').write_text(json.dumps({'project':p,'database_exists':True}))
        item=recycle.listing()['items'][0];self.assertGreater(item['expires'],time.time()+29*86400)
        with patch('shared_operations.context',return_value=(MagicMock(),['docker','compose'])),patch('operations.command',return_value=b'existing'),patch('database_profiles.profile',return_value={'service':'db'}),patch('database_profiles.sql_command',return_value=['exec']),patch('shared_runtime.database_info',return_value={'database':'fixture'}):recycle.restore_project(item['id'])
        self.assertEqual((self.root/'projects'/name/'site/index.php').read_text(),'site')
        with db() as c:self.assertEqual(c.execute('SELECT status FROM projects WHERE slug=?',(name,)).fetchone()[0],'stopped')
        self.assertFalse(folder.exists());self.assertEqual(recycle.listing()['items'],[])
