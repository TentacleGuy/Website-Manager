"""Cached project state, daily read-only checks, local restore and account shortcuts."""
import hashlib,json,secrets,shutil,threading,time,zipfile
from pathlib import Path
from store import DATA,db,project,records,job
CANCEL=threading.Event()
USER_LOCKS={}

def invalidate_users(name):
    (DATA/'projects'/name/'users-cache.json').unlink(missing_ok=True)

def users(name,refresh=False):
    project(name)
    with USER_LOCKS.setdefault(name,threading.Lock()):
        file=DATA/'projects'/name/'users-cache.json'
        try:value=json.loads(file.read_text())
        except (OSError,ValueError):value=None
        if refresh or value is None:
            rows=__import__('project_service').user_action(name,{'action':'list'})
            value={'users':rows,'checked':time.time_ns()}
            file.parent.mkdir(parents=True,exist_ok=True)
            temp=file.with_suffix('.new');temp.write_text(json.dumps(value));temp.replace(file)
        return {**value,'defaultUser':{'id':default_user(name)}}


def cache(name):
    project(name)
    try:
        value=json.loads((DATA/'projects'/name/'extension-inventory.json').read_text())
        if project(name)['cms']=='joomla':
            import re
            site=DATA/'projects'/name/'site'
            for x in value['items']:
                if x.get('author'):continue
                e=x.get('element','');kind=x.get('kind');folder=x.get('folder','')
                if not re.fullmatch(r'[A-Za-z0-9_-]+',e) or folder and not re.fullmatch(r'[A-Za-z0-9_-]+',folder):continue
                paths={'component':[site/'administrator/components'/e/(e.removeprefix('com_')+'.xml')], 'module':[site/'modules'/e/(e+'.xml'),site/'administrator/modules'/e/(e+'.xml')], 'plugin':[site/'plugins'/folder/e/(e+'.xml')], 'template':[site/'templates'/e/'templateDetails.xml',site/'administrator/templates'/e/'templateDetails.xml']}.get(kind,[])
                for file in paths:
                    if file.is_file():
                        author=re.search(r'<author>([^<]+)',file.read_text(errors='replace'))
                        if author:x['author']=author[1]
                        break
        return value
    except (OSError,ValueError):return {'items':[],'checked':None}

def project_rows():
    from backup_service import detect
    values=records('projects')
    for p in values:
        try:
            cms,version=detect(DATA/'projects'/p['slug']/'site')
            if version!='Backup' and version!=p['version']:
                with db() as c:c.execute('UPDATE projects SET version=? WHERE slug=?',(version,p['slug']))
                p['version']=version
        except (ValueError,OSError):pass
        try:p['users_checked']=json.loads((DATA/'projects'/p['slug']/'users-cache.json').read_text()).get('checked')
        except (OSError,ValueError):p['users_checked']=None
        try:p['health']=json.loads((DATA/'projects'/p['slug']/'health.json').read_text())
        except (OSError,ValueError):p['health']=None
    return values

def check_project(name):
    import operations as op
    p=project(name)
    try:
        status=op.exec_php(p,['curl','-s','-o','/dev/null','--max-time','15','-w','%{http_code}','-H','Host: '+name+'.vmm.test','http://127.0.0.1/'],timeout=30).decode().strip()
        (DATA/'projects'/name/'health.json').write_text(json.dumps({'checked':int(time.time()),'http':status,'reachable':status.isdigit() and 200<=int(status)<400}))
        return __import__('extension_service').project_updates(name)
    finally:users(name,refresh=True)


def scan():
    import extension_service as ext
    import operations as op
    CANCEL.clear();values=project_rows();total=len(values);errors=[]
    for i,p in enumerate(values):
        if CANCEL.is_set():return 'Abgebrochen nach '+str(i)+' von '+str(total)+' Projekten.'
        message=str(i)+'/'+str(total)+' · '+p['slug']
        with db() as c:c.execute("UPDATE jobs SET message=? WHERE resource='project-checks' AND status='running'",(message,))
        if p.get('restore') or p['status']!='running':continue
        with db() as c:
            if c.execute("SELECT 1 FROM jobs WHERE resource=? AND status IN ('queued','running')",(p['slug'],)).fetchone():continue
        try:
            def check():return check_project(p['slug'])
            ident=job(p['slug'],'daily-check',check)
            while True:
                with db() as c:row=c.execute('SELECT status,message FROM jobs WHERE id=?',(ident,)).fetchone()
                if row['status'] not in ('queued','running'):
                    if row['status']=='error':errors.append(p['slug'])
                    break
                time.sleep(.5)
        except Exception:errors.append(p['slug'])
    return str(total)+'/'+str(total)+' Projekte geprüft.'+(' Fehler: '+', '.join(errors) if errors else '')

def scheduler():
    # A persisted timestamp prevents repeated CMS requests on each manager restart.
    file=DATA/'project-checks.json'
    while True:
        try:
            try:last=json.loads(file.read_text()).get('started',0)
            except (OSError,ValueError):last=0
            if time.time()-last>=86400:
                ident=job('project-checks','project-checks',scan)
                file.write_text(json.dumps({'started':int(time.time()),'job':ident}))
        except Exception:pass
        time.sleep(60)

def profiles(name):
    import operations as op
    p=project(name);op.write_tools(p)
    file=op.folder(p)/'tools/akeeba-profiles.php';shutil.copyfile(Path(__file__).parent/'tools/akeeba-profiles.php',file)
    return json.loads(op.exec_php(p,['php','/vmm-tools/akeeba-profiles.php'],timeout=60))

def account(name,body):
    import operations as op
    p=project(name);uid=int(body['id'])
    users=__import__('project_service').user_action(name,{'action':'list'})
    if not any(int(x['ID'])==uid for x in users):raise ValueError('Benutzer nicht gefunden.')
    selected=next(x for x in users if int(x['ID'])==uid)
    if body['action'] in ('login','default') and int(selected.get('block',0)):raise ValueError('Dieser Benutzer ist im CMS gesperrt.')
    root=op.folder(p);file=root/'manager-user.json'
    if body['action']=='default':file.write_text(json.dumps({'id':uid}));return {'ok':True}
    if body['action']=='delete':
        if len(users)<=1:raise ValueError('Der letzte Benutzer kann nicht gelöscht werden.')
        if file.exists() and json.loads(file.read_text()).get('id')==uid:raise ValueError('Zuerst einen anderen Standardbenutzer auswählen.')
        if p['cms']=='wordpress':
            selected=next(x for x in users if int(x['ID'])==uid)
            if 'administrator' in selected.get('roles','') and sum('administrator' in x.get('roles','') for x in users)<=1:raise ValueError('Der letzte Administrator kann nicht gelöscht werden.')
            target=next(x for x in users if int(x['ID'])!=uid)
            op.exec_php(p,['wp','--allow-root','user','delete',str(uid),'--reassign='+str(target['ID']),'--yes'])
        else:
            op.write_tools(p);op.exec_php(p,['php','/vmm-tools/cms-users.php'],input=json.dumps({'action':'delete','id':uid}).encode())
        invalidate_users(name)
        return {'ok':True}
    if body['action']!='login':raise ValueError('Unbekannte Benutzeraktion.')
    token=secrets.token_urlsafe(32);tools=root/'tools';tools.mkdir(exist_ok=True)
    (tools/('login-'+hashlib.sha256(token.encode()).hexdigest()+'.json')).write_text(json.dumps({'id':uid,'expires':time.time()+60,'cms':p['cms']}))
    shutil.copyfile(Path(__file__).parent/'tools/manager-login.php',root/'site/vmm-manager-login.php')
    from runtime import ports
    return {'url':'http://'+name+'.vmm.test:'+str(ports(p['php'])[0])+'/vmm-manager-login.php?token='+token}

def default_user(name):
    project(name)
    try:return json.loads((DATA/'projects'/name/'manager-user.json').read_text()).get('id')
    except (OSError,ValueError):return None

def restore_export(filename,name):
    """Always restore into a new slug. Never overwrite an existing project."""
    import server,operations as op
    from catalog import validate_zip
    from runtime import slug,PHP
    from shared_operations import ensure_database,context
    from database_profiles import sql_command
    name=slug(name)
    if (DATA/'projects'/name).exists() or any((DATA/'trash').glob(name+'-*/metadata.json')):raise ValueError('Projektname ist bereits belegt. Bitte einen neuen Namen wählen.')
    if not __import__('re').fullmatch(r'[a-z0-9][a-z0-9._-]*\.zip',filename):raise ValueError('Ungültige Sicherung.')
    source=DATA/'exports'/filename;validate_zip(source)
    with zipfile.ZipFile(source) as z:
        info=json.loads(z.read('project.json'))
        from catalog import valid_cms
        valid_cms(info.get('cms'))
        if info.get('php') not in PHP:raise ValueError('PHP-Version der Sicherung wird nicht unterstützt.')
        if 'database.sql' not in z.namelist() or not any(x.startswith('site/') for x in z.namelist()):raise ValueError('Website-Dateien oder Datenbank fehlen.')
    # Reserve the name synchronously before queuing; no existing site is touched.
    with db() as c:
        c.execute("INSERT INTO projects(slug,cms,php,status,created,db_password,db_root_password,version,storage,database_profile) VALUES(?,?,?,'preparing',?,?,?,?, 'shared','mariadb-11.4')",(name,info['cms'],info['php'],int(time.time()),secrets.token_urlsafe(24),secrets.token_urlsafe(24),info.get('version','')))
    def restore():
        p=project(name);root=op.folder(p);root.mkdir(parents=True,exist_ok=True)
        try:
            with zipfile.ZipFile(source) as z:z.extractall(root/'restore')
            (root/'restore/site').rename(root/'site')
            from project_files import prepare_local
            prepare_local(root/'site',root/'tools');op.write_tools(p)
            from compatibility import requirements
            from database_profiles import select,profile
            selected=select(requirements(root/'site',p['cms'],p.get('version','')))
            with db() as c:c.execute('UPDATE projects SET database_profile=? WHERE slug=?',(selected,name))
            p=project(name);ensure_database(p)
            _,args=context()
            from shared_runtime import database_info
            import tempfile
            info=database_info(p);client='mysql' if profile(p)['engine']=='mysql' else 'mariadb'
            # The dump receives this new project's restricted account, never a root account.
            with tempfile.TemporaryFile() as payload:
                payload.write((info['user']+'\n'+info['password']+'\n').encode())
                with (root/'restore/database.sql').open('rb') as sql:shutil.copyfileobj(sql,payload)
                payload.seek(0)
                script='IFS= read -r restore_user; IFS= read -r restore_password; exec '+client+' -u"$restore_user" -p"$restore_password" "$1"'
                op.command(args+['exec','-T',profile(p)['service'],'sh','-c',script,'restore',info['database']],stdin=payload,timeout=1800)
            # Rewrite only this new clone's database settings, using the same isolated config helper.
            helper=root/'tools/verification-config.php';shutil.copyfile(Path(__file__).parent/'tools/verification-config.php',helper)
            from shared_runtime import database_info
            info=database_info(p)
            from runtime import ports
            info['url']='http://'+name+'.vmm.test:'+str(ports(p['php'])[0])
            op.exec_php(p,['env','VMM_VERIFICATION=1','php','/vmm-tools/verification-config.php'],input=json.dumps(info).encode())
            if p['cms']=='wordpress':
                op.finalize_restore(name)
            shutil.rmtree(root/'restore');op.transition(name,'start')
            return 'Projektsicherung als '+name+' wiederhergestellt.'
        except Exception as e:
            with db() as c:c.execute("UPDATE projects SET status='error',error=? WHERE slug=?",(str(e),name))
            raise
    return {'slug':name,'job':job(name,'restore-export',restore)}
