"""GitHub release checks and supervised Docker self-updates."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile
from store import DATA, db, LOCK

RELEASE=json.loads((Path(__file__).parent/'release.json').read_text())
REPOSITORY=RELEASE['repository']
STATE=DATA/'updates/status.json'
UPDATE_LOCK=threading.RLock()
INSTALL_LOCK=threading.Lock()


def version(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',str(value))
    if not match:raise ValueError('Ungültige Release-Version.')
    return tuple(map(int,match.groups()))


def fetch(url,limit=64*1024*1024):
    from urllib.parse import urlparse
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in ('api.github.com','github.com'):raise ValueError('Ungültige GitHub-Updatequelle.')
    with urlopen(Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'Tentacle-Website-Manager'}),timeout=60) as response:
        if urlparse(response.url).scheme!='https':raise ValueError('Unsichere Downloadumleitung.')
        data=response.read(limit+1)
    if len(data)>limit:raise ValueError('Updatepaket überschreitet die maximale Größe.')
    return data


def save(value):
    STATE.parent.mkdir(exist_ok=True);temporary=STATE.with_suffix('.new');temporary.write_text(json.dumps(value));temporary.replace(STATE)


def installation_status():
    file=DATA/'updates/apply-status.json'
    try:value=json.loads(file.read_text())
    except (OSError,ValueError):return None
    ident=value.get('id','')
    # Older update workers did not persist the identifier in their status file.
    if not re.fullmatch(r'[a-f0-9]{16}',ident):
        candidates=[p for pattern in ('*/update.log','*/apply.py') for p in file.parent.glob(pattern) if re.fullmatch(r'[a-f0-9]{16}',p.parent.name)]
        ident=max(candidates,key=lambda p:p.stat().st_mtime).parent.name if candidates else ''
    from store import redact
    if ident:
        value['id']=ident
        if 'time' not in value:value['time']=int((DATA/'updates'/ident).stat().st_mtime)
        log=DATA/'updates'/ident/'update.log'
        if log.is_file():
            with log.open('rb') as stream:
                stream.seek(max(0,log.stat().st_size-16000));value['log']=redact(stream.read().decode(errors='replace'))
    if value.get('status') in ('queued','running'):
        value['waiting']=time.time()-value.get('time',time.time())>90
    return value


def diagnostics():
    value=status();installation=value.get('installation') or {};ident=installation.get('id','')
    if not re.fullmatch(r'[a-f0-9]{16}',ident):
        return {**value,'diagnostics':'Noch kein Updatehelfer vorhanden. Prüfe Activity Log für Download- oder Startfehler.'}
    import operations as op
    from store import redact
    try:
        container=json.loads(op.command(['docker','inspect','vmm-update-'+ident],timeout=5))[0]
        state=container['State'];text='Updatehelfer: '+str(state.get('Status','unbekannt'))+' · Exit-Code: '+str(state.get('ExitCode','?'))
        import subprocess
        logs=subprocess.run(['docker','logs','--tail','100','vmm-update-'+ident],capture_output=True,timeout=5)
        text+='\n'+(logs.stdout+logs.stderr).decode(errors='replace')
        installation=installation_status() or installation
        if state.get('Status') in ('exited','dead') and installation.get('status') in ('queued','running'):
            installation.pop('log',None);installation.pop('waiting',None)
            installation.update(status='error',message='Der Updatehelfer wurde beendet. Details stehen in der Diagnose.',diagnostics=redact(text),time=int(time.time()))
            file=DATA/'updates/apply-status.json';temp=file.with_suffix('.diagnostic-new');temp.write_text(json.dumps(installation));temp.replace(file)
            with db() as c:
                c.execute("UPDATE jobs SET status='error',message=?,finished=? WHERE resource='manager-update' AND kind='manager-install' AND status IN ('queued','running')",(installation['message'],int(time.time())))
            value=status()
        return {**value,'diagnostics':redact(text)}
    except Exception as e:return {**value,'diagnostics':'Updatehelfer konnte nicht abgefragt werden: '+redact(str(e))}


def progress(ident,expected,message,phase,**extra):
    with UPDATE_LOCK:
        file=DATA/'updates/apply-status.json';file.parent.mkdir(exist_ok=True)
        value={'id':ident,'version':expected,'status':'running','message':message,'phase':phase,'time':int(time.time()),**extra}
        temp=file.with_suffix('.new');temp.write_text(json.dumps(value));temp.replace(file)
    return value


def status():
    with UPDATE_LOCK:
        try:saved=json.loads(STATE.read_text())
        except (OSError,ValueError):saved={}
        installation=installation_status()
        if installation:saved['installation']=installation
        return {**saved,'current':RELEASE['version'],'repository':REPOSITORY,'source':'https://github.com/'+REPOSITORY+'/releases','available':bool(saved.get('latest') and version(saved['latest'])>version(RELEASE['version']))}


def check():
    old=status()
    try:
        release=json.loads(fetch('https://api.github.com/repos/'+REPOSITORY+'/releases/latest',2*1024*1024))
        if release.get('draft') or release.get('prerelease'):raise ValueError('Kein stabiles Release.')
        latest=release['tag_name'].removeprefix('v');version(latest)
        assets={a['name']:a['browser_download_url'] for a in release.get('assets',[])}
        for name in ('manager-update.zip','manager-update.zip.sha256'):
            expected='https://github.com/'+REPOSITORY+'/releases/download/'+release['tag_name']+'/'+name
            if assets.get(name)!=expected:raise ValueError('Release enthält kein vollständiges Manager-Updatepaket.')
        value={'latest':latest,'checked':int(time.time()),'error':None,'assets':assets}
    except Exception as e:
        value={k:v for k,v in old.items() if k in ('latest','assets')}
        value.update(checked=int(time.time()),error=('Noch kein öffentliches Release vorhanden.' if isinstance(e,HTTPError) and e.code==404 else str(e)))
        value.pop('assets',None)
    with UPDATE_LOCK:save(value)
    return status()


def check_message():
    value=check()
    if value.get('error'):return value['error']
    return 'Manager-Update '+value['latest']+' verfügbar.' if value['available'] else 'Der Manager ist aktuell.'


def allowed(name):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or any(p.startswith('.') and p not in ('.dockerignore',) for p in path.parts):return False
    return name in ('Dockerfile','compose.yaml','requirements.txt','.dockerignore','scripts/setup.py','scripts/installer_config.py') or (len(path.parts)>1 and path.parts[0]=='app' and '__pycache__' not in path.parts) or (name.startswith('infra/runtime/') and len(path.parts)>2)


def validate_bundle(content,expected):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        seen=set();total=0
        for item in archive.infolist():
            if item.is_dir():continue
            if not allowed(item.filename) or item.filename in seen or stat.S_ISLNK(item.external_attr>>16):raise ValueError('Updatepaket enthält einen unzulässigen Dateipfad.')
            total+=item.file_size;seen.add(item.filename)
            if total>128*1024*1024:raise ValueError('Entpacktes Updatepaket ist zu groß.')
        for name in ('app/server.py','app/release.json','Dockerfile','compose.yaml','scripts/setup.py'):
            if name not in seen:raise ValueError('Updatepaket ist unvollständig: '+name)
        metadata=json.loads(archive.read('app/release.json'))
        if metadata.get('repository')!=REPOSITORY or version(metadata.get('version'))!=version(expected):raise ValueError('Updatepaket gehört nicht zu diesem Release.')


def install(expected):
    with INSTALL_LOCK:
        previous=installation_status()
        if previous and previous.get("status") in ("queued","running"):raise ValueError("Manager-Update läuft bereits.")
        ident=secrets.token_hex(8)
        progress(ident,expected,"Updatequelle wird geprüft …","check")
        try:
            return prepare_install(expected,ident)
        except Exception as e:
            progress(ident,expected,str(e),"error",status="error")
            raise


def installation_host_paths(own):
    from runtime import host_path
    raw=next(m['Source'] for m in own['Mounts'] if m['Destination']=='/data')
    data=host_path(raw)
    if PurePosixPath(data).name!='data':raise ValueError('Manager-Updates benötigen den Datenordner data innerhalb der Installation.')
    return data,str(PurePosixPath(data).parent)


def prepare_install(expected,ident):
    import operations as op
    # A fresh check prevents installing an unexpected version from a stale UI.
    value=check()
    if value.get('error') or not value.get('assets'):raise ValueError(value.get('error') or 'Kein Updatepaket vorhanden.')
    if not value['available'] or expected!=value['latest']:raise ValueError('Updateanzeige hat sich geändert. Erneut prüfen.')
    with db() as c:
        if c.execute("SELECT 1 FROM jobs WHERE status IN ('running','queued') AND resource!='manager-update'").fetchone():raise ValueError('Laufende Vorgänge zuerst abschließen lassen.')
    progress(ident,expected,'Prüfsumme wird heruntergeladen …','checksum')
    checksum=fetch(value['assets']['manager-update.zip.sha256'],4096).decode().split()[0]
    if not re.fullmatch(r'[a-fA-F0-9]{64}',checksum):raise ValueError('Ungültige Release-Prüfsumme.')
    progress(ident,expected,'Updatepaket wird heruntergeladen …','download')
    content=fetch(value['assets']['manager-update.zip'])
    progress(ident,expected,'Prüfsumme und Paketinhalt werden geprüft …','validate')
    if hashlib.sha256(content).hexdigest()!=checksum.lower():raise ValueError('Prüfsumme des Updatepakets stimmt nicht.')
    validate_bundle(content,expected)
    stage=DATA/'updates'/ident;stage.mkdir()
    (stage/'manager-update.zip').write_bytes(content)
    shutil.copyfile(Path(__file__).parent/'update_worker.py',stage/'apply.py')
    # Identify this Compose installation rather than deriving a project name.
    hostname=os.environ.get('HOSTNAME','')
    own=json.loads(op.command(['docker','inspect',hostname]))[0]
    labels=own['Config']['Labels'];compose_project=labels['com.docker.compose.project']
    host_data,host_root=installation_host_paths(own)
    docker_socket=next(m['Source'] for m in own['Mounts'] if m['Destination']=='/var/run/docker.sock')
    image=own['Image']
    with db() as c:
        row=c.execute("SELECT id FROM jobs WHERE resource='manager-update' AND kind='manager-install' AND status IN ('queued','running') ORDER BY created DESC LIMIT 1").fetchone()
    progress(ident,expected,'Installationsordner für den Updatehelfer wird geprüft …','mount-check',job=row['id'] if row else None)
    probe="from pathlib import Path; root=Path('/installation'); required=['compose.yaml','data/updates/"+ident+"/apply.py','data/updates/"+ident+"/manager-update.zip']; missing=[p for p in required if not (root/p).is_file()]; assert not missing, 'Installationsordner falsch eingebunden; fehlend: '+', '.join(missing)"
    op.command(['docker','run','--rm','--mount','type=bind,source='+host_root+',target=/installation,readonly',image,'python','-c',probe],timeout=30)
    progress(ident,expected,'Separater Updatehelfer wird gestartet …','launch',job=row['id'] if row else None)
    op.command(['docker','run','-d','--name','vmm-update-'+ident,'--label','vmm.manager.update=true',
            '--mount','type=bind,source='+host_root+',target=/installation',
            '--mount','type=bind,source='+docker_socket+',target=/var/run/docker.sock',
            '-e','VMM_UPDATE_SOCKET='+docker_socket,'-e','VMM_UPDATE_PROJECT='+compose_project,'-e','VMM_UPDATE_HOST_DATA='+host_data,
            '-w','/installation',image,'python','/installation/data/updates/'+ident+'/apply.py',ident],timeout=30)
    return 'Update gestartet. Der Manager startet neu; diese Seite verbindet sich automatisch wieder.'

def monitor():
    next_check=0
    while True:
        try:
            if time.time()>=next_check:
                check();next_check=time.time()+6*60*60
            state=installation_status() or {}
            if state.get('status') in ('queued','running') and state.get('phase') in (None,'launch','worker') and time.time()-state.get('time',time.time())>10:
                diagnostics()
        except Exception:pass
        time.sleep(5)
