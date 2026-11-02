"""Build and validate an install/update round trip using temporary local files only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'app'),str(ROOT/'scripts')]


def main():
    with tempfile.TemporaryDirectory(prefix='manager-platform-smoke-') as tmp:
        root=Path(tmp)/'Installation with spaces';root.mkdir()
        os.environ['VMM_DATA']=str(root/'data')
        from build_release import build
        from build_windows_installer import source_files
        shutil.copytree(ROOT/'installer',root/'installer')
        # Build against an isolated copy; never write dist or data into the checkout.
        for source in source_files(ROOT):
            target=root/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        for name in ('build_release.py','build_windows_installer.py','build_macos_installer.py','build_linux_installer.py'):
            source=ROOT/'scripts'/name
            if not (root/'scripts'/name).exists():shutil.copyfile(source,root/'scripts'/name)
        shutil.copyfile(ROOT/'CHANGELOG.md',root/'CHANGELOG.md')
        artifact=build(root)
        assert 'Website Manager '+json.loads((root/'app/release.json').read_text())['version'] in (root/'dist/release-notes.md').read_text(encoding='utf-8')
        digest=artifact.with_suffix('.zip.sha256').read_text().split()[0]
        assert hashlib.sha256(artifact.read_bytes()).hexdigest()==digest
        from catalog import validate_zip
        validate_zip(artifact)
        destination=Path(tmp)/'Fresh installation';destination.mkdir()
        with zipfile.ZipFile(artifact) as package:
            assert 'app/static/workspace.js' in package.namelist()
            assert not any(n.startswith(('data/','.env')) for n in package.namelist())
            package.extractall(destination)
        # Updating program files must preserve an existing installation's private data.
        (destination/'data').mkdir();(destination/'data/keep.txt').write_text('private project data')
        (destination/'.env').write_text('CUSTOM_SETTING=keep\n')
        with zipfile.ZipFile(artifact) as package:package.extractall(destination)
        assert (destination/'data/keep.txt').read_text()=='private project data'
        assert (destination/'.env').read_text()=='CUSTOM_SETTING=keep\n'
        assert json.loads((destination/'app/release.json').read_text())['version']
        from desktop_service import native_path
        assert native_path('C:/Sites/My site')=='C:\\Sites\\My site'
        assert native_path('/home/user/My site')=='/home/user/My site'
        print('PASS: install/update packages, checksums, paths with spaces and private-data preservation on '+sys.platform)


if __name__=='__main__':main()
