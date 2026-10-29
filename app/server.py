import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote, parse_qs
from catalog import valid_cms, version, register, download, sync, digest, validate_zip
from runtime import PHP, ports, slug, project_links
from store import DATA, LOCK, db, records, project, job, cipher
from operations import transition, snapshot, restore_akeeba, finalize_restore, install_extension, wp_updates, monitor

import extension_service as extensions
import project_service as projects_service

from credentials import listing as credential_list, change as credential_change

STATIC=Path(__file__).parent/'static'
MAX_UPLOAD=4*1024*1024*1024

def public(row):
    return {k:v for k,v in dict(row).items() if k not in ('db_password','db_root_password','secret','filename')}

def create_project(body):
    name=slug(body.get('slug'));restore=bool(body.get('backup_id'));cms='auto' if restore else valid_cms(body.get('cms'));php_mode=body.get('php','auto');php='8.4' if php_mode=='auto' else php_mode;ports(php)
    from database_profiles import validate
    database_profile=validate(body.get('database_profile','auto'))
    if any((DATA/'trash').glob(name+'-*/metadata.json')):raise ValueError('Dieser Projektname liegt im lokalen Papierkorb. Zur Wiederherstellung reserviert; bitte einen anderen Namen verwenden.')
    plans=[] if restore else extensions.validate_plans(cms,body.get('extensions',[]),name)
    restore=bool(body.get('backup_id'))
    if body.get('admin') and not restore:projects_service.admin_settings(body['admin'])
    package_id=body.get('package_id')
    with db() as c:
        if restore:
            group=body.get('backup_id');archive=body.get('archive','')
            if not isinstance(group,str) or not re.fullmatch(r'[a-f0-9]{24}',group): raise ValueError('Ungültige Backup-Gruppe.')
            if not isinstance(archive,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.(jpa|jps|zip)',archive,re.I): raise ValueError('Backup-Hauptarchiv auswählen.')
            if not (DATA/'backups'/group/archive).is_file(): raise ValueError('Backup-Hauptarchiv fehlt.')
            if archive.lower().endswith('.jps') and not body.get('password'): raise ValueError('Passwort für das verschlüsselte JPS-Archiv eingeben.')
            import kickstart_service
            choice=body.get('kickstart','auto')
            if choice not in ('auto','manual') and not re.fullmatch(r'\d+\.\d+\.\d+',str(choice)):raise ValueError('Ungültige Kickstart-Version.')
            v='Backup';package_id=None
        else:
            package=c.execute('SELECT * FROM packages WHERE id=?',(package_id,)).fetchone()
            if not package or package['cms']!=cms: raise ValueError('Ein archiviertes Installationspaket für dieses CMS auswählen.')
            v=package['version']
        c.execute('INSERT INTO projects (slug,cms,php,status,created,db_password,db_root_password,error,version,package_id,storage,restore) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (name,cms,php,'stopped',int(time.time()),secrets.token_urlsafe(24),secrets.token_urlsafe(24),None,v,package_id,'shared',int(restore)))
    with db() as c:c.execute('UPDATE projects SET database_profile=?,php_mode=? WHERE slug=?',(database_profile,'auto' if php_mode=='auto' else 'manual',name))
    if restore:
        with db() as c:c.execute("UPDATE projects SET status='preparing',backup_group=?,backup_archive=?,kickstart=? WHERE slug=?",(group,archive,choice,name))
    extensions.assign(name,plans)
    return name

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass

    def send(self,code,value):
        body=json.dumps(value).encode();self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)

    def trusted_host(self):
        # Prevent DNS rebinding into the intentionally unauthenticated local API.
        host=urlparse('//'+self.headers.get('Host','')).hostname
        if not host: return False
        if host=='localhost' or host=='vmm.test' or host.endswith('.vmm.test'): return True
        try: return ipaddress.ip_address(host).is_loopback or ipaddress.ip_address(host).is_private
        except ValueError: return False

    def website_request(self):
        host=urlparse('//'+self.headers.get('Host','')).hostname or ''
        match=re.fullmatch(r'([a-z][a-z0-9-]{0,39})\.vmm\.test',host)
        if not match: return False
        name=match.group(1)
        try:
            p=project(name)
            requested=urlparse('//'+self.headers.get('Host','')).port
            php=next((v for v in PHP if requested in ports(v)),None)
            if not php: raise ValueError('Unbekannter PHP-Port.')
            if p['status']=='preparing' or p.get('restore'):
                title='Projekt ist gestoppt.' if p['status']=='stopped' else 'Projekt konnte nicht gestartet werden.'
                text='Projekt im VMM-Dashboard starten bzw. den Fehler prüfen.'
                refresh=False
            else:
                if p['storage']=='legacy': raise ValueError('Älteres Projekt unterstützt diesen Port nicht.')
                try: job(name,'runtime',lambda:transition(name,'start',php))
                except ValueError: pass
                title='PHP '+php+' wird vorbereitet.'
                text='Die Seite lädt automatisch neu, sobald die Laufzeit bereit ist. Der erste Start kann einige Minuten dauern.'
                refresh=True
        except ValueError as e:
            title='Website nicht verfügbar.';text=str(e);refresh=False
        import html
        self.send_response(503)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy',"default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        page='<!doctype html><html lang="de"><meta charset="utf-8"><title>VMM · Website starten</title>'
        if refresh: page+='<meta http-equiv="refresh" content="5">'
        page+='<h1>'+html.escape(title)+'</h1><p>'+html.escape(text)+'</p></html>'
        self.wfile.write(page.encode())
        return True

    def do_GET(self):
        if self.website_request(): return
        if not self.trusted_host(): return self.send(403,{'error':'Host nicht freigegeben.'})
        path=urlparse(self.path).path
        try:
            if path=='/api/database-profiles':
                from database_profiles import listing
                return self.send(200,{'profiles':listing()})
            if path=='/api/environment':
                import environment_service
                from database_profiles import profile,listing
                return self.send(200,{**environment_service.saved_report(DATA),'existing_database':profile({'database_profile':'existing'}),'database_profiles':listing()})
            if path=='/api/projects': return self.send(200,{'projects':[{**public(p),**project_links(dict(p),DATA/'projects'/p['slug']),'extension_status':extensions.inventory_summary(p['slug'])} for p in records('projects')],'php':PHP})
            if re.fullmatch(r'/api/projects/[a-z][a-z0-9-]{0,39}/credentials',path):
                return self.send(200,{'credentials':credential_list(slug(path.split('/')[3]))})
            if path=='/api/packages':
                with db() as c: releases=[dict(r) for r in c.execute('SELECT * FROM releases')]
                return self.send(200,{'packages':[public(p) for p in records('packages')],'releases':releases})
            if path=='/api/jobs':
                history=parse_qs(urlparse(self.path).query).get('history',[''])[0]=='1'
                return self.send(200,{'jobs':records('jobs') if history else records('jobs')[:100]})
            if path=='/api/extensions':
                with db() as c: assignments=[dict(r) for r in c.execute('SELECT * FROM project_extensions')]
                with db() as c: plans=[dict(r) for r in c.execute('SELECT * FROM extension_plans')]
                return self.send(200,{'extensions':[public(p) for p in records('extensions')],'licenses':extensions.licenses(),'assignments':assignments,'sources':extensions.sources(),'plans':plans,'providers':extensions.providers.listing()})
            if re.fullmatch(r'/api/projects/[a-z][a-z0-9-]{0,39}/extensions',path):
                return self.send(200,{'installed':extensions.installed(path.split('/')[3])})
            if path=='/api/backups':
                groups=[]
                root=DATA/'backups'
                if root.exists():
                    for folder in root.iterdir():
                        if folder.is_dir(): groups.append({'id':folder.name,'files':[p.name for p in folder.iterdir() if p.is_file() and not p.name.endswith('.partial')]})
                return self.send(200,{'backups':groups})
            if path=='/api/exports':
                root=DATA/'exports'
                return self.send(200,{'exports':[{'name':p.name,'size':p.stat().st_size} for p in root.glob('*.zip')] if root.exists() else []})
            if path.startswith('/api/exports/'):
                filename=unquote(path.split('/')[-1])
                if not re.fullmatch(r'[a-z0-9-]+\.zip',filename): raise ValueError('Ungültiger Dateiname.')
                file=DATA/'exports'/filename
                if not file.is_file(): return self.send(404,{'error':'Datei fehlt.'})
                self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Disposition','attachment; filename="'+filename+'"');self.send_header('Content-Length',str(file.stat().st_size));self.end_headers()
                with file.open('rb') as f: shutil.copyfileobj(f,self.wfile)
                return
            if path.startswith('/api/projects/') and path.endswith('/database'):
                p=project(slug(path.split('/')[3]))
                from shared_runtime import database_info
                return self.send(200,database_info(p) if p['storage']=='shared' else {'host':'db','database':'website','user':'website','password':p['db_password']})
            if path=='/api/runtimes':
                from shared_operations import runtime_status
                return self.send(200,{'runtimes':runtime_status()})
            if path=='/api/system-credentials':
                file=DATA/'shared/secrets.json'
                value=json.loads(file.read_text()) if file.is_file() else {}
                return self.send(200,{'MariaDB-Host':'db','MariaDB-Administrator':'root','MariaDB-Root-Passwort':value.get('root_password','')})
            if path=='/api/kickstart':
                import kickstart_service
                return self.send(200,{'versions':kickstart_service.available(),'manual':(DATA/'tools/kickstart.php').is_file()})
            if path=='/api/manager-update':
                import update_service
                return self.send(200,update_service.status())
            if path=='/api/health':
                try:
                    r=subprocess.run(['docker','info','--format','{{.ServerVersion}}'],capture_output=True,text=True,timeout=5);ok=r.returncode==0
                except (OSError,subprocess.TimeoutExpired): ok=False
                return self.send(200,{'docker':ok,'login':False,'kickstart':(DATA/'tools'/'kickstart.php').exists(),'domain':'vmm.test'})
            if path.startswith('/api/'): return self.send(404,{'error':'Nicht gefunden.'})
            files={'/':'index.html','/app.js':'app.js','/theme.js':'theme.js','/style.css':'style.css','/assets/tentacle-logo.png':'assets/tentacle-logo.png'}
            if path not in files: return self.send(404,{'error':'Nicht gefunden.'})
            file=STATIC/files[path];self.send_response(200)
            self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript','css':'text/css','png':'image/png'}[file.suffix[1:]])
            self.send_header('Cache-Control','no-cache')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(file.read_bytes())
        except (ValueError,RuntimeError,OSError) as e: self.send(400,{'error':str(e)})

    def upload(self,path,length):
        name=unquote(self.headers.get('X-VMM-Filename',''))
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}',name) or name.startswith('.'): raise ValueError('Ungültiger Dateiname.')
        with tempfile.TemporaryDirectory(dir=DATA) as tmp:
            file=Path(tmp)/name
            with file.open('wb') as out:
                remaining=length
                while remaining:
                    chunk=self.rfile.read(min(1024*1024,remaining))
                    if not chunk: raise ValueError('Upload wurde unterbrochen.')
                    out.write(chunk);remaining-=len(chunk)
            query=parse_qs(urlparse(self.path).query)
            if path=='/api/uploads/packages':
                ident=register(file,query.get('cms',[''])[0],query.get('version',[''])[0],'manual')
                return self.send(201,{'id':ident})
            if path=='/api/uploads/extensions':
                source_id=query.get('source',[''])[0]
                if source_id:
                    source=extensions.source(source_id)
                else:
                    detected=extensions.inspect_upload(file);provider=query.get('provider',['custom'])[0]
                    source_id=extensions.save_source({**detected,'provider':provider})
                    source=extensions.source(source_id)
                requested=query.get('version',[''])[0] or extensions.package_version(file,source['cms'])
                ident=extensions.register_package(file,source,version(requested))
                return self.send(201,{'id':ident,'source':source_id})
            if path=='/api/uploads/kickstart':
                if name.lower()!='kickstart.php' or file.stat().st_size>20*1024*1024: raise ValueError('Offizielle kickstart.php auswählen (max. 20 MB).')
                if b'<?php' not in file.read_bytes()[:2048]: raise ValueError('Keine PHP-Datei.')
                folder=DATA/'tools';folder.mkdir(exist_ok=True);shutil.copyfile(file,folder/'kickstart.php')
                return self.send(201,{'ok':True})
            if path.startswith('/api/uploads/backups/'):
                group=path.split('/')[-1]
                if not re.fullmatch(r'[a-f0-9]{24}',group): raise ValueError('Ungültige Backup-Gruppe.')
                if not re.search(r'\.(jpa|jps|zip|j\d+|z\d+)$',name,re.I): raise ValueError('Keine Akeeba-Archivdatei.')
                folder=DATA/'backups'/group;folder.mkdir(parents=True,exist_ok=True)
                if (folder/name).exists(): raise ValueError('Datei bereits vorhanden. Neue Backup-Gruppe verwenden.')
                shutil.copyfile(file,folder/name)
                return self.send(201,{'id':group,'filename':name})
            return self.send(404,{'error':'Uploadziel nicht gefunden.'})

    def do_POST(self):
        if self.website_request(): return
        if not self.trusted_host() or self.headers.get('X-VMM-Request')!='1': return self.send(403,{'error':'Ungültige Anfrage.'})
        origin=self.headers.get('Origin')
        if origin and urlparse(origin).netloc!=self.headers.get('Host'): return self.send(403,{'error':'Fremder Ursprung ist nicht erlaubt.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<0: raise ValueError('Ungültige Anfragegröße.')
            path=urlparse(self.path).path
            if path.startswith('/api/uploads/'):
                if length>MAX_UPLOAD: return self.send(413,{'error':'Datei zu groß (max. 4 GB pro Teil).'})
                return self.upload(path,length)
            if length>16384: return self.send(413,{'error':'Anfrage zu groß.'})
            body=json.loads(self.rfile.read(length) or '{}')
            if not isinstance(body,dict): raise ValueError('JSON-Objekt erwartet.')
            if path.startswith('/api/runtimes/'):
                from shared_operations import runtime_transition
                version=path.split('/')[-1];ports(version);action=body.get('action')
                if action not in ('start','stop'):raise ValueError('Ungültige Laufzeitaktion.')
                return self.send(202,{'job':job('shared-runtime','runtime',lambda:runtime_transition(version,action))})
            if path=='/api/environment/check':
                import environment_service
                return self.send(202,{'job':job('environment','environment-check',lambda:environment_service.check(DATA))})
            if path=='/api/kickstart/sync':
                import kickstart_service
                return self.send(202,{'job':job('kickstart','catalog',lambda:str(len(kickstart_service.catalog(True)))+' Kickstart-Versionen verfügbar.')})
            if path=='/api/kickstart/download':
                import kickstart_service
                return self.send(202,{'job':job('kickstart','download',lambda:'Kickstart gespeichert: '+str(kickstart_service.ensure(body.get('version','auto')).parent.name))})
            if path=='/api/manager-update/check':
                import update_service
                return self.send(202,{'job':job('manager-update','manager-check',lambda:update_service.check_message())})
            if path=='/api/manager-update/install':
                import update_service
                return self.send(202,{'job':job('manager-update','manager-install',lambda:update_service.install(body.get('version')))})
            if path=='/api/projects':
                name=create_project(body)
                if body.get('backup_id'):
                    ident=job(name,'akeeba',lambda:restore_akeeba(name,body['backup_id'],body.get('archive',''),body.get('password','')))
                    return self.send(202,{'slug':name,'job':ident})
                if body.get('admin') or body.get('prepare'):return self.send(202,{'slug':name,'job':job(name,'provision',lambda:projects_service.provision(name,body.get('admin')))})
                return self.send(201,{'slug':name})
            if path=='/api/catalog/sync':
                cms=valid_cms(body.get('cms'));return self.send(202,{'job':job('catalog-'+cms,'catalog',lambda:sync(cms))})
            if path=='/api/packages/download':
                cms=valid_cms(body.get('cms'));v=version(body.get('version'))
                return self.send(202,{'job':job('package-'+cms+'-'+v,'download',lambda:download(cms,v))})
            if path=='/api/providers':return self.send(201,{'id':extensions.providers.save(body)})
            if path in ('/api/licenses','/api/extension-sources') and body.get('provider') not in {p['id'] for p in extensions.providers.listing()}:raise ValueError('Anbieter zuerst über „Anbieter hinzufügen“ anlegen.')
            if path=='/api/licenses':return self.send(201,{'id':extensions.save_license(body)})
            if path=='/api/extension-sources':return self.send(201,{'id':extensions.save_source(body)})
            source_action=re.fullmatch(r'/api/extension-sources/([a-f0-9]{24})/(check|download)',path)
            if source_action:
                ident,action=source_action.groups();extensions.source(ident)
                def task():
                    if action=='check':return extensions.check(ident,body.get('license'))
                    extensions.download_package(ident,body.get('version','latest'),body.get('license'));return 'Erweiterung dauerhaft archiviert.'
                return self.send(202,{'job':job('extension-'+ident,action,task)})
            parts=path.strip('/').split('/')
            if len(parts)==4 and parts[:2]==['api','projects']:
                name=slug(parts[2]);action=parts[3];p=project(name)
                if action=='extensions':
                    items=extensions.validate_plans(p['cms'],body.get('extensions',[]),name)
                    if body.get('install') and not extensions.ready(p):raise ValueError('Zuerst die CMS-Einrichtung abschließen.')
                    extensions.assign(name,items)
                    if body.get('install'):return self.send(202,{'job':job(name,'extensions',lambda:extensions.process_pending(name))})
                    return self.send(200,{'ok':True})
                if action=='license-scan':return self.send(200,projects_service.scan_licenses(name))
                if action=='license-import':return self.send(201,projects_service.import_license(name,body))
                if action=='users':return self.send(200,projects_service.user_action(name,body))
                if action=='delete':
                    if body.get('confirm')!=name:raise ValueError('Zum Löschen den Projektnamen eingeben.')
                    return self.send(202,{'job':job(name,'delete-project',lambda:projects_service.delete_project(name))})
                if action=='credentials': return self.send(200,credential_change(name,body))
                if action=='runtime':
                    php=body.get('php') if action=='runtime' else None
                    if php: ports(php)
                    return self.send(202,{'job':job(name,action,lambda:transition(name,'start' if action!='stop' else 'stop',php))})
                if action=='restore':
                    if not p['restore']: raise ValueError('Dieses Projekt ist kein offener Akeeba-Import.')
                    group=body.get('backup_id','');archive=body.get('archive','');password=body.get('password','')
                    if not isinstance(group,str) or not re.fullmatch(r'[a-f0-9]{24}',group): raise ValueError('Backup-Gruppe auswählen.')
                    if not isinstance(archive,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.(jpa|jps|zip)',archive,re.I): raise ValueError('Backup-Hauptarchiv auswählen.')
                    if not isinstance(password,str): raise ValueError('Ungültiges Passwort.')
                    if archive.lower().endswith('.jps') and not password: raise ValueError('JPS-Passwort eingeben.')
                    choice=body.get('kickstart',p.get('kickstart','auto'))
                    with db() as c:c.execute('UPDATE projects SET kickstart=? WHERE slug=?',(choice,name))
                    return self.send(202,{'job':job(name,'akeeba',lambda:restore_akeeba(name,group,archive,password))})
                if action=='snapshot': return self.send(202,{'job':job(name,action,lambda:snapshot(name))})
                if action=='finalize': return self.send(202,{'job':job(name,action,lambda:finalize_restore(name))})
                if action=='update-extension':
                    ident=str(body.get('extension',''))
                    return self.send(202,{'job':job(name,'install-extension',lambda:extensions.update_single(name,ident))})
                if action in ('updates','update-all'):
                    return self.send(202,{'job':job(name,action,lambda:extensions.project_updates(name,action=='update-all'))})
                if action=='extension':
                    ident=body.get('extension');license_id=body.get('license') or None
                    with db() as c:
                        ext=c.execute('SELECT * FROM extensions WHERE id=?',(ident,)).fetchone()
                        if not ext or ext['cms']!=p['cms']: raise ValueError('Erweiterung passt nicht zum Projekt.')
                        if license_id:
                            license_row=c.execute('SELECT provider FROM licenses WHERE id=?',(license_id,)).fetchone()
                            if not license_row or license_row['provider']!=ext['provider']: raise ValueError('Lizenz passt nicht zum Anbieter.')
                        c.execute('INSERT OR REPLACE INTO project_extensions VALUES (?,?,?,?)',(name,ident,license_id,'assigned'))
                    if ext['source_id']:
                        extensions.assign(name,[{'source':ext['source_id'],'license':license_id,'version':ext['version']}])
                        if body.get('install'):return self.send(202,{'job':job(name,'install-extension',lambda:extensions.install_plan(name,ext['source_id']))})
                    elif body.get('install'): return self.send(202,{'job':job(name,'install-extension',lambda:install_extension(name,ident))})
                    return self.send(200,{'ok':True})
            return self.send(404,{'error':'Nicht gefunden.'})
        except __import__('sqlite3').IntegrityError: self.send(409,{'error':'Eintrag existiert bereits oder eine Zuordnung ist ungültig.'})
        except (ValueError,TypeError,KeyError,RuntimeError,OSError,zipfile.BadZipFile) as e: self.send(400,{'error':str(e)})

if __name__=='__main__':
    threading.Thread(target=monitor,daemon=True).start()
    import update_service
    threading.Thread(target=update_service.monitor,daemon=True).start()
    ThreadingHTTPServer((os.environ.get('VMM_LISTEN','127.0.0.1'),8090),Handler).serve_forever()
