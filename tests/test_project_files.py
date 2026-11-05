import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import project_files as files
ROOT=Path(__file__).resolve().parents[1]


class LocalServerFileTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        site=root/'site';tools=root/'tools';site.mkdir();return site,tools

    def test_import_preserves_production_and_activates_only_existing_htaccess(self):
        site,tools=self.fixture()
        for name in files.SERVER_FILES:(site/name).write_text('production '+name)
        (site/'htaccess.txt').write_text('local rewrite rules')
        files.prepare_local(site,tools)
        self.assertEqual((site/'.htaccess').read_text(),'local rewrite rules')
        self.assertFalse((site/'htaccess.txt').exists())
        for name in files.SERVER_FILES:self.assertEqual((site/(name+'.vmm-original')).read_text(),'production '+name)
        self.assertFalse((site/'php.ini').exists());self.assertFalse((site/'.user.ini').exists())
        mapping,required=files.archive_mapping(site,tools)
        self.assertEqual(mapping['.htaccess'],'htaccess.txt');self.assertIn('.htaccess',required)
        self.assertEqual(mapping['.user.ini.vmm-original'],'.user.ini')

    def test_cms_original_and_manager_plugin_export(self):
        site,tools=self.fixture()
        original="<?php class JConfig {public $sitename='Example';public $mailonline=true;}"
        (site/'configuration.php').write_text(original)
        files.prepare_local(site,tools)
        (site/'configuration.php').write_text('local configuration')
        plugin=site/'wp-content/mu-plugins/vmm-local.php'
        plugin.parent.mkdir(parents=True);plugin.write_text('local mail filter')
        (site/'vmm-manager-login.php').write_text('manager login')
        entries={name:path.read_text() for path,name in files.archive_entries(site,tools)}
        self.assertEqual(entries['configuration.php'],original)
        self.assertNotIn('configuration.php.vmm-original.php',entries)
        self.assertNotIn('wp-content/mu-plugins/vmm-local.php',entries)
        self.assertNotIn('vmm-manager-login.php',entries)
        self.assertEqual((site/'configuration.php').read_text(),'local configuration')

    def test_wordpress_original_config_and_existing_mu_plugin_are_restored(self):
        site,tools=self.fixture()
        config="<?php define('WP_HOME','https://example.org'); define('FORCE_SSL_ADMIN',true);"
        (site/'wp-config.php').write_text(config)
        plugin=site/'wp-content/mu-plugins/vmm-local.php'
        plugin.parent.mkdir(parents=True);plugin.write_text('original plugin')
        files.prepare_local(site,tools)
        (site/'wp-config.php').write_text('local config')
        plugin.write_text('manager override')
        entries={name:path.read_text() for path,name in files.archive_entries(site,tools)}
        self.assertEqual(entries['wp-config.php'],config)
        self.assertEqual(entries['wp-content/mu-plugins/vmm-local.php'],'original plugin')
        self.assertFalse(any('vmm-original' in name for name in entries))
        self.assertEqual(plugin.read_text(),'manager override')
        self.assertFalse((plugin.parent/'vmm-local.php.vmm-original.php').exists())

    def test_missing_or_changed_original_never_falls_back_to_local_config(self):
        for change in ('missing','modified'):
            with self.subTest(change=change):
                site,tools=self.fixture()
                (site/'configuration.php').write_text('original config')
                files.prepare_local(site,tools)
                (site/'configuration.php').write_text('local config with mail disabled')
                saved=site/'configuration.php.vmm-original.php'
                if change=='missing':saved.unlink()
                else:saved.write_text('changed original')
                with self.assertRaisesRegex(ValueError,'Originaldatei fehlt oder wurde verändert'):
                    list(files.archive_entries(site,tools))

    def test_server_file_generated_only_locally_is_not_exported(self):
        site,tools=self.fixture();files.prepare_local(site,tools)
        (site/'.htaccess').write_text('local redirect')
        self.assertNotIn('.htaccess',dict((name,path) for path,name in files.archive_entries(site,tools)))

    def test_preservation_failure_removes_partial_copies(self):
        site,tools=self.fixture();(site/'configuration.php').write_text('source config')
        with patch.object(files.shutil,'copyfileobj',side_effect=OSError('copy failed')):
            with self.assertRaises(OSError):files.prepare_local(site,tools)
        self.assertEqual((site/'configuration.php').read_text(),'source config')
        self.assertFalse((site/'configuration.php.vmm-original.php').exists())
        self.assertFalse((tools/files.MANIFEST).exists())

    def test_only_installer_generated_configuration_backup_is_excluded(self):
        for original_present in (False,True):
            with self.subTest(original_present=original_present):
                site,tools=self.fixture()
                if original_present:(site/'configuration.bak.php').write_text('original backup')
                files.prepare_local(site,tools)
                if not original_present:(site/'configuration.bak.php').write_text('generated local backup')
                entries={name:path.read_text() for path,name in files.archive_entries(site,tools)}
                if original_present:self.assertEqual(entries['configuration.bak.php'],'original backup')
                else:self.assertNotIn('configuration.bak.php',entries)

    def test_template_is_left_untouched_without_previous_htaccess(self):
        site,tools=self.fixture();(site/'htaccess.txt').write_text('template')
        files.prepare_local(site,tools)
        self.assertTrue((site/'htaccess.txt').exists());self.assertFalse((site/'.htaccess').exists())
        self.assertEqual(files.archive_mapping(site,tools),({},[]))

    def test_original_only_import_and_older_manager_imports(self):
        site,tools=self.fixture();(site/'.htaccess.vmm-original').write_text('production')
        (site/'htaccess.txt').write_text('local')
        files.prepare_local(site,tools)
        self.assertEqual((site/'.htaccess').read_text(),'local')
        self.assertEqual((site/'.htaccess.vmm-original').read_text(),'production')

    def test_ambiguous_files_are_never_overwritten(self):
        site,tools=self.fixture();(site/'.htaccess').write_text('one');(site/'.htaccess.vmm-original').write_text('two')
        with self.assertRaisesRegex(ValueError,'Mehrdeutige'):files.prepare_local(site,tools)
        self.assertEqual((site/'.htaccess').read_text(),'one');self.assertEqual((site/'.htaccess.vmm-original').read_text(),'two')

    def test_zip_project_export_uses_original_names_and_preserves_local_template(self):
        site,tools=self.fixture()
        for name in files.SERVER_FILES:(site/name).write_text('production '+name)
        (site/'htaccess.txt').write_text('local')
        files.prepare_local(site,tools)
        target=site.parent/'export.zip'
        with zipfile.ZipFile(target,'w') as archive:
            for path,name in files.archive_entries(site,tools):archive.write(path,'site/'+name)
        with zipfile.ZipFile(target) as archive:
            self.assertEqual(archive.read('site/.htaccess'),b'production .htaccess')
            self.assertEqual(archive.read('site/htaccess.txt'),b'local')
            self.assertFalse(any(name.endswith('.vmm-original') for name in archive.namelist()))
        self.assertEqual((site/'.htaccess').read_text(),'local')

    def test_failure_rolls_back_all_renames(self):
        site,tools=self.fixture();(site/'.htaccess').write_text('production');(site/'htaccess.txt').write_text('local')
        tools.write_text('not a directory')
        with self.assertRaises(OSError):files.prepare_local(site,tools)
        self.assertEqual((site/'.htaccess').read_text(),'production');self.assertEqual((site/'htaccess.txt').read_text(),'local')
        self.assertFalse((site/'.htaccess.vmm-original').exists())

    @unittest.skipUnless(shutil.which('php'),'PHP CLI required for archive adapter integration')
    def test_archive_mapping_keeps_live_files_and_round_trips_names_and_contents(self):
        site,tools=self.fixture()
        for name in files.SERVER_FILES:(site/name).write_text('production '+name)
        (site/'htaccess.txt').write_text('local rewrite rules')
        files.prepare_local(site,tools)
        (site/'subdir').mkdir();(site/'subdir/.htaccess').write_text('nested rules')
        before={str(p.relative_to(site)):p.read_bytes() for p in site.rglob('*') if p.is_file()}
        mapping,required=files.archive_mapping(site,tools)
        (tools/'akeeba-originals.json').write_text(json.dumps(mapping))
        shutil.copyfile(ROOT/'app/tools/akeeba-originals-archiver.php',tools/'akeeba-originals-archiver.php')
        shutil.copyfile(ROOT/'app/tools/akeeba-local.php',tools/'akeeba-local.php')
        script=tools/'test.php';script.write_text('''<?php
namespace Akeeba\\Engine\\Archiver;
class Jpa {
    public $entries=[];
    protected function _addFile($virtual,&$source,$target){$this->entries[$target]=$virtual?$source:file_get_contents($source);return true;}
    public function add($source,$target){return $this->_addFile(false,$source,$target);}
}
require __DIR__.'/akeeba-local.php';
$root=$argv[1];putenv('VMM_PROJECT_ROOT='.$root);$archive=new Vmmjpa();
foreach(new \\RecursiveIteratorIterator(new \\RecursiveDirectoryIterator($root,\\FilesystemIterator::SKIP_DOTS)) as $file){if($file->isFile())$archive->add($file->getPathname(),substr($file->getPathname(),strlen($root)+1));}
echo json_encode($archive->entries);
''')
        run=subprocess.run(['php',str(script),str(site.resolve())],capture_output=True,check=True,text=True)
        archive=json.loads(run.stdout)
        for name in files.SERVER_FILES:self.assertEqual(archive[name],'production '+name)
        self.assertEqual(archive['htaccess.txt'],'local rewrite rules');self.assertEqual(archive['subdir/.htaccess'],'nested rules')
        self.assertFalse(any(n.endswith('.vmm-original') for n in archive))
        after={str(p.relative_to(site)):p.read_bytes() for p in site.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        seen=json.loads((tools/'akeeba-originals-report.json').read_text());self.assertTrue(all(seen.get(n) for n in required))
        other=site.parent/'restored';other.mkdir()
        for name,content in archive.items():p=other/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
        files.prepare_local(other,site.parent/'other-tools')
        self.assertEqual((other/'.htaccess').read_text(),'local rewrite rules')
        self.assertEqual((other/'.htaccess.vmm-original').read_text(),'production .htaccess')

    @unittest.skipUnless(shutil.which('php'),'PHP CLI required for archive adapter integration')
    def test_archive_adapter_skip_succeeds_and_failed_writes_are_not_confirmed(self):
        site,tools=self.fixture();tools.mkdir()
        (site/'.user.ini').write_text('local')
        (site/'.user.ini.vmm-original').write_text('production')
        (tools/'akeeba-originals.json').write_text(json.dumps({'.user.ini':None,'.user.ini.vmm-original':'.user.ini'}))
        shutil.copyfile(ROOT/'app/tools/akeeba-originals-archiver.php',tools/'akeeba-originals-archiver.php')
        script=tools/'test.php';script.write_text('''<?php
namespace Akeeba\\Engine\\Archiver;
class Jpa {
    public $calls=0;
    protected function _addFile($virtual,&$source,$target){$this->calls++;return false;}
    public function add($source,$target){return $this->_addFile(false,$source,$target);}
}
require __DIR__.'/akeeba-originals-archiver.php';
putenv('VMM_PROJECT_ROOT='.$argv[1]);$archive=new Vmmjpa();
$skip=$archive->add($argv[1].'/.user.ini','.user.ini');
$failed=$archive->add($argv[1].'/.user.ini.vmm-original','.user.ini.vmm-original');
echo json_encode([$skip,$failed,$archive->calls,is_file(__DIR__.'/akeeba-originals-report.json')]);
''')
        run=subprocess.run(['php',str(script),str(site.resolve())],capture_output=True,check=True,text=True)
        self.assertEqual(json.loads(run.stdout),[True,False,1,False])
