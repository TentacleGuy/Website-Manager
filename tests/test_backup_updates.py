import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

TEST_DATA=tempfile.TemporaryDirectory()
os.environ.setdefault('VMM_DATA',TEST_DATA.name)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import server
import backup_service as backups
import kickstart_service as kickstart
import update_service as updates
import project_service as projects
from store import db,project


class BackupTests(unittest.TestCase):
    def test_backup_creation_without_cms_or_uploaded_kickstart(self):
        group='f'*24;root=server.DATA/'backups'/group;root.mkdir(parents=True,exist_ok=True);(root/'site.jpa').write_bytes(b'fixture')
        server.create_project({'slug':'automatic-backup','php':'8.2','backup_id':group,'archive':'site.jpa','kickstart':'9.2.0'})
        p=project('automatic-backup')
        self.assertEqual(p['cms'],'auto');self.assertEqual(p['status'],'preparing');self.assertIsNone(p['package_id'])
        self.assertEqual(p['kickstart'],'9.2.0')
        self.assertTrue(all(v is None for v in server.project_links(p,root).values()))

    def test_detect_cms_from_files_and_reject_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'wp-includes').mkdir();(root/'wp-includes/version.php').write_text("<?php $wp_version='6.8.3';");(root/'wp-config.php').touch()
            self.assertEqual(backups.detect(root),('wordpress','6.8.3'))
            (root/'administrator').mkdir();(root/'configuration.php').touch()
            with self.assertRaises(ValueError):backups.detect(root)

    def test_delete_stopped_unprovisioned_project_and_its_assignments(self):
        name='delete-never-started'
        with db() as c:c.execute("INSERT INTO projects (slug,cms,php,status,created,db_password,storage,restore) VALUES (?,?,?,'stopped',0,'test-password','shared',0)",(name,'joomla','8.2'))
        with patch('operations.command',return_value=b''),patch('shared_operations.sync'):
            result=projects.delete_project(name)
        self.assertIn('Papierkorb',result)
        with self.assertRaises(ValueError):project(name)
        trash=next((server.DATA/'trash').glob(name+'-*'))
        self.assertFalse((trash/'database.sql').exists());self.assertTrue((trash/'metadata.json').exists())

    def test_delete_dump_error_keeps_project_and_files(self):
        name='delete-dump-error'
        with db() as c:c.execute("INSERT INTO projects (slug,cms,php,status,created,db_password,storage,restore) VALUES (?,?,?,'stopped',0,'test-password','shared',0)",(name,'joomla','8.2'))
        root=server.DATA/'projects'/name/'site';root.mkdir(parents=True);(root/'index.php').write_text('keep me')
        with patch('operations.command',side_effect=[b'',b'vmm_delete_dump_error',RuntimeError('dump error')]):
            with self.assertRaisesRegex(RuntimeError,'dump error'):projects.delete_project(name)
        self.assertEqual(project(name)['slug'],name);self.assertEqual((root/'index.php').read_text(),'keep me')

    def test_official_version_catalog_paginates_and_caches(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(kickstart,'DATA',Path(tmp)):
            pages={kickstart.BASE:b'<a href="/download/akeeba-kickstart/9-2-0.html">9</a><a href="?start=20">2</a>',kickstart.BASE+'?start=20':b'<a href="/download/akeeba-kickstart/5-0-0.html">5</a>'}
            with patch.object(kickstart,'fetch',side_effect=lambda url:pages[url]) as fetch:
                self.assertEqual([r['version'] for r in kickstart.catalog()],['9.2.0','5.0.0'])
                kickstart.catalog();self.assertEqual(fetch.call_count,2)

    def test_kickstart_download_is_versioned_and_cached(self):
        package=io.BytesIO()
        with zipfile.ZipFile(package,'w') as archive:archive.writestr('kickstart.php','<?php // fixture')
        with tempfile.TemporaryDirectory() as tmp,patch.object(kickstart,'DATA',Path(tmp)),patch.object(kickstart,'catalog',return_value=[{'version':'9.2.0','page':'https://www.akeeba.com/download/akeeba-kickstart/9-2-0.html'}]),patch.object(kickstart,'fetch',side_effect=[b'<a href="/download/akeeba-kickstart/9-2-0/kickstart-core-9-2-0-zip.zip">Core</a>',package.getvalue()]) as fetch:
            path=kickstart.ensure('9.2.0');self.assertEqual(path.parent.name,'9.2.0');self.assertIn('<?php',path.read_text())
            self.assertEqual(kickstart.ensure('9.2.0'),path);self.assertEqual(fetch.call_count,2)


class UpdateTests(unittest.TestCase):
    def bundle(self,extra=None,release='1.1.0'):
        data=io.BytesIO()
        files={'app/server.py':'#fixture','app/release.json':json.dumps({'version':release,'repository':updates.REPOSITORY}),'Dockerfile':'FROM python','compose.yaml':'services: {}','scripts/setup.py':'#fixture'}
        files.update(extra or {})
        with zipfile.ZipFile(data,'w') as z:
            for name,value in files.items():z.writestr(name,value)
        return data.getvalue()

    def test_validate_update_rejects_traversal_secrets_and_wrong_release(self):
        updates.validate_bundle(self.bundle(),'1.1.0')
        for name in ('../outside','.env','data/vault.key','exports/site.jpa','app/../../evil','/absolute'):
            with self.assertRaises(ValueError,msg=name):updates.validate_bundle(self.bundle({name:'private'}),'1.1.0')
        with self.assertRaises(ValueError):updates.validate_bundle(self.bundle(release='1.2.0'),'1.1.0')

    def test_check_reports_new_stable_release(self):
        tag='v1.1.0';base='https://github.com/'+updates.REPOSITORY+'/releases/download/'+tag+'/'
        release={'tag_name':tag,'assets':[{'name':name,'browser_download_url':base+name} for name in ('manager-update.zip','manager-update.zip.sha256')]}
        with tempfile.TemporaryDirectory() as tmp,patch.object(updates,'RELEASE',{'version':'1.0.0'}),patch.object(updates,'DATA',Path(tmp)),patch.object(updates,'STATE',Path(tmp)/'updates/status.json'),patch.object(updates,'fetch',return_value=json.dumps(release).encode()):
            self.assertTrue(updates.check()['available']);self.assertEqual(updates.status()['latest'],'1.1.0')
            with patch.object(updates,'fetch',side_effect=OSError('offline')):
                result=updates.check();self.assertIn('offline',result['error']);self.assertNotIn('assets',result)

    def test_checksum_failure_never_starts_update_worker(self):
        import operations
        value={'latest':'1.1.0','available':True,'assets':{'manager-update.zip':'zip','manager-update.zip.sha256':'sha'}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(updates,'DATA',Path(tmp)),patch.object(updates,'check',return_value=value),patch.object(updates,'fetch',side_effect=[b'0'*64,b'bad']),patch('operations.command') as execute:
            (Path(tmp)/'updates').mkdir()
            # Other test cases may have left queued jobs; isolate the quiescence check.
            with db() as c:c.execute("UPDATE jobs SET status='done' WHERE status IN ('queued','running')")
            with self.assertRaisesRegex(ValueError,'Prüfsumme'):updates.install('1.1.0')
            execute.assert_not_called()

class UpdateProgressTests(unittest.TestCase):
    def test_mount_probe_failure_never_launches_update_helper(self):
        import hashlib
        ident='d'*16;bundle=UpdateTests().bundle(release='1.2.1')
        value={'latest':'1.2.1','available':True,'assets':{'manager-update.zip':'zip','manager-update.zip.sha256':'sha'}}
        own={'Config':{'Labels':{'com.docker.compose.project':'windows-test'}},'Image':'test-image','Mounts':[{'Destination':'/data','Source':'C:/VMM/data/'},{'Destination':'/var/run/docker.sock','Source':'/var/run/docker.sock'}]}
        with tempfile.TemporaryDirectory() as tmp,patch.object(updates,'DATA',Path(tmp)),patch.object(updates,'check',return_value=value),patch.object(updates.secrets,'token_hex',return_value=ident),patch.object(updates,'fetch',side_effect=[hashlib.sha256(bundle).hexdigest().encode(),bundle]),patch('operations.command',side_effect=[json.dumps([own]).encode(),RuntimeError('Installationsordner falsch eingebunden')]) as execute:
            (Path(tmp)/'updates').mkdir()
            with db() as c:c.execute("UPDATE jobs SET status='done' WHERE status IN ('queued','running')")
            with self.assertRaisesRegex(RuntimeError,'falsch eingebunden'):updates.install('1.2.1')
            self.assertEqual(execute.call_count,2)
            self.assertIn('--rm',execute.call_args.args[0]);self.assertNotIn('-d',execute.call_args.args[0])
            state=json.loads((Path(tmp)/'updates/apply-status.json').read_text());self.assertEqual(state['status'],'error')

    def test_windows_installation_paths_accept_backslashes_and_trailing_separators(self):
        for raw in ('C:\\Users\\Mario\\WebsiteManager\\data\\','C:/Users/Mario/WebsiteManager/data/','/run/desktop/mnt/host/c/Users/Mario/WebsiteManager/data/'):
            own={'Mounts':[{'Destination':'/data','Source':raw}]}
            data,root=updates.installation_host_paths(own)
            self.assertEqual(data,'/run/desktop/mnt/host/c/Users/Mario/WebsiteManager/data')
            self.assertEqual(root,'/run/desktop/mnt/host/c/Users/Mario/WebsiteManager')
        with self.assertRaises(ValueError):updates.installation_host_paths({'Mounts':[{'Destination':'/data','Source':'C:/other-folder'}]})

    def test_status_stays_responsive_during_release_network_request(self):
        import threading
        started=threading.Event();release=threading.Event()
        def blocked(url,*args):
            started.set();release.wait(3);raise OSError('offline')
        with tempfile.TemporaryDirectory() as tmp,patch.object(updates,'DATA',Path(tmp)),patch.object(updates,'STATE',Path(tmp)/'updates/status.json'),patch.object(updates,'fetch',side_effect=blocked):
            thread=threading.Thread(target=updates.check);thread.start()
            try:
                self.assertTrue(started.wait(1))
                done=threading.Event()
                reader=threading.Thread(target=lambda:(updates.status(),done.set()));reader.start()
                self.assertTrue(done.wait(1),'Status request blocked by network operation')
            finally:release.set();thread.join();reader.join()

    def test_exited_helper_is_reported_as_error_and_stderr_is_visible(self):
        import subprocess
        ident='b'*16
        with tempfile.TemporaryDirectory() as tmp,patch.object(updates,'DATA',Path(tmp)),patch.object(updates,'STATE',Path(tmp)/'updates/status.json'):
            root=Path(tmp)/'updates';stage=root/ident;stage.mkdir(parents=True)
            (root/'apply-status.json').write_text(json.dumps({'id':ident,'status':'running','time':0}))
            with patch('operations.command',return_value=json.dumps([{'State':{'Status':'exited','ExitCode':1}}]).encode()),patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,b'',b'Windows mount failed')):
                value=updates.diagnostics()
            self.assertEqual(value['installation']['status'],'error')
            self.assertIn('Windows mount failed',value['diagnostics'])
            self.assertIn('Exit-Code: 1',value['diagnostics'])

    def test_old_helper_identifier_is_found_before_first_log_exists(self):
        ident='c'*16
        with tempfile.TemporaryDirectory() as tmp,patch.object(updates,'DATA',Path(tmp)):
            root=Path(tmp)/'updates';stage=root/ident;stage.mkdir(parents=True)
            (stage/'apply.py').write_text('# staged worker')
            (root/'apply-status.json').write_text(json.dumps({'status':'queued'}))
            self.assertEqual(updates.installation_status()['id'],ident)

    def test_status_tails_and_redacts_update_log(self):
        ident='a'*16
        with tempfile.TemporaryDirectory() as tmp,patch.object(updates,'DATA',Path(tmp)),patch.object(updates,'STATE',Path(tmp)/'updates/status.json'):
            root=Path(tmp)/'updates';stage=root/ident;stage.mkdir(parents=True)
            (root/'apply-status.json').write_text(json.dumps({'id':ident,'status':'running','time':0}))
            (stage/'update.log').write_text('x'*20000+'\nhttps://example.test/file?key=private-token\nlast output')
            value=updates.status()['installation']
            self.assertLessEqual(len(value['log']),3000);self.assertIn('last output',value['log'])
            self.assertNotIn('private-token',value['log']);self.assertTrue(value['waiting'])

class WorkerTests(unittest.TestCase):
    def test_failed_build_rolls_back_program_without_touching_user_files(self):
        import update_worker
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();stage=root/'data/updates/test';stage.mkdir(parents=True)
            (root/'app').mkdir();(root/'app/server.py').write_text('previous')
            (root/'.env').write_text('private settings');(root/'data/project.txt').write_text('site data')
            (root/'compose.yaml').write_text('services: {}')
            with zipfile.ZipFile(stage/'manager-update.zip','w') as z:z.writestr('app/server.py','new version')
            def run(args,**kwargs):
                if 'build' in args and (root/'app/server.py').read_text()=='new version':return subprocess.CompletedProcess(args,1,b'failed build')
                return subprocess.CompletedProcess(args,0,b'')
            def logged(args,*a,**kw):
                if run(args).returncode:raise RuntimeError('failed build')
            with patch('update_worker.run_logged',side_effect=logged),patch.dict(os.environ,{'VMM_UPDATE_PROJECT':'test-manager','VMM_UPDATE_HOST_DATA':'/host/manager/data'}),patch.object(update_worker.subprocess,'run',side_effect=run),patch.object(update_worker.subprocess,'check_output',return_value='29.1.0'):
                with self.assertRaises(RuntimeError):update_worker.apply(root,'test')
            self.assertEqual((root/'app/server.py').read_text(),'previous')
            self.assertEqual((root/'.env').read_text(),'private settings');self.assertEqual((root/'data/project.txt').read_text(),'site data')
            self.assertEqual(json.loads((root/'data/updates/apply-status.json').read_text())['status'],'error')
            override=json.loads((stage/'compose.update.json').read_text())
            self.assertIn('/host/manager/data:/data',override['services']['manager']['volumes'])

    def test_build_keeps_manager_available_until_restart(self):
        import update_worker,subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();stage=root/'data/updates/test';stage.mkdir(parents=True)
            (root/'app').mkdir();(root/'app/server.py').write_text('old')
            (root/'compose.yaml').write_text('services: {}')
            with zipfile.ZipFile(stage/'manager-update.zip','w') as z:
                z.writestr('app/server.py','new');z.writestr('scripts/setup.py','def protocol_routes(root): pass')
            calls=[]
            def logged(args,*a,**kw):calls.append(args)
            def output(args,**kw):return '29.1.0' if 'version' in args else 'test-manager'
            with patch.dict(os.environ,{'VMM_UPDATE_PROJECT':'isolated-test','VMM_UPDATE_HOST_DATA':'/host/test/data'}),patch('update_worker.run_logged',side_effect=logged),patch('update_worker.subprocess.check_output',side_effect=output),patch('update_worker.subprocess.run',return_value=subprocess.CompletedProcess([],0)):
                update_worker.apply(root,'test')
            build=next(i for i,a in enumerate(calls) if 'build' in a)
            stop=next(i for i,a in enumerate(calls) if 'stop' in a)
            self.assertLess(build,stop)
            self.assertEqual(json.loads((root/'data/updates/apply-status.json').read_text())['status'],'done')

    def test_docker_output_is_visible_before_command_finishes(self):
        import update_worker
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);log=root/'update.log';signal=root/'continue'
            script="import sys,time,pathlib; print('first output',flush=True); p=pathlib.Path(sys.argv[1]); end=time.monotonic()+5\nwhile not p.exists() and time.monotonic()<end: time.sleep(.01)\nprint('finished',flush=True); sys.exit(0 if p.exists() else 2)"
            def heartbeat():
                if 'first output' in log.read_text():signal.touch()
            update_worker.run_logged([sys.executable,'-c',script,str(signal)],root,os.environ.copy(),log,heartbeat,timeout=8)
            self.assertTrue(signal.exists());self.assertIn('finished',log.read_text())

    def test_failing_command_keeps_stderr_for_diagnosis(self):
        import update_worker
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'update.log'
            with self.assertRaisesRegex(RuntimeError,'Exit-Code 7'):
                update_worker.run_logged([sys.executable,'-c',"import sys; print('specific failure',file=sys.stderr); sys.exit(7)"],Path(tmp),os.environ.copy(),log,lambda:None)
            self.assertIn('specific failure',log.read_text())

    def test_both_wrong_protocols_have_dedicated_redirects(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('qa_setup',Path(__file__).resolve().parents[1]/'scripts/setup.py');setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)
        with tempfile.TemporaryDirectory() as tmp:
            setup.protocol_routes(Path(tmp));value=json.loads((Path(tmp)/'infra/dynamic/protocols.yaml').read_text())['http']
            self.assertEqual(value['middlewares']['vmm-protocol-tls84']['redirectScheme'],{'scheme':'https','port':'8184','permanent':False})
            self.assertNotIn('tls',value['routers']['vmm-protocol-tls84'])
            self.assertEqual(value['middlewares']['vmm-protocol-php84']['redirectScheme']['scheme'],'http')
            self.assertEqual(value['routers']['vmm-protocol-php84']['tls'],{})
