"""One PHP service per version, shared MariaDB and loopback-only phpMyAdmin."""
import json
import os
import re
import secrets
from pathlib import Path
from runtime import PHP, host_path, slug
from database_profiles import profile,service as database_service,LEGACY,freeze_existing


def database_info(p):
    name='vmm_'+slug(p['slug']).replace('-','_')
    return {'host':profile(p)['service'],'database':name,'user':name,'password':p['db_password']}


def stack(host_data, root_password, database_profiles=None):
    host=host_path(host_data)
    from storage_paths import host_location
    project_host=host_location('projects',host_data);extension_host=host_location('extensions',host_data);backup_host=host_location('backups',host_data)
    profiles=list(dict.fromkeys([LEGACY]+list(database_profiles or [])))
    services={};volumes={}
    for ident in profiles:
        item=profile({'database_profile':ident});services[item['service']]=database_service(item,root_password);volumes[item['volume']]={}
    for php in PHP:
        suffix=php.replace('.','');ident='vmm-shared-'+suffix
        labels={'traefik.enable':'true','traefik.docker.network':'vmm-gateway'}
        for tls,entry in ((False,'php'),(True,'tls')):
            router=ident+('-tls' if tls else '');base='traefik.http.routers.'+router
            labels[base+'.rule']='HostRegexp(`^[a-z][a-z0-9-]*[.]vmm[.]test$`)'
            labels[base+'.priority']='10';labels[base+'.entrypoints']=entry+suffix;labels[base+'.service']=ident
            if tls:labels[base+'.tls']='true'
        labels['traefik.http.services.'+ident+'.loadbalancer.server.port']='80'
        services['php'+suffix]={'image':'vmm-php:'+php,'profiles':['php'+suffix],
            'volumes':[
                project_host+':/vmm-projects',host+'/shared/apache:/etc/apache2/sites-enabled:ro',
                host+'/shared/state:/vmm-state:ro',host+'/shared/tools:/vmm-tools:ro',
                extension_host+':/vmm-extensions:ro',backup_host+':/vmm-backups'],
            'networks':['default','gateway'],'labels':labels,'restart':'unless-stopped'}
    labels={'traefik.enable':'true','traefik.docker.network':'vmm-gateway',
        'traefik.http.routers.vmm-shared-database.rule':'Host(`localhost`)',
        'traefik.http.routers.vmm-shared-database.entrypoints':'database',
        'traefik.http.routers.vmm-shared-database.priority':'50',
        'traefik.http.services.vmm-shared-database.loadbalancer.server.port':'80'}
    services['phpmyadmin']={'image':'phpmyadmin:5.2-apache','environment':{'UPLOAD_LIMIT':'512M'},'volumes':[host+'/shared/pma:/vmm-pma:ro'],
        'entrypoint':['/bin/sh','-c','ln -sf /vmm-pma/config.php /etc/phpmyadmin/config.user.inc.php; exec /docker-entrypoint.sh "$@"','vmm'],
        'command':['apache2-foreground'],
        'networks':['default','gateway'],'labels':labels,'restart':'unless-stopped'}
    return {'name':os.environ.get('VMM_RUNTIME_PROJECT','vmm-runtime'),'services':services,'volumes':volumes,'networks':{'gateway':{'external':True,'name':'vmm-gateway'}}}


def atomic(path,text):
    temp=path.with_suffix(path.suffix+'.new');temp.write_text(text);temp.chmod(0o600);temp.replace(path)


def write_config(data, host, projects):
    root=data/'shared';root.mkdir(exist_ok=True)
    freeze_existing(data)
    for name in ('apache','state','tools','pma'): (root/name).mkdir(exist_ok=True)
    secret=root/'secrets.json'
    if not secret.exists():atomic(secret,json.dumps({'root_password':secrets.token_urlsafe(36)}))
    password=json.loads(secret.read_text())['root_password']
    config=stack(host,password,[profile(p)['id'] for p in projects if p['storage']=='shared'])
    from database_profiles import legacy_spec
    old={**legacy_spec(data),'id':LEGACY,'volume':'database'}
    config['services']['db']=database_service(old,password)
    atomic(root/'compose.json',json.dumps(config,indent=2))
    # Default vhost rejects unknown domains; no directory listing or tools are web-accessible.
    configs={'000-default.conf':'''<VirtualHost *:80>
ServerName vmm-invalid
DocumentRoot /var/www/html
<Location />
Require all denied
</Location>
</VirtualHost>
'''}
    servers={}
    for p in projects:
        if p['storage']!='shared':continue
        name=slug(p['slug']);site='/vmm-projects/'+name+'/site'
        configs[name+'.conf']=f'''<VirtualHost *:80>
ServerName {name}.vmm.test
DocumentRoot "{site}"
<Directory "{site}">
Options -Indexes +FollowSymLinks
AllowOverride All
Require all {"denied" if p.get("restore") else "granted"}
</Directory>
</VirtualHost>
'''
        servers[name]=database_info(p)
    for name,text in configs.items():atomic(root/'apache'/name,text)
    # Apache worker www-data must read config files mounted from macOS/Windows/Linux.
    for path in (root/'apache').glob('*.conf'):
        if path.name not in configs:path.unlink()
        else:path.chmod(0o644)
    prefix="""<?php
if (PHP_SAPI !== 'cli') {
  if (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https') $_SERVER['HTTPS']='on';
  $root=$_SERVER['DOCUMENT_ROOT'] ?? '';
  $minimum=null;
  if (is_file($root.'/cli/joomla.php')) {
    if (preg_match("/JOOMLA_MINIMUM_PHP\\s*=\\s*'([0-9.]+)'/",file_get_contents($root.'/cli/joomla.php'),$matches)) $minimum=$matches[1];
  } elseif (is_file($root.'/wp-includes/version.php')) {
    if (preg_match("/required_php_version\\s*=\\s*'([0-9.]+)'/",file_get_contents($root.'/wp-includes/version.php'),$matches)) $minimum=$matches[1];
  }
  if ($minimum && version_compare(PHP_VERSION,$minimum,'<')) {
    http_response_code(503);header('Content-Type: text/plain; charset=utf-8');
    exit('Dieses CMS benötigt mindestens PHP '.$minimum.'. Bitte einen passenden PHP-Port wählen.');
  }
}
"""
    atomic(root/'tools/prepend.php',prefix);(root/'tools/prepend.php').chmod(0o644)
    # One local administrator session sees every project database on the shared server.
    encoded=json.dumps(password).replace('$','\\$')
    config="<?php\n$cfg['Servers']=[];$i=1;\n"
    for ident in dict.fromkeys([LEGACY]+[profile(p)['id'] for p in projects if p['storage']=='shared']):
        item=profile({'database_profile':ident})
        config+="$i="+str(item['server'])+";$cfg['Servers'][$i]=['auth_type'=>'config','host'=>'"+item['service']+"','user'=>'root','password'=>"+encoded+",'verbose'=>'"+item['engine']+' '+item['version']+"','AllowNoPassword'=>false];$i++;\n"
    active=[profile(p)['server'] for p in projects if p['storage']=='shared']
    default=1 if 1 in active else active[0] if active else 0
    config+="$cfg['ServerDefault']="+str(default)+";$cfg['PmaAbsoluteUri']='http://localhost:8091/';$cfg['AllowArbitraryServer']=false;\n"
    atomic(root/'pma/config.php',config);(root/'pma/config.php').chmod(0o644)
    return root/'compose.json'
