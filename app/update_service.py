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


def status():
    with UPDATE_LOCK:
        saved=json.loads(STATE.read_text()) if STATE.is_file() else {}
        helper=DATA/'updates/apply-status.json'
        if helper.is_file():saved['installation']=json.loads(helper.read_text())
        return {**saved,'current':RELEASE['version'],'repository':REPOSITORY,'source':'https://github.com/'+REPOSITORY+'/releases','available':bool(saved.get('latest') and version(saved['latest'])>version(RELEASE['version']))}


def check():
    with UPDATE_LOCK:
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
            # Never offer a stale artifact after a failed refresh.
            value.pop('assets',None)
        save(value);return status()


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
    import operations as op
    with UPDATE_LOCK,LOCK:
        # A fresh check prevents installing an unexpected version from a stale UI.
        value=check()
        if value.get('error') or not value.get('assets'):raise ValueError(value.get('error') or 'Kein Updatepaket vorhanden.')
        if not value['available'] or expected!=value['latest']:raise ValueError('Updateanzeige hat sich geändert. Erneut prüfen.')
        with db() as c:
            if c.execute("SELECT 1 FROM jobs WHERE status IN ('running','queued') AND resource!='manager-update'").fetchone():raise ValueError('Laufende Vorgänge zuerst abschließen lassen.')
        helper=DATA/'updates/apply-status.json'
        if helper.is_file() and json.loads(helper.read_text()).get('status') in ('queued','running'):raise ValueError('Manager-Update läuft bereits.')
        checksum=fetch(value['assets']['manager-update.zip.sha256'],4096).decode().split()[0]
        if not re.fullmatch(r'[a-fA-F0-9]{64}',checksum):raise ValueError('Ungültige Release-Prüfsumme.')
        content=fetch(value['assets']['manager-update.zip'])
        if hashlib.sha256(content).hexdigest()!=checksum.lower():raise ValueError('Prüfsumme des Updatepakets stimmt nicht.')
        validate_bundle(content,expected)
        ident=secrets.token_hex(8);stage=DATA/'updates'/ident;stage.mkdir()
        (stage/'manager-update.zip').write_bytes(content)
        shutil.copyfile(Path(__file__).parent/'update_worker.py',stage/'apply.py')
        # Identify this Compose installation rather than deriving a project name.
        hostname=os.environ.get('HOSTNAME','')
        own=json.loads(op.command(['docker','inspect',hostname]))[0]
        labels=own['Config']['Labels'];compose_project=labels['com.docker.compose.project']
        host_data=next(m['Source'] for m in own['Mounts'] if m['Destination']=='/data')
        host_root=host_data.rsplit('/',1)[0]
        docker_socket=next(m['Source'] for m in own['Mounts'] if m['Destination']=='/var/run/docker.sock')
        image=own['Image']
        helper.write_text(json.dumps({'status':'queued','version':expected,'message':'Update wird vorbereitet.'}))
        try:
            op.command(['docker','run','-d','--name','vmm-update-'+ident,'--label','vmm.manager.update=true',
                '--mount','type=bind,source='+host_root+',target=/installation',
                '--mount','type=bind,source='+docker_socket+',target=/var/run/docker.sock',
                '-e','VMM_UPDATE_SOCKET='+docker_socket,'-e','VMM_UPDATE_PROJECT='+compose_project,'-e','VMM_UPDATE_HOST_DATA='+host_data,
                '-w','/installation',image,'python','/installation/data/updates/'+ident+'/apply.py',ident],timeout=30)
        except Exception:
            helper.write_text(json.dumps({'status':'error','version':expected,'message':'Updatehelfer konnte nicht gestartet werden.'}));raise
        return 'Update gestartet. Der Manager startet neu; diese Seite verbindet sich automatisch wieder.'


def monitor():
    while True:
        try:check()
        except Exception:pass
        time.sleep(6*60*60)
