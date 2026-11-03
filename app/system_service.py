"""Bounded diagnostics and lifecycle controls for manager-owned Docker services only."""
from config_env import config_env
import json,os,re,secrets,subprocess,threading,time
from pathlib import Path
from store import DATA,LOCK,db,job,redact,records
from storage_paths import AREAS

STATE=DATA/'service-check.json'
SHUTTING_DOWN=False

def docker(*args,timeout=15):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise ValueError(redact((result.stderr or result.stdout or 'Docker nicht erreichbar.').strip()))
    return result.stdout

def definitions():
    runtime=config_env('RUNTIME_PROJECT','tentacle-runtime')
    result={'gateway:traefik':('tentacle-gateway','traefik','Website-Gateway'),
            'gateway:dns':('tentacle-gateway','dns','Lokale Namensauflösung (DNS)')}
    path=DATA/'shared/compose.json'
    if path.is_file():
        config=json.loads(path.read_text());runtime=config.get('name','vmm-runtime')
        for name in config.get('services',{}):
            if not re.fullmatch(r'(?:php\d\d|phpmyadmin|db(?:-[a-z0-9-]+)?)',name):continue
            title='PHP '+name[3]+'.'+name[4] if re.fullmatch(r'php\d\d',name) else 'phpMyAdmin' if name=='phpmyadmin' else 'Datenbank · '+name
            result['runtime:'+name]=(runtime,name,title)
    return result

def containers():
    # Query labels, never arbitrary names supplied by the browser.
    values={}
    for key,(project,service,title) in definitions().items():
        values[(project,service)]=key
    lines=docker('ps','-a','--format','{{json .}}')
    result={}
    parsed=[json.loads(line) for line in lines.splitlines()]
    # Support older installers' Compose project name only when their gateway is on our network.
    legacy_gateway=any('vmm-gateway' in item.get('Networks','').split(',') and 'com.docker.compose.project=infra' in item.get('Labels','').split(',') and 'com.docker.compose.service=traefik' in item.get('Labels','').split(',') for item in parsed)
    if legacy_gateway:
        for service in ('traefik','dns'):values[('infra',service)]='gateway:'+service
    for item in parsed:
        labels=dict(x.split('=',1) for x in item.get('Labels','').split(',') if '=' in x)
        key=values.get((labels.get('com.docker.compose.project'),labels.get('com.docker.compose.service')))
        if not key:continue
        ident=item.get('ID','')
        if not re.fullmatch(r'[a-f0-9]{12,64}',ident):continue
        if key in result:raise ValueError('Mehrere Container für '+key+'. Bitte die Installation prüfen.')
        result[key]={'id':ident,'status':item.get('State','unknown'),'detail':item.get('Status','')}
    return result

def own_container():
    ident=os.environ.get('HOSTNAME','')
    if not re.fullmatch(r'[a-f0-9]{12,64}',ident):return None
    value=json.loads(docker('inspect',ident))[0]
    if value.get('Config',{}).get('Labels',{}).get('com.docker.compose.service')!='manager':return None
    # The current container must mount the same data and socket as this process.
    mounts={m.get('Destination') for m in value.get('Mounts',[])}
    return value['Id'] if '/data' in mounts and '/var/run/docker.sock' in mounts else None

def status():
    try:return json.loads(STATE.read_text())
    except (OSError,ValueError):return {'checked':None,'services':[],'permissions':[]}

def save(value):
    temp=STATE.with_suffix('.new');temp.write_text(json.dumps(value));temp.replace(STATE)

def check():
    value={'checked':int(time.time()),'services':[],'permissions':[]}
    permissions=value['permissions']
    try:
        docker('info','--format','{{.ServerVersion}}',timeout=8)
        permissions.append({'name':'Docker-Steuerung','status':'ok','detail':'Der Manager kann den Docker-Dienst über den eingebundenen Socket erreichen.'})
        items=containers()
        for key,(_,_,title) in definitions().items():
            item=items.get(key)
            value['services'].append({'key':key,'name':title,'status':item['status'] if item else 'missing','detail':item['detail'] if item else 'Noch kein Container vorhanden.','actions':['start','restart','stop'] if item else ['start'] if key.startswith('runtime:') else []})
        own=own_container()
        value['services'].insert(0,{'key':'manager','name':'Website Manager','status':'running','detail':'Die Oberfläche und ihre Schnittstelle antworten.','actions':['restart','stop'] if own else []})
        try:
            network=json.loads(docker('network','inspect','vmm-gateway'))[0]
            permissions.append({'name':'Internes Netzwerk','status':'ok' if network.get('Containers') else 'warning','detail':'Docker-Netzwerk vmm-gateway vorhanden.'})
        except Exception as e:permissions.append({'name':'Internes Netzwerk','status':'error','detail':redact(e)})
        # Check the actual PHP worker identity, without starting idle runtimes.
        projects=records('projects')
        for key,item in items.items():
            if not re.fullmatch(r'runtime:php\d\d',key) or item['status']!='running':continue
            names=[p['slug'] for p in projects if p.get('storage')=='shared' and 'runtime:php'+p['php'].replace('.','')==key and p['status']=='running']
            if not names:continue
            code='$bad=[];foreach(json_decode($argv[1],true) as $s){$p="/vmm-projects/".$s."/site";if(!is_readable($p)||!is_writable($p))$bad[]=$s;}echo json_encode($bad);'
            try:
                bad=json.loads(docker('exec','--user','www-data',item['id'],'php','-r',code,json.dumps(names),timeout=10))
                permissions.append({'name':'Website-Zugriff · '+key.split(':')[1],'status':'error' if bad else 'ok','detail':'Lesen/Schreiben als PHP-Benutzer nicht möglich: '+', '.join(bad) if bad else 'PHP-Benutzer kann die aktiven Projektordner lesen und beschreiben (Dateirechte geprüft).'})
            except Exception as e:permissions.append({'name':'Website-Zugriff · '+key.split(':')[1],'status':'error','detail':redact(e)})
    except Exception as e:
        permissions.append({'name':'Docker-Steuerung','status':'error','detail':redact(e)})
        value['services'].append({'key':'manager','name':'Website Manager','status':'running','detail':'Docker-Host nicht steuerbar. Docker Desktop bzw. Docker Engine am Rechner starten und die lokale Starten-Datei ausführen.','actions':[]})
    for key,title in {'data':'Manager-Daten',**AREAS}.items():
        path=DATA if key=='data' else DATA/key
        try:
            if not path.is_dir():raise ValueError('Speicherordner fehlt.')
            next(path.iterdir(),None)
            # A unique exclusive probe tests effective write access, not only mode bits.
            probe=path/('.vmm-access-'+secrets.token_hex(12))
            try:
                with probe.open('xb') as stream:stream.write(b'permission check\n')
                if probe.read_bytes()!=b'permission check\n':raise ValueError('Lesetest fehlgeschlagen.')
            finally:probe.unlink(missing_ok=True)
            permissions.append({'name':'Speicherzugriff · '+title,'status':'ok','detail':'Lesen, Schreiben und Entfernen einer temporären Prüfdatei erfolgreich.'})
        except Exception as e:permissions.append({'name':'Speicherzugriff · '+title,'status':'error','detail':redact(e)})
    try:integration=json.loads((DATA/'desktop-integration.json').read_text())
    except (OSError,ValueError):integration={}
    permissions.append({'name':'Finder / Explorer / Dateimanager','status':'unknown','detail':'Lokale Anbindung ist eingerichtet. Ihre Funktion und die Freigabe bitte mit „Ordnerfreigabe anfragen“ testen.' if integration.get('scheme')=='tentacle-project' else 'Noch nicht eingerichtet. Den Manager auf diesem Rechner einmal über die lokale Starten-Datei starten.'})
    value['desktop_registered']=integration.get('scheme')=='tentacle-project'
    value['desktop_platform']=integration.get('platform','')
    try:value['desktop_test']=json.loads((DATA/'desktop-access.json').read_text())
    except (OSError,ValueError):pass
    value['finished']=int(time.time());save(value)
    return 'Dienste und Zugriffsrechte geprüft. '+str(sum(p['status']=='error' for p in permissions))+' Problem(e) gefunden.'

def ensure_idle():
    import storage_service
    if storage_service.busy() or storage_service.ACTIVE_UPLOADS:raise ValueError('Bitte die laufende Dateiübertragung oder Speicherumstellung abwarten.')
    with db() as c:
        active=c.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running') AND resource!='system-services' LIMIT 1").fetchone()
    if active:raise ValueError('Bitte laufende Aufgaben zuerst abschließen oder beenden. Dienste werden gerade benötigt.')

def transition(key,action):
    if action not in ('start','restart','stop'):raise ValueError('Ungültige Dienstaktion.')
    ensure_idle()
    if key=='manager':raise ValueError('Manager-Aktion wird separat angefordert.')
    if key not in definitions():raise ValueError('Unbekannter Manager-Dienst.')
    item=containers().get(key)
    if not item:
        if not key.startswith('runtime:') or action!='start':raise ValueError('Diesen Dienst mit der lokalen Starten-Datei einrichten.')
        service=key.split(':')[1]
        from shared_operations import context
        op,args=context()
        if re.fullmatch(r'php\d\d',service):op.ensure_runtime(service[3]+'.'+service[4])
        op.command(args+['up','-d','--wait','--wait-timeout','180',service],timeout=1800)
    else:docker(action,*(['--time','20'] if action in ('stop','restart') else []),item['id'],timeout=60)
    check()
    return 'Dienst '+{'start':'gestartet','restart':'neu gestartet','stop':'beendet'}[action]+'.'

def request(body):
    global SHUTTING_DOWN
    if SHUTTING_DOWN:raise ValueError('Der Manager wird bereits beendet oder neu gestartet.')
    key=body.get('service');action=body.get('action')
    if not isinstance(key,str) or key not in {*definitions(),'manager'} or action not in ('start','restart','stop'):raise ValueError('Ungültige Dienstaktion.')
    if key!='manager':return {'job':job('system-services','service-control',lambda:transition(key,action))}
    if action not in ('restart','stop'):raise ValueError('Ungültige Manager-Aktion.')
    with LOCK:
        ensure_idle();ident=own_container()
        if not ident:raise ValueError('Eigener Manager-Container konnte nicht sicher erkannt werden.')
        with db() as c:c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),'system-services','service-control','done','Manager-'+('Neustart' if action=='restart' else 'Stopp')+' angefordert.',int(time.time()),int(time.time())))
        SHUTTING_DOWN=True
        def apply():
            global SHUTTING_DOWN
            time.sleep(2)
            try:docker(action,'--time','20',ident,timeout=60)
            except Exception as error:
                SHUTTING_DOWN=False
                value=status();value['action_error']=redact(error);save(value)
        threading.Thread(target=apply,daemon=True).start()
    return {'manager':action,'message':'Manager wird '+('neu gestartet.' if action=='restart' else 'beendet. Zum Starten die lokale Starten-Datei ausführen.')}
