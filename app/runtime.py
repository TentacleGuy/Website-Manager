"""Compose generation; PHP variants share files and database within one project."""
import re
import json
from legacy_runtime import compose as legacy_compose

PHP = ('7.4','8.0','8.1','8.2','8.3','8.4','8.5')

def slug(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',value):
        raise ValueError('Projektname: 1–40 Kleinbuchstaben, Ziffern oder Bindestriche; Beginn mit Buchstabe.')
    return value

def ports(version):
    if version not in PHP: raise ValueError('PHP-Version wird nicht unterstützt.')
    suffix=version.replace('.','')
    return int('80'+suffix),int('81'+suffix)

def host_path(value):
    value=value.replace('\\','/').rstrip('/')
    # Child Compose runs inside the Linux manager, not the Windows host CLI.
    if re.match(r'^[A-Za-z]:/',value):
        value='/run/desktop/mnt/host/'+value[0].lower()+value[2:]
    return value

def compose(project,host_data):
    if project.get('storage','legacy') == 'legacy':
        result=legacy_compose(project,host_data)
        result['services']['phpmyadmin']=database_admin(project)
        return result
    name=slug(project['slug']); ports(project['php'])
    host_data=host_path(host_data)
    root=host_data+'/projects/'+name
    services={
        'db':{'image':'mariadb:10.11','environment':{'MARIADB_DATABASE':'website','MARIADB_USER':'website','MARIADB_PASSWORD':project['db_password'],'MARIADB_ROOT_PASSWORD':project['db_root_password']},'volumes':['database:/var/lib/mysql'], 'healthcheck':{'test':['CMD','healthcheck.sh','--connect','--innodb_initialized'],'interval':'5s','timeout':'5s','retries':30}}
    }
    for version in PHP:
        suffix=version.replace('.',''); ident=name+'-'+suffix
        labels={'traefik.enable':'true','traefik.docker.network':'vmm-gateway'}
        for tls,entry in ((False,'php'),(True,'tls')):
            router=ident+('-tls' if tls else '')
            base='traefik.http.routers.'+router
            labels[base+'.rule']='Host(`'+name+'.vmm.test`)'
            labels[base+'.entrypoints']=entry+suffix
            labels[base+'.service']=ident
            if tls: labels[base+'.tls']='true'
        labels['traefik.http.services.'+ident+'.loadbalancer.server.port']='80'
        services['php'+suffix]={'image':'vmm-php:'+version,'profiles':['php'+suffix],
            'depends_on':{'db':{'condition':'service_healthy'}},'volumes':[
                {'type':'bind','source':root+'/site','target':'/var/www/html'},
                {'type':'bind','source':root+'/tools','target':'/vmm-tools','read_only':True},
                {'type':'bind','source':host_data+'/extensions','target':'/vmm-extensions','read_only':True}],
            'environment':{'VMM_PROJECT':name,'VMM_DB_PASSWORD':project['db_password']},
            'networks':['default','gateway'],'labels':labels}
    services['phpmyadmin']=database_admin(project)
    return {'name':'vmm-'+name,'services':services,'volumes':{'database':{}},'networks':{'gateway':{'external':True,'name':'vmm-gateway'}}}


def preview_ports(path):
    """Read only the restricted loopback preview override we support."""
    if not path.exists(): return {}
    value=json.loads(path.read_text())
    if set(value)!={'services'}: raise ValueError('Ungültige Vorschau-Konfiguration.')
    result={}
    for service, config in value['services'].items():
        if service not in {'php'+v.replace('.','') for v in PHP}|{'web'} or set(config)!={'ports'}:
            raise ValueError('Ungültiger Vorschau-Dienst.')
        entries=config['ports']
        if len(entries)!=1: raise ValueError('Genau ein Vorschau-Port erforderlich.')
        entry=entries[0]
        if set(entry)!={'target','published','host_ip','protocol'} or entry['target']!=80 or entry['host_ip']!='127.0.0.1' or entry['protocol']!='tcp':
            raise ValueError('Vorschau muss ausschließlich lokales HTTP bereitstellen.')
        port=int(entry['published'])
        if not 1024<=port<=65535: raise ValueError('Ungültiger Vorschau-Port.')
        result[service]=port
    return result


def project_links(project, root):
    service='web' if project['storage']=='legacy' else 'php'+project['php'].replace('.','')
    preview=preview_ports(root/'preview.compose.json').get(service)
    http,https=ports(project['php'])
    base='http://localhost:'+str(preview) if preview else 'http://'+project['slug']+'.vmm.test:'+str(http)
    if project.get('restore') and (project.get('cms')=='auto' or project.get('status')=='preparing'):
        return {key:None for key in ('frontend_url','backend_url','database_url','http_url','https_url','admin_url')}
    path='/installation/' if project['restore'] else '/'
    return {'frontend_url':base+'/','backend_url':base+('/administrator/' if project['cms']=='joomla' else '/wp-admin/'),
            'database_url':('http://localhost:8091/index.php?route=/database/structure&db=vmm_'+project['slug'].replace('-','_') if project['storage']=='shared' else 'http://localhost:8091/'+project['slug']+'/'),'http_url':base+path,'https_url':None if preview else 'https://'+project['slug']+'.vmm.test:'+str(https)+path,
            'admin_url':base+('/installation/' if project['restore'] else '/administrator/' if project['cms']=='joomla' else '/wp-admin/'), 'local_preview':bool(preview)}


def database_admin(project):
    name=slug(project['slug']); ident=name+'-database'
    return {'image':'phpmyadmin:5.2-apache',
            'depends_on':{'db':{'condition':'service_healthy'}},
            'environment':{'PMA_HOST':'db','PMA_USER':'website','PMA_PASSWORD':project['db_password'],
                           'PMA_ABSOLUTE_URI':'http://localhost:8091/'+name+'/','UPLOAD_LIMIT':'256M'},
            'networks':['default','gateway'],
            'labels':{'traefik.enable':'true','traefik.docker.network':'vmm-gateway',
                      'traefik.http.routers.'+ident+'.rule':'Host(`localhost`) && PathPrefix(`/'+name+'/`)'
                      ,'traefik.http.routers.'+ident+'.middlewares':ident+'-path'
                      ,'traefik.http.middlewares.'+ident+'-path.stripprefix.prefixes':'/'+name,
                      'traefik.http.routers.'+ident+'.entrypoints':'database',
                      'traefik.http.routers.'+ident+'.service':ident,
                      'traefik.http.services.'+ident+'.loadbalancer.server.port':'80'}}
