import json
import hashlib
import os
import re
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import zipfile
from catalog import digest, unpack
from runtime import PHP, compose, ports, slug, host_path, preview_ports
from store import DATA, db, project, redact

RUNTIME_DOCKERFILE = Path(__file__).resolve().parent.parent/'infra'/'runtime'/'Dockerfile'
if not RUNTIME_DOCKERFILE.exists(): RUNTIME_DOCKERFILE = Path('/runtime/Dockerfile')

def command(args, **kwargs):
    result=subprocess.run(args,capture_output=True,timeout=kwargs.pop('timeout',900),**kwargs)
    if result.returncode:
        def output(value):
            return value.decode(errors='replace') if isinstance(value,bytes) else (value or '')
        # APT and compiler diagnostics often go to stdout. Keeping stderr alone
        # hid the actual failure behind Docker's generic exit-code message.
        details='\n'.join(part for part in (output(result.stderr),output(result.stdout)) if part)
        raise RuntimeError(redact(details or 'Docker-Vorgang fehlgeschlagen.'))
    return result.stdout

def folder(p): return DATA/'projects'/p['slug']

def write_compose(p):
    if p.get('storage')=='shared':
        from shared_operations import context
        return context()[1]
    root=folder(p);root.mkdir(parents=True,exist_ok=True)
    (DATA/'extensions').mkdir(exist_ok=True)
    path=root/'compose.json'
    path.write_text(json.dumps(compose(p,os.environ.get('VMM_HOST_DATA',str(DATA))),indent=2));path.chmod(0o600)
    args=['docker','compose','-f',str(path)]
    preview=root/'preview.compose.json'
    if preview_ports(preview): args+=['-f',str(preview)]
    return args

def ensure_runtime(php):
    ports(php)
    source=RUNTIME_DOCKERFILE.read_bytes()
    revision=hashlib.sha256(source).hexdigest()
    try:
        actual=command(['docker','image','inspect','vmm-php:'+php,'--format','{{index .Config.Labels "vmm.runtime.revision"}}'],timeout=15).decode().strip()
        if actual==revision: return
    except Exception:
        pass
    command(['docker','build','-t','vmm-php:'+php,'--label','vmm.runtime.revision='+revision,'--build-arg','PHP_VERSION='+php,'-'],input=source,timeout=1800)

def php_service(p): return 'web' if p['storage']=='legacy' else 'php'+p['php'].replace('.','')

def exec_php(p,args,**kwargs):
    if p.get('storage')=='shared':
        from shared_operations import exec_php as execute
        return execute(p,args,**kwargs)
    return command(write_compose(p)+['exec','-T',php_service(p)]+args,**kwargs)

def write_tools(p):
    tools=folder(p)/'tools';tools.mkdir(parents=True,exist_ok=True)
    # Prepend applies to restored configurations too, before the CMS sees HTTPS.
    (tools/'prepend.php').write_text('''<?php
if (PHP_SAPI !== 'cli') {
  if (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https') {
    $_SERVER['HTTPS'] = 'on';
  }
}
''')
    for name in ('joomla-updates.php','extension-bridge.php','wordpress-extension-updates.php','cms-users.php','restore-backup.php'):
        shutil.copyfile(Path(__file__).parent/'tools'/name,tools/name)
    from shared_runtime import database_info
    info=database_info(p) if p.get('storage')=='shared' else {'host':'db','database':'website','user':'website','password':p['db_password']}
    (tools/'database.json').write_text(json.dumps(info))
    (tools/'database.json').chmod(0o600)

def prepare(p):
    root=folder(p);root.mkdir(parents=True,exist_ok=True);write_tools(p)
    site=root/'site'
    if site.exists() and any(site.iterdir()): return
    if p['restore']:
        raise ValueError('Akeeba-Projekt wird über den Backup-Import vorbereitet.')
    with db() as c: package=c.execute('SELECT * FROM packages WHERE id=?',(p['package_id'],)).fetchone()
    if not package: raise ValueError('CMS-Paket fehlt. Zuerst ein Installationspaket archivieren.')
    source=DATA/'packages'/package['filename']
    if digest(source)!=package['sha256']: raise ValueError('Prüfsumme des archivierten Pakets stimmt nicht.')
    staging=root/'preparing'
    if staging.exists(): shutil.rmtree(staging)
    unpack(source,staging)
    if site.exists(): site.rmdir()
    staging.rename(site)
    if p['cms']=='wordpress':
        conf="""<?php
$host = isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : 'PROJECT.vmm.test:8084';
if (!preg_match('/^PROJECT\\.vmm\\.test(?::[0-9]+)?$/D', $host)) $host='PROJECT.vmm.test:8084';
$scheme = !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https' : 'http';
define('WP_HOME', $scheme.'://'.$host);
define('WP_SITEURL', WP_HOME);
define('DB_NAME','website'); define('DB_USER','website'); define('DB_PASSWORD',__DB_PASSWORD__); define('DB_HOST','db');
define('DB_CHARSET','utf8mb4'); define('DB_COLLATE','');
SALTS
$table_prefix='wp_';
define('WP_DEBUG',false);
define('WP_ENVIRONMENT_TYPE','local');
if (!defined('ABSPATH')) define('ABSPATH',__DIR__.'/');
require_once ABSPATH.'wp-settings.php';
"""
        salts='\n'.join("define('"+key+"','"+secrets.token_hex(32)+"');" for key in ('AUTH_KEY','SECURE_AUTH_KEY','LOGGED_IN_KEY','NONCE_KEY','AUTH_SALT','SECURE_AUTH_SALT','LOGGED_IN_SALT','NONCE_SALT'))
        from shared_runtime import database_info
        info=database_info(p) if p.get('storage')=='shared' else {'database':'website','user':'website'}
        conf=conf.replace("define('DB_NAME','website')","define('DB_NAME','"+info['database']+"')").replace("define('DB_USER','website')","define('DB_USER','"+info['user']+"')")
        (site/'wp-config.php').write_text(conf.replace('PROJECT',p['slug']).replace('__DB_PASSWORD__',json.dumps(p['db_password'])).replace('SALTS',salts))
        mu=site/'wp-content'/'mu-plugins';mu.mkdir(parents=True,exist_ok=True)
        (mu/'vmm-local.php').write_text("<?php\nadd_filter('pre_wp_mail', function(){ return false; });\n")
    # Apache can write uploads and finish the Joomla installer.
    for directory, dirs, files in os.walk(site):
        os.chmod(directory,0o777)
        for name in files: os.chmod(Path(directory)/name,0o666)

def compatible(p,php):
    site=folder(p)/'site'
    source=site/'cli'/'joomla.php' if p['cms']=='joomla' else site/'wp-includes'/'version.php'
    if not source.is_file(): return
    pattern=r"JOOMLA_MINIMUM_PHP\s*=\s*'([0-9.]+)'" if p['cms']=='joomla' else r"\$required_php_version\s*=\s*'([0-9.]+)'"
    match=re.search(pattern,source.read_text(errors='replace'))
    if match and tuple(map(int,php.split('.'))) < tuple(map(int,match.group(1).split('.')[:2])):
        raise ValueError('Dieses CMS benötigt mindestens PHP '+match.group(1)+'. Gewählt: '+php+'.')


def transition(name,action,php=None):
    p=project(name)
    try:
        if p.get('storage')=='shared':
            from shared_operations import transition as shared_transition
            return shared_transition(p,action,php)
        if action=='start':
            with db() as c: c.execute("UPDATE projects SET status='starting',error=NULL WHERE slug=?",(name,))
            if p['storage']!='legacy':
                prepare(p);compatible(p,php or p['php']);ensure_runtime(php or p['php'])
            args=write_compose(p)
            target='web' if p['storage']=='legacy' else 'php'+(php or p['php']).replace('.','')
            command(args+['up','-d','--wait','--wait-timeout','180',target,'phpmyadmin'],timeout=1800)
            if php:
                with db() as c: c.execute('UPDATE projects SET php=? WHERE slug=?',(php,name))
            state='running'
        else:
            with db() as c: c.execute("UPDATE projects SET status='stopping' WHERE slug=?",(name,))
            # --profile '*' includes every PHP variant previously started.
            command(write_compose(p)+['--profile','*','stop'])
            state='stopped'
        with db() as c: c.execute('UPDATE projects SET status=?,error=NULL WHERE slug=?',(state,name))
        return 'Projekt '+('gestartet.' if action=='start' else 'gestoppt.')
    except Exception as e:
        with db() as c: c.execute('UPDATE projects SET status=?,error=? WHERE slug=?',('running' if p['status']=='running' else 'error',redact(e),name))
        raise

def snapshot(name):
    p=project(name)
    if p.get('storage')=='shared':
        from shared_operations import snapshot as shared_snapshot
        return shared_snapshot(p)
    if p['storage']=='legacy': raise ValueError('Export älterer Projekte mit Docker-Volumes ist noch nicht unterstützt.')
    if p['status']!='running': raise ValueError('Projekt für die Datenbanksicherung zuerst starten.')
    root=DATA/'exports';root.mkdir(exist_ok=True)
    ident=name+'-'+str(int(time.time()))+'-'+secrets.token_hex(3)
    running=command(write_compose(p)+['--profile','*','ps','--services','--status','running'],timeout=20).decode().splitlines()
    web=[s for s in running if s=='web' or s.startswith('php')]
    paused=False
    try:
        if web:
            command(write_compose(p)+['pause']+web,timeout=30);paused=True
        # DB password stays inside the container, never in host arguments.
        dump=command(write_compose(p)+['exec','-T','db','sh','-c','exec mariadb-dump -uwebsite -p"$MARIADB_PASSWORD" --single-transaction --routines --triggers website'],timeout=300)
        target=root/(ident+'.zip')
        temp=target.with_suffix('.partial')
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('database.sql',dump)
            z.writestr('project.json',json.dumps({k:p[k] for k in ('slug','cms','php','version')},indent=2))
            for path in (folder(p)/'site').rglob('*'):
                if path.is_file() and not path.is_symlink(): z.write(path,'site/'+str(path.relative_to(folder(p)/'site')))
        temp.rename(target)
        return 'Sicherung erstellt: '+target.name
    finally:
        if paused: command(write_compose(p)+['unpause']+web,timeout=30)



def install_extension(name,ident):
    p=project(name)
    if p['status']!='running': raise ValueError('Projekt zuerst starten.')
    with db() as c: ext=c.execute('SELECT * FROM extensions WHERE id=?',(ident,)).fetchone()
    if not ext or ext['cms']!=p['cms']: raise ValueError('Erweiterung passt nicht zum CMS.')
    if digest(DATA/'extensions'/ext['filename'])!=ext['sha256']: raise ValueError('Paket-Prüfsumme stimmt nicht.')
    if p['cms']=='joomla' and not (folder(p)/'site'/'configuration.php').is_file():
        raise ValueError('Zuerst den Joomla-Installationsassistenten abschließen.')
    compatible(p,p['php'])
    snapshot(name)
    path='/vmm-extensions/'+ext['filename']
    if p['cms']=='wordpress':
        kind='theme' if ext['kind']=='theme' else 'plugin'
        exec_php(p,['wp','--allow-root',kind,'install',path,'--force'],timeout=300)
    else:
        # Joomla extracts next to the package, so copy out of the read-only catalogue.
        staging='/tmp/vmm-install-'+ident
        exec_php(p,['php','-r','if (!is_dir($argv[1])) mkdir($argv[1],0700,true); if(!copy($argv[2],$argv[1]."/package.zip"))exit(1);',staging,path])
        try:
            exec_php(p,['php','cli/joomla.php','extension:install','--path='+staging+'/package.zip'],timeout=300)
        finally:
            exec_php(p,['php','-r','function clean($p){if(is_link($p)||is_file($p)){unlink($p);return;}if(is_dir($p)){foreach(scandir($p) as $n)if($n!=="."&&$n!=="..")clean($p."/".$n);rmdir($p);}} clean($argv[1]);',staging])
    with db() as c: c.execute("UPDATE project_extensions SET status='installed' WHERE project=? AND extension=?",(name,ident))
    return 'Erweiterung installiert. Aktivierung und Lizenzkonfiguration im CMS prüfen.'


def wp_updates(name,apply=False):
    p=project(name)
    if p['status']!='running': raise ValueError('Projekt zuerst starten.')
    compatible(p,p['php'])
    if apply: snapshot(name)
    if p['cms']=='joomla':
        write_tools(p)
        args=['php','/vmm-tools/joomla-updates.php','vmm:updates']
        if apply: args.append('--apply')
        return exec_php(p,args,timeout=900).decode(errors='replace')[-3000:]
    parts=[]
    for kind in ('plugin','theme'):
        args=['wp','--allow-root',kind]
        args+=['update','--all'] if apply else ['list','--update=available','--format=table']
        output=exec_php(p,args,timeout=600).decode(errors='replace')
        parts.append(output[-1500:])
    return '\n'.join(parts) or 'Keine Updates verfügbar.'


def restore_akeeba(name,backup_id,archive,password=''):
    import re
    p=project(name)
    if not re.fullmatch(r'[a-f0-9]{24}',backup_id): raise ValueError('Ungültige Backup-Gruppe.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.(jpa|jps|zip)',archive,re.I): raise ValueError('Hauptarchiv auswählen: JPA, JPS oder ZIP.')
    inputs=DATA/'backups'/backup_id
    if not (inputs/archive).is_file(): raise ValueError('Backup-Datei fehlt.')
    import kickstart_service
    # Resolve the selected release inside the job so download errors remain visible.
    kickstart=None
    site=folder(p)/'site'
    resume=p.get('restore_phase')=='extracted' and p.get('backup_group')==backup_id and p.get('backup_archive')==archive
    if site.exists() and any(site.iterdir()) and not resume: raise ValueError('Wiederherstellung nur in einem leeren neuen Projekt möglich.')
    site.mkdir(parents=True,exist_ok=True)
    # Extractor has no DAC override capability and may not own the host mount.
    site.chmod(0o777)
    write_tools(p)
    try:
        with db() as c: c.execute("UPDATE projects SET status='preparing',error=NULL WHERE slug=?",(name,))
        ensure_runtime(p['php'])
        if resume:
            from backup_service import restore
            return restore(name)
        kickstart=kickstart_service.ensure(p.get('kickstart','auto'),p['php'])
        host=host_path(os.environ.get('VMM_HOST_DATA',str(DATA)))
        script=folder(p)/'tools'/'extract.php'
        script.write_text("<?php\n$input=json_decode(stream_get_contents(STDIN),true); $argv=['kickstart.php','/vmm-input/'.$input['archive'],'/var/www/html','--silent']; if($input['password']!=='') $argv[]='--password='.$input['password']; $argc=count($argv); $_SERVER['argv']=$argv; $_SERVER['argc']=$argc; require '/vmm-kickstart/kickstart.php';\n")
        command(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,size=256m',
            '--mount','type=bind,source='+host+'/projects/'+name+'/site,target=/var/www/html',
            '--mount','type=bind,source='+host+'/projects/'+name+'/tools,target=/vmm-tools,readonly',
            '--mount','type=bind,source='+host+'/backups/'+backup_id+',target=/vmm-input,readonly',
            '--mount','type=bind,source='+host+'/tools/'+kickstart.relative_to(DATA/'tools').as_posix()+',target=/vmm-kickstart/kickstart.php,readonly',
            '-i','vmm-php:'+p['php'],'php','/vmm-tools/extract.php'],input=json.dumps({'archive':archive,'password':password}).encode(),timeout=1800)
        if not (site/'installation'/'index.php').exists(): raise ValueError('Das Archiv enthält keinen unterstützten Akeeba-Wiederherstellungsassistenten.')
        for filename in ('.htaccess','.user.ini','php.ini'):
            original=site/filename
            if original.exists(): original.rename(site/(filename+'.vmm-original'))
        for directory, dirs, files in os.walk(site):
            for entry in dirs:
                if (Path(directory)/entry).is_symlink():raise ValueError('Backup enthält symbolische Verknüpfungen. Bitte als reguläre Dateien sichern.')
            os.chmod(directory,0o777)
            for filename in files:
                if (Path(directory)/filename).is_symlink():raise ValueError('Backup enthält symbolische Verknüpfungen. Bitte als reguläre Dateien sichern.')
                os.chmod(Path(directory)/filename,0o666)
        with db() as c:c.execute("UPDATE projects SET restore_phase='extracted',backup_group=?,backup_archive=? WHERE slug=?",(backup_id,archive,name))
        from backup_service import restore
        return restore(name)
    except Exception as e:
        message=redact(str(e).replace(password,'[redacted]') if password else e)
        with db() as c: c.execute("UPDATE projects SET status='error',error=? WHERE slug=?",(message,name))
        # Keep extracted data for diagnosis; never overwrite it on retry.
        raise ValueError('Akeeba-Wiederherstellung fehlgeschlagen: '+message) from None


def finalize_restore(name):
    import re
    p=project(name);site=folder(p)/'site'
    if (site/'installation').exists(): raise ValueError('Zuerst den Akeeba-Assistenten abschließen und dessen Installationsverzeichnis entfernen lassen.')
    if p['cms']=='joomla':
        path=site/'configuration.php'
        if not path.exists(): raise ValueError('Joomla-Konfiguration fehlt.')
        content=path.read_text()
        content=re.sub(r"(public\s+\$live_site\s*=\s*)[^;]*;",r"\1'';",content)
        content=re.sub(r"(public\s+\$force_ssl\s*=\s*)[^;]*;",r'\g<1>0;',content)
        content=re.sub(r"(public\s+\$mailonline\s*=\s*)[^;]*;",r'\g<1>false;',content)
        path.write_text(content)
    else:
        if not (site/'wp-config.php').exists(): raise ValueError('WordPress-Konfiguration fehlt.')
        mu=site/'wp-content'/'mu-plugins';mu.mkdir(parents=True,exist_ok=True)
        (mu/'vmm-local.php').write_text("""<?php
function vmm_local_origin($value) {
 if (PHP_SAPI === 'cli') return $value;
 $host = $_SERVER['HTTP_HOST'] ?? '';
 if (!preg_match('/^[a-z][a-z0-9-]*\\.vmm\\.test(?::[0-9]+)?$/D',$host)) return $value;
 return ((!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https://' : 'http://').$host;
}
add_filter('option_home','vmm_local_origin',PHP_INT_MAX);
add_filter('option_siteurl','vmm_local_origin',PHP_INT_MAX);
add_filter('pre_wp_mail', function(){ return false; });
""")
    with db() as c: c.execute("UPDATE projects SET restore=0,restore_phase='complete' WHERE slug=?",(name,))
    return 'Lokale URL-/HTTPS-Konfiguration angewendet. Absolute Inhaltslinks und externe Integrationen im CMS prüfen.'


def reconcile():
    """Refresh status after external Docker changes, without touching active jobs."""
    from store import records
    try:
        output=command(['docker','ps','-a','--filter','label=com.docker.compose.project','--format','{{.Label "com.docker.compose.project"}}\t{{.Label "com.docker.compose.service"}}\t{{.State}}'],timeout=8).decode()
    except Exception:
        return
    states={}
    for line in output.splitlines():
        parts=line.split('\t')
        if len(parts)==3: states.setdefault(parts[0],{})[parts[1]]=parts[2]
    with db() as c:
        for p in records('projects'):
            if p['status'] in ('starting','stopping','preparing','error') or p.get('restore'): continue
            if c.execute("SELECT 1 FROM jobs WHERE resource=? AND status IN ('queued','running')",(p['slug'],)).fetchone(): continue
            if p.get('storage')=='shared':
                services=states.get('vmm-runtime',{})
                running=services.get('db')=='running' and (DATA/'shared/state'/(p['slug']+'.enabled')).is_file()
                c.execute('UPDATE projects SET status=? WHERE slug=?',('running' if running else 'stopped',p['slug']))
                continue
            services=states.get('vmm-'+p['slug'],{})
            running=services.get('db')=='running' and any(v=='running' for k,v in services.items() if k=='web' or k.startswith('php'))
            c.execute('UPDATE projects SET status=? WHERE slug=?',('running' if running else 'stopped',p['slug']))


def monitor():
    try:
        from shared_operations import sync
        sync()
    except Exception:pass
    while True:
        try:
            reconcile()
            from extension_service import queue_pending
            queue_pending()
        except Exception: pass
        time.sleep(15)
