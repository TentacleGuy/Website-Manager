"""Portable, non-destructive Docker diagnostics shared by installers and the UI."""
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time
from urllib.parse import urlsplit


def execute(args,timeout=30):
    result=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise ValueError((result.stderr or result.stdout or 'Docker nicht erreichbar.').strip()[-1800:])
    return result.stdout.strip()


def engine(info,version,compose):
    server=version.get('Server',version)
    architecture={'aarch64':'arm64','x86_64':'amd64'}.get(info.get('Architecture',''),info.get('Architecture',''))
    if info.get('OSType')!='linux':raise ValueError('Der gewählte Docker-Dienst verwendet Windows-Container. Für den Manager werden Linux-Container benötigt.')
    if architecture not in ('arm64','amd64'):raise ValueError('Nicht unterstützte Docker-Prozessorarchitektur: '+architecture+'. Unterstützt: ARM64 und AMD64.')
    match=re.search(r'(\d+)\.(\d+)',compose)
    if not match or tuple(map(int,match.groups()))<(2,20):raise ValueError('Docker Compose ab 2.20 wird benötigt. Bitte das Compose-Plugin aktualisieren.')
    match=re.match(r'(\d+)\.',server.get('Version',''))
    if not match or int(match[1])<24:raise ValueError('Docker Engine ab 24 wird benötigt. Bitte Docker aktualisieren.')
    return {'architecture':architecture,'os':'linux','docker_version':server['Version'],
            'api':server.get('ApiVersion',server.get('APIVersion','')),'minimum_api':server.get('MinAPIVersion',''),
            'compose':compose,'cli_image':'docker:'+match[1]+'-cli'}


def socket_path(context,desktop=False):
    endpoint=context.get('Endpoints',{}).get('docker',{}).get('Host','')
    if endpoint.startswith('npipe:') or desktop or (platform.system()=='Darwin' and endpoint.startswith('unix://') and not endpoint.startswith('unix:///run/user/')):return '/var/run/docker.sock'
    if endpoint.startswith('unix://'):
        path=urlsplit(endpoint).path
        if not path.startswith('/') or any(c in path for c in '\n\r,'):raise ValueError('Ungültiger lokaler Docker-Socket.')
        return path
    raise ValueError('Diese Installation benötigt einen lokalen Docker-Dienst. Der gewählte Kontext verweist auf einen entfernten Dienst; lokale Projektordner wären dort nicht verfügbar.')


def probe(docker='docker',host_context=None):
    info=json.loads(execute([docker,'info','--format','{{json .}}']))
    version=json.loads(execute([docker,'version','--format','{{json .}}']))
    result=engine(info,version,execute([docker,'compose','version','--short']))
    # Inside a manager container the mounted daemon socket is the actual endpoint.
    if host_context is not None:
        result['context']=host_context.get('Name','')
        result['socket']=socket_path(host_context,'docker desktop' in info.get('OperatingSystem','').lower())
    result['checked']=int(time.time())
    result['platform']=platform.system().lower()
    result['warnings']=[]
    memory=info.get('MemTotal',0)
    if memory and memory<4*1024**3:result['warnings'].append('Docker stehen weniger als 4 GB Arbeitsspeicher zur Verfügung. Mehrere Projekte können dadurch scheitern.')
    result['status']='ok'
    return result


def save(data,value):
    path=Path(data)/'setup-report.json';path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.new');temp.write_text(json.dumps(value,indent=2));temp.replace(path)


def saved_report(data):
    path=Path(data)/'setup-report.json'
    return json.loads(path.read_text()) if path.is_file() else {'status':'unknown','message':'Die Umgebung wurde noch nicht geprüft.'}


def check(data):
    previous=saved_report(data)
    try:
        value=probe()
        for key in ('context','socket','platform'):
            if key in previous:value[key]=previous[key]
        save(data,value)
        return 'Docker '+value['docker_version']+', '+value['architecture']+' und Compose '+value['compose']+' sind erreichbar.'
    except Exception as e:
        save(data,{**previous,'status':'error','checked':int(time.time()),'message':str(e)})
        raise


def configure_host(root,docker='docker'):
    root=Path(root)
    selected=execute([docker,'context','show'])
    context=json.loads(execute([docker,'context','inspect',selected]))[0]
    if os.environ.get('DOCKER_HOST'):
        context={**context,'Endpoints':{'docker':{'Host':os.environ['DOCKER_HOST']}}}
    value=probe(docker,context)
    override=os.environ.get('VMM_DOCKER_SOCKET')
    if override:
        if not override.startswith('/') or any(c in override for c in '\n\r,'):raise ValueError('Ungültiger Docker-Socket-Pfad.')
        value['socket']=override
    env=root/'.env'
    text=env.read_text() if env.is_file() else ''
    settings={'VMM_DOCKER_CLI_IMAGE':value['cli_image'],'VMM_DOCKER_SOCKET':value['socket']}
    for key,item in settings.items():
        line=key+'='+item
        pattern=r'^'+key+r'=.*$'
        text=re.sub(pattern,lambda _:line,text,flags=re.M) if re.search(pattern,text,re.M) else text.rstrip('\n')+'\n'+line+'\n'
    env.write_text(text.lstrip('\n'));env.chmod(0o600)
    save(root/'data',value)
    return value


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--docker',default='docker');args=parser.parse_args()
    try:print(json.dumps(configure_host(args.root,args.docker)))
    except Exception as e:
        save(args.root/'data',{'status':'error','checked':int(time.time()),'message':str(e)})
        raise SystemExit(str(e))
