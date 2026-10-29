"""Provision CMS projects and manage accounts through native CMS APIs."""
import json,re,secrets,shutil,time
from store import DATA,db,project
import operations as op
from shared_runtime import database_info


def admin_settings(body):
    value={k:str(body.get(k,'')).strip() for k in ('username','email','name')};value['password']=body.get('password','')
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{2,80}',value['username']):raise ValueError('Benutzername: 2–80 Zeichen, Buchstaben, Zahlen oder . _ @ - verwenden.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value['email']):raise ValueError('Gültige E-Mail-Adresse angeben.')
    if not isinstance(value['password'],str) or not 12<=len(value['password'])<=256:raise ValueError('Passwort mit mindestens 12 Zeichen angeben.')
    value['name']=value['name'] or value['username']
    return value


def provision(name,admin=None):
    op.transition(name,'start');p=project(name);site=op.folder(p)/'site'
    if not admin:return 'Projekt eingerichtet und erreichbar.'
    if p['cms']=='wordpress':
        # wp --prompt keeps credentials off process arguments.
        op.exec_php(p,['wp','--allow-root','core','install','--url=http://'+name+'.vmm.test:'+str(op.ports(p['php'])[0]),'--title='+name,'--admin_user='+admin['username'],'--admin_email='+admin['email'],'--skip-email','--prompt=admin_password'],input=(admin['password']+'\n').encode(),timeout=300)
    else:
        config=database_info(p)
        payload={'site_name':name,'admin_user':admin['name'],'admin_username':admin['username'],'admin_password':admin['password'],'admin_email':admin['email'],'db_type':'mysqli','db_host':config['host'],'db_user':config['user'],'db_pass':config['password'],'db_name':config['database'],'db_prefix':'cms_'}
        # Native installer launched inside PHP; passwords are read from stdin.
        script='$v=json_decode(stream_get_contents(STDIN),true);$a=["installation/joomla.php","install","--no-interaction"];foreach($v as $k=>$x)$a[]="--".str_replace("_","-",$k)."=".$x;$_SERVER["argv"]=$a;$argv=$a;require "installation/joomla.php";'
        op.exec_php(p,['php','-r',script],input=json.dumps(payload).encode(),timeout=300)
    from credentials import change
    change(name,{'label':'CMS Administrator','username':admin['username'],'password':admin['password'],'url':'http://'+name+'.vmm.test:'+str(op.ports(p['php'])[0])+('/administrator/' if p['cms']=='joomla' else '/wp-admin/'),'note':admin['email']})
    from extension_service import process_pending
    return 'CMS und Administratorkonto eingerichtet. '+process_pending(name)


def user_action(name,body):
    p=project(name)
    if body.get('action') not in ('list','create','reset'):raise ValueError('Unbekannte Benutzeraktion.')
    op.write_tools(p)
    if p['cms']=='wordpress':
        if body['action']=='list':return json.loads(op.exec_php(p,['wp','--allow-root','user','list','--fields=ID,user_login,user_email,display_name,roles','--format=json']))
        values=admin_settings(body)
        role=body.get('role','editor')
        if role not in ('administrator','editor','author','subscriber'):raise ValueError('Ungültige Rolle.')
        if body['action']=='create':args=['user','create',values['username'],values['email'],'--display_name='+values['name'],'--role='+role,'--prompt=user_pass']
        else:args=['user','update',str(int(body['id'])),'--prompt=user_pass']
        op.exec_php(p,['wp','--allow-root',*args],input=(values['password']+'\n').encode())
    else:
        values=admin_settings(body) if body['action']!='list' else {}
        payload={**values,**body}
        result=op.exec_php(p,['php','/vmm-tools/cms-users.php'],input=json.dumps(payload).encode())
        if body['action']=='list':return json.loads(result)
    from credentials import change,listing
    existing=next((entry for entry in listing(name) if entry.get('username')==values['username'] and not entry.get('archived')),None)
    change(name,{'id':existing['id'] if existing else None,'label':existing['label'] if existing else 'CMS Benutzer · '+values['username'],'username':values['username'],'password':values['password'],'note':values['email'],'url':'http://'+name+'.vmm.test:'+str(op.ports(p['php'])[0])+('/administrator/' if p['cms']=='joomla' else '/wp-admin/')})
    return {'ok':True}


def delete_project(name):
    """Recoverable deletion: site, SQL and metadata go to a local trash folder."""
    p=project(name)
    if p['storage']!='shared':raise ValueError('Ältere Volume-Projekte zuerst auf gemeinsame Laufzeiten umstellen.')
    from shared_operations import context,LOCK
    from database_profiles import profile,sql_command
    # Serialize against shared stack reconfiguration and preserve rollback material.
    with LOCK:
        archive=DATA/'trash'/(name+'-'+str(int(time.time()))+'-'+secrets.token_hex(3));archive.mkdir(parents=True)
        archive.chmod(0o700)
        _,args=context();info=database_info(p)
        flag=DATA/'shared/state'/(name+'.enabled');enabled=flag.exists();flag.unlink(missing_ok=True)
        moved=False;meta=None
        try:
            # Stopped / never provisioned projects may not have a database yet.
            op.command(args+['up','-d','--wait','--wait-timeout','180',profile(p)['service']],timeout=300)
            exists=op.command(args+sql_command(p,extra=['-N']),input=("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='"+info['database']+"';").encode()).decode().strip()
            if exists:
                dump=op.command(args+sql_command(p,dump=True,database=True),timeout=300)
                (archive/'database.sql').write_bytes(dump);(archive/'database.sql').chmod(0o600)
            with db() as c:
                meta={'project':dict(p),'database_exists':bool(exists),'credentials':[dict(r) for r in c.execute('SELECT * FROM credentials WHERE project=?',(name,))],'plans':[dict(r) for r in c.execute('SELECT * FROM extension_plans WHERE project=?',(name,))],'assignments':[dict(r) for r in c.execute('SELECT * FROM project_extensions WHERE project=?',(name,))]}
            (archive/'metadata.json').write_text(json.dumps(meta));(archive/'metadata.json').chmod(0o600)
            if op.folder(p).exists():shutil.move(str(op.folder(p)),str(archive/'project'));moved=True
            with db() as c:
                for table in ('credentials','extension_plans','project_extensions'):c.execute('DELETE FROM '+table+' WHERE project=?',(name,))
                c.execute('DELETE FROM projects WHERE slug=?',(name,))
            context()
        except Exception:
            if moved:shutil.move(str(archive/'project'),str(op.folder(p)))
            if meta:
                with db() as c:
                    c.execute('INSERT OR REPLACE INTO projects ('+','.join(p)+') VALUES ('+','.join('?' for _ in p)+')',tuple(p.values()))
                    for table,key in (('credentials','credentials'),('extension_plans','plans'),('project_extensions','assignments')):
                        for row in meta[key]:c.execute('INSERT OR REPLACE INTO '+table+' ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
            if enabled:flag.write_text('enabled\n')
            context()
            # Failed trash attempts must not reserve the still-existing project name.
            if (archive/'metadata.json').exists():(archive/'metadata.json').rename(archive/'failed-metadata.json')
            raise
        # Reload only active workers; an offline worker reads the new config on start.
        try:
            from shared_operations import sync
            sync()
        except Exception:pass
        return 'Projekt gelöscht. Dateien und Metadaten liegen im lokalen Papierkorb: '+archive.name+'. Vorhandene Datenbank wurde gesichert und zur Wiederherstellung aufbewahrt.'


def scan_licenses(name):
    p=project(name);op.write_tools(p)
    if p['cms']=='joomla':
        raw=json.loads(op.exec_php(p,['php','/vmm-tools/extension-bridge.php','license-scan']))
    else:
        code="""$out=[];foreach(get_option('vmm_extension_sources',[]) as $v){$s=$v['source'];$k=$v['credentials']['key']??'';if($k)$out[]=['element'=>$s['element'],'label'=>$s['name'],'key'=>$k,'url'=>$s['url']??''];} foreach(['yootheme_apikey','yootheme_api_key'] as $n){$k=get_option($n,'');if(is_string($k)&&$k)$out[]=['element'=>'yootheme','label'=>'YOOtheme','key'=>$k,'url'=>''];} echo json_encode($out);"""
        raw=json.loads(op.exec_php(p,['wp','--allow-root','eval',code]))
    from extension_service import sources
    result=[];seen=set()
    for item in raw:
        normalize=lambda value:re.sub(r'^(?:pkg_|com_|plg_)','',value.lower())
        match=next((s for s in sources() if s['cms']==p['cms'] and normalize(s['element'])==normalize(item['element'])),None)
        if not match:continue
        marker=(match['id'],item['key'])
        if marker in seen:continue
        seen.add(marker);result.append({'label':match['name'],'source':match['id'],'provider':match['provider'],'key':item['key']})
    return {'candidates':result}


def import_license(name,body):
    from extension_service import save_license,licenses,source
    candidate=body['candidate'];valid=next((c for c in scan_licenses(name)['candidates'] if c['source']==candidate.get('source') and c['key']==candidate.get('key')),None)
    if not valid:raise ValueError('Schlüssel wurde im CMS nicht mehr gefunden. Erneut auslesen.')
    parent=body.get('parent','')
    if not parent:
        roots=[l for l in licenses() if not l.get('parent') and not l.get('project') and l['provider']==valid['provider']]
        if len(roots)==1:parent=roots[0]['id']
        elif len(roots)>1:raise ValueError('Bitte die passende Hauptlizenz bzw. Kundenlizenz auswählen.')
    if not parent:parent=save_license({'label':valid['label']+' · importierte Hauptlizenz','provider':valid['provider'],'owner':'Aus Backup übernommen'})
    existing=next((l for l in licenses() if l.get('project')==name and l.get('source')==valid['source'] and l.get('parent')==parent),None)
    ident=save_license({'id':existing['id'] if existing else None,'label':valid['label']+' · '+name,'provider':valid['provider'],'parent':parent,'project':name,'source':valid['source'],'key':valid['key']})
    return {'id':ident}
