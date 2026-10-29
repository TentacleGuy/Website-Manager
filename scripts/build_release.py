"""Build the public source release and update artifact from a strict allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from build_windows_installer import ROOT,source_files,build as windows
from build_macos_installer import build as macos
from build_linux_installer import build as linux


def build(root=ROOT):
    output=root/'dist';output.mkdir(exist_ok=True)
    update=output/'manager-update.zip'
    with zipfile.ZipFile(update,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in source_files(root):
            if path.is_symlink():raise ValueError('Symlink darf nicht veröffentlicht werden: '+str(path))
            archive.write(path,path.relative_to(root).as_posix())
    update.with_suffix('.zip.sha256').write_text(hashlib.sha256(update.read_bytes()).hexdigest()+'  '+update.name+'\n')
    windows(root);macos(root);linux(root)
    return update


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--tag');args=parser.parse_args()
    metadata=json.loads((ROOT/'app/release.json').read_text())
    if args.tag and args.tag!='v'+metadata['version']:raise SystemExit('Git-Tag und app/release.json stimmen nicht überein.')
    print(build())
