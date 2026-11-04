"""Keep production server configuration separate from the local CMS template."""
import hashlib
import json
import shutil

SERVER_FILES=('.htaccess','.user.ini','php.ini')
CONFIG_FILES=('configuration.php','wp-config.php')
MANAGER_FILES=('wp-content/mu-plugins/vmm-local.php','vmm-manager-login.php','wp-content/mu-plugins/vmm-extension-updates.php')
MANIFEST='local-server-files.json'


def prepare_local(site,tools):
    """Preserve source files transactionally before any installer/local changes."""
    plan=[];copies=[];originals={}
    absent=[name for name in SERVER_FILES if not (site/name).exists() and not (site/(name+'.vmm-original')).exists()]
    for name in SERVER_FILES:
        active=site/name;saved=site/(name+'.vmm-original')
        for path in (active,saved):
            if path.is_symlink() or (path.exists() and not path.is_file()):raise ValueError('Ungültige Server-Konfigurationsdatei: '+path.name)
        if active.exists():
            if saved.exists():raise ValueError('Mehrdeutige Server-Konfiguration: '+name+' und '+saved.name+' sind beide vorhanden. Beide Dateien wurden beibehalten.')
            plan.append((active,saved))
        source=active if active.exists() else saved
        if source.is_file():originals[name]={'saved':saved.relative_to(site).as_posix(),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    had_htaccess=(site/'.htaccess').is_file() or (site/'.htaccess.vmm-original').is_file()
    template=next((site/name for name in ('htaccess.txt','.htaccess.txt') if (site/name).is_file()),None) if had_htaccess else None
    if template and template.is_symlink():raise ValueError('Die lokale htaccess-Vorlage darf keine Verknüpfung sein.')
    if template:plan.append((template,site/'.htaccess'))
    for names,suffix in ((CONFIG_FILES,'.vmm-original.php'),(MANAGER_FILES,'.vmm-original')):
        for name in names:
            active=site/name;saved=site/(name+suffix)
            for path in (active,saved):
                if path.is_symlink() or (path.exists() and not path.is_file()):raise ValueError('Ungültige Originaldatei: '+name)
            if active.is_file() and not saved.exists():copies.append((active,saved))
            source=saved if saved.is_file() else active
            if source.is_file():originals[name]={'saved':saved.relative_to(site).as_posix(),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    moved=[];created=[]
    try:
        tools.mkdir(parents=True,exist_ok=True)
        for source,target in copies:
            # Exclusive creation never overwrites an existing original.
            with target.open('xb') as output:
                created.append(target)
                with source.open('rb') as incoming:shutil.copyfileobj(incoming,output)
            target.chmod(0o600)
        for source,target in plan:source.rename(target);moved.append((source,target))
        metadata={'version':2,'htaccess_template':template.name if template else None,'originals':originals,'absent_server_files':absent}
        temporary=tools/(MANIFEST+'.new');temporary.write_text(json.dumps(metadata));temporary.chmod(0o600);temporary.replace(tools/MANIFEST)
    except Exception:
        for source,target in reversed(moved):target.rename(source)
        for path in created:path.unlink(missing_ok=True)
        raise


def restore_configuration(site,cms):
    """Discard installer defaults, then let the caller apply local DB/path values."""
    name='configuration.php' if cms=='joomla' else 'wp-config.php'
    original=site/(name+'.vmm-original.php')
    if not original.is_file() or original.is_symlink():raise ValueError('Gesicherte ursprüngliche CMS-Konfiguration fehlt: '+name)
    shutil.copyfile(original,site/name)


def original_config_missing(site,cms):
    name='configuration.php' if cms=='joomla' else 'wp-config.php'
    return not (site/(name+'.vmm-original.php')).is_file()


def archive_mapping(site,tools):
    mapping={};required=[]
    try:metadata=json.loads((tools/MANIFEST).read_text())
    except (OSError,ValueError):metadata={}
    # A missing/modified preserved source must never silently fall back to local settings.
    for name,entry in metadata.get('originals',{}).items():
        saved=site/entry['saved']
        if (not saved.resolve().is_relative_to(site.resolve()) or saved.is_symlink() or not saved.is_file()
                or hashlib.sha256(saved.read_bytes()).hexdigest()!=entry['sha256']):
            raise ValueError('Gesicherte Originaldatei fehlt oder wurde verändert: '+name)
    for name in metadata.get('absent_server_files',[]):
        if name in SERVER_FILES and (site/name).is_file():mapping[name]=None
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
    for name in CONFIG_FILES:
        saved=site/(name+'.vmm-original.php')
        if saved.is_symlink():raise ValueError('Verknüpfte CMS-Konfiguration ist unzulässig.')
        if saved.is_file():
            mapping[saved.name]=name;mapping[name]=None;required.append(name)
    for name in MANAGER_FILES:
        saved=site/(name+'.vmm-original')
        if saved.is_symlink():raise ValueError('Verknüpfte Manager-Originaldatei ist unzulässig.')
        if saved.is_file():mapping[name+'.vmm-original']=name;required.append(name)
        if (site/name).is_file():mapping[name]=None
    return mapping,required


def archive_entries(site,tools):
    """The same archive-only name mapping for ordinary ZIP project exports."""
    mapping,_=archive_mapping(site,tools)
    for path in site.rglob('*'):
        if not path.is_file() or path.is_symlink():continue
        relative=path.relative_to(site)
        target=mapping.get(relative.as_posix(),relative.as_posix())
        if target is not None:yield path,target
