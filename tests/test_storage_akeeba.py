import json
import os
import secrets
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _isolated=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_isolated.name
import storage_paths as paths
import storage_worker as worker
import storage_service
import akeeba_service as akeeba
from store import db


class StoragePathTests(unittest.TestCase):
    def test_rejects_nested_targets_swaps_system_paths_and_relative_paths(self):
        current={k:'/data/'+k for k in paths.AREAS}
        for value in ('relative','/','/etc/new','/data','/data/shared','/data/projects/new','/dest/../new','/dest/$HOME'):
            with self.subTest(value=value),self.assertRaises(ValueError):paths.validate_paths({**current,'extensions':value},current,'/data')
        with self.assertRaises(ValueError):paths.validate_paths({**current,'projects':'/dest','extensions':'/dest/child'},current,'/data')
        with self.assertRaises(ValueError):paths.validate_paths({**current,'projects':current['extensions'],'extensions':current['projects']},current,'/data')
        result=paths.validate_paths({**current,'projects':'/Volumes/My Disk/Websites'},current,'/data')
        self.assertEqual(result['projects'],'/Volumes/My Disk/Websites')

    def test_windows_paths_use_docker_desktop_host_mapping(self):
        current={k:'C:/VMM/data/'+k for k in paths.AREAS}
        result=paths.validate_paths({**current,'projects':'D:\\Sites'},current,'C:/VMM/data')
        self.assertEqual(result['projects'],'D:/Sites')

    def test_host_runtime_uses_configured_paths(self):
        from shared_runtime import stack
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);(data/'storage').mkdir();(data/'storage/settings.json').write_text(json.dumps({'projects':'/external/sites','extensions':'/external/packages','backups':'/external/backups'}))
            with patch('store.DATA',data):value=stack('/host/data','secret')
            mounts=value['services']['php84']['volumes']
            self.assertIn('/external/sites:/vmm-projects',mounts)
            self.assertIn('/external/packages:/vmm-extensions:ro',mounts)
            self.assertIn('/external/backups:/vmm-backups',mounts)

    def test_inventory_detects_corruption_and_rejects_external_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);one=root/'one';two=root/'two';one.mkdir();(one/'file').write_text('original');shutil.copytree(one,two)
            self.assertEqual(worker.inventory(one),worker.inventory(two))
            (two/'file').write_text('changed')
            self.assertNotEqual(worker.inventory(one),worker.inventory(two))
            (one/'outside').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):worker.inventory(one)

    def test_env_update_preserves_other_settings_and_literal_spaces(self):
        result=worker.env_paths('VMM_BIND=0.0.0.0\n# keep\nTOKEN=unchanged\nVMM_PROJECTS_PATH=old\n',{'projects':'/Volumes/My Disk/Sites'},{'projects':'VMM_PROJECTS_PATH'})
        self.assertIn('TOKEN=unchanged',result);self.assertIn("VMM_PROJECTS_PATH='/Volumes/My Disk/Sites'",result)
        self.assertEqual(result.count('VMM_PROJECTS_PATH='),1)


class StorageMigrationTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        for key in ('installation','vmm-data','sources/extensions','targets/extensions'):(root/key).mkdir(parents=True)
        (root/'installation/.env').write_text('VMM_HOST_DATA=/host/data\nCUSTOM=keep\n')
        (root/'sources/extensions/package.zip').write_bytes(b'original-package')
        data=root/'vmm-data';(data/'storage/jobs/test').mkdir(parents=True)
        with sqlite3.connect(data/'manager.sqlite') as c:
            c.execute('CREATE TABLE jobs(id TEXT,status TEXT,message TEXT,finished INTEGER)');c.execute("INSERT INTO jobs VALUES('test','queued','',NULL)")
        plan={'id':'test','changed':['extensions'],'paths':{'extensions':'/new/packages'},'host_paths':{'extensions':'/new/packages'},'env_keys':{'extensions':'VMM_EXTENSIONS_PATH'},'compose_project':'test-only','current_volumes':[],'new_volumes':[]}
        def mapped(value):
            value=str(value)
            if value.startswith(('/installation','/vmm-data','/sources','/targets')):return root/value.lstrip('/')
            return Path(value)
        return root,plan,mapped

    def test_migration_verifies_data_and_retains_originals(self):
        root,plan,mapped=self.fixture()
        with patch('storage_worker.Path',side_effect=mapped),patch('storage_worker.subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout=b'test-manager',stderr=b'')):
            worker.apply(plan)
        self.assertEqual((root/'targets/extensions/package.zip').read_bytes(),b'original-package')
        self.assertTrue((root/'sources/extensions/package.zip').exists())
        state=json.loads((root/'vmm-data/storage/apply-status.json').read_text())
        self.assertEqual(state['status'],'done')
        self.assertIn('CUSTOM=keep',(root/'installation/.env').read_text())

    def test_failed_copy_restores_old_settings_and_original_data(self):
        root,plan,mapped=self.fixture();settings=root/'vmm-data/storage/settings.json';settings.write_text('{"extensions":"/old/packages"}')
        original=(root/'installation/.env').read_bytes()
        with patch('storage_worker.Path',side_effect=mapped),patch('storage_worker.subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout=b'test-manager',stderr=b'')),patch('storage_worker.shutil.copytree',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):worker.apply(plan)
        self.assertEqual(json.loads(settings.read_text())['extensions'],'/old/packages')
        self.assertEqual((root/'installation/.env').read_bytes(),original)
        self.assertEqual((root/'sources/extensions/package.zip').read_bytes(),b'original-package')
        self.assertEqual(json.loads((root/'vmm-data/storage/apply-status.json').read_text())['status'],'error')

    def test_probe_rejects_nonempty_destination(self):
        root,plan,mapped=self.fixture();(root/'targets/extensions/existing').write_text('keep')
        with patch('storage_worker.Path',side_effect=mapped),self.assertRaises(ValueError):worker.probe(plan)
        self.assertTrue((root/'targets/extensions/existing').exists())


class AkeebaCreationTests(unittest.TestCase):
    def setup_project(self,name='akeeba-native-test',cms='joomla'):
        with db() as c:c.execute('INSERT OR REPLACE INTO projects (slug,cms,php,status,storage,restore) VALUES (?,?,?,?,?,?)',(name,cms,'8.4','running','shared',0))
        return name

    def test_native_creation_requires_completed_status_and_preserves_multipart(self):
        name=self.setup_project();ident=secrets.token_hex(12)
        def execute(p,args,**kwargs):
            stage=akeeba.DATA/'backups'/ident;base='vmm-'+name+'-'+ident
            if 'akeeba:backup:take' in args:
                self.assertIn('allowed_returncodes',kwargs)
                overrides=next(x for x in args if x.startswith('--overrides='))
                self.assertIn('akeeba.advanced.postproc_engine=none',overrides)
                self.assertIn('akeeba.quota.enable_count_quota=0',overrides)
                self.assertIn('/vmm-backups/'+ident,overrides)
                (stage/(base+'.jpa')).write_bytes(b'JPA-test-native-archive');(stage/(base+'.j01')).write_bytes(b'part-one')
                return b'Backup complete'
            return json.dumps([{'id':42,'description':'VMM-'+ident,'status':'complete','multipart':2}]).encode()
        with patch('akeeba_service.capability',return_value={'available':True}),patch('akeeba_service.secrets.token_hex',return_value=ident),patch('operations.write_tools',side_effect=lambda p:(akeeba.DATA/'projects'/name/'tools').mkdir(parents=True,exist_ok=True)),patch('operations.exec_php',side_effect=execute):
            result=akeeba.create(name)
        self.assertIn('2 Archivteile',result)
        info=json.loads((akeeba.DATA/'backups'/ident/'manager-backup.json').read_text())
        self.assertEqual(info['status'],'complete');self.assertEqual(len(info['files']),2);self.assertEqual(len(info['sha256']),2)

    def test_native_backup_requires_verified_original_server_files(self):
        from project_files import prepare_local
        name=self.setup_project('akeeba-originals-evidence');ident=secrets.token_hex(12)
        site=akeeba.DATA/'projects'/name/'site';site.mkdir(parents=True,exist_ok=True)
        (site/'.htaccess').write_text('production');(site/'htaccess.txt').write_text('local')
        tools=site.parent/'tools';prepare_local(site,tools)
        with patch('akeeba_service.capability',return_value={'available':True}),patch('akeeba_service.secrets.token_hex',return_value=ident),patch('operations.write_tools'),patch('operations.exec_php',return_value=b'Backup complete'):
            with self.assertRaisesRegex(ValueError,'ursprünglichen Serverdateien'):akeeba.create(name)
        self.assertEqual(json.loads((akeeba.DATA/'backups'/ident/'manager-backup.json').read_text())['status'],'error')
        self.assertEqual((site/'.htaccess').read_text(),'local');self.assertEqual((site/'.htaccess.vmm-original').read_text(),'production')

    def test_native_backup_records_original_configuration_without_live_renames(self):
        from project_files import prepare_local
        name=self.setup_project('akeeba-originals-success');ident=secrets.token_hex(12)
        site=akeeba.DATA/'projects'/name/'site';site.mkdir(parents=True,exist_ok=True)
        (site/'.htaccess').write_text('production');(site/'htaccess.txt').write_text('local')
        tools=site.parent/'tools';prepare_local(site,tools)
        def execute(p,args,**kwargs):
            if 'akeeba:backup:take' in args:
                self.assertEqual((site/'.htaccess').read_text(),'local')
                self.assertTrue(any('akeeba.advanced.archiver_engine=vmmjpa' in arg for arg in args))
                (tools/'akeeba-originals-report.json').write_text(json.dumps({'.htaccess':True,'htaccess.txt':True}))
                (akeeba.DATA/'backups'/ident/('vmm-'+name+'-'+ident+'.jpa')).write_bytes(b'JPA-fixture')
                return b'done'
            return json.dumps([{'description':'VMM-'+ident,'status':'complete','id':1}]).encode()
        with patch('akeeba_service.capability',return_value={'available':True}),patch('akeeba_service.secrets.token_hex',return_value=ident),patch('operations.write_tools'),patch('operations.exec_php',side_effect=execute):akeeba.create(name)
        self.assertEqual((site/'.htaccess').read_text(),'local')
        self.assertEqual(json.loads((akeeba.DATA/'backups'/ident/'manager-backup.json').read_text())['restored_server_files'],['.htaccess'])

    def test_failed_native_backup_is_not_listed_as_complete(self):
        name=self.setup_project('akeeba-native-fail');ident=secrets.token_hex(12)
        with patch('akeeba_service.capability',return_value={'available':True}),patch('akeeba_service.secrets.token_hex',return_value=ident),patch('operations.write_tools',side_effect=lambda p:(akeeba.DATA/'projects'/name/'tools').mkdir(parents=True,exist_ok=True)),patch('operations.exec_php',return_value=b'[]'):
            with self.assertRaises(ValueError):akeeba.create(name)
        state=json.loads((akeeba.DATA/'backups'/ident/'manager-backup.json').read_text())
        self.assertEqual(state['status'],'error')

    def test_legacy_joomla_cli_has_specific_explanation(self):
        name=self.setup_project('akeeba-legacy','joomla')
        from store import project
        site=akeeba.DATA/'projects'/name/'site'
        (site/'cli').mkdir(parents=True,exist_ok=True)
        (site/'cli/akeeba-backup.php').write_text('<?php')
        value=akeeba.capability(project(name))
        self.assertFalse(value['available'])
        self.assertIn('Joomla 3',value['reason'])
        self.assertIn('Joomla-Backend',value['reason'])

    def test_capability_does_not_claim_akeeba_for_plain_wordpress(self):
        name=self.setup_project('akeeba-uninstalled','wordpress')
        from store import project
        self.assertFalse(akeeba.capability(project(name))['available'])


class RuntimeOwnershipTests(unittest.TestCase):
    def test_foreign_runtime_is_rejected_before_stop(self):
        foreign=[{'Mounts':[{'Destination':'/vmm-projects','Source':'/host_mnt/Users/live/data/projects'}]}]
        with self.assertRaisesRegex(ValueError,'anderen Installation'):worker.verify_runtime_owner(foreign,'/private/tmp/test/data/projects')
        worker.verify_runtime_owner(foreign,'/Users/live/data/projects')

    def test_test_instances_can_use_their_own_runtime_project(self):
        from shared_runtime import stack
        with patch.dict(os.environ,{'VMM_RUNTIME_PROJECT':'vmm-test-only-runtime'}):
            self.assertEqual(stack('/test/data','secret')['name'],'vmm-test-only-runtime')


class ForeignRuntimeMigrationTests(unittest.TestCase):
    fixture=StorageMigrationTests.fixture
    def test_foreign_runtime_is_never_stopped_or_recreated(self):
        root,plan,mapped=self.fixture();shared=root/'vmm-data/shared';shared.mkdir();(shared/'compose.json').write_text('{"name":"vmm-runtime","services":{}}')
        plan['current']={'projects':'/isolated/test/projects'}
        commands=[]
        def run(args,**kwargs):
            commands.append(args)
            if args[:2]==['docker','inspect']:out=json.dumps([{'Mounts':[{'Destination':'/vmm-projects','Source':'/host_mnt/Users/live/data/projects'}]}]).encode()
            elif '--services' in args:out=b'php84\n'
            elif '-q' in args:out=b'foreign-container\n'
            else:out=b''
            return types.SimpleNamespace(returncode=0,stdout=out,stderr=b'')
        with patch('storage_worker.Path',side_effect=mapped),patch('storage_worker.subprocess.run',side_effect=run):
            with self.assertRaisesRegex(ValueError,'anderen Installation'):worker.apply(plan)
        self.assertFalse(any('stop' in command or 'up' in command for command in commands))
        self.assertEqual((root/'sources/extensions/package.zip').read_bytes(),b'original-package')
