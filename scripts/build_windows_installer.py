"""Build a distributable bootstrap ZIP from an explicit source allowlist."""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'Tentacle-Projektmanager-Windows-Setup'
FILES = ('Dockerfile', 'compose.yaml', 'requirements.txt', '.dockerignore',
         'scripts/setup.py', 'scripts/installer_config.py')


def source_files(root):
    files = [root / item for item in FILES]
    for directory in ('app', 'infra/runtime'):
        files.extend(p for p in (root / directory).rglob('*') if p.is_file()
                     and not any(part.startswith('.') or part == '__pycache__'
                                 for part in p.relative_to(root).parts)
                     and p.suffix not in ('.pyc', '.pyo'))
    return sorted(files)


def build(root=ROOT, output=None):
    output = output or root / 'dist' / (NAME + '.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in source_files(root):
            if path.is_symlink():
                raise ValueError('Symlinks duerfen nicht ins Installationspaket: ' + str(path))
            archive.write(path, NAME + '/payload/' + path.relative_to(root).as_posix())
        for path in sorted((root / 'installer/windows').iterdir()):
            if path.is_file() and path.suffix in ('.ps1', '.cmd', '.txt'):
                archive.writestr(NAME + '/' + path.name, path.read_text().replace('\n', '\r\n').encode('utf-8'))
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(checksum + '  ' + output.name + '\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(build(output=args.output))
