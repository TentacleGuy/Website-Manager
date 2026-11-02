"""Restore a copy into disposable containers on an internal network without host ports."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import time
from store import DATA,db,job,project,redact


def report_file(kind,ident):
    digest=hashlib.sha256((kind+':'+ident).encode()).hexdigest()
    return DATA/'verification/reports'/(digest+'.json')


def result(kind,ident):
    try:return json.loads(report_file(kind,ident).read_text())
    except (OSError,ValueError):return None


def write_report(kind,ident,value):
    path=report_file(kind,ident);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.new');temp.write_text(json.dumps(value));temp.replace(path)
    if kind=='backup':
        file=DATA/'backups'/ident/'manager-backup.json'
        try:metadata=json.loads(file.read_text())
        except (OSError,ValueError):return
        metadata['verification']={k:v for k,v in value.items() if k not in ('containers','network')}
        temp=file.with_suffix('.verify-new');temp.write_text(json.dumps(metadata));temp.replace(file)


def start(kind,ident,php=None):
    if kind not in ('backup','export') or not isinstance(ident,str):raise ValueError('Eine Akeeba- oder ZIP-Sicherung auswählen.')
    import cleanup_service
    info=cleanup_service.review(kind,ident)
    if info['blocked']:raise ValueError(' '.join(info['blocked']))
    return {'job':job('verify-'+kind+'-'+ident,'backup-verify',lambda:run(kind,ident,php))}


def run(kind,ident,php=None,completed_backup=False):
    import operations as op
    from runtime import host_path,PHP
    from storage_paths import host_location
    from database_profiles import profile,DEFAULT
    from backup_service import detect
    import cleanup_service
    info=cleanup_service.review(kind,ident)
    blocked=[x for x in info['blocked'] if 'Prüfung dieser Sicherung' not in x]
    if completed_backup and kind=='backup':
        meta=DATA/'backups'/ident/'manager-backup.json'
        if meta.is_file() and json.loads(meta.read_text()).get('status')=='complete':blocked=[x for x in blocked if 'Backup wird noch erstellt' not in x]
    if blocked:raise ValueError(' '.join(blocked))
    token=secrets.token_hex(12);stage=DATA/'verification/runs'/token;site=stage/'site';tools=stage/'tools'
    site.mkdir(parents=True);site.chmod(0o777);tools.mkdir()
    host=host_path(os.environ.get('VMM_HOST_DATA',str(DATA)))+'/verification/runs/'+token
    network='vmm-verify-'+token;database=network+'-db';web=network+'-php'
    value={'id':token,'kind':kind,'source':ident,'status':'running','created':int(time.time()),'message':'Wiederherstellungskopie wird vorbereitet.','containers':[database,web],'network':network}
    metadata={}
    def report(message,**fields):
        value.update(message=message,**fields);write_report(kind,ident,value)
        resource=metadata.get('project') if completed_backup else 'verify-'+kind+'-'+ident
        if resource:
            with db() as c:c.execute("UPDATE jobs SET message=? WHERE resource=? AND status IN ('queued','running')",(message,resource))
    def execute(args,**kwargs):return op.command(args,**kwargs)
    try:
        associated={}
        metadata={}
        if kind=='backup':
            metadata_file=DATA/'backups'/ident/'manager-backup.json'
            if metadata_file.exists():metadata=json.loads(metadata_file.read_text())
            if metadata.get('project'):
                try:associated=project(metadata['project'])
                except ValueError:pass
            source=DATA/'backups'/ident
            archives=sorted(p.name for p in source.iterdir() if p.is_file() and not p.is_symlink() and re.search(r'\.(jpa|zip|jps)$',p.name,re.I))
            if len(archives)!=1:raise ValueError('Genau ein Hauptarchiv pro Sicherung wird für die Prüfung benötigt.')
            archive=archives[0]
            if archive.lower().endswith('.jps'):raise ValueError('Verschlüsselte JPS-Archive müssen zuerst mit ihrem Passwort in ein Projekt importiert werden.')
            if shutil.disk_usage(DATA).free<max(sum(p.stat().st_size for p in source.iterdir() if p.is_file())*3,1024**3):raise ValueError('Nicht genug freier Speicherplatz für eine isolierte Wiederherstellungskopie.')
            for name,digest in metadata.get('sha256',{}).items():
                path=source/name
                if Path(name).name!=name or path.is_symlink() or not path.is_file() or op.digest(path)!=digest:raise ValueError('Archiv-Prüfsumme stimmt nicht. Originaldatei wurde nicht verändert.')
            php=php or associated.get('php') or '8.4'
            if php not in PHP:raise ValueError('Eine unterstützte PHP-Version auswählen.')
            execute(['docker','image','inspect','vmm-php:'+php],timeout=15)
            import kickstart_service
            kickstart=kickstart_service.ensure('auto',php)
            report('Akeeba-Archiv wird in eine getrennte Testkopie entpackt.')
            execute(['docker','run','--rm','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=bind,source='+host+'/site,target=/restore','--mount','type=bind,source='+host_location('backups')+'/'+ident+',target=/input,readonly','--mount','type=bind,source='+host+'/tools,target=/vmm-tools,readonly','--mount','type=bind,source='+host_path(os.environ.get('VMM_HOST_DATA',str(DATA)))+'/tools/'+kickstart.relative_to(DATA/'tools').as_posix()+',target=/kickstart.php,readonly','vmm-php:'+php,'php','-d','auto_prepend_file=','/kickstart.php','/input/'+archive,'/restore','--silent'],timeout=1800)
        else:
            if not re.fullmatch(r'[a-z0-9][a-z0-9._-]*\.zip',ident):raise ValueError('Ungültige Projektsicherung.')
            source=DATA/'exports'/ident
            from catalog import validate_zip
            import zipfile
            validate_zip(source)
            with zipfile.ZipFile(source) as archive:archive.extractall(stage/'zip')
            contents=stage/'zip'
            if not (contents/'site').is_dir() or not (contents/'database.sql').is_file():raise ValueError('ZIP benötigt Website-Dateien und database.sql.')
            shutil.rmtree(site);(contents/'site').rename(site)
            try:associated=json.loads((contents/'project.json').read_text())
            except (OSError,ValueError):associated={}
            php=php or associated.get('php') or '8.4'
            if php not in PHP:raise ValueError('Eine unterstützte PHP-Version auswählen.')
            execute(['docker','image','inspect','vmm-php:'+php],timeout=15)
        for folder,dirs,files in os.walk(site):
            if Path(folder).is_symlink():raise ValueError('Verknüpfungen sind in Wiederherstellungsproben nicht erlaubt.')
            Path(folder).chmod(0o777)
            for name in dirs+files:
                p=Path(folder)/name
                if p.is_symlink():raise ValueError('Verknüpfungen sind in Wiederherstellungsproben nicht erlaubt.')
                if p.is_file():p.chmod(0o666)
        cms,cms_version=detect(site)
        from project_files import prepare_local
        prepare_local(site,tools)
        for name in ('restore-backup.php','verification-config.php'):shutil.copyfile(Path(__file__).parent/'tools'/name,tools/name)
        (tools/'prepend.php').write_text('<?php\n')
        config=profile(associated if associated.get('database_profile') else {'database_profile':DEFAULT})
        engine=config['engine'];db_password=secrets.token_hex(20);root_password=secrets.token_hex(20)
        prefix='MYSQL' if engine=='mysql' else 'MARIADB'
        env=stage/'database.env';env.write_text('\n'.join([prefix+'_ROOT_PASSWORD='+root_password,prefix+'_DATABASE=vmm_verify',prefix+'_USER=vmm_verify',prefix+'_PASSWORD='+db_password])+'\n');env.chmod(0o600)
        database_info={'host':'verify-db','database':'vmm_verify','user':'vmm_verify','password':db_password}
        execute(['docker','image','inspect',config['image']],timeout=15)
        execute(['docker','network','create','--internal',network],timeout=30)
        report('Getrennte Testdatenbank wird gestartet.',cms=cms,version=cms_version,php=php)
        execute(['docker','run','--rm','-d','--name',database,'--label','vmm.verification=true','--network',network,'--network-alias','verify-db','--memory','1536m','--cpus','1','--tmpfs','/var/lib/mysql:rw,size=1536m','--env-file',str(env),config['image']],timeout=60)
        client='mysql' if engine=='mysql' else 'mariadb';admin='mysqladmin' if engine=='mysql' else 'mariadb-admin'
        ready=False
        for attempt in range(60):
            try:execute(['docker','exec',database,'sh','-c','exec '+admin+' ping -h127.0.0.1 -uroot -p"$'+prefix+'_ROOT_PASSWORD" --silent'],timeout=5);ready=True;break
            except RuntimeError:time.sleep(1)
        if not ready:raise ValueError('Die isolierte Testdatenbank ist nicht gestartet.')
        execute(['docker','run','--rm','-d','--name',web,'--label','vmm.verification=true','--network',network,'--memory','768m','--cpus','1','-e','VMM_VERIFICATION=1','-e','VMM_PROJECT_ROOT=/var/www/html','--mount','type=bind,source='+host+'/site,target=/var/www/html','--mount','type=bind,source='+host+'/tools,target=/vmm-tools,readonly','vmm-php:'+php],timeout=60)
        def php_command(args,**kwargs):return execute(['docker','exec','-i','-w','/var/www/html',web]+args,**kwargs)
        report('Datenbank wird ausschließlich in die Testdatenbank wiederhergestellt.')
        if kind=='backup':
            native=(site/'installation/src/Framework/Cli/InstallationQueue.php').is_file()
            if native:php_command(['php','installation/cli.php','config:make'],timeout=300)
            output=php_command(['php','/vmm-tools/restore-backup.php'],input=json.dumps({'database':database_info,'url':'http://localhost'}).encode(),timeout=1800)
            if (b'VMM_CONFIGURED' if native else b'VMM_DATABASE_RESTORED') not in output:raise ValueError('Der Akeeba-Installer hat die Testdatenbank nicht bestätigt.')
            if native:
                output=php_command(['php','installation/cli.php','execute'],timeout=1800)
                if b'Restoration complete' not in output:raise ValueError('Der Akeeba-Installer hat die Wiederherstellung nicht abgeschlossen.')
        else:
            with (stage/'zip/database.sql').open('rb') as sql:
                execute(['docker','exec','-i',database,'sh','-c','exec '+client+' -u"$'+prefix+'_USER" -p"$'+prefix+'_PASSWORD" "$'+prefix+'_DATABASE"'],stdin=sql,timeout=1800)
        php_command(['php','/vmm-tools/verification-config.php'],input=json.dumps(database_info).encode(),timeout=120)
        for name in ('configuration.php','wp-config.php'):
            if (site/name).is_file():(site/name).chmod(0o666)
        if cms=='wordpress':
            old=php_command(['php','/usr/local/bin/wp','--allow-root','--skip-plugins','--skip-themes','option','get','siteurl'],timeout=120).decode().strip()
            if old and old!='http://localhost':php_command(['php','/usr/local/bin/wp','--allow-root','--skip-plugins','--skip-themes','search-replace',old,'http://localhost','--all-tables-with-prefix','--skip-columns=guid'],timeout=900)
        if (site/'installation').exists():shutil.rmtree(site/'installation')
        report('Wiederhergestellte Tabellen und lokale HTTP-Antwort werden geprüft.')
        query='SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE();'
        count=execute(['docker','exec',database,'sh','-c','exec '+client+' -N -u"$'+prefix+'_USER" -p"$'+prefix+'_PASSWORD" "$'+prefix+'_DATABASE" -e "$1"','sh',query],timeout=30).decode().strip()
        if not count.isdigit() or int(count)<1:raise ValueError('Keine wiederhergestellten Datenbanktabellen gefunden.')
        status=php_command(['curl','--silent','--show-error','--max-time','30','--output','/tmp/vmm-response','--write-out','%{http_code}','http://127.0.0.1/'],timeout=45).decode().strip()
        if not status.isdigit() or not 200<=int(status)<400:raise ValueError('Die Testwebsite liefert HTTP '+status+'.')
        report('Wiederherstellungsprobe bestanden: Datenbank und Website antworten.',status='done',finished=int(time.time()),tables=int(count),http=int(status))
        return value['message']
    except Exception as e:
        report(redact(str(e)),status='error',finished=int(time.time()))
        raise ValueError('Wiederherstellungsprobe fehlgeschlagen: '+redact(str(e))) from None
    finally:
        for container in (web,database):
            try:execute(['docker','rm','-f',container],timeout=30)
            except Exception:pass
        try:execute(['docker','network','rm',network],timeout=30)
        except Exception:pass
        shutil.rmtree(stage,ignore_errors=True)


def recover_interrupted():
    """Remove only disposable containers recorded by this installation before restart."""
    import operations as op
    reports=DATA/'verification/reports'
    if not reports.exists():return
    for file in reports.glob('*.json'):
        try:value=json.loads(file.read_text())
        except (OSError,ValueError):continue
        token=value.get('id','')
        if value.get('status')!='running' or not re.fullmatch(r'[a-f0-9]{24}',token):continue
        kind=value.get('kind');ident=value.get('source')
        if kind not in ('backup','export') or not isinstance(ident,str):continue
        with db() as c:
            if c.execute("SELECT 1 FROM jobs WHERE resource=? AND status IN ('queued','running')",('verify-'+kind+'-'+ident,)).fetchone():continue
        prefix='vmm-verify-'+token
        for name in (prefix+'-php',prefix+'-db'):
            try:op.command(['docker','rm','-f',name],timeout=15)
            except Exception:pass
        try:op.command(['docker','network','rm',prefix],timeout=15)
        except Exception:pass
        stage=DATA/'verification/runs'/token
        if stage.is_dir() and not stage.is_symlink():shutil.rmtree(stage,ignore_errors=True)
        value.update(status='interrupted',message='Manager wurde während der Wiederherstellungsprobe neu gestartet. Testkopie und Testcontainer wurden aufgeräumt.',finished=int(time.time()))
        write_report(kind,ident,value)
