"""Create genuine Akeeba archives using the CMS's native CLI, never a renamed ZIP."""
import json
from pathlib import Path
import re
import secrets
import shutil
import time
from store import DATA,project


def capability(p):
    import operations as op
    site=op.folder(p)/'site'
    if p.get('storage')=='legacy':return {'available':False,'reason':'Dieses ältere Volume-Projekt zuerst auf gemeinsame Laufzeiten umstellen.'}
    if p['cms']=='joomla':
        if (site/'cli/akeeba-backup.php').is_file() and not (site/'administrator/components/com_akeebabackup').is_dir():
            return {'available':False,'reason':'Hier ist die ältere Akeeba-Version für Joomla 3 installiert. Deren CLI wird vom Manager noch nicht unterstützt. Ein Backup ist weiterhin im Joomla-Backend unter Komponenten → Akeeba Backup möglich.'}
        ready=(site/'administrator/components/com_akeebabackup/src/CliCommands/BackupTake.php').is_file() and (site/'cli/joomla.php').is_file()
        return {'available':ready,'reason':'' if ready else 'Akeeba Backup mit Joomla-CLI-Unterstützung installieren. Das Akeeba-Konsolenplugin muss aktiviert sein.'}
    plugins=site/'wp-content/plugins'
    candidates=list(plugins.glob('*/wpcli/Command/ProFeatures.php')) if plugins.exists() else []
    ready=any((path.parents[2]/'akeebabackupwp.php').is_file() for path in candidates)
    return {'available':ready,'reason':'' if ready else 'Für diese Funktion wird die unterstützte CLI von Akeeba Backup Professional für WordPress benötigt.'}


def listing(name):
    p=project(name);result=[];root=DATA/'backups'
    if root.exists():
        for folder in root.iterdir():
            if not folder.is_dir() or folder.is_symlink():continue
            file=folder/'manager-backup.json'
            try:info=json.loads(file.read_text())
            except (OSError,ValueError):continue
            if info.get('project')!=name or info.get('status') not in ('complete','error'):continue
            files=[]
            for entry in info.get('files',[]):
                path=folder/entry
                if path.is_file() and not path.is_symlink():files.append({'name':entry,'size':path.stat().st_size})
            result.append({**info,'id':folder.name,'files':files})
    result.sort(key=lambda x:x['created'],reverse=True)
    return {'capability':capability(p),'backups':result}


def json_records(raw):
    text=raw.decode(errors='replace').strip()
    for index,char in enumerate(text):
        if char not in '[{':continue
        try:value,_=json.JSONDecoder().raw_decode(text[index:])
        except ValueError:continue
        if isinstance(value,list):return value
        if isinstance(value,dict) and value and all(isinstance(x,dict) for x in value.values()):return list(value.values())
    raise ValueError('Akeeba hat keinen lesbaren Sicherungsstatus geliefert.')


def create(name,profile=1):
    import operations as op
    p=project(name);available=capability(p)
    if not available['available']:raise ValueError(available['reason'])
    if p.get('restore') or p['status']!='running':raise ValueError('Das vollständig eingerichtete Projekt zuerst starten.')
    if isinstance(profile,bool) or not isinstance(profile,int) or not 1<=profile<=99999:raise ValueError('Eine gültige Akeeba-Profilnummer angeben.')
    op.write_tools(p)
    ident=secrets.token_hex(12);description='VMM-'+ident;filename='vmm-'+name+'-'+ident
    root=DATA/'backups';root.mkdir(exist_ok=True)
    stage=root/ident;stage.mkdir()
    metadata=stage/'manager-backup.json'
    metadata.write_text(json.dumps({'project':name,'created':int(time.time()),'profile':profile,'status':'creating','files':[]}))
    try:
        tools=op.folder(p)/'tools'
        from project_files import archive_mapping,SERVER_FILES
        mapping,required=archive_mapping(op.folder(p)/'site',tools)
        report=tools/'akeeba-originals-report.json'
        report.unlink(missing_ok=True)
        (tools/'akeeba-originals.json').write_text(json.dumps(mapping))
        shutil.copyfile(Path(__file__).parent/'tools/akeeba-originals-archiver.php',tools/'akeeba-originals-archiver.php')
        shutil.copyfile(Path(__file__).parent/'tools/akeeba-local.php',tools/'akeeba-local.php')
        output='/vmm-backups/'+ident
        overrides={'akeeba.basic.output_directory':output,'akeeba.basic.archive_name':filename,'akeeba.basic.backup_type':'full','akeeba.advanced.archiver_engine':'vmmjpa' if mapping else 'jpa','akeeba.advanced.postproc_engine':'none','akeeba.quota.enable_count_quota':'0','akeeba.quota.enable_size_quota':'0','akeeba.quota.maxage.enable':'0','akeeba.quota.remotely.enable_count_quota':'0','akeeba.quota.remotely.enable_size_quota':'0','akeeba.quota.remotely.maxage.enable':'0','akeeba.quota.obsolete_quota':'0','akeeba.quota.enable_logfiles':'0'}
        params='--overrides='+','.join(k+'='+v for k,v in overrides.items())
        if p['cms']=='joomla':base=['php','-d','auto_prepend_file=/vmm-tools/akeeba-local.php','cli/joomla.php'];take=['akeeba:backup:take'];query=['akeeba:backup:list']
        else:base=['php','-d','auto_prepend_file=/vmm-tools/akeeba-local.php','/usr/local/bin/wp','--allow-root'];take=['akeeba','backup','take'];query=['akeeba','backup','list']
        op.exec_php(p,base+take+['--profile='+str(profile),'--description='+description,params],timeout=7200,allowed_returncodes=(0,2))
        if required:
            try:seen=json.loads(report.read_text())
            except (OSError,ValueError):seen={}
            if any(not seen.get(name) for name in required):raise ValueError('Akeeba hat nicht alle ursprünglichen Serverdateien gesichert. Bitte Datei-Ausschlüsse im Profil prüfen. Das Archiv wird nicht als vollständig angeboten.')
        rows=json_records(op.exec_php(p,base+query+['--description='+description,'--format=json'],timeout=120))
        record=next((r for r in rows if r.get('description')==description and r.get('status')=='complete'),None)
        if not record:raise ValueError('Akeeba hat die Sicherung nicht als vollständig abgeschlossen bestätigt. Dateien bleiben als unvollständige Sicherung zur Diagnose erhalten.')
        main=stage/(filename+'.jpa')
        parts=max(1,int(record.get('multipart') or 1))
        if parts>10000:raise ValueError('Akeeba meldet eine ungültige Anzahl Archivteile.')
        names=[filename+'.jpa']+[filename+'.j'+str(i).zfill(2) for i in range(1,parts)]
        if any(not (stage/file).is_file() or (stage/file).is_symlink() or (stage/file).stat().st_size==0 for file in names):raise ValueError('Akeeba-Sicherung ist unvollständig: Mindestens ein Archivteil fehlt.')
        with main.open('rb') as stream:
            if stream.read(3)!=b'JPA':raise ValueError('Akeeba hat kein gültiges JPA-Hauptarchiv erzeugt.')
        info={'project':name,'created':int(time.time()),'profile':profile,'status':'complete','files':names,'restored_server_files':[name for name in SERVER_FILES if name in required],'native_id':str(record.get('id','')),'sha256':{file:op.digest(stage/file) for file in names}}
        metadata.write_text(json.dumps(info))
    except Exception:
        metadata.write_text(json.dumps({'project':name,'created':int(time.time()),'profile':profile,'status':'error','files':[]}))
        raise
    return 'Akeeba-Backup erstellt: '+filename+'.jpa · '+str(len(names))+' Archivteile. Download im Projekt unter Akeeba-Backups.'
