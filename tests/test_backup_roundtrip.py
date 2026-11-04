"""Exercise import defaults, local settings and archive restoration together."""
from contextlib import ExitStack, nullcontext
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _data=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_data.name
import backup_service
import operations
import project_files
import shared_operations
import shared_runtime

ROOT=Path(__file__).resolve().parents[1]


class BackupRoundTripTests(unittest.TestCase):
    def fixture(self,root,cms):
        site=root/'site';site.mkdir();tools=root/'tools'
        config='configuration.php' if cms=='joomla' else 'wp-config.php'
        if cms=='joomla':
            (site/'administrator').mkdir()
            source="""<?php class JConfig {
public $host='live-db';public $user='live-user';public $password='live;password';public $db='live-database';
public $sitename='Original Website';public $mailonline=true;public $mailer='smtp';
public $smtphost='smtp.example.org';public $smtpuser='smtp-user';public $smtppass='smtp-secret';
public $mailfrom='website@example.org';public $fromname='Original Sender';
public $live_site='https://example.org';public $force_ssl=2;
public $log_path='/live/logs';public $tmp_path='/live/tmp';}
"""
        else:
            (site/'wp-includes').mkdir();(site/'wp-includes/version.php').write_text("<?php $wp_version='6.8';")
            source="""<?php
define('DB_HOST','live-db');define('DB_USER','live-user');define('DB_PASSWORD','live;password');define('DB_NAME','live-database');
define('WP_HOME','https://example.org');define('WP_SITEURL','https://example.org');
define('FORCE_SSL_ADMIN',true);define('WP_ENVIRONMENT_TYPE','production');
define('SMTP_HOST','smtp.example.org');define('SMTP_PASSWORD','smtp-secret');
"""
        (site/config).write_text(source)
        (site/'.htaccess').write_text('original redirects and access settings')
        (site/'htaccess.txt').write_text('local template')
        (site/'.user.ini').write_text('original PHP settings')
        native=site/'installation/src/Framework/Cli';native.mkdir(parents=True)
        (native/'InstallationQueue.php').touch()
        project_files.prepare_local(site,tools)
        return site,tools,config,source

    def test_joomla_and_wordpress_import_and_export_preserve_original_settings(self):
        for cms in ('joomla','wordpress'):
            with self.subTest(cms=cms),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);site,tools,config,source=self.fixture(root,cms)
                p={'slug':'roundtrip','cms':cms,'php':'8.4','storage':'shared','db_password':'local-secret'}
                calls=[]
                def php(project,args,**kwargs):
                    calls.append(args)
                    if args[-1]=='config:make':return b''
                    if args[-1]=='execute':
                        # An installer can regenerate incorrect defaults; these must not survive.
                        (site/config).write_text("<?php /* Your Joomla Site; mailonline=false */")
                        return b'Restoration complete'
                    if args[-1]=='/vmm-tools/restore-backup.php':return b'VMM_CONFIGURED'
                    if args[:4]==['wp','--allow-root','config','set']:
                        key,value=args[4:6];literal=value if '--raw' in args else json.dumps(value)
                        text=(site/config).read_text()
                        (site/config).write_text(re.sub(r"define\('"+key+r"',.*?\);",lambda m:"define('"+key+"',"+literal+");",text))
                        return b''
                    self.fail('Unexpected command: '+repr(args))
                for name,value in [('folder',lambda p:root),('exec_php',php),('write_tools',lambda p:None),('compatible',lambda *a:None),('ensure_runtime',lambda *a:None),('check_modules',lambda *a:None),('transition',lambda *a:None),('project',lambda name:p),('db',lambda:nullcontext(Mock()))]:
                    stack.enter_context(patch.object(operations,name,value))
                stack.enter_context(patch.object(backup_service,'project',return_value=p))
                stack.enter_context(patch.object(backup_service,'db',side_effect=lambda:nullcontext(Mock())))
                stack.enter_context(patch('compatibility.resolve'))
                stack.enter_context(patch.object(shared_operations,'ensure_database'))
                info={'host':'local-db','database':'local-database','user':'local-user','password':'local-secret'}
                stack.enter_context(patch.object(shared_operations,'database_info',return_value=info))
                stack.enter_context(patch.object(shared_runtime,'database_info',return_value=info))
                backup_service.restore('roundtrip')
                local=(site/config).read_text()
                self.assertIn('local-db',local);self.assertIn('smtp-secret',local)
                if cms=='joomla':
                    self.assertIn("$sitename='Original Website'",local)
                    self.assertIn('$mailonline=false',local)
                else:
                    self.assertIn('roundtrip.vmm.test',local)
                    self.assertFalse(any('search-replace' in cmd or 'option' in cmd for cmd in calls))
                # Edits made after import must be present in both kinds of backup.
                (site/'new-content.txt').write_text('new local content')
                before={str(f.relative_to(site)):f.read_bytes() for f in site.rglob('*') if f.is_file()}
                entries=dict((name,path.read_bytes()) for path,name in project_files.archive_entries(site,tools))
                self.assertEqual(entries[config],source.encode())
                self.assertEqual(entries['.htaccess'],b'original redirects and access settings')
                self.assertEqual(entries['.user.ini'],b'original PHP settings')
                self.assertEqual(entries['new-content.txt'],b'new local content')
                self.assertFalse(any('vmm-original' in name for name in entries))
                self.assertNotIn('wp-content/mu-plugins/vmm-local.php',entries)
                if shutil.which('php'):
                    # Feed the same import into the actual PHP adapter used by Akeeba.
                    mapping,required=project_files.archive_mapping(site,tools)
                    (tools/'akeeba-originals.json').write_text(json.dumps(mapping))
                    shutil.copyfile(ROOT/'app/tools/akeeba-originals-archiver.php',tools/'adapter.php')
                    runner=tools/'runner.php';runner.write_text('''<?php
namespace Akeeba\\Engine\\Archiver;
class Jpa {
 public $entries=[];
 protected function _addFile($virtual,&$source,$target){$this->entries[$target]=$virtual?$source:file_get_contents($source);return true;}
 public function add($source,$target){return $this->_addFile(false,$source,$target);}
}
require __DIR__.'/adapter.php';putenv('VMM_PROJECT_ROOT='.$argv[1]);$archive=new Vmmjpa();
foreach(new \\RecursiveIteratorIterator(new \\RecursiveDirectoryIterator($argv[1],\\FilesystemIterator::SKIP_DOTS)) as $f){if($f->isFile())$archive->add($f->getPathname(),substr($f->getPathname(),strlen($argv[1])+1));}
echo json_encode($archive->entries);
''')
                    output=subprocess.run(['php',str(runner),str(site)],capture_output=True,check=True,text=True)
                    akeeba_entries=json.loads(output.stdout)
                    self.assertEqual(akeeba_entries[config],source)
                    self.assertEqual(akeeba_entries,{name:data.decode() for name,data in entries.items()})
                    report=json.loads((tools/'akeeba-originals-report.json').read_text())
                    self.assertTrue(all(report.get(name) for name in required))
                self.assertEqual(before,{str(f.relative_to(site)):f.read_bytes() for f in site.rglob('*') if f.is_file()})
