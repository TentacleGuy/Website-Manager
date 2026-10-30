"""Standalone migration helper; does not import store or initialise application state."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.new');temp.write_text(value);temp.chmod(0o600);temp.replace(path)


def inventory(root):
    found={}
    if not root.exists():return found
    for path in root.rglob('*'):
        relative=path.relative_to(root).as_posix()
        if path.is_symlink():
            target=path.resolve()
            if root.resolve() not in target.parents:raise ValueError('Externe symbolische Verknüpfung im Quellordner: '+relative)
            if os.path.isabs(os.readlink(path)):raise ValueError('Absolute symbolische Verknüpfung kann nicht sicher umgezogen werden: '+relative)
            found[relative]=('link',os.readlink(path))
        elif path.is_dir():found[relative]=('directory',)
        elif path.is_file():
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            found[relative]=('file',path.stat().st_size,digest.hexdigest())
        else:raise ValueError('Nicht unterstützter Dateityp im Quellordner: '+relative)
    return found


def probe(plan):
    result=[];requirements={}
    for key in plan['changed']:
        source=Path('/sources')/key;target=Path('/targets')/key
        if target.is_symlink() or not target.is_dir():raise ValueError(key+': Ziel ist kein regulärer Ordner.')
        if any(target.iterdir()):raise ValueError(key+': Der Zielordner muss leer sein.')
        size=sum(p.stat().st_size for p in source.rglob('*') if p.is_file() and not p.is_symlink()) if source.exists() else 0
        free=shutil.disk_usage(target).free
        if free<size+max(64*1024*1024,size//20):raise ValueError(key+': Zu wenig freier Speicher für Kopie und Reserve.')
        device=target.stat().st_dev
        previous=requirements.get(device,(0,free))
        requirements[device]=(previous[0]+size,min(previous[1],free))
        test=target/('.vmm-write-test-'+plan['id'])
        try:test.write_bytes(b'vmm');test.unlink()
        except OSError:raise ValueError(key+': Zielordner ist nicht beschreibbar.') from None
        result.append({'key':key,'bytes':size,'free':free,'writable':True})
    for size,free in requirements.values():
        if free<size+max(64*1024*1024,size//20):raise ValueError('Zu wenig gemeinsamer freier Speicher für alle ausgewählten Bereiche.')
    return result


def env_paths(text,paths,env_keys):
    lines=text.splitlines()
    for key,value in paths.items():
        variable=env_keys[key];line=variable+"='"+value+"'"
        indexes=[i for i,x in enumerate(lines) if x.startswith(variable+'=')]
        if indexes:
            lines[indexes[0]]=line
            for i in reversed(indexes[1:]):lines.pop(i)
        else:lines.append(line)
    return '\n'.join(lines)+'\n'


def canonical_host(value):
    value=value.replace('\\','/').rstrip('/')
    if len(value)>2 and value[1:3]==':/':value='/'+value[0].lower()+value[2:]
    for prefix in ('/host_mnt','/run/desktop/mnt/host'):
        if value.startswith(prefix+'/'):value=value[len(prefix):]
    return value


def verify_runtime_owner(containers,project_root):
    expected=canonical_host(project_root)
    for container in containers:
        mount=next((m for m in container.get('Mounts',[]) if m.get('Destination')=='/vmm-projects'),None)
        if not mount or canonical_host(mount['Source'])!=expected:
            raise ValueError('PHP-Laufzeiten gehören zu einer anderen Installation. Die Speicherort-Umstellung wurde vor dem Anhalten abgebrochen.')


def apply(plan):
    data=Path('/vmm-data');root=Path('/installation');stage=data/'storage/jobs'/plan['id']
    status=data/'storage/apply-status.json';saved=data/'storage/settings.json';override=data/'storage/compose.storage.json'
    def report(state,message):
        atomic(status,json.dumps({'id':plan['id'],'status':state,'message':message,'time':int(time.time())}))
        try:
            with sqlite3.connect(data/'manager.sqlite',timeout=30) as c:
                c.execute('UPDATE jobs SET status=?,message=?,finished=? WHERE id=?',(state,message,int(time.time()) if state in ('done','error') else None,plan['id']))
        except sqlite3.Error:pass
    def command(args):
        result=subprocess.run(args,cwd=root,capture_output=True,timeout=3600)
        with (stage/'migration.log').open('ab') as log:log.write(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Docker-Schritt fehlgeschlagen. Details: storage/jobs/'+plan['id']+'/migration.log')
        return result.stdout
    compose=['docker','compose','-p',plan['compose_project'],'-f',str(root/'compose.yaml'),'-f',str(override)]
    # This override is also used for recovery, before any settings are changed.
    previous_override=override.read_bytes() if override.exists() else None
    previous_settings=saved.read_bytes() if saved.exists() else None
    previous_env=(root/'.env').read_bytes()
    shared=data/'shared/compose.json';previous_shared=shared.read_bytes() if shared.exists() else None
    php=[];php_stopped=False;stopped=False
    try:
        report('running','Zielordner und freien Speicher prüfen …');probe(plan)
        recovery={'services':{'manager':{'volumes':plan['current_volumes']}}}
        atomic(override,json.dumps(recovery))
        if shared.exists() and set(plan['changed']) & {'projects','extensions','backups'}:
            output=command(['docker','compose','-f',str(shared),'--profile','*','ps','--services','--status','running']).decode()
            php=[s for s in output.splitlines() if re.fullmatch(r'php\d\d',s)]
            if php:
                ids=command(['docker','compose','-f',str(shared),'--profile','*','ps','-q',*php]).decode().split()
                containers=json.loads(command(['docker','inspect',*ids])) if ids else []
                if len(containers)!=len(php):raise ValueError('PHP-Laufzeiten konnten nicht eindeutig geprüft werden.')
                verify_runtime_owner(containers,plan['current']['projects'])
                command(['docker','compose','-f',str(shared),'stop',*php]);php_stopped=True
        command(compose+['stop','manager']);stopped=True
        report('running','Daten kopieren und mit Prüfsummen vergleichen …')
        for key in plan['changed']:
            source=Path('/sources')/key;target=Path('/targets')/key
            expected=inventory(source)
            shutil.copytree(source,target,symlinks=True,dirs_exist_ok=True)
            if inventory(target)!=expected or inventory(source)!=expected:raise ValueError(key+': Die Kopie stimmt nicht vollständig mit dem Original überein.')
        # Commit only after every area has passed verification.
        atomic(saved,json.dumps(plan['paths'],indent=2))
        atomic(root/'.env',env_paths(previous_env.decode(),plan['paths'],plan['env_keys']))
        atomic(override,json.dumps({'services':{'manager':{'volumes':plan['new_volumes']}}},indent=2))
        if shared.exists():
            value=json.loads(shared.read_text())
            for service in value['services'].values():
                mounts=[]
                for mount in service.get('volumes',[]):
                    if isinstance(mount,str) and ':/vmm-projects' in mount:mount=plan['host_paths']['projects']+mount[mount.index(':/vmm-projects'):]
                    elif isinstance(mount,str) and ':/vmm-extensions' in mount:mount=plan['host_paths']['extensions']+mount[mount.index(':/vmm-extensions'):]
                    elif isinstance(mount,str) and ':/vmm-backups' in mount:mount=plan['host_paths']['backups']+mount[mount.index(':/vmm-backups'):]
                    mounts.append(mount)
                service['volumes']=mounts
            atomic(shared,json.dumps(value,indent=2))
        report('running','Geprüfte Speicherorte aktivieren und Laufzeiten starten …')
        if php:command(['docker','compose','-f',str(shared),'--profile','*','up','-d','--no-deps',*php])
        command(compose+['up','-d','--no-deps','--no-build','manager'])
        container=command(compose+['ps','-q','manager']).decode().strip()
        healthy=False
        for _ in range(30):
            response=subprocess.run(['docker','exec',container,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/api/jobs',timeout=3)"],capture_output=True)
            if response.returncode==0:healthy=True;break
            time.sleep(2)
        if not healthy:raise RuntimeError('Der Manager antwortet nach der Umstellung nicht.')
        report('done','Speicherorte umgestellt. Kopien geprüft; bisherige Ordner bleiben als Rückfallmöglichkeit erhalten.')
    except Exception as e:
        for file,old in ((saved,previous_settings),(override,previous_override),(root/'.env',previous_env),(shared,previous_shared)):
            if old is None:file.unlink(missing_ok=True)
            else:file.write_bytes(old)
        if php_stopped and not stopped:
            try:command(['docker','compose','-f',str(shared),'--profile','*','up','-d','--no-deps',*php])
            except Exception:pass
        if stopped:
            # Use a temporary explicit override to retain the former manager mounts.
            recovery=stage/'recovery.json';atomic(recovery,json.dumps({'services':{'manager':{'volumes':plan['current_volumes']}}}))
            try:
                if php_stopped:command(['docker','compose','-f',str(shared),'--profile','*','up','-d','--no-deps',*php])
                command(['docker','compose','-p',plan['compose_project'],'-f',str(root/'compose.yaml'),'-f',str(recovery),'up','-d','--no-deps','--no-build','manager'])
            except Exception:pass
        report('error',str(e)+' Die bisherigen Speicherorte wurden wieder eingestellt; Originaldaten wurden nicht gelöscht.')
        raise


if __name__=='__main__':
    plan=json.loads(Path(sys.argv[2]).read_text())
    try:
        if sys.argv[1]=='probe':print(json.dumps({'areas':probe(plan)}))
        else:apply(plan)
    except (ValueError,OSError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
