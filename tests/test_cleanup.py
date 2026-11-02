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
import cleanup_service as cleanup
from store import db


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data_patch=patch.object(cleanup,'DATA',self.root);self.data_patch.start();self.addCleanup(self.data_patch.stop)
        with db() as c:c.execute("UPDATE jobs SET status='done' WHERE status IN ('queued','running')")
        self.ident=secrets.token_hex(12)

    def package(self,project=False,prepared=False):
        folder=self.root/'packages';folder.mkdir(exist_ok=True);path=folder/(self.ident+'.zip');path.write_bytes(b'archive')
        with db() as c:
            c.execute('INSERT INTO packages VALUES (?,?,?,?,?,?,?,?)',(self.ident,'joomla','5.4.9',path.name,'0'*64,7,'fixture',0))
            if project:c.execute("INSERT INTO projects (slug,cms,php,status,created,package_id) VALUES (?,?,?,'stopped',0,?)",('cleanup-'+self.ident[:8],'joomla','8.4',self.ident))
        if project and prepared:
            site=self.root/'projects'/('cleanup-'+self.ident[:8])/'site';site.mkdir(parents=True);(site/'index.php').write_text('website')
        return path

    def test_installed_cms_package_can_be_removed_without_removing_website(self):
        archive=self.package(project=True,prepared=True);site=self.root/'projects'/('cleanup-'+self.ident[:8])/'site/index.php'
        cleanup.delete('cms',self.ident)
        self.assertFalse(archive.exists());self.assertEqual(site.read_text(),'website')
        with db() as c:
            self.assertIsNone(c.execute('SELECT id FROM packages WHERE id=?',(self.ident,)).fetchone())
            self.assertIsNone(c.execute('SELECT package_id FROM projects WHERE slug=?',('cleanup-'+self.ident[:8],)).fetchone()['package_id'])

    def test_unprepared_project_protects_required_cms_package(self):
        archive=self.package(project=True)
        with self.assertRaisesRegex(ValueError,'benötigt'):cleanup.delete('cms',self.ident)
        self.assertTrue(archive.exists())

    def test_source_deletion_removes_packages_and_assignments_not_installed_site(self):
        folder=self.root/'extensions';folder.mkdir();file=folder/(self.ident+'.zip');file.write_bytes(b'package')
        source=secrets.token_hex(12);name='cleanup-ext-'+self.ident[:8]
        site=self.root/'projects'/name/'site';site.mkdir(parents=True);(site/'plugin.php').write_text('installed')
        with db() as c:
            c.execute('INSERT INTO extension_sources (id,config) VALUES (?,?)',(source,json.dumps({'name':'Library extension','cms':'wordpress'})))
            c.execute("INSERT INTO projects(slug,cms,php,status,created) VALUES (?,'wordpress','8.4','running',0)",(name,))
            c.execute('INSERT INTO extensions (id,name,cms,kind,provider,version,filename,sha256,created,source_id,archived) VALUES (?,?,?,?,?,?,?,?,?,?,1)',(self.ident,'Extension','wordpress','plugin','custom','1.0',file.name,'0'*64,0,source))
            c.execute('INSERT INTO extension_plans(project,source,status) VALUES (?,?,?)',(name,source,'installed'))
            c.execute('INSERT INTO project_extensions(project,extension,status) VALUES (?,?,?)',(name,self.ident,'installed'))
        cleanup.delete('extension',source)
        self.assertFalse(file.exists());self.assertEqual((site/'plugin.php').read_text(),'installed')
        with db() as c:self.assertIsNone(c.execute('SELECT id FROM extension_sources WHERE id=?',(source,)).fetchone())

    def test_all_backup_parts_are_removed_together(self):
        folder=self.root/'backups'/self.ident;folder.mkdir(parents=True)
        for name in ('site.jpa','site.j01','site.j02'):(folder/name).write_bytes(b'part')
        cleanup.delete('backup',self.ident);self.assertFalse(folder.exists())

    def test_active_backup_and_restore_are_protected(self):
        folder=self.root/'backups'/self.ident;folder.mkdir(parents=True);(folder/'manager-backup.json').write_text('{"status":"creating"}')
        with self.assertRaisesRegex(ValueError,'erstellt'):cleanup.delete('backup',self.ident)
        (folder/'manager-backup.json').write_text('{"status":"complete"}')
        with db() as c:c.execute("INSERT INTO projects (slug,cms,php,status,created,restore,backup_group) VALUES (?,'joomla','8.4','error',0,1,?)",('restore-'+self.ident[:8],self.ident))
        with self.assertRaisesRegex(ValueError,'Wiederherstellung'):cleanup.delete('backup',self.ident)

    def test_symlinks_and_path_traversal_are_rejected(self):
        outer=self.root/'keep';outer.write_text('keep');(self.root/'exports').mkdir();(self.root/'exports/linked.zip').symlink_to(outer)
        for ident in ('../keep','linked.zip','/tmp/keep.zip'):
            with self.assertRaises(ValueError):cleanup.delete('export',ident)
        self.assertEqual(outer.read_text(),'keep')

    def test_failed_rename_rolls_back_metadata_and_original_file(self):
        archive=self.package()
        with patch.object(Path,'rename',side_effect=OSError('permission denied')):
            with self.assertRaises(OSError):cleanup.delete('cms',self.ident)
        self.assertTrue(archive.exists())
        with db() as c:self.assertIsNotNone(c.execute('SELECT id FROM packages WHERE id=?',(self.ident,)).fetchone())

    def test_failed_purge_is_visible_as_removable_residue(self):
        archive=self.package()
        with patch.object(Path,'unlink',side_effect=OSError('locked file')):result=cleanup.delete('cms',self.ident)
        self.assertEqual(result['remaining'],1);self.assertFalse(archive.exists())
        residues=[x for x in cleanup.inventory()['items'] if x['kind']=='residue'];self.assertEqual(len(residues),1)
        cleanup.delete('residue',residues[0]['id']);self.assertFalse(list((self.root/'packages').iterdir()))

    def test_update_cache_and_kickstart_downloads_are_removable(self):
        update='a'*16;folder=self.root/'updates'/update;folder.mkdir(parents=True);(folder/'manager-update.zip').write_bytes(b'zip')
        kick=self.root/'tools/kickstart/9.2.0';kick.mkdir(parents=True);(kick/'kickstart.php').write_text('<?php')
        cleanup.delete('manager-download',update);cleanup.delete('kickstart','9.2.0')
        self.assertFalse(folder.exists());self.assertFalse(kick.exists())

    def test_project_trash_can_be_removed_without_traversing_it_for_the_list(self):
        ident='removed-project-1793335103-abcdef';folder=self.root/'trash'/ident;folder.mkdir(parents=True)
        (folder/'database.sql').write_text('fixture database')
        with patch.object(Path,'rglob',side_effect=AssertionError('inventory must not recursively scan old projects')):
            items=cleanup.inventory()['items']
        item=next(x for x in items if x['kind']=='trash');self.assertIsNone(item['size'])
        cleanup.delete('trash',ident);self.assertFalse(folder.exists())
