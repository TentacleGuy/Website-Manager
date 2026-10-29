"""Build Linux setup for existing local Docker Engine installations."""
from pathlib import Path
import hashlib
import stat
import zipfile
from build_windows_installer import ROOT,source_files

NAME='Tentacle-Projektmanager-Linux-Setup'


def build(root=ROOT,output=None):
    output=output or root/'dist'/(NAME+'.zip');output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in source_files(root):
            if any(part in ('windows','macos') for part in file.relative_to(root).parts):continue
            archive.write(file,NAME+'/payload/'+file.relative_to(root).as_posix())
        for file in sorted((root/'installer/linux').iterdir()):
            if not file.is_file():continue
            info=zipfile.ZipInfo(NAME+'/'+file.name);info.create_system=3;info.external_attr=(stat.S_IFREG|0o755)<<16;info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,file.read_bytes())
    output.with_suffix('.zip.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n');return output


if __name__=='__main__':print(build())
