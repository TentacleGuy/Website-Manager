import sys
from pathlib import Path
import tempfile
import unittest
import zipfile
import stat
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from catalog import checked_url, validate_zip, unpack

class ArchiveTests(unittest.TestCase):
    def test_block_path_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.zip'
            for name in ('../outside.php','/absolute.php','a\\b.php','C:/evil.php'):
                with zipfile.ZipFile(path,'w') as z:z.writestr(name,'test')
                with self.assertRaises(ValueError):validate_zip(path)
            info=zipfile.ZipInfo('link');info.external_attr=(stat.S_IFLNK|0o777)<<16
            with zipfile.ZipFile(path,'w') as z:z.writestr(info,'/etc/passwd')
            with self.assertRaises(ValueError):validate_zip(path)

    def test_wordpress_wrapper_removed_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'good.zip';target=Path(tmp)/'site'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('wordpress/wp-includes/version.php','<?php');z.writestr('wordpress/index.php','<?php')
            unpack(path,target)
            self.assertTrue((target/'wp-includes'/'version.php').exists())
            self.assertTrue((target/'index.php').exists())
            with self.assertRaises(ValueError):unpack(path,target)

    def test_only_official_download_origins(self):
        self.assertEqual(checked_url('https://downloads.wordpress.org/release/wordpress-6.8.zip'),'https://downloads.wordpress.org/release/wordpress-6.8.zip')
        for url in ('http://wordpress.org/file.zip','https://wordpress.org.evil.test/file.zip','https://127.0.0.1/file.zip','https://user:pass@wordpress.org/file.zip','https://wordpress.org:8443/file.zip'):
            with self.assertRaises(ValueError):checked_url(url)

if __name__=='__main__':unittest.main()
