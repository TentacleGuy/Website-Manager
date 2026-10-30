import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _isolated=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_isolated.name
import desktop_service as desktop
ROOT=Path(__file__).resolve().parents[1]


class ProjectFolderTests(unittest.TestCase):
    def test_native_windows_macos_and_linux_paths(self):
        for raw in ('C:/Sites/Projekt/site','C:\\Sites\\Projekt\\site','/run/desktop/mnt/host/c/Sites/Projekt/site','/host_mnt/c/Sites/Projekt/site'):
            self.assertEqual(desktop.native_path(raw),'C:\\Sites\\Projekt\\site')
        self.assertEqual(desktop.native_path('//server/share/Sites'),'\\\\server\\share\\Sites')
        self.assertEqual(desktop.native_path('/host_mnt/Users/Test Person/Sites'),'/Users/Test Person/Sites')
        self.assertEqual(desktop.native_path('/home/test/Sites'),'/home/test/Sites')
        with self.assertRaises(ValueError):desktop.native_path('relative/site')

    def test_custom_storage_and_desktop_registration(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(desktop,'DATA',Path(tmp)):
            root=Path(tmp);(root/'projects/example/site').mkdir(parents=True);(root/'storage').mkdir()
            (root/'storage/settings.json').write_text(json.dumps({'projects':'D:/Eigene Websites'}))
            (root/'desktop-integration.json').write_text(json.dumps({'platform':'windows','scheme':desktop.SCHEME,'version':1}))
            result=desktop.folder({'slug':'example','storage':'shared'})
            self.assertTrue(result['available']);self.assertTrue(result['registered'])
            self.assertEqual(result['path'],'D:\\Eigene Websites\\example\\site')
            self.assertEqual(result['url'],'tentacle-project://open/example')

    def test_missing_legacy_and_symlinked_folders_never_open(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(desktop,'DATA',Path(tmp)):
            root=Path(tmp);(root/'projects/one/site').mkdir(parents=True)
            self.assertFalse(desktop.folder({'slug':'one','storage':'legacy'})['available'])
            self.assertFalse(desktop.folder({'slug':'missing','storage':'shared'})['available'])
            (root/'projects/two').symlink_to(root/'projects/one',target_is_directory=True)
            self.assertFalse(desktop.folder({'slug':'two','storage':'shared'})['available'])
            with self.assertRaises(ValueError):desktop.folder({'slug':'../one','storage':'shared'})


class NativeHandlerTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        binaries=root/'bin';binaries.mkdir();folder=root/'Website mit Leerzeichen und ü';folder.mkdir()
        tools={'uname':'printf "Linux\\n"','curl':'printf "%s\\n" "$*" >> "$TEST_CURL"; printf "%s" "$TEST_FOLDER"','xdg-open':'printf "%s" "$1" > "$TEST_OPEN"','xdg-mime':'printf "%s" "$*" > "$TEST_MIME"'}
        for name,body in tools.items():
            file=binaries/name;file.write_text('#!/bin/bash\n'+body+'\n');file.chmod(0o755)
        env={**os.environ,'PATH':str(binaries)+os.pathsep+os.environ['PATH'],'TEST_FOLDER':str(folder),'TEST_CURL':str(root/'curl.log'),'TEST_OPEN':str(root/'opened'),'TEST_MIME':str(root/'mime'),'XDG_DATA_HOME':str(root/'xdg')}
        return root,env

    def test_linux_opens_exact_directory_with_spaces(self):
        root,env=self.fixture()
        subprocess.run(['bash',str(ROOT/'app/installer_assets/folder-opener.sh'),'tentacle-project://open/example'],env=env,check=True,capture_output=True)
        self.assertEqual((root/'opened').read_text(),env['TEST_FOLDER'])
        self.assertIn('http://127.0.0.1:8090/api/projects/example/folder?format=path',(root/'curl.log').read_text())

    def test_invalid_links_never_reach_manager_or_file_opener(self):
        root,env=self.fixture()
        for url in ('file:///etc','tentacle-project://open/../../etc','tentacle-project://open/example?path=/etc','tentacle-project://open/example;touch-test','tentacle-project://open/%2e%2e'):
            result=subprocess.run(['bash',str(ROOT/'app/installer_assets/folder-opener.sh'),url],env=env,capture_output=True)
            self.assertNotEqual(result.returncode,0)
        self.assertFalse((root/'opened').exists());self.assertFalse((root/'curl.log').exists())

    def test_linux_registration_is_per_user_and_uses_native_handler(self):
        root,env=self.fixture();installation=root/'Manager mit Leerzeichen';assets=installation/'app/installer_assets';assets.mkdir(parents=True)
        shutil.copyfile(ROOT/'app/installer_assets/folder-opener.sh',assets/'folder-opener.sh')
        subprocess.run(['bash',str(ROOT/'app/installer_assets/register-folders.sh'),str(installation)],env=env,check=True,capture_output=True)
        self.assertEqual((root/'mime').read_text(),'default tentacle-project-folder.desktop x-scheme-handler/tentacle-project')
        entry=(root/'xdg/applications/tentacle-project-folder.desktop').read_text()
        self.assertIn('"'+str((assets/'folder-opener.sh').resolve())+'" %u',entry)
        self.assertEqual(json.loads((installation/'data/desktop-integration.json').read_text())['platform'],'linux')
