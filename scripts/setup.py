"""Cross-platform Compose/DNS setup; optional mkcert certificates."""
import argparse
import ipaddress
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PHP=('7.4','8.0','8.1','8.2','8.3','8.4','8.5')

def generate(root,lan_ip):
    ipaddress.IPv4Address(lan_ip)
    data=root/'data';data.mkdir(exist_ok=True)
    infra=root/'infra';infra.mkdir(exist_ok=True)
    (infra/'dynamic').mkdir(exist_ok=True)
    (data/'certs').mkdir(exist_ok=True)
    env=root/'.env'
    if not env.exists():
        env.write_text('VMM_HOST_DATA='+data.as_posix()+'\nVMM_BIND=127.0.0.1\n')
        env.chmod(0o600)
    command=['--providers.file.directory=/etc/traefik/dynamic','--providers.file.watch=true','--providers.docker=true','--providers.docker.exposedbydefault=false']
    command.append('--entrypoints.database.address=:8091')
    mappings=['127.0.0.1:8091:8091']
    for php in PHP:
        suffix=php.replace('.','')
        for prefix,kind in (('80','php'),('81','tls')):
            port=prefix+suffix
            command.append('--entrypoints.'+kind+suffix+'.address=:'+port)
            mappings.append(port+':'+port)
    gateway={'services':{
        'traefik':{'image':'traefik:v3.7.14','command':command,'ports':mappings,'volumes':['/var/run/docker.sock:/var/run/docker.sock:ro','./dynamic:/etc/traefik/dynamic:ro','../data/certs:/certs:ro'],'networks':['gateway'],'restart':'unless-stopped'},
        'dns':{'image':'coredns/coredns:1.12.0','command':['-conf','/etc/coredns/Corefile'],'ports':['53:53/udp','53:53/tcp'],'volumes':['./Corefile:/etc/coredns/Corefile:ro'],'restart':'unless-stopped'}},
        'networks':{'gateway':{'name':'vmm-gateway','external':True}}}
    (infra/'compose.gateway.yaml').write_text(json.dumps(gateway,indent=2)+'\n')
    fallback={'http':{'routers':{},'services':{'vmm-manager':{'loadBalancer':{'servers':[{'url':'http://manager:8090'}]}}}}}
    for kind in ('php','tls'):
        router={'rule':'HostRegexp(`^[a-z][a-z0-9-]*[.]vmm[.]test$`)','entryPoints':[kind+v.replace('.','') for v in PHP],'priority':1,'service':'vmm-manager'}
        if kind=='tls': router['tls']={}
        fallback['http']['routers']['vmm-warmup-'+kind]=router
    (infra/'dynamic'/'warmup.yaml').write_text(json.dumps(fallback,indent=2))
    (infra/'Corefile').write_text('''vmm.test:53 {
    template IN A {
        answer "{{ .Name }} 60 IN A ADDRESS"
    }
    template IN AAAA {
        rcode NOERROR
    }
    errors
}
.:53 {
    forward . 1.1.1.1 9.9.9.9
    cache 30
    errors
}
'''.replace('ADDRESS',lan_ip))
    protocol_routes(root)
    return data

def protocol_routes(root):
    routers={};middlewares={}
    for php in PHP:
        suffix=php.replace('.','')
        for scheme,entry,tls in (('https','tls',False),('http','php',True)):
            name='vmm-protocol-'+entry+suffix
            middlewares[name]={'redirectScheme':{'scheme':scheme,'port':('81' if scheme=='https' else '80')+suffix,'permanent':False}}
            router={'rule':'HostRegexp(`^[a-z][a-z0-9-]*[.]vmm[.]test$`)','entryPoints':[entry+suffix],'priority':10000,'service':'noop@internal','middlewares':[name]}
            if tls:router['tls']={}
            routers[name]=router
    target=root/'infra/dynamic/protocols.yaml';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps({'http':{'routers':routers,'middlewares':middlewares}},indent=2))


def certificates(root):
    mkcert=shutil.which('mkcert')
    if not mkcert: raise RuntimeError('mkcert fehlt. Zuerst von https://github.com/FiloSottile/mkcert installieren, dann erneut mit --certificates aufrufen.')
    certs=root/'data'/'certs'
    subprocess.run([mkcert,'-install'],check=True)
    subprocess.run([mkcert,'-cert-file',str(certs/'vmm.test.pem'),'-key-file',str(certs/'vmm.test-key.pem'),'vmm.test','*.vmm.test','localhost','127.0.0.1'],check=True)
    (certs/'vmm.test-key.pem').chmod(0o600)
    (root/'infra'/'dynamic'/'tls.yaml').write_text(json.dumps({'tls':{'certificates':[{'certFile':'/certs/vmm.test.pem','keyFile':'/certs/vmm.test-key.pem'}]}},indent=2))
    caroot=subprocess.check_output([mkcert,'-CAROOT'],text=True).strip()
    # Only the public CA certificate may be shared with other LAN clients.
    shutil.copyfile(Path(caroot)/'rootCA.pem',certs/'rootCA.pem')
    print('Öffentliches Stammzertifikat für weitere Geräte: data/certs/rootCA.pem')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lan-ip',default=None,help='LAN-IP des Docker-Rechners, für Wildcard-DNS')
    parser.add_argument('--certificates',action='store_true',help='mkcert ausführen und lokale CA vertrauen')
    args=parser.parse_args()
    try:
        lan_ip=args.lan_ip
        if not lan_ip:
            existing=ROOT/'infra'/'Corefile'
            match=re.search(r'60 IN A ([0-9.]+)',existing.read_text()) if existing.exists() else None
            lan_ip=match.group(1) if match else '127.0.0.1'
        generate(ROOT,lan_ip)
        if args.certificates: certificates(ROOT)
        print('Konfiguration erzeugt. Keine Anmeldung erforderlich.')
        print('Start: docker compose -f infra/compose.gateway.yaml up -d')
        print('Danach: docker compose up -d --build')
        print('Dashboard: http://localhost:8090')
        print('DNS: vmm.test über den DNS-Dienst des Docker-Rechners auflösen lassen.')
    except (ValueError,RuntimeError,subprocess.CalledProcessError) as e:
        print(str(e),file=sys.stderr);sys.exit(1)
