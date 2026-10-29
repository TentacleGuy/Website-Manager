"""Explicit database families, separate persistent volumes and constraint selection."""
import json
import re
from pathlib import Path

LEGACY='existing'
DEFAULT='mariadb-11.4'
PROFILES={
    'mariadb-10.11':{'engine':'mariadb','version':'10.11','image':'mariadb:10.11'},
    'mariadb-11.4':{'engine':'mariadb','version':'11.4','image':'mariadb:11.4'},
    'mariadb-11.8':{'engine':'mariadb','version':'11.8','image':'mariadb:11.8'},
    'mysql-8.0':{'engine':'mysql','version':'8.0','image':'mysql:8.0'},
    'mysql-8.4':{'engine':'mysql','version':'8.4','image':'mysql:8.4'},
}


def validate(value):
    if value!='auto' and value not in PROFILES:raise ValueError('Unbekanntes Datenbankprofil. Ein angebotenes MySQL-/MariaDB-Profil auswählen.')
    return value


def legacy_spec(data=None):
    if data is None:
        from store import DATA
        data=DATA
    path=Path(data)/'shared/backend.json'
    if path.is_file():return json.loads(path.read_text())
    return {'engine':'mariadb','version':'10.11','image':'mariadb:10.11'}


def freeze_existing(data):
    """Retain the actual old service image before generating a new Compose file."""
    path=Path(data)/'shared/backend.json'
    if path.exists():return
    previous=Path(data)/'shared/compose.json'
    image='mariadb:10.11'
    if previous.is_file():
        image=json.loads(previous.read_text()).get('services',{}).get('db',{}).get('image','')
    match=re.fullmatch(r'(?:docker.io/library/)?(mariadb|mysql):(\d+\.\d+(?:\.\d+)?)(?:@sha256:[a-f0-9]{64})?',image)
    if not match:raise ValueError('Die vorhandene Datenbank verwendet ein unbekanntes oder unversioniertes Image. Es wurde nicht ersetzt. Bitte die tatsächlich installierte Version zuerst prüfen: '+image)
    value={'engine':match[1],'version':match[2],'image':image}
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.new');temp.write_text(json.dumps(value));temp.chmod(0o600);temp.replace(path)


def profile(p):
    key=p.get('database_profile') or LEGACY
    if key==LEGACY:return {**legacy_spec(),'id':LEGACY,'service':'db','volume':'database','server':1}
    if key=='auto':key=DEFAULT
    validate(key)
    return {**PROFILES[key],'id':key,'service':'db-'+key.replace('.','-'),'volume':'database-'+key.replace('.','-'),'server':list(PROFILES).index(key)+2}


def listing():
    return [profile({'database_profile':key}) for key in PROFILES]


def sql_command(p,dump=False,extra=None,database=False):
    item=profile(p);client=('mariadb-dump' if dump else 'mariadb') if item['engine']=='mariadb' else ('mysqldump' if dump else 'mysql')
    secret='MARIADB_ROOT_PASSWORD' if item['engine']=='mariadb' else 'MYSQL_ROOT_PASSWORD'
    options=list(extra or [])
    if dump:options=['--single-transaction','--routines','--triggers']+(['--set-gtid-purged=OFF','--no-tablespaces'] if item['engine']=='mysql' else [])+options
    # Only fixed, internal flags are accepted. Database names arrive as positional args.
    if any(not re.fullmatch(r'[-A-Za-z0-9_=]+',v) for v in options):raise ValueError('Ungültige Datenbankoption.')
    script='exec '+client+' -uroot -p"$'+secret+'"'+(' '+' '.join(options) if options else '')+(' "$1"' if database else '')
    return ['exec','-T',item['service'],'sh','-c',script]+(['vmm','vmm_'+p['slug'].replace('-','_')] if database else [])


def service(item,password):
    mysql=item['engine']=='mysql';prefix='MYSQL' if mysql else 'MARIADB'
    mysql_host='' if item['id']==LEGACY else ' -h 127.0.0.1'
    health=['CMD-SHELL','MYSQL_PWD="$$MYSQL_ROOT_PASSWORD" mysql'+mysql_host+" -uroot --silent -e 'SELECT 1'"] if mysql else ['CMD','healthcheck.sh','--connect','--innodb_initialized']
    environment={prefix+'_ROOT_PASSWORD':password}
    if mysql and item['id']!=LEGACY:environment['MYSQL_ROOT_HOST']='%'
    return {'image':item['image'],'profiles':['database-'+item['id'].replace('.','-')],
            'environment':environment,'volumes':[item['volume']+':/var/lib/mysql'],
            'healthcheck':{'test':health,'interval':'3s','timeout':'5s','retries':60},'restart':'unless-stopped'}


def select(requirements,requested='auto'):
    from compatibility import satisfies
    if requested!=LEGACY:validate(requested)
    candidates=listing() if requested=='auto' else [profile({'database_profile':requested})]
    def allowed(item):
        for req in requirements:
            databases=req.get('database',{})
            if databases:
                expression=databases.get(item['engine'])
                if expression is None:return False
                series=item['version'];patches={0,999}
                for found in re.findall(r'(?<![0-9.])'+re.escape(series)+r'\.(\d+)',expression):
                    patch=int(found);patches.update((max(0,patch-1),patch,patch+1))
                if not any(satisfies(series+'.'+str(patch),expression) for patch in patches):return False
        return True
    choices=[item for item in candidates if allowed(item)]
    if not choices:
        labels=', '.join(r.get('label','Projekt') for r in requirements if r.get('database'))
        raise ValueError('Keine kompatible Datenbankkombination für '+(labels or 'dieses Projekt')+'. Anforderungen und Datenbankprofil prüfen.')
    # Prefer a maintained LTS baseline, but satisfy declared stricter minima/families.
    order={DEFAULT:0,'mariadb-11.8':1,'mariadb-10.11':2,LEGACY:2,'mysql-8.4':3,'mysql-8.0':4}
    return min(choices,key=lambda item:order[item['id']])['id']
