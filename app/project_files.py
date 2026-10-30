"""Keep production server configuration separate from the local CMS template."""
import json

SERVER_FILES=('.htaccess','.user.ini','php.ini')
MANIFEST='local-server-files.json'


def prepare_local(site,tools):
    """Called after extraction, before the restored application can run."""
    plan=[]
    for name in SERVER_FILES:
        active=site/name;saved=site/(name+'.vmm-original')
        for path in (active,saved):
            if path.is_symlink() or (path.exists() and not path.is_file()):raise ValueError('Ungültige Server-Konfigurationsdatei: '+path.name)
        if active.exists():
            if saved.exists():raise ValueError('Mehrdeutige Server-Konfiguration: '+name+' und '+saved.name+' sind beide vorhanden. Beide Dateien wurden beibehalten.')
            plan.append((active,saved))
    had_htaccess=(site/'.htaccess').is_file() or (site/'.htaccess.vmm-original').is_file()
    template=next((site/name for name in ('htaccess.txt','.htaccess.txt') if (site/name).is_file()),None) if had_htaccess else None
    if template and template.is_symlink():raise ValueError('Die lokale htaccess-Vorlage darf keine Verknüpfung sein.')
    if template:plan.append((template,site/'.htaccess'))
    moved=[]
    try:
        for source,target in plan:source.rename(target);moved.append((source,target))
        tools.mkdir(parents=True,exist_ok=True)
        metadata={'version':1,'htaccess_template':template.name if template else None}
        temporary=tools/(MANIFEST+'.new');temporary.write_text(json.dumps(metadata));temporary.replace(tools/MANIFEST)
    except Exception:
        for source,target in reversed(moved):target.rename(source)
        raise


def archive_mapping(site,tools):
    mapping={};required=[]
    try:metadata=json.loads((tools/MANIFEST).read_text())
    except (OSError,ValueError):metadata={}
    template=metadata.get('htaccess_template')
    if template not in ('htaccess.txt','.htaccess.txt',None):raise ValueError('Ungültige lokale Serverdatei-Zuordnung.')
    for name in SERVER_FILES:
        saved=site/(name+'.vmm-original')
        if not saved.exists() and not saved.is_symlink():continue
        if not saved.is_file() or saved.is_symlink():raise ValueError('Die Originaldatei ist keine reguläre Datei: '+saved.name)
        mapping[saved.name]=name;required.append(name)
        if (site/name).exists():
            if (site/name).is_symlink():raise ValueError('Verknüpfte Serverdateien können nicht gesichert werden.')
            target=template if name=='.htaccess' else None
            if target and (site/target).exists():raise ValueError('Die lokale htaccess-Vorlage liegt unter zwei Namen vor. Bitte zuerst den Konflikt beheben.')
            mapping[name]=target
            if target:required.append(target)
    return mapping,required


def archive_entries(site,tools):
    """The same archive-only name mapping for ordinary ZIP project exports."""
    mapping,_=archive_mapping(site,tools)
    for path in site.rglob('*'):
        if not path.is_file() or path.is_symlink():continue
        relative=path.relative_to(site)
        target=mapping.get(relative.name,relative.name) if len(relative.parts)==1 else relative.as_posix()
        if target is not None:yield path,target
