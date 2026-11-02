"""Read-only file access to known downloads, with deletion delegated to cleanup guards."""
from pathlib import PurePosixPath
from store import db
import cleanup_service

def entries(kind,ident):
    with db() as c:value=cleanup_service.describe(c,kind,ident)
    result=[]
    for i,root in enumerate(value['_paths']):
        candidates=root.rglob('*') if root.is_dir() else [root]
        for path in candidates:
            if path.is_symlink() or not path.is_file():continue
            try:path.resolve().relative_to(root.resolve() if root.is_dir() else root.resolve().parent)
            except ValueError:continue
            relative=path.relative_to(root).as_posix() if root.is_dir() else path.name
            name=relative if root.is_dir() else value.get('_names',[r.name for r in value['_paths']])[i]
            result.append({'path':str(i)+'/'+relative,'name':name,'size':path.stat().st_size})
            if len(result)>=5000:break
    return {'name':value['name'],'files':result,'truncated':len(result)>=5000}

def file(kind,ident,relative):
    with db() as c:value=cleanup_service.describe(c,kind,ident)
    if not isinstance(relative,str) or '\\' in relative or ':' in relative:raise ValueError('Ungültiger Dateipfad.')
    parts=PurePosixPath(relative).parts
    if len(parts)<2 or not parts[0].isdigit() or '..' in parts or relative.startswith('/'):raise ValueError('Ungültiger Dateipfad.')
    index=int(parts[0])
    if index>=len(value['_paths']):raise ValueError('Datei nicht gefunden.')
    root=value['_paths'][index];path=root.joinpath(*parts[1:]) if root.is_dir() else root
    if not root.is_dir() and '/'.join(parts[1:])!=root.name:raise ValueError('Datei nicht gefunden.')
    if path.is_symlink() or not path.is_file():raise ValueError('Datei nicht gefunden.')
    try:path.resolve().relative_to(root.resolve() if root.is_dir() else root.resolve().parent)
    except ValueError:raise ValueError('Verknüpfte Dateien werden nicht geöffnet.') from None
    return path
