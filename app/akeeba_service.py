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
            ready=(site/'administrator/components/com_akeeba/version.php').is_file() and (site/'libraries/fof40/Cli/Application.php').is_file() and (site/'configuration.php').is_file()
            return {'available':ready,'driver':'joomla-legacy','reason':'' if ready else 'Die ältere Akeeba-Installation für Joomla 3 ist unvollständig. Bitte im Joomla-Backend prüfen.'}
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
            if info.get('project')!=name or info.get('status') not in ('complete','unverified','error'):continue
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


def archive_names(filename, parts):
    if not isinstance(filename,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:jpa|zip)',filename,re.I):
        raise ValueError('Akeeba meldet einen ungültigen Archivnamen.')
    parts=max(1,int(parts or 1))
    if parts>10000:raise ValueError('Akeeba meldet eine ungültige Anzahl Archivteile.')
    base=filename[:-4];part_prefix='.z' if filename.lower().endswith('.zip') else '.j'
    return [filename]+[base+part_prefix+str(i).zfill(2) for i in range(1,parts)]


def validate_archives(folder,names):
    if any(not (folder/name).is_file() or (folder/name).is_symlink() or (folder/name).stat().st_size==0 for name in names):
        raise ValueError('Akeeba-Sicherung ist unvollständig: Mindestens ein Archivteil fehlt.')
    # Akeeba puts the JPA header in the FIRST part (.j01 for split archives),
    # while the final part always retains the .jpa extension.
    first=folder/(names[1] if len(names)>1 else names[0])
    with first.open('rb') as stream:
        header=stream.read(4)
        # Akeeba ZIPs may prepend the PK00 spanning marker to the first local header.
        if header==b'PK00':header=stream.read(4)
        if names[0].lower().endswith('.zip'):
            if header not in (b'PK\x03\x04',b'PK\x07\x08',b'PK\x05\x06'):raise ValueError('Akeeba hat kein gültiges ZIP-Archiv erzeugt.')
        elif header[:3]!=b'JPA':raise ValueError('Akeeba hat kein gültiges JPA-Archiv erzeugt.')


def reconcile(name):
    """Recover this manager's failed attempts from native, completed records."""
    import operations as op
    from store import redact
    p=project(name)
    if p.get('restore') or p['status']!='running':raise ValueError('Das vollständig eingerichtete Projekt zuerst starten.')
    site=op.folder(p)/'site';tools=op.folder(p)/'tools';tools.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(Path(__file__).parent/'tools/akeeba-backup-record.php',tools/'akeeba-backup-record.php')
    root=DATA/'backups';recovered=0;errors=[]
    for folder in sorted(root.iterdir()) if root.exists() else []:
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'[a-f0-9]{24}',folder.name):continue
        meta=folder/'manager-backup.json'
        if meta.is_symlink():continue
        try:info=json.loads(meta.read_text())
        except (OSError,ValueError):continue
        if info.get('project')!=name or info.get('status')!='error':continue
        try:
            description='VMM-'+folder.name
            rows=json_records(op.exec_php(p,['php','/vmm-tools/akeeba-backup-record.php'],input=json.dumps({'description':description,'profile':info.get('profile',1)}).encode(),timeout=120))
            record=next((r for r in rows if r.get('description')==description and r.get('status')=='complete' and r.get('type')=='full'),None)
            if not record:raise ValueError('Akeeba bestätigt für diesen Versuch kein abgeschlossenes vollständiges Website-Backup.')
            names=archive_names(record.get('archivename'),record.get('multipart'))
            native=record.get('absolute_path','')
            if not isinstance(native,str) or Path(native).name!=names[0]:raise ValueError('Akeeba meldet einen ungültigen Archivpfad.')
            # Translate only mounts belonging to this project or this backup.
            prefixes={'/vmm-projects/'+name+'/site':site,'/var/www/html':site,'/vmm-backups/'+folder.name:folder}
            source=None
            for prefix,local in prefixes.items():
                if native.startswith(prefix+'/'):
                    relative=Path(native[len(prefix)+1:])
                    if '..' in relative.parts:raise ValueError('Ungültiger Archivpfad.')
                    candidate=local/relative
                    if candidate.resolve().is_relative_to(local.resolve()):source=candidate.parent
                    break
            if source is None:raise ValueError('Das Archiv liegt außerhalb der freigegebenen Projekt- und Backupordner.')
            validate_archives(source,names)
            hashes={file:op.digest(source/file) for file in names}
            for file in names:
                if (source/file).resolve()==(folder/file).resolve():continue
                temp=folder/(file+'.recovering-'+secrets.token_hex(6))
                try:
                    with (source/file).open('rb') as incoming,temp.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing)
                    temp.chmod(0o600)
                    if op.digest(temp)!=hashes[file] or op.digest(source/file)!=hashes[file]:raise ValueError('Das Archiv wurde während der Übernahme verändert.')
                    temp.replace(folder/file)
                finally:temp.unlink(missing_ok=True)
            validate_archives(folder,names)
            info.pop('error',None)
            info.update(status='unverified',files=names,native_id=str(record['id']),sha256=hashes,warning='Akeeba hat das Backup erfolgreich abgeschlossen. Die ursprünglichen Serverdateien wurden vom Manager nicht bestätigt; keine geprüfte Produktionssicherung.',native_status='complete')
            temp=meta.with_suffix('.new');temp.write_text(json.dumps(info));temp.replace(meta);recovered+=1
        except Exception as error:
            info['error']=redact(str(error));meta.write_text(json.dumps(info));errors.append(info['error'])
    if errors and not recovered:raise ValueError('Vorhandenes Backup konnte nicht übernommen werden: '+errors[0])
    return str(recovered)+' vorhandene Akeeba-Sicherung(en) übernommen.'+(' Weitere Versuche konnten nicht übernommen werden; Details im Backup-Eintrag.' if errors else '')


def joomla_overrides(p,overrides):
    """Use the installed command's option definition, not a Joomla-version guess."""
    import operations as op
    raw=op.exec_php(p,['php','/vmm-tools/akeeba-cli-options.php','vmm:akeeba-options'],timeout=120).decode(errors='replace')
    definition=None
    for index,char in enumerate(raw):
        if char!='{':continue
        try:value,_=json.JSONDecoder().raw_decode(raw[index:])
        except ValueError:continue
        if isinstance(value,dict) and isinstance(value.get('definition'),dict):
            definition=value['definition'];break
    option=(definition or {}).get('options',{}).get('overrides',{})
    multiple=option.get('is_multiple')
    if not isinstance(multiple,bool) or not option.get('accept_value'):
        raise ValueError('Akeebas CLI-Format für Backup-Einstellungen konnte nicht ermittelt werden. Es wurde keine Sicherung gestartet.')
    values=[key+'='+value for key,value in overrides.items()]
    if multiple:return ['--overrides='+value for value in values]
    if any(',' in value for value in values):raise ValueError('Akeebas CLI unterstützt keine Kommas in Backup-Einstellungen.')
    return ['--overrides='+','.join(values)]


def create(name,profile=1,verify=False):
    import operations as op
    p=project(name);available=capability(p)
    if not available['available']:raise ValueError(available['reason'])
    if p.get('restore') or p['status']!='running':raise ValueError('Das vollständig eingerichtete Projekt zuerst starten.')
    if isinstance(profile,bool) or not isinstance(profile,int) or not 1<=profile<=99999:raise ValueError('Eine gültige Akeeba-Profilnummer angeben.')
    if not isinstance(verify,bool):raise ValueError('Ungültige Einstellung für die Wiederherstellungsprobe.')
    op.write_tools(p)
    ident=secrets.token_hex(12);description='VMM-'+ident;filename='vmm-'+name+'-'+ident
    root=DATA/'backups';root.mkdir(exist_ok=True)
    stage=root/ident;stage.mkdir()
    metadata=stage/'manager-backup.json'
    metadata.write_text(json.dumps({'project':name,'created':int(time.time()),'profile':profile,'status':'creating','files':[]}))
    try:
        tools=op.folder(p)/'tools'
        from project_files import archive_mapping,SERVER_FILES,original_config_missing
        mapping,required=archive_mapping(op.folder(p)/'site',tools)
        report=tools/'akeeba-originals-report.json'
        report.unlink(missing_ok=True)
        (tools/'akeeba-originals.json').write_text(json.dumps(mapping))
        shutil.copyfile(Path(__file__).parent/'tools/akeeba-originals-archiver.php',tools/'akeeba-originals-archiver.php')
        shutil.copyfile(Path(__file__).parent/'tools/akeeba-local.php',tools/'akeeba-local.php')
        output='/vmm-backups/'+ident
        overrides={'akeeba.basic.output_directory':output,'akeeba.basic.archive_name':filename,'akeeba.basic.backup_type':'full','akeeba.advanced.archiver_engine':'vmmjpa' if mapping else 'jpa','akeeba.advanced.postproc_engine':'none','akeeba.quota.enable_count_quota':'0','akeeba.quota.enable_size_quota':'0','akeeba.quota.maxage.enable':'0','akeeba.quota.remotely.enable_count_quota':'0','akeeba.quota.remotely.enable_size_quota':'0','akeeba.quota.remotely.maxage.enable':'0','akeeba.quota.obsolete_quota':'0','akeeba.quota.enable_logfiles':'0'}
        # Installed Akeeba versions differ: a scalar option silently keeps only
        # the final repeated value, losing original-file and output overrides.
        legacy=available.get('driver')=='joomla-legacy'
        params=(joomla_overrides(p,overrides) if p['cms']=='joomla' and not legacy
                else ['--overrides='+','.join(k+'='+v for k,v in overrides.items())])
        if p['cms']=='joomla':base=['php','-d','auto_prepend_file=/vmm-tools/akeeba-local.php','cli/joomla.php'];take=['akeeba:backup:take'];query=['akeeba:backup:list']
        else:base=['php','-d','auto_prepend_file=/vmm-tools/akeeba-local.php','/usr/local/bin/wp','--allow-root'];take=['akeeba','backup','take'];query=['akeeba','backup','list']
        if legacy:
            shutil.copyfile(Path(__file__).parent/'tools/akeeba-legacy-status.php',tools/'akeeba-legacy-status.php')
            take_command=['php','-d','auto_prepend_file=/vmm-tools/akeeba-local.php','cli/akeeba-backup.php','--profile='+str(profile),'--description='+description]+['--override='+k+'='+v for k,v in overrides.items()]
        else:take_command=base+take+['--profile='+str(profile),'--description='+description]+params
        op.exec_php(p,take_command,timeout=7200,allowed_returncodes=(0,2))
        if legacy:
            raw=op.exec_php(p,['php','/vmm-tools/akeeba-legacy-status.php'],input=json.dumps({'description':description,'profile':profile}).encode(),timeout=120)
        else:raw=op.exec_php(p,base+query+['--description='+description,'--format=json'],timeout=120)
        rows=json_records(raw)
        record=next((r for r in rows if r.get('description')==description and r.get('status')=='complete'),None)
        if not record:raise ValueError('Akeeba hat die Sicherung nicht als vollständig abgeschlossen bestätigt. Dateien bleiben als unvollständige Sicherung zur Diagnose erhalten.')
        names=archive_names(record.get('archivename') or filename+'.jpa',record.get('multipart'))
        validate_archives(stage,names)
        try:seen=json.loads(report.read_text()) if required else {}
        except (OSError,ValueError):seen={}
        missing=[entry for entry in required if not isinstance(seen,dict) or not seen.get(entry)]
        if p.get('backup_group') and original_config_missing(op.folder(p)/'site',p['cms']):missing.append('ursprüngliche CMS-Konfiguration (älterer Import ohne Sicherung)')
        info={'project':name,'created':int(time.time()),'profile':profile,'status':'complete','files':names,'restored_server_files':[name for name in SERVER_FILES if name in required],'restored_original_files':required,'native_id':str(record.get('id','')),'sha256':{file:op.digest(stage/file) for file in names}}
        if missing:
            info.update(status='unverified',native_status='complete',warning='Akeeba hat das Backup erfolgreich abgeschlossen. Der Sicherungsnachweis für ursprüngliche Serverdateien fehlt: '+', '.join(missing)+'. Keine geprüfte Produktionssicherung.')
        metadata.write_text(json.dumps(info))
    except Exception as error:
        from store import redact
        metadata.write_text(json.dumps({'project':name,'created':int(time.time()),'profile':profile,'status':'error','files':[],'error':redact(str(error))}))
        # The native CLI may have kept its profile's output location. Recover
        # that completed archive instead of reporting that no backup exists.
        if locals().get('record'):
            try:
                reconcile(name)
                recovered=json.loads(metadata.read_text())
                if recovered.get('status')=='unverified':
                    if verify:raise ValueError('Das Archiv steht zum Download bereit; ursprüngliche Serverdateien sind noch nicht bestätigt.')
                    return 'Akeeba-Backup aus dem Projektordner übernommen und zum Download verfügbar. '+recovered['warning']
            except Exception:
                if json.loads(metadata.read_text()).get('status')=='unverified':raise
        raise
    if verify and info['status']=='unverified':raise ValueError('Das Archiv steht zum Download bereit; die ursprünglichen Serverdateien sind noch nicht bestätigt.')
    if verify:
        from verification_service import run
        try:run('backup',ident,p['php'],completed_backup=True)
        except Exception as e:raise ValueError('Das Akeeba-Backup wurde erstellt und bleibt erhalten; die Wiederherstellungsprobe ist fehlgeschlagen: '+str(e)) from None
    if info['status']=='unverified':return 'Akeeba-Backup erstellt und zum Download verfügbar. '+info['warning']
    return 'Akeeba-Backup erstellt: '+names[0]+' · '+str(len(names))+' Archivteile. Download im Projekt unter Akeeba-Backups.'
