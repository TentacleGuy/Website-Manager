"""Opt-in integration validation on alternate ports; preserves existing stacks.
Requires the real demo packages/projects prepared through VMM. Leaves manager
running, stops demo projects and removes its temporary validation gateway.
"""
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import ssl
import subprocess
import time
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
TEMP=DATA/'validation'

def run(args,timeout=1800):
    r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    if r.returncode:
        # Compose configuration and CMS credentials must not enter test output.
        raise RuntimeError('Befehl fehlgeschlagen: '+args[0]+' '+args[1]+'\n'+r.stderr[-1200:])
    return r.stdout

def api(path,body=None):
    data=json.dumps(body).encode() if body is not None else None
    headers={'X-VMM-Request':'1','Content-Type':'application/json'}
    with urlopen(Request('http://localhost:8090/api/'+path,data=data,headers=headers),timeout=15) as r:return json.load(r)

def wait_job(ident,timeout=900):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        j=next(j for j in api('jobs')['jobs'] if j['id']==ident)
        if j['status']=='done':return j
        if j['status'] in ('error','interrupted'):raise RuntimeError(j['kind']+': '+j['message'])
        time.sleep(1)
    raise RuntimeError('Zeitlimit für Hintergrundvorgang überschritten.')

def request_page(port,host,path='/',tls=False):
    if tls:
        context=ssl.create_default_context(cafile=str(TEMP/'certs'/'cert.pem'))
        # Connect to loopback with SNI and verification for the project domain.
        import socket
        sock=socket.create_connection(('127.0.0.1',port),timeout=15)
        try:
            secure=context.wrap_socket(sock,server_hostname=host.split(':')[0])
        except ssl.SSLCertVerificationError:
            # Read only the public peer certificate for diagnostics. This socket
            # never sends an HTTP request and is not counted as a passing test.
            from cryptography import x509
            diagnostic=ssl._create_unverified_context().wrap_socket(socket.create_connection(('127.0.0.1',port),timeout=10),server_hostname=host.split(':')[0])
            peer=x509.load_der_x509_certificate(diagnostic.getpeercert(binary_form=True));diagnostic.close()
            local=x509.load_pem_x509_certificate((TEMP/'certs'/'cert.pem').read_bytes())
            print('TLS-Diagnose: peer subject='+peer.subject.rfc4514_string()+' issuer='+peer.issuer.rfc4514_string(),flush=True)
            print('TLS-Diagnose: local subject='+local.subject.rfc4514_string()+' issuer='+local.issuer.rfc4514_string(),flush=True)
            raise
        conn=http.client.HTTPConnection(host,timeout=15);conn.sock=secure
    else:conn=http.client.HTTPConnection('127.0.0.1',port,timeout=15)
    conn.request('GET',path,headers={'Host':host})
    response=conn.getresponse();body=response.read();status=response.status;conn.close()
    return status,body

if __name__=='__main__':
    gateway_file=TEMP/'compose.json';gateway_started=False
    TEMP.mkdir(parents=True,exist_ok=True)
    (TEMP/'certs').mkdir(exist_ok=True);(TEMP/'dynamic').mkdir(exist_ok=True)
    try:
        try:run(['docker','network','inspect','vmm-gateway'],timeout=15)
        except RuntimeError:run(['docker','network','create','vmm-gateway'],timeout=15)
        run(['docker','compose','up','-d','--build','manager'])
        for _ in range(30):
            try:
                assert api('health')['login'] is False
                break
            except Exception:time.sleep(1)
        else:raise RuntimeError('Manager nicht erreichbar.')
        print('PASS Manager läuft als Docker-Container ohne Login.',flush=True)
        run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=vmm.test','-addext','subjectAltName=DNS:*.vmm.test','-keyout',str(TEMP/'certs'/'key.pem'),'-out',str(TEMP/'certs'/'cert.pem')])
        config=json.loads((ROOT/'infra'/'compose.gateway.yaml').read_text())
        traefik=config['services']['traefik']
        traefik['ports']=['127.0.0.1:18082:8082','127.0.0.1:18084:8084','127.0.0.1:18184:8184']
        traefik['volumes']=['/var/run/docker.sock:/var/run/docker.sock:ro',str(TEMP/'dynamic')+':/etc/traefik/dynamic:ro',str(TEMP/'certs')+':/test-certs:ro']
        config['services']={'gateway':traefik}
        config['name']='vmm-validation'
        config['networks']['gateway']={'name':'vmm-gateway','external':True}
        gateway_file.write_text(json.dumps(config))
        shutil.copyfile(ROOT/'infra'/'dynamic'/'warmup.yaml',TEMP/'dynamic'/'warmup.yaml')
        (TEMP/'dynamic'/'tls.yaml').write_text(json.dumps({'tls':{'certificates':[{'certFile':'/test-certs/cert.pem','keyFile':'/test-certs/key.pem'}]}}))
        gateway_started=True
        run(['docker','compose','-f',str(gateway_file),'up','-d'])
        for name in ('wordpress-demo','joomla-demo'):
            wait_job(api('projects/'+name+'/start',{})['job'])
        time.sleep(3)
        for name,path in (('wordpress-demo','/wp-admin/install.php'),('joomla-demo','/installation/index.php')):
            status,body=request_page(18084,name+'.vmm.test:8084',path)
            if status not in (200,302,303):raise RuntimeError(name+' HTTP-Status '+str(status)+': '+body[:300].decode(errors='replace'))
            print('PASS '+name+' über Traefik HTTP: '+str(status),flush=True)
        status,body=request_page(18184,'wordpress-demo.vmm.test:8184','/wp-admin/install.php',tls=True)
        if status!=200:raise RuntimeError('TLS-Test fehlgeschlagen: '+str(status))
        print('PASS HTTPS mit geprüfter lokaler Test-Zertifikatskette.',flush=True)
        status,body=request_page(18082,'wordpress-demo.vmm.test:8082')
        if status!=503 or b'PHP 8.2' not in body:raise RuntimeError('On-Demand-Startseite fehlt.')
        until=time.monotonic()+900
        runtime_job=None
        while time.monotonic()<until:
            candidates=[j for j in api('jobs')['jobs'] if j['resource']=='wordpress-demo' and j['kind']=='runtime']
            if candidates:runtime_job=candidates[0];break
            time.sleep(1)
        if not runtime_job:raise RuntimeError('On-Demand-Job fehlt.')
        wait_job(runtime_job['id'])
        time.sleep(3)
        status,body=request_page(18082,'wordpress-demo.vmm.test:8082','/wp-admin/install.php')
        if status!=200:raise RuntimeError('PHP-8.2-Routing fehlgeschlagen: '+str(status))
        compose=DATA/'projects'/'wordpress-demo'/'compose.json'
        php=run(['docker','compose','-f',str(compose),'exec','-T','php82','php','-r','echo PHP_VERSION;']).strip()
        if not php.startswith('8.2.'):raise RuntimeError('Falsche PHP-Laufzeit.')
        print('PASS URL-Port aktiviert PHP '+php+' bei gemeinsamen Projektdaten.',flush=True)
        wait_job(api('projects/wordpress-demo/snapshot',{})['job'])
        exports=api('exports')['exports']
        if not exports:raise RuntimeError('Sicherung fehlt.')
        import zipfile
        with zipfile.ZipFile(DATA/'exports'/exports[0]['name']) as z:
            assert 'database.sql' in z.namelist() and 'site/wp-config.php' in z.namelist()
        print('PASS Dateisicherung und SQL-Export im echten Docker-Betrieb.',flush=True)
    except Exception:
        if gateway_started:
            print(run(['docker','compose','-f',str(gateway_file),'logs','--tail','40']),flush=True)
        raise
    finally:
        for name in ('wordpress-demo','joomla-demo'):
            try:wait_job(api('projects/'+name+'/stop',{})['job'],timeout=120)
            except Exception:pass
        if gateway_started:run(['docker','compose','-f',str(gateway_file),'down'],timeout=60)
        if TEMP.exists():shutil.rmtree(TEMP)
