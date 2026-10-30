"""Real handlers with in-memory requests; no socket, network or Docker needed."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
TEMP=tempfile.TemporaryDirectory()
os.environ['VMM_DATA']=TEMP.name
import server
import catalog
from store import db


def fixture(cms='wordpress',v='6.8.3'):
    path=Path(TEMP.name)/(cms+v+'.zip')
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('wordpress/wp-includes/version.php' if cms=='wordpress' else 'installation/index.php','<?php // test package')
    return catalog.register(path,cms,v,'test')

class ApiTests(unittest.TestCase):
    def request(self,path,payload=None,custom=True,host='localhost:8090',origin=None,get=False,raw=None,filename=None):
        h=server.Handler.__new__(server.Handler);h.path=path
        data=raw if raw is not None else json.dumps(payload or {}).encode()
        h.rfile=io.BytesIO(data);h.headers={'Content-Length':str(len(data)),'Host':host}
        if custom:h.headers['X-VMM-Request']='1'
        if origin:h.headers['Origin']=origin
        if filename:h.headers['X-VMM-Filename']=filename
        response=[];h.send=lambda *args:response.append(args)
        h.wfile=io.BytesIO();h.send_response=lambda code:response.append((code,{}))
        h.send_header=lambda *args:None;h.end_headers=lambda:None
        h.do_GET() if get else h.do_POST()
        return response[0]

    def test_get_projects_without_login(self):
        result=self.request('/api/projects',get=True)
        self.assertEqual(result[0],200)
        self.assertNotIn('db_password',json.dumps(result[1]))

    def test_reject_cross_origin_and_dns_rebinding(self):
        self.assertEqual(self.request('/api/projects',custom=False)[0],403)
        self.assertEqual(self.request('/api/projects',host='attacker.example:8090')[0],403)
        self.assertEqual(self.request('/api/projects',origin='https://attacker.example')[0],403)
        self.assertEqual(self.request('/api/projects',host='192.168.1.20:8090',get=True)[0],200)

    def test_project_credentials_visible_scoped_and_editable(self):
        for name in ('vault-one','vault-two'):
            self.assertEqual(self.request('/api/projects',{'slug':name,'cms':'wordpress','php':'8.4','package_id':fixture()})[0],201)
        route='/api/projects/vault-one/credentials'
        payload={'label':'CMS Admin','username':'alice','password':'test-secret-unique','url':'http://vault-one.vmm.test:8084/wp-admin/','note':'Editor account'}
        response=self.request(route,payload);self.assertEqual(response[0],200);ident=response[1]['id']
        with db() as c: stored=c.execute('SELECT secret FROM credentials WHERE id=?',(ident,)).fetchone()['secret']
        for value in ('test-secret-unique','alice','Editor account'): self.assertIn(value,stored)
        listed=self.request(route,get=True)[1]['credentials']
        self.assertEqual(listed[0]['username'],'alice');self.assertTrue(listed[0]['has_password'])
        self.assertEqual(listed[0]['password'],'test-secret-unique')
        self.assertEqual(self.request('/api/projects/vault-two/credentials',get=True)[1]['credentials'],[])
        self.assertEqual(self.request('/api/projects/vault-two/credentials',{'action':'reveal','id':ident})[0],400)
        self.assertEqual(self.request(route,{'action':'reveal','id':ident})[1]['password'],'test-secret-unique')
        self.assertEqual(self.request(route,{**payload,'id':ident,'password':None,'label':'Changed'})[0],200)
        self.assertEqual(self.request(route,{'action':'reveal','id':ident})[1]['password'],'test-secret-unique')
        self.request(route,{'action':'archive','id':ident})
        self.assertTrue(self.request(route,get=True)[1]['credentials'][0]['archived'])
        self.request(route,{'action':'restore','id':ident})
        self.assertFalse(self.request(route,get=True)[1]['credentials'][0]['archived'])
        self.request(route,{**payload,'id':ident,'password':''})
        self.assertFalse(self.request(route,get=True)[1]['credentials'][0]['has_password'])
        self.assertEqual(self.request(route,{'action':'reveal','id':ident},custom=False)[0],403)

    def test_credentials_validate_urls_and_lengths(self):
        self.request('/api/projects',{'slug':'vault-validation','cms':'wordpress','php':'8.4','package_id':fixture()})
        route='/api/projects/vault-validation/credentials'
        for body in ({'label':''},{'label':'x','url':'javascript:alert(1)'},{'label':'x','url':'http://user:password@example.com'},{'label':'x','password':'x'*4097},{'label':'x','note':[]}):
            self.assertEqual(self.request(route,body)[0],400)
        self.assertEqual(self.request('/api/projects/missing/credentials',get=True)[0],400)

    def test_login_removed(self):
        self.assertEqual(self.request('/api/login')[0],404)

    def test_create_persist_and_duplicate_without_login(self):
        body={'slug':'persisted','cms':'wordpress','php':'8.2','package_id':fixture()}
        self.assertEqual(self.request('/api/projects',body)[0],201)
        self.assertEqual(self.request('/api/projects',body)[0],409)
        p=server.project('persisted')
        self.assertEqual(p['storage'],'shared');self.assertEqual(p['version'],'6.8.3')
        self.assertNotIn('db_password',server.public(p))
        self.assertNotEqual(p['db_password'],p['db_root_password'])

    def test_create_project_with_extensions_waits_for_finished_cms(self):
        source=server.extensions.save_source({'name':'Selected at creation','cms':'wordpress','kind':'plugin','provider':'custom','element':'selected-plugin','source_type':'upload','auth_type':'none'})
        response=self.request('/api/projects',{'slug':'with-extensions','cms':'wordpress','php':'8.4','package_id':fixture(),'extensions':[{'source':source}]})
        self.assertEqual(response[0],201)
        with db() as c:plan=c.execute('SELECT * FROM extension_plans WHERE project=?',('with-extensions',)).fetchone()
        self.assertEqual(plan['status'],'pending');self.assertEqual(plan['source'],source)
        response=self.request('/api/projects',{'slug':'wrong-extensions','cms':'joomla','php':'8.4','package_id':fixture('joomla','6.2.0'),'extensions':[{'source':source}]})
        self.assertEqual(response[0],400)
        with db() as c:self.assertIsNone(c.execute('SELECT 1 FROM projects WHERE slug=?',('wrong-extensions',)).fetchone())

    def test_joomla_package_selection(self):
        result=self.request('/api/projects',{'slug':'joomla-test','cms':'joomla','php':'8.4','package_id':fixture('joomla','5.3.0')})
        self.assertEqual(result[0],201)
        self.assertEqual(server.project('joomla-test')['cms'],'joomla')

    def test_reject_wrong_cms_and_invalid_paths(self):
        ident=fixture()
        for body in ({'slug':'../escape','cms':'wordpress','php':'8.4','package_id':ident},{'slug':'valid','cms':'joomla','php':'8.4','package_id':ident},{'slug':'valid','cms':'wordpress','php':'9.0','package_id':ident},{'slug':'valid','cms':'wordpress','php':'8.4'}):
            self.assertEqual(self.request('/api/projects',body)[0],400)

    def test_bad_json_shape(self):
        self.assertEqual(self.request('/api/projects',raw=b'[]')[0],400)

    def test_package_upload_without_login(self):
        path=Path(TEMP.name)/'upload.zip'
        with zipfile.ZipFile(path,'w') as z:z.writestr('installation/index.php','<?php')
        response=self.request('/api/uploads/packages?cms=joomla&version=5.4.0',raw=path.read_bytes(),filename='joomla.zip')
        self.assertEqual(response[0],201)

    def test_backup_parts_kept_together(self):
        group='a'*24
        self.assertEqual(self.request('/api/uploads/backups/'+group,raw=b'part',filename='site.j01')[0],201)
        self.assertEqual(self.request('/api/uploads/backups/'+group,raw=b'main',filename='site.jpa')[0],201)
        self.assertEqual(self.request('/api/uploads/backups/'+group,raw=b'other',filename='site.jpa')[0],400)
        result=self.request('/api/backups',get=True)
        found=next(b for b in result[1]['backups'] if b['id']==group)
        self.assertEqual(set(found['files']),{'site.jpa','site.j01'})

    def test_failed_start_records_redacted_error(self):
        import operations
        server.create_project({'slug':'failure','cms':'wordpress','php':'8.4','package_id':fixture()})
        p=server.project('failure')
        with patch('operations.ensure_runtime',side_effect=RuntimeError('failure '+p['db_password'])):
            with self.assertRaises(RuntimeError):operations.transition('failure','start')
        p=server.project('failure');self.assertEqual(p['status'],'error');self.assertEqual(p['error'],'failure [redacted]')
        config=(server.DATA/'projects'/'failure'/'site'/'wp-config.php').read_text()
        self.assertIn("define('DB_PASSWORD',",config)
        self.assertNotIn('__DB_PASSWORD__',config)

    def test_project_subdomains_never_expose_management_api(self):
        result=self.request('/api/projects',host='nonexistent.vmm.test:8084',get=True)
        self.assertEqual(result[0],503)
        self.assertNotIn('projects',result[1])

    def test_on_demand_port_starts_requested_php(self):
        server.create_project({'slug':'warmup','cms':'wordpress','php':'8.4','package_id':fixture()})
        with db() as c:c.execute("UPDATE projects SET status='running' WHERE slug='warmup'")
        with patch('server.job',return_value='test-job') as enqueue:
            self.assertEqual(self.request('/',host='warmup.vmm.test:8182',get=True)[0],503)
            self.assertEqual(enqueue.call_args[0][:2],('warmup','runtime'))
            with patch('server.transition') as transition:
                enqueue.call_args[0][2]()
                transition.assert_called_once_with('warmup','start','8.2')
        with db() as c:c.execute("UPDATE projects SET status='stopped' WHERE slug='warmup'")
        with patch('server.job') as enqueue:
            self.request('/',host='warmup.vmm.test:8082',get=True)
            enqueue.assert_called_once()

    def test_snapshot_unpauses_after_dump_error(self):
        import operations
        server.create_project({'slug':'snapshot-test','cms':'wordpress','php':'8.4','package_id':fixture()})
        with db() as c:c.execute("UPDATE projects SET status='running' WHERE slug='snapshot-test'")
        calls=[]
        def command(args,**kwargs):
            calls.append(args)
            if 'ps' in args:return b'php84\n'
            if 'exec' in args:raise RuntimeError('dump failed')
            return b''
        with patch('operations.command',side_effect=command):
            with self.assertRaises(RuntimeError):operations.snapshot('snapshot-test')
        self.assertIn('pause',calls[1]);self.assertIn('unpause',calls[-1])

    def test_minimum_php_checked_before_runtime_build(self):
        import operations
        server.create_project({'slug':'compatibility','cms':'joomla','php':'8.4','package_id':fixture('joomla','6.2.0')})
        p=server.project('compatibility');source=server.DATA/'projects'/'compatibility'/'site'/'cli'
        source.mkdir(parents=True)
        (source/'joomla.php').write_text("<?php const JOOMLA_MINIMUM_PHP = '8.3.0';")
        with self.assertRaises(ValueError):operations.compatible(p,'8.2')
        operations.compatible(p,'8.4')

    def test_backup_validation_does_not_leave_project_record(self):
        result=self.request('/api/projects',{'slug':'bad-backup','cms':'joomla','php':'8.4','backup_id':'a'*24,'archive':'missing.jpa'})
        self.assertEqual(result[0],400)
        with self.assertRaises(ValueError):server.project('bad-backup')

    def test_docker_error_includes_actual_build_stdout(self):
        import operations
        from subprocess import CompletedProcess
        result=CompletedProcess(['docker','build'],100,stdout=b'E: Failed to fetch package.deb 404 Not Found',stderr=b'Legacy builder warning')
        with patch('operations.subprocess.run',return_value=result):
            with self.assertRaisesRegex(RuntimeError,'Failed to fetch package.deb 404'):
                operations.command(['docker','build'])

    def test_restore_build_failure_sets_project_error(self):
        import operations
        server.create_project({'slug':'restore-failure','cms':'joomla','php':'7.4','package_id':fixture('joomla','3.10.12')})
        with db() as c:c.execute("UPDATE projects SET restore=1 WHERE slug='restore-failure'")
        group='c'*24;folder=server.DATA/'backups'/group;folder.mkdir(parents=True,exist_ok=True)
        (folder/'site.jpa').write_bytes(b'backup')
        tools=server.DATA/'tools';tools.mkdir(exist_ok=True);(tools/'kickstart.php').write_text('<?php')
        with patch('operations.ensure_runtime',side_effect=RuntimeError('APT package 404')):
            with self.assertRaisesRegex(ValueError,'APT package 404'):
                operations.restore_akeeba('restore-failure',group,'site.jpa')
        p=server.project('restore-failure')
        self.assertEqual(p['status'],'error');self.assertIn('APT package 404',p['error'])
        self.assertFalse(any((server.DATA/'projects'/'restore-failure'/'site').iterdir()))

    def test_restore_retry_does_not_overwrite_existing_files(self):
        import operations
        server.create_project({'slug':'restore-existing','cms':'joomla','php':'7.4','package_id':fixture('joomla','3.10.12')})
        group='d'*24;backup=server.DATA/'backups'/group;backup.mkdir(parents=True,exist_ok=True)
        (backup/'site.jpa').write_bytes(b'backup')
        tools=server.DATA/'tools';tools.mkdir(exist_ok=True);(tools/'kickstart.php').write_text('<?php')
        site=server.DATA/'projects'/'restore-existing'/'site';site.mkdir(parents=True);(site/'index.php').write_text('existing content')
        with patch('operations.ensure_runtime') as build:
            with self.assertRaisesRegex(ValueError,'leeren'):
                operations.restore_akeeba('restore-existing',group,'site.jpa')
            build.assert_not_called()
        self.assertEqual((site/'index.php').read_text(),'existing content')

    def test_restore_retry_keeps_existing_project(self):
        server.create_project({'slug':'restore-retry','cms':'joomla','php':'7.4','package_id':fixture('joomla','3.10.12')})
        with db() as c:c.execute("UPDATE projects SET restore=1 WHERE slug='restore-retry'")
        before=server.project('restore-retry')
        body={'backup_id':'e'*24,'archive':'site.jpa','password':''}
        with patch('server.job',return_value='retry-job') as enqueue:
            response=self.request('/api/projects/restore-retry/restore',body)
            self.assertEqual(response[0],202)
            with patch('server.restore_akeeba') as restore:
                enqueue.call_args[0][2]()
                restore.assert_called_once_with('restore-retry','e'*24,'site.jpa','')
        self.assertEqual(server.project('restore-retry')['db_password'],before['db_password'])

    def test_licenses_visible_in_database_and_api(self):
        try: import cryptography
        except ImportError:self.skipTest('cryptography not installed')
        key='private-license-key'
        result=self.request('/api/licenses',{'provider':'yootheme','label':'Test','key':key})
        self.assertEqual(result[0],201)
        with db() as c:row=c.execute('SELECT * FROM licenses WHERE id=?',(result[1]['id'],)).fetchone()
        self.assertNotEqual(row['secret'],key)
        self.assertEqual(json.loads(row['secret'])['key'],key)
        response=self.request('/api/extensions',get=True)
        self.assertIn(key,json.dumps(response));self.assertEqual(next(x for x in response[1]['licenses'] if x['id']==result[1]['id'])['key'],key)

if __name__=='__main__':unittest.main()


class ActivityAndBackupTests(unittest.TestCase):
    request = ApiTests.request

    def test_activity_time_range_pagination_and_status(self):
        import time
        now=int(time.time())
        with db() as c:
            for i in range(120):
                c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',('activity-page-'+str(i),'activity-pagination','updates','done','Test',now-i,now))
            c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',('activity-old','activity-pagination','updates','done','Old',now-8*86400,now-8*86400))
        route='/api/jobs?history=1&search=activity-pagination&limit=50'
        code,data=self.request(route,get=True)
        self.assertEqual(code,200);self.assertEqual(data['total'],120);self.assertEqual(len(data['jobs']),50)
        _,second=self.request(route+'&offset=50',get=True)
        self.assertTrue(set(j['id'] for j in data['jobs']).isdisjoint(j['id'] for j in second['jobs']))
        _,filtered=self.request(route+'&from='+str(now-10)+'&to='+str(now-5),get=True)
        self.assertEqual(filtered['total'],6)
        _,filtered=self.request(route+'&status=running',get=True)
        self.assertEqual(filtered['total'],0)
        _,translated=self.request('/api/jobs?history=1&search=pruefen&kind=updates&status=done',get=True)
        self.assertGreaterEqual(translated['total'],120)
        self.assertEqual(self.request(route+'&from='+str(now)+'&to=1',get=True)[0],400)
        self.assertEqual(self.request(route.replace('limit=50','limit=100000'),get=True)[0],400)
        with db() as c:c.execute("DELETE FROM jobs WHERE resource='activity-pagination'")

    def test_log_deletion_strict_boundary_and_active_protection(self):
        import time
        cutoff=int(time.time())-100
        rows=[('older','done',cutoff-1,cutoff),('boundary','done',cutoff,cutoff),('newer','error',cutoff+1,cutoff+2),('running','running',cutoff-20,None),('queued','queued',cutoff-20,None),('interrupted','interrupted',cutoff-2,cutoff-1)]
        with db() as c:
            for ident,status,created,finished in rows:
                c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',('retention-'+ident,'retention-test','updates',status,'Test',created,finished))
        code,_=self.request('/api/jobs/delete',{'before':cutoff})
        self.assertEqual(code,200)
        with db() as c:remaining={r['id'] for r in c.execute("SELECT id FROM jobs WHERE resource='retention-test'")}
        self.assertEqual(remaining,{'retention-boundary','retention-newer','retention-running','retention-queued'})
        for value in (None,True,'bad','NaN',float('inf'),time.time()+3600):
            self.assertEqual(self.request('/api/jobs/delete',{'before':value})[0],400)
        with db() as c:c.execute("DELETE FROM jobs WHERE resource='retention-test'")

    def test_delete_backup_group_protects_pending_restore(self):
        group='abcd'*6
        root=server.DATA/'backups'/group;root.mkdir(parents=True,exist_ok=True)
        (root/'site.jpa').write_bytes(b'archive');(root/'site.j01').write_bytes(b'part')
        with db() as c:
            c.execute('INSERT INTO projects (slug,cms,php,status,restore,backup_group) VALUES (?,?,?,?,?,?)',('delete-backup-guard','auto','8.4','error',1,group))
        route='/api/backups/'+group+'/delete'
        self.assertEqual(self.request(route)[0],400);self.assertTrue((root/'site.jpa').exists())
        with db() as c:c.execute("UPDATE projects SET restore=0 WHERE slug='delete-backup-guard'")
        self.assertEqual(self.request(route)[0],200);self.assertFalse(root.exists())
        self.assertEqual(self.request(route)[0],400)
        with db() as c:c.execute("DELETE FROM projects WHERE slug='delete-backup-guard'")

    def test_delete_export_checks_filename_and_running_snapshots(self):
        root=server.DATA/'exports';root.mkdir(exist_ok=True)
        file=root/'deletion-test.zip';file.write_bytes(b'archive')
        with db() as c:
            # Other fixtures may contain intentionally queued jobs.
            c.execute("UPDATE jobs SET status='done' WHERE status IN ('running','queued')")
            c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',('export-delete-guard','demo','snapshot','running','Test',100,None))
        self.assertEqual(self.request('/api/exports/delete',{'name':file.name})[0],400)
        self.assertTrue(file.exists())
        with db() as c:c.execute("DELETE FROM jobs WHERE id='export-delete-guard'")
        self.assertEqual(self.request('/api/exports/delete',{'name':'../outside.zip'})[0],400)
        self.assertEqual(self.request('/api/exports/delete',{'name':file.name})[0],200)
        self.assertFalse(file.exists())


class LibraryApiTests(unittest.TestCase):
    request=ApiTests.request

    def test_simple_upload_archive_download_and_delete(self):
        content=io.BytesIO()
        with zipfile.ZipFile(content,'w') as z:z.writestr('api-library/api-library.php','<?php /*\nPlugin Name: API Library\nVersion: 1.0.0\nUpdate URI: https://premium.example/api-library\n*/')
        code,result=self.request('/api/uploads/extensions',raw=content.getvalue(),filename='library.zip')
        self.assertEqual(code,201);self.assertEqual(result['cms'],'wordpress')
        ident=result['id'];source=result['source']
        self.assertEqual(self.request('/api/extension-packages/'+ident,get=True)[0],200)
        self.assertEqual(self.request('/api/extension-sources/'+source+'/edit',{'name':'Renamed API Library','key':'global-test-key'})[0],200)
        self.assertEqual(self.request('/api/extension-packages/'+ident+'/delete',custom=False)[0],403)
        self.assertEqual(self.request('/api/extension-packages/'+ident+'/delete')[0],200)
        _,listing=self.request('/api/extensions',get=True)
        self.assertNotIn(ident,{x['id'] for x in listing['extensions']})
        self.assertIn(source,{x['id'] for x in listing['sources']})
        self.assertEqual(self.request('/api/extension-packages/'+ident,get=True)[0],400)

    def test_project_candidate_endpoint_does_not_leak_download_credentials(self):
        import extension_library
        row={'key':'plugin:premium/premium.php','name':'Premium','cms':'wordpress','version':'1.0','latest':'2.0','kind':'plugin','element':'premium','can_download':True,'origin':'vendor.example','has_key':True,'license_key':'NEVER-PUBLIC','url':'https://vendor.example?key=NEVER-PUBLIC'}
        with patch('extension_library.bridge',return_value=[row]):
            code,result=self.request('/api/projects/demo/library',get=True)
        self.assertEqual(code,200)
        self.assertNotIn('NEVER-PUBLIC',json.dumps(result))


class StorageAndNativeBackupApiTests(unittest.TestCase):
    request=ApiTests.request

    def test_storage_status_and_host_paths_are_available(self):
        code,data=self.request('/api/storage',get=True)
        self.assertEqual(code,200);self.assertEqual(len(data['areas']),5)
        self.assertEqual({x['key'] for x in data['areas']},{'projects','extensions','packages','backups','exports'})
        self.assertEqual(self.request('/api/storage/apply',{'paths':{}},custom=False)[0],403)

    def test_storage_migration_blocks_new_actions(self):
        with patch('storage_service.busy',return_value=True):
            self.assertEqual(self.request('/api/jobs/delete',{'before':1})[0],400)
            self.assertEqual(self.request('/api/uploads/backups/'+'e'*24,raw=b'archive',filename='site.jpa')[0],400)

    def test_backup_metadata_is_never_exposed_as_an_archive_and_partial_groups_are_hidden(self):
        import secrets
        group=secrets.token_hex(12);root=server.DATA/'backups'/group;root.mkdir(parents=True)
        (root/'site.jpa').write_bytes(b'JPA-native-test')
        meta=root/'manager-backup.json';meta.write_text(json.dumps({'project':'demo','status':'creating','files':['site.jpa']}))
        _,groups=self.request('/api/backups',get=True)
        self.assertNotIn(group,{x['id'] for x in groups['backups']})
        self.assertEqual(self.request('/api/backups/'+group+'/site.jpa',get=True)[0],400)
        self.assertEqual(self.request('/api/backups/'+group+'/manager-backup.json',get=True)[0],400)
        self.assertEqual(self.request('/api/backups/'+group+'/delete')[0],400)
        meta.write_text(json.dumps({'project':'demo','status':'complete','files':['site.jpa']}))
        self.assertEqual(self.request('/api/backups/'+group+'/site.jpa',get=True)[0],200)
        self.assertEqual(self.request('/api/backup-bundles/'+group+'.zip',get=True)[0],200)
        _,groups=self.request('/api/backups',get=True)
        item=next(x for x in groups['backups'] if x['id']==group)
        self.assertEqual(item['files'],['site.jpa'])

    def test_storage_uses_worker_check_and_apply_handlers(self):
        with patch('storage_service.check',return_value={'message':'checked'}) as check:
            self.assertEqual(self.request('/api/storage/check',{'paths':{'projects':'/new'}})[0],200)
            check.assert_called_once_with({'projects':'/new'})
        with patch('storage_service.start',return_value={'job':'migration'}) as start:
            self.assertEqual(self.request('/api/storage/apply',{'paths':{'projects':'/new'}})[0],202)
            start.assert_called_once_with({'projects':'/new'})
