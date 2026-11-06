"""Explicit removal of stored downloads; never uninstall files from a website."""
import json
from pathlib import Path
import re
import secrets
import shutil
from store import DATA,LOCK,db

LABELS={'cms':'CMS-Paket','extension':'Erweiterung','extension-package':'Erweiterungspaket','backup':'Akeeba-Backup','export':'Projektsicherung','kickstart':'Kickstart-Download','manager-download':'Manager-Download','trash':'Projektpapierkorb','residue':'Restdateien'}


def roots():
    return {k:DATA/k for k in ('packages','extensions','backups','exports','updates','trash')}|{'kickstart':DATA/'tools/kickstart','tools':DATA/'tools'}


def safe_file(root,name):
    if not isinstance(name,str) or not name or Path(name).name!=name or name in ('.','..') or '\\' in name:raise ValueError('Ungültiger Dateiname.')
    path=root/name
    if path.is_symlink():raise ValueError('Verknüpfte Dateien werden nicht gelöscht.')
    if path.exists() and path.resolve().parent!=root.resolve():raise ValueError('Dateipfad liegt außerhalb des Speicherbereichs.')
    return path


def size(path):
    if not path.exists():return 0
    if path.is_file():return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())


def state(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return {}


def describe(c,kind,ident):
    if kind=='recycle':return __import__('recycle_service').describe(c,ident)
    if kind not in LABELS:raise ValueError('Unbekannter Speicherbereich.')
    paths=[];references=[];blocked=[];cms='';note='Installierte Websites bleiben erhalten.';name=ident
    active=[dict(r) for r in c.execute("SELECT * FROM jobs WHERE status IN ('queued','running')")]
    busy={r['kind'] for r in active}
    if kind in ('cms','extension','extension-package','backup') and not re.fullmatch(r'[a-f0-9]{24}',ident):raise ValueError('Ungültige Kennung.')
    if kind=='cms':
        row=c.execute('SELECT * FROM packages WHERE id=?',(ident,)).fetchone()
        if not row:raise ValueError('CMS-Paket nicht gefunden.')
        cms=row['cms'];name=cms.title()+' '+row['version'];paths=[safe_file(DATA/'packages',row['filename'])]
        for p in c.execute('SELECT slug FROM projects WHERE package_id=?',(ident,)):
            references.append(p['slug']);site=DATA/'projects'/p['slug']/'site'
            if not site.is_dir() or not any(site.iterdir()):blocked.append('Projekt '+p['slug']+' benötigt das Paket noch zur Einrichtung.')
        if busy.intersection(('provision','akeeba')) or any(r['resource']=='package-'+cms+'-'+row['version'] for r in active):blocked.append('Eine Einrichtung oder ein zugehöriger Download läuft noch.')
        note='Das gespeicherte Installationspaket wird entfernt. Bereits entpackte Websites bleiben erhalten; die Version kann erneut heruntergeladen werden.'
    elif kind=='extension-package':
        row=c.execute('SELECT * FROM extensions WHERE id=? AND archived=1',(ident,)).fetchone()
        if not row:raise ValueError('Erweiterungspaket nicht gefunden.')
        cms=row['cms'];name=row['name']+' '+row['version'];paths=[safe_file(DATA/'extensions',row['filename'])]
        references=[r['project'] for r in c.execute('SELECT project FROM project_extensions WHERE extension=?',(ident,))]
        if busy.intersection(('provision','extensions','install-extension','update-all','library-import')) or any(r['resource']=='extension-'+str(row['source_id']) for r in active):blocked.append('Eine Erweiterungsinstallation oder ein zugehöriger Download läuft noch.')
        note='Nur dieses gespeicherte ZIP wird entfernt. Updatequelle, Projektzuordnungen und installierte Erweiterungen bleiben erhalten.'
    elif kind=='extension':
        row=c.execute('SELECT config FROM extension_sources WHERE id=?',(ident,)).fetchone()
        if not row:raise ValueError('Erweiterung nicht gefunden.')
        config=json.loads(row['config']);cms=config['cms'];name=config['name']
        entries=list(c.execute('SELECT filename FROM extensions WHERE source_id=?',(ident,)))
        paths=[safe_file(DATA/'extensions',r['filename']) for r in entries]
        references=[r['project'] for r in c.execute('SELECT project FROM extension_plans WHERE source=?',(ident,))]
        if busy.intersection(('provision','extensions','install-extension','update-all','library-import')) or any(r['resource']=='extension-'+ident for r in active):blocked.append('Eine Erweiterungsinstallation oder ein zugehöriger Download läuft noch.')
        note='Bibliothekseintrag, alle zugehörigen Pakete und Manager-Zuordnungen werden entfernt. Installierte Websites und gespeicherte Lizenzschlüssel bleiben erhalten.'
    elif kind=='backup':
        folder=safe_file(DATA/'backups',ident)
        if not folder.is_dir():raise ValueError('Backup nicht gefunden.')
        info=state(folder/'manager-backup.json');paths=[folder]
        archives=sorted(p.name for p in folder.iterdir() if p.is_file() and re.search(r'\.(jpa|jps|zip)$',p.name,re.I))
        name=(info.get('project','')+' · ' if info.get('project') else '')+(archives[0] if archives else 'Backup '+ident)
        references=[r['slug'] for r in c.execute('SELECT slug FROM projects WHERE backup_group=? AND restore=1',(ident,))]
        if references:blocked.append('Für eine laufende oder fortsetzbare Wiederherstellung benötigt: '+', '.join(references)+'.')
        if info.get('status')=='creating' or any(r['kind']=='akeeba-backup' and r['resource']==info.get('project') for r in active):blocked.append('Das Backup wird noch erstellt.')
        note='Das gesamte Backup einschließlich aller Teilarchive wird gelöscht. Bereits wiederhergestellte Websites bleiben erhalten.'
        if info.get('status')=='unverified':
            note=info.get('warning','Ursprüngliche Serverdateien noch nicht bestätigt.')
        if info.get('status')=='error':
            name=(info.get('project','')+' · ' if info.get('project') else '')+'Fehlgeschlagener Backup-Versuch'
            note='Keine vollständige Sicherung. '+info.get('error','Details stehen im Activity Log.')
    elif kind=='export':
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]*\.zip',ident):raise ValueError('Ungültiger Dateiname.')
        file=safe_file(DATA/'exports',ident)
        if not file.is_file():raise ValueError('Projektsicherung nicht gefunden.')
        paths=[file]
        if busy.intersection(('snapshot','restore-export','update-all','install-extension','extensions')):blocked.append('Eine Sicherung oder Erweiterungsinstallation läuft noch.')
        note='Nur dieses ZIP mit Website-Dateien und Datenbankexport wird entfernt.'
    elif kind=='kickstart':
        if ident=='manual':
            paths=[safe_file(DATA/'tools','kickstart.php')];name='Eigene kickstart.php'
            references=[r['slug'] for r in c.execute("SELECT slug FROM projects WHERE restore=1 AND kickstart='manual'")]
            if references:blocked.append('Die eigene Kickstart-Datei wird für eine fortsetzbare Wiederherstellung benötigt.')
        else:
            if not re.fullmatch(r'\d+\.\d+\.\d+',ident):raise ValueError('Ungültige Kickstart-Version.')
            paths=[safe_file(DATA/'tools/kickstart',ident)];name='Kickstart '+ident
        if not paths[0].exists():raise ValueError('Kickstart-Download nicht gefunden.')
        if busy.intersection(('akeeba','provision','backup-verify','akeeba-backup')) or any(r['resource']=='kickstart' for r in active):blocked.append('Eine Wiederherstellung oder ein Kickstart-Download läuft noch.')
        note='Die gespeicherten Kickstart-Dateien werden entfernt. Offizielle Versionen werden bei Bedarf erneut heruntergeladen.'
    elif kind=='manager-download':
        if not re.fullmatch(r'[a-f0-9]{16}',ident):raise ValueError('Ungültige Updatekennung.')
        folder=safe_file(DATA/'updates',ident)
        if not folder.is_dir():raise ValueError('Manager-Download nicht gefunden.')
        paths=[folder];name='Manager-Download '+ident
        update=state(DATA/'updates/apply-status.json')
        if update.get('status') in ('queued','running') or any(r['resource']=='manager-update' for r in active):blocked.append('Ein Manager-Update läuft noch.')
        note='Download, alte Programmdateien und Protokolle dieses Updateversuchs werden entfernt. Die installierte Manager-Version und Projekte bleiben erhalten.'
    elif kind=='trash':
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*-[0-9]+-[a-f0-9]{6}',ident):raise ValueError('Ungültiger Papierkorbeintrag.')
        folder=safe_file(DATA/'trash',ident)
        if not folder.is_dir():raise ValueError('Papierkorbeintrag nicht gefunden.')
        paths=[folder];name='Gelöschtes Projekt · '+ident
        if busy.intersection(('delete-project',)):blocked.append('Eine Projektlöschung läuft noch.')
        note='Die aufbewahrten Website-Dateien, Metadaten und der Datenbankexport werden endgültig entfernt.'
    else:
        area,sep,filename=ident.partition('~')
        if not sep or area not in roots() or not re.fullmatch(r'\.vmm-delete-[a-f0-9]{24}-.+',filename):raise ValueError('Ungültige Restdatei-Kennung.')
        paths=[safe_file(roots()[area],filename)];name='Restdateien · '+area
        if not paths[0].exists():raise ValueError('Restdateien nicht gefunden.')
        note='Verbliebene Dateien einer früheren Löschung werden endgültig entfernt.'
    update=state(DATA/'updates/apply-status.json')
    if update.get('status') in ('queued','running'):blocked.append('Bitte den Abschluss des Manager-Updates abwarten.')
    import storage_service
    if storage_service.busy() or storage_service.ACTIVE_UPLOADS:blocked.append('Eine Speicherumstellung oder ein Upload läuft noch.')
    if kind in ('backup','export') and any(r['resource']=='verify-'+kind+'-'+ident for r in active):blocked.append('Eine Prüfung dieser Sicherung läuft noch.')
    paths=list(dict.fromkeys(p for p in paths if p.exists()))
    verification=None
    if kind in ('backup','export'):
        from verification_service import result
        verification=result(kind,ident)
    created=info.get('created') if kind=='backup' else None
    if not created and kind in ('backup','export') and paths:
        entries=[f for path in paths for f in (list(path.iterdir()) if path.is_dir() else [path]) if f.is_file() and f.suffix.lower() in ('.zip','.jpa','.jps')]
        created=int(min((f.stat().st_mtime for f in entries),default=paths[0].stat().st_mtime))
    return {'created':created,'backup_purpose':('live' if info.get('project') else 'import') if kind=='backup' else ('snapshot' if kind=='export' else None),'source_project':info.get('project') if kind=='backup' else None,'verification':verification,'kind':kind,'id':ident,'label':LABELS[kind],'name':name,'cms':cms,'size':None if kind=='trash' else sum(size(p) for p in paths),'files':len(paths),'projects':references,'note':note,'status':info.get('status') if kind=='backup' else None,'archive_files':info.get('files',[]) if kind=='backup' and info.get('status') in ('complete','unverified') else [],'blocked':list(dict.fromkeys(blocked)),'_paths':paths}


def public(value):return {k:v for k,v in value.items() if not k.startswith('_')}


def review(kind,ident):
    with LOCK,db() as c:
        value=public(describe(c,kind,ident));value['deletion_mode']='permanent' if kind in ('trash','recycle') else __import__('recycle_service').settings()['mode'];return value


def inventory():
    with LOCK,db() as c:
        keys=[('cms',r['id']) for r in c.execute('SELECT id FROM packages')]
        keys += [('extension-package',r['id']) for r in c.execute('SELECT id FROM extensions WHERE archived=1')]
        for kind,base,pattern in [('backup',DATA/'backups',r'[a-f0-9]{24}'),('manager-download',DATA/'updates',r'[a-f0-9]{16}'),('kickstart',DATA/'tools/kickstart',r'\d+\.\d+\.\d+'),('trash',DATA/'trash',r'[a-z0-9][a-z0-9-]*-[0-9]+-[a-f0-9]{6}')]:
            if base.exists():keys += [(kind,p.name) for p in base.iterdir() if p.is_dir() and not p.is_symlink() and re.fullmatch(pattern,p.name)]
        if (DATA/'exports').exists():keys += [('export',p.name) for p in (DATA/'exports').glob('*.zip') if p.is_file() and not p.is_symlink()]
        if (DATA/'tools/kickstart.php').is_file():keys.append(('kickstart','manual'))
        for area,base in roots().items():
            if base.exists():keys += [('residue',area+'~'+p.name) for p in base.glob('.vmm-delete-*') if not p.is_symlink()]
        values=[]
        for kind,ident in keys:
            try:values.append(public(describe(c,kind,ident)))
            except ValueError:continue
    return {'items':values,'total':sum(v['size'] or 0 for v in values)}


def delete(kind,ident):
    staged=[]
    with LOCK:
        try:
            with db() as c:
                value=describe(c,kind,ident)
                if value['blocked']:raise ValueError(' '.join(value['blocked']))
                for path in value['_paths']:
                    target=path.with_name('.vmm-delete-'+secrets.token_hex(12)+'-'+path.name)
                    path.rename(target);staged.append((path,target))
                if kind=='cms':
                    c.execute('UPDATE projects SET package_id=NULL WHERE package_id=?',(ident,));c.execute('DELETE FROM packages WHERE id=?',(ident,))
                elif kind=='extension-package':c.execute('UPDATE extensions SET archived=0 WHERE id=?',(ident,))
                elif kind=='extension':
                    c.execute('DELETE FROM extension_plans WHERE source=?',(ident,))
                    c.execute('DELETE FROM project_extensions WHERE extension IN (SELECT id FROM extensions WHERE source_id=?)',(ident,))
                    c.execute('DELETE FROM extensions WHERE source_id=?',(ident,));c.execute('DELETE FROM extension_sources WHERE id=?',(ident,))
        except Exception:
            for original,target in reversed(staged):
                if target.exists():target.rename(original)
            raise
        remaining=[]
        for _,target in staged:
            try:
                if target.is_dir():shutil.rmtree(target)
                else:target.unlink()
            except OSError:remaining.append(target.name)
    message=value['label']+' gelöscht. Installierte Websites bleiben erhalten.'
    if remaining:message+=' Einige Restdateien konnten nicht entfernt werden. Sie stehen unter „Weitere Downloads“ erneut zur Löschung bereit.'
    return {'message':message,'deleted':ident,'remaining':len(remaining)}


def remove(kind,ident):
    import recycle_service as recycle
    with LOCK:
        if kind=='recycle':return recycle.purge(ident)
        if kind=='trash':
            value=next((v for v in recycle.listing()['items'] if v['original_id']==ident and v.get('legacy')),None)
            if not value:raise ValueError('Papierkorbeintrag nicht gefunden.')
            return recycle.purge(value['id'])
        if recycle.settings()['mode']=='trash':return recycle.move(kind,ident)
        with db() as c:recycle.guards(c)
        return delete(kind,ident)
