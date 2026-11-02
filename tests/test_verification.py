import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _isolated=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_isolated.name
import server
import verification_service as verification
import cleanup_service as cleanup
import update_service as updates
from store import db


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for module in (verification,cleanup):
            p=patch.object(module,'DATA',self.root);p.start();self.addCleanup(p.stop)
        with db() as c:c.execute("UPDATE jobs SET status='done' WHERE status IN ('queued','running')")

    def test_failed_restore_cleans_unique_containers_and_retains_original(self):
        archive=self.root/'exports/fixture.zip';archive.parent.mkdir();archive.write_bytes(b'not-a-zip')
        calls=[]
        with patch('operations.command',side_effect=lambda args,**kw:calls.append(args) or b''):
            with self.assertRaisesRegex(ValueError,'Wiederherstellungsprobe fehlgeschlagen'):verification.run('export',archive.name)
        self.assertEqual(archive.read_bytes(),b'not-a-zip')
        report=verification.result('export',archive.name);self.assertEqual(report['status'],'error')
        self.assertEqual(calls,[['docker','rm','-f',report['network']+'-php'],['docker','rm','-f',report['network']+'-db'],['docker','network','rm',report['network']]])
        self.assertFalse(list((self.root/'verification/runs').iterdir()))

    def test_running_probe_blocks_deletion(self):
        archive=self.root/'exports/fixture.zip';archive.parent.mkdir();archive.write_bytes(b'archive')
        with db() as c:c.execute("INSERT INTO jobs VALUES(?,?,'backup-verify','running','',0,NULL)",(secrets.token_hex(12),'verify-export-fixture.zip'))
        with self.assertRaisesRegex(ValueError,'Prüfung'):cleanup.delete('export','fixture.zip')
        self.assertTrue(archive.exists())

    def test_verification_failure_does_not_mark_valid_backup_incomplete(self):
        ident=secrets.token_hex(12);folder=self.root/'backups'/ident;folder.mkdir(parents=True)
        file=folder/'manager-backup.json';file.write_text(json.dumps({'status':'complete','files':['site.jpa']}))
        verification.write_report('backup',ident,{'status':'error','message':'HTTP 500','containers':['private-test']})
        value=json.loads(file.read_text());self.assertEqual(value['status'],'complete');self.assertEqual(value['files'],['site.jpa'])
        self.assertNotIn('containers',value['verification'])

    def test_restart_cleanup_ignores_untrusted_container_identifiers(self):
        file=verification.report_file('export','fixture.zip');file.parent.mkdir(parents=True)
        file.write_text(json.dumps({'id':'../../production','kind':'export','source':'fixture.zip','status':'running'}))
        with patch('operations.command') as execute:verification.recover_interrupted()
        execute.assert_not_called()

    def test_old_update_error_is_history_while_running_update_is_current(self):
        file=self.root/'updates/apply-status.json';file.parent.mkdir()
        with patch.object(updates,'DATA',self.root):
            file.write_text(json.dumps({'status':'error','message':'old missing apply.py'}))
            value=updates.installation_status();self.assertTrue(value['historical']);self.assertEqual(value['installed_version'],updates.RELEASE['version'])
            file.write_text(json.dumps({'status':'running'}))
            self.assertFalse(updates.installation_status()['historical'])

class VerificationConfigTests(unittest.TestCase):
    def test_joomla_and_wordpress_rewrite_only_the_clone_including_quoted_passwords(self):
        import shutil
        import subprocess
        php=shutil.which('php')
        if not php:self.skipTest('PHP CLI is not installed on this runner')
        helper=Path(__file__).resolve().parents[1]/'app/tools/verification-config.php'
        cases=[('configuration.php',"<?php class JConfig {public $host='production';public $user='prod';public $password='old;password';public $db='prod';}"),('wp-config.php',"<?php define('DB_HOST','production');define('DB_USER','prod');define('DB_PASSWORD','old;password');define('DB_NAME','prod');")]
        for filename,source in cases:
            with self.subTest(filename=filename),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);file=root/filename;file.write_text(source)
                result=__import__('subprocess').run([php,str(helper)],cwd=root,input=json.dumps({'host':'verify-db','database':'vmm_verify','user':'vmm_verify','password':"fixture;'key"}).encode(),capture_output=True,env={**os.environ,'VMM_VERIFICATION':'1'},check=True)
                self.assertIn(b'VMM_ISOLATED_CONFIGURED',result.stdout)
                subprocess.run([php,'-l',str(file)],capture_output=True,check=True)
                self.assertIn('verify-db',file.read_text());self.assertNotIn('production',file.read_text());self.assertNotIn('old;password',file.read_text())

    def test_helper_refuses_to_run_without_isolation_marker(self):
        import shutil
        import subprocess
        php=shutil.which('php')
        if not php:self.skipTest('PHP CLI is not installed on this runner')
        helper=Path(__file__).resolve().parents[1]/'app/tools/verification-config.php'
        env={k:v for k,v in os.environ.items() if k!='VMM_VERIFICATION'}
        self.assertNotEqual(subprocess.run([php,str(helper)],input=b'{}',capture_output=True,env=env).returncode,0)
