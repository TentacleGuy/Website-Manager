"""Standalone update worker; runs in a separate container during manager restart."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile


def apply(root,ident):
    updates=root/'data/updates';stage=updates/ident;backup=stage/'previous';backup.mkdir(exist_ok=True)
    status=updates/'apply-status.json'
    def report(state,message):
        temp=status.with_suffix('.new');temp.write_text(json.dumps({'status':state,'message':message,'time':int(time.time())}));temp.replace(status)
        if state in ('done','error') and (root/'data/manager.sqlite').is_file():
            try:
                with sqlite3.connect(root/'data/manager.sqlite',timeout=30) as connection:
                    connection.execute("UPDATE jobs SET status=?,message=?,finished=? WHERE id=(SELECT id FROM jobs WHERE resource='manager-update' AND kind='manager-install' ORDER BY created DESC LIMIT 1)",(state,message,int(time.time())))
            except sqlite3.Error:pass
    project=os.environ['VMM_UPDATE_PROJECT'];host_data=os.environ['VMM_UPDATE_HOST_DATA'];docker_socket=os.environ.get('VMM_UPDATE_SOCKET','/var/run/docker.sock')
    env={**os.environ,'VMM_HOST_DATA':host_data,'COMPOSE_PROJECT_NAME':project}
    def command(args):
        result=subprocess.run(args,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=1800)
        with (stage/'update.log').open('ab') as out:out.write(result.stdout)
        if result.returncode:raise RuntimeError('Updateschritt fehlgeschlagen. Details: data/updates/'+ident+'/update.log')
    compose=['docker','compose','-p',project,'-f',str(root/'compose.yaml')]
    override=stage/'compose.update.json'
    override.write_text(json.dumps({'services':{'manager':{'volumes':[host_data+':/data',docker_socket+':/var/run/docker.sock']}}}))
    storage_override=root/'data/storage/compose.storage.json'
    if storage_override.exists():compose+=['-f',str(storage_override)]
    compose+=['-f',str(override)]
    changed=[];stopped=False
    report('running','Manager wird aktualisiert. Projekte bleiben erhalten.')
    try:
        # Stop the manager before copying SQLite or changing application files.
        command(compose+['stop','manager']);stopped=True
        database=root/'data/manager.sqlite'
        if database.is_file():
            with sqlite3.connect(database) as source,sqlite3.connect(stage/'manager.sqlite') as target:source.backup(target)
        with zipfile.ZipFile(stage/'manager-update.zip') as archive:
            for item in archive.infolist():
                if item.is_dir():continue
                path=root/item.filename
                # Bundle is validated by the running manager before launching this worker.
                if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=root):raise ValueError('Symlink im Installationspfad.')
                old=backup/item.filename
                if path.exists():old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,old)
                changed.append(item.filename);path.parent.mkdir(parents=True,exist_ok=True)
                temp=path.with_suffix(path.suffix+'.update');temp.write_bytes(archive.read(item));temp.replace(path)
        if (root/'.tentacle-installer').exists():
            system='windows' if (root/'Gemeinsam.ps1').exists() else 'macos' if (root/'Gemeinsam.sh').exists() else 'linux'
            for file in (root/'app/installer_assets'/system).glob('*'):
                if not file.is_file() or file.suffix not in ('.ps1','.cmd','.sh','.command','.txt'):continue
                target=root/file.name;old=backup/file.name
                if target.exists():shutil.copy2(target,old)
                changed.append(file.name);shutil.copy2(file,target)
                if file.suffix in ('.sh','.command'):target.chmod(0o755)
        server=subprocess.check_output(['docker','version','--format','{{.Server.Version}}'],text=True).strip()
        major=server.split('.')[0]
        if not major.isdigit() or int(major)<24:raise ValueError('Nicht unterstützte Docker-Version: '+server)
        command(compose+['build','--build-arg','DOCKER_CLI_IMAGE=docker:'+major+'-cli','manager'])
        command(compose+['up','-d','--no-deps','manager'])
        import importlib.util
        spec=importlib.util.spec_from_file_location('vmm_setup',root/'scripts/setup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.protocol_routes(root)
        container=subprocess.check_output(compose+['ps','-q','manager'],cwd=root,env=env,text=True).strip()
        healthy=False
        for attempt in range(30):
            check=subprocess.run(['docker','exec',container,'python','-c',"import urllib.request; urllib.request.urlopen('http://localhost:8090/api/projects',timeout=3)"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if check.returncode==0:healthy=True;break
            time.sleep(2)
        if not healthy:raise RuntimeError('Der aktualisierte Manager antwortet nicht.')
        report('done','Update installiert. Manager wurde neu gestartet.')
    except Exception as e:
        for name in reversed(changed):
            target=root/name;old=backup/name
            if old.is_file():shutil.copy2(old,target)
            else:target.unlink(missing_ok=True)
        if stopped:
            try:
                command(compose+['build','manager']);command(compose+['up','-d','--no-deps','manager'])
            except Exception:pass
        report('error',str(e)+' Vorherige Programmdateien wurden wiederhergestellt.')
        raise


if __name__=='__main__':apply(Path('/installation'),sys.argv[1])
