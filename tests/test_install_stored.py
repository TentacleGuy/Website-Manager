import os,sys,tempfile,secrets,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _temp=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_temp.name
import extension_service as ext
from store import db
class StoredInstallTests(unittest.TestCase):
    def setUp(self):
        self.name='upload-'+secrets.token_hex(4);self.ident=secrets.token_hex(12)
        with db() as c:
            c.execute("INSERT INTO projects(slug,cms,php,status,created) VALUES(?,'wordpress','8.4','running',0)",(self.name,))
            c.execute("INSERT INTO extensions(id,name,cms,kind,provider,version,filename,sha256,created,archived) VALUES(?,'Fixture','wordpress','plugin','custom','1.0','fixture.zip',?,0,1)",(self.ident,'0'*64))
    def test_installs_exact_uploaded_id_without_release_resolution(self):
        with patch.object(ext,'ready',return_value=True),patch('operations.install_extension',return_value='installed') as install,patch.object(ext,'download_package') as resolve:
            ext.install_stored(self.name,self.ident)
        install.assert_called_once_with(self.name,self.ident);resolve.assert_not_called()
        with db() as c:self.assertEqual(c.execute('SELECT status FROM project_extensions WHERE project=? AND extension=?',(self.name,self.ident)).fetchone()['status'],'installed')
    def test_unfinished_cms_never_installs(self):
        with patch.object(ext,'ready',return_value=False),patch('operations.install_extension') as install:
            with self.assertRaisesRegex(ValueError,'CMS-Einrichtung'):ext.install_stored(self.name,self.ident)
        install.assert_not_called()
    def test_wrong_cms_never_installs(self):
        with db() as c:c.execute("UPDATE extensions SET cms='joomla' WHERE id=?",(self.ident,))
        with patch.object(ext,'ready',return_value=True),patch('operations.install_extension') as install:
            with self.assertRaisesRegex(ValueError,'CMS'):ext.install_stored(self.name,self.ident)
        install.assert_not_called()
