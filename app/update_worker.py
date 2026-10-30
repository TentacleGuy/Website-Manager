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
import queue
import threading


def run_logged(args,root,env,log,heartbeat,timeout=1800):
    """Drain output continuously; keep status alive even during quiet Docker steps."""
    with subprocess.Popen(args,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0) as process:
        output=queue.Queue()
        def read():
            try:
                while True:
                    chunk=process.stdout.read(4096)
                    if not chunk:break
                    output.put(chunk)
            finally:output.put(None)
        threading.Thread(target=read,daemon=True).start()
        deadline=time.monotonic()+timeout;ended=False
        try:
            with log.open('ab',buffering=0) as stream:
                stream.write(('\n$ '+' '.join(args)+'\n').encode())
                while not ended:
                    if time.monotonic()>deadline:raise TimeoutError('Zeitlimit für diesen Updateschritt überschritten.')
                    try:
                        chunk=output.get(timeout=1)
                        if chunk is None:ended=True
                        else:stream.write(chunk)
                    except queue.Empty:pass
                    heartbeat()
            code=process.wait(timeout=max(1,deadline-time.monotonic()))
            if code:raise RuntimeError('Updateschritt fehlgeschlagen (Exit-Code '+str(code)+'). Siehe Updateprotokoll.')
        except BaseException:
            process.kill();process.wait();raise


def apply(root,ident):
    updates=root/'data/updates';stage=updates/ident;backup=stage/'previous';backup.mkdir(exist_ok=True)
    status=updates/'apply-status.json'
    try:metadata=json.loads(status.read_text())
    except (OSError,ValueError):metadata={}
    def report(state,message):
        metadata.update(id=ident,status=state,message=message,time=int(time.time()))
        temp=status.with_suffix('.worker-new');temp.write_text(json.dumps(metadata));temp.replace(status)
        if state in ('done','error') and (root/'data/manager.sqlite').is_file():
            try:
                with sqlite3.connect(root/'data/manager.sqlite',timeout=30) as connection:
                    connection.execute("UPDATE jobs SET status=?,message=?,finished=? WHERE id=(SELECT id FROM jobs WHERE resource='manager-update' AND kind='manager-install' ORDER BY created DESC LIMIT 1)",(state,message,int(time.time())))
            except sqlite3.Error:pass
    project=os.environ['VMM_UPDATE_PROJECT'];host_data=os.environ['VMM_UPDATE_HOST_DATA'];docker_socket=os.environ.get('VMM_UPDATE_SOCKET','/var/run/docker.sock')
    env={**os.environ,'VMM_HOST_DATA':host_data,'COMPOSE_PROJECT_NAME':project}
    def command(args):
        run_logged(args,root,env,stage/'update.log',lambda:report('running',metadata['message']))
    compose=['docker','compose','-p',project,'-f',str(root/'compose.yaml')]
    override=stage/'compose.update.json'
    override.write_text(json.dumps({'services':{'manager':{'volumes':[host_data+':/data',docker_socket+':/var/run/docker.sock']}}}))
    storage_override=root/'data/storage/compose.storage.json'
    if storage_override.exists():compose+=['-f',str(storage_override)]
    compose+=['-f',str(override)]
    changed=[];stopped=False;built=False
    report('running','Manager wird aktualisiert. Projekte bleiben erhalten.')
    try:
        # Running application files live in the container image. Prepare the new
        # host files and image while the old manager continues serving progress.
        report('running','Programmdateien werden gesichert und entpackt …')
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
        report('running','Neues Manager-Image wird gebaut. Docker-Ausgaben stehen im Protokoll …')
        command(compose+['build','--build-arg','DOCKER_CLI_IMAGE=docker:'+major+'-cli','manager']);built=True
        report('running','Manager wird neu gestartet. Die Verbindung wird kurz unterbrochen …')
        command(compose+['stop','manager']);stopped=True
        database=root/'data/manager.sqlite'
        if database.is_file():
            with sqlite3.connect(database) as source,sqlite3.connect(stage/'manager.sqlite') as target:source.backup(target)
        command(compose+['up','-d','--no-deps','manager'])
        report('running','Neuer Manager wird auf Erreichbarkeit geprüft …')
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
        report('running','Update fehlgeschlagen. Vorherige Version wird wiederhergestellt …')
        for name in reversed(changed):
            target=root/name;old=backup/name
            if old.is_file():shutil.copy2(old,target)
            else:target.unlink(missing_ok=True)
        recovery_error=''
        if stopped or built:
            try:
                command(compose+['build','manager']);command(compose+['up','-d','--no-deps','manager'])
            except Exception as recovery:recovery_error=' Der Neustart der vorherigen Version ist ebenfalls fehlgeschlagen: '+str(recovery)
        report('error',str(e)+' Vorherige Programmdateien wurden wiederhergestellt.'+recovery_error)
        raise


if __name__=='__main__':apply(Path('/installation'),sys.argv[1])
