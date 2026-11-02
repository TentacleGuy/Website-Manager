import os,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _temp=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_temp.name
import server,cleanup_service as cleanup,file_service as files
from catalog import identify_package
class FileManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        p=patch.object(cleanup,'DATA',self.root);p.start();self.addCleanup(p.stop)
        (self.root/'exports').mkdir();(self.root/'exports/fixture.zip').write_bytes(b'fixture')
    def test_known_archive_lists_and_downloads(self):
        value=files.entries('export','fixture.zip');self.assertEqual(value['files'][0]['name'],'fixture.zip')
        self.assertEqual(files.file('export','fixture.zip',value['files'][0]['path']).read_bytes(),b'fixture')
    def test_traversal_and_linked_files_are_rejected(self):
        for path in ('0/../../private','/etc/passwd','0/other.zip','1/fixture.zip'):
            with self.assertRaises(ValueError):files.file('export','fixture.zip',path)
        (self.root/'exports/link.zip').symlink_to(self.root/'exports/fixture.zip')
        with self.assertRaises(ValueError):files.entries('export','link.zip')
    def test_cms_package_versions_are_detected_without_running_php(self):
        path=self.root/'wp.zip'
        with zipfile.ZipFile(path,'w') as z:z.writestr('wordpress/wp-includes/version.php',"<?php $wp_version='7.1.4';")
        self.assertEqual(identify_package(path,'wordpress'),'7.1.4')
        with self.assertRaises(ValueError):identify_package(path,'joomla')
        with zipfile.ZipFile(path,'w') as z:z.writestr('libraries/src/Version.php','<?php const MAJOR_VERSION=5;const MINOR_VERSION=4;const PATCH_VERSION=10;')
        self.assertEqual(identify_package(path,'joomla'),'5.4.10')
