"""Build a universal macOS bootstrap ZIP with executable Finder launchers."""
import argparse
import hashlib
from pathlib import Path
import stat
import zipfile

from build_windows_installer import ROOT, source_files

NAME = 'Tentacle-Projektmanager-Mac-Setup'


def add(archive, path, name, executable=False):
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, path.read_bytes())


def build(root=ROOT, output=None):
    output = output or root / 'dist' / (NAME + '.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w') as archive:
        for path in source_files(root):
            if any(part in ('windows','linux') for part in path.relative_to(root).parts):continue
            if path.is_symlink():
                raise ValueError('Symlinks duerfen nicht ins Installationspaket: ' + str(path))
            add(archive, path, NAME + '/payload/' + path.relative_to(root).as_posix())
        for path in sorted((root / 'installer/macos').iterdir()):
            if path.is_file() and path.suffix in ('.sh', '.command', '.txt'):
                add(archive, path, NAME + '/' + path.name, path.suffix in ('.sh', '.command'))
    output.with_suffix('.zip.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(build(output=args.output))
