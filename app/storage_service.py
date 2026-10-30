"""Storage settings and a separately supervised Docker migration."""
import json
import os
from pathlib import Path
import secrets
import shutil
import threading
import time
from storage_paths import AREAS,ENV_KEYS,host_location,settings,validate_paths
from store import DATA,LOCK,db

_USAGE={}
ACTIVE_UPLOADS=0


def migration_status():
    file=DATA/'storage/apply-status.json'
    try:return json.loads(file.read_text())
    except (OSError,ValueError):return None


def busy():
    state=migration_status()
    return bool(state and state.get('status') in ('queued','running') and time.time()-state.get('time',0)<7200)


def status():
    base=os.environ.get('VMM_HOST_DATA',str(DATA));saved=settings();areas=[]
    for key,label in AREAS.items():
        path=DATA/key;path.mkdir(exist_ok=True)
        cached=_USAGE.get(str(path))
        if not cached or time.time()-cached[0]>60:
            used=sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())
            cached=(time.time(),used);_USAGE[str(path)]=cached
        usage=shutil.disk_usage(path)
        areas.append({'key':key,'label':label,'path':saved.get(key,base.rstrip('/')+'/'+key),'default':base.rstrip('/')+'/'+key,'used':cached[1],'free':usage.free})
    return {'areas':areas,'migration':migration_status(),'database':'Datenbanken bleiben in ihren bisherigen Docker-Volumes. Zugangsdaten, Zertifikate und Manager-Metadaten bleiben im Manager-Datenordner.'}


def prepare(paths):
    import operations as op
    from runtime import host_path
    base=os.environ.get('VMM_HOST_DATA',str(DATA));current={key:settings().get(key,base.rstrip('/')+'/'+key) for key in AREAS}
    paths=validate_paths(paths,current,base)
    changed=[key for key in AREAS if host_path(paths[key])!=host_path(current[key])]
    if not changed:raise ValueError('Die Speicherorte sind unverändert.')
    own=json.loads(op.command(['docker','inspect',os.environ.get('HOSTNAME','')],timeout=20))[0]
    labels=own['Config']['Labels'];host_data=next(m['Source'] for m in own['Mounts'] if m['Destination']=='/data')
    root=labels.get('com.docker.compose.project.working_dir','')
    if not root or root=='/installation':root=host_data.rsplit('/',1)[0]
    current_volumes=[]
    for mount in own['Mounts']:
        current_volumes.append({'type':mount['Type'],'source':mount.get('Name') if mount['Type']=='volume' else mount['Source'],'target':mount['Destination'],'read_only':not mount['RW']})
    old_targets={m['target']:m for m in current_volumes}
    new_targets=dict(old_targets)
    for key in AREAS:new_targets['/data/'+key]={'type':'bind','source':host_path(paths[key]),'target':'/data/'+key}
    return {'id':secrets.token_hex(12),'paths':paths,'current':current,'changed':changed,'host_paths':{key:host_path(value) for key,value in paths.items()},'env_keys':ENV_KEYS,'compose_project':labels['com.docker.compose.project'],'host_data':host_data,'host_root':root,'image':own['Image'],'socket':next(m['Source'] for m in own['Mounts'] if m['Destination']=='/var/run/docker.sock'),'current_volumes':current_volumes,'new_volumes':list(new_targets.values())}


def helper_args(plan,mode):
    from runtime import host_path
    args=['docker','run','--rm']
    if mode=='apply':args+=['-d','--name','vmm-storage-'+plan['id'],'--label','vmm.manager.storage=true']
    args+=['--mount','type=bind,source='+plan['host_data']+',target=/vmm-data', '--mount','type=bind,source='+plan['host_root']+',target=/installation', '--mount','type=bind,source='+plan['socket']+',target=/var/run/docker.sock']
    for key in plan['changed']:
        # -v creates new host directories; the helper rejects nonempty destinations.
        args+=['-v',host_path(plan['current'][key])+':/sources/'+key+':ro','-v',plan['host_paths'][key]+':/targets/'+key]
    args+=[plan['image'],'python','/vmm-data/storage/jobs/'+plan['id']+'/worker.py',mode,'/vmm-data/storage/jobs/'+plan['id']+'/plan.json']
    return args


def stage(plan):
    root=DATA/'storage/jobs'/plan['id'];root.mkdir(parents=True)
    (root/'plan.json').write_text(json.dumps(plan));(root/'plan.json').chmod(0o600)
    shutil.copyfile(Path(__file__).with_name('storage_worker.py'),root/'worker.py')
    return root


def check(paths):
    import operations as op
    if busy():raise ValueError('Eine Speicherort-Umstellung läuft bereits.')
    plan=prepare(paths);stage(plan)
    result=json.loads(op.command(helper_args(plan,'probe'),timeout=180))
    return {**result,'paths':plan['paths'],'message':'Zielordner sind leer, beschreibbar und haben ausreichend freien Speicher.'}


def start(paths):
    import operations as op
    with LOCK:
        if busy():raise ValueError('Eine Speicherort-Umstellung läuft bereits.')
        if ACTIVE_UPLOADS:raise ValueError('Laufende Datei-Uploads zuerst abschließen lassen.')
        with db() as c:
            if c.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running')").fetchone():raise ValueError('Alle laufenden Vorgänge zuerst abschließen lassen.')
        plan=prepare(paths);stage(plan)
        # Probe again to catch changes since the user's preliminary check.
        op.command(helper_args(plan,'probe'),timeout=180)
        now=int(time.time())
        with db() as c:c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,NULL)',(plan['id'],'storage-settings','storage-migrate','queued','Speicherorte werden vorbereitet …',now))
        state={'id':plan['id'],'status':'queued','message':'Speicherorte werden vorbereitet …','time':now}
        (DATA/'storage/apply-status.json').write_text(json.dumps(state))
        try:op.command(helper_args(plan,'apply'),timeout=30)
        except Exception:
            state.update(status='error',message='Umstellungshelfer konnte nicht gestartet werden.')
            (DATA/'storage/apply-status.json').write_text(json.dumps(state))
            with db() as c:c.execute("UPDATE jobs SET status='error',message=?,finished=? WHERE id=?",(state['message'],int(time.time()),plan['id']))
            raise
        return {'job':plan['id'],'message':'Die Speicherorte werden umgestellt. Der Manager verbindet sich nach dem Neustart automatisch wieder.'}
