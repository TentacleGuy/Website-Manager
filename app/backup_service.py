"""Detect the extracted CMS and restore with the installer shipped in its backup."""
import json
import re
import shutil
from store import db, project


def detect(site):
    wordpress=(site/'wp-includes/version.php').is_file() and (site/'wp-config.php').is_file()
    joomla=(site/'configuration.php').is_file() and ((site/'administrator').is_dir() or (site/'libraries').is_dir())
    if wordpress==joomla:raise ValueError('Backup-CMS nicht eindeutig erkannt. Unterstützt werden Joomla und WordPress.')
    if wordpress:
        content=(site/'wp-includes/version.php').read_text(errors='replace')
        match=re.search(r"\$wp_version\s*=\s*['\"]([^'\"]+)",content)
        return 'wordpress',match[1] if match else 'Backup'
    for path in ('administrator/manifests/files/joomla.xml','libraries/src/Version.php','libraries/cms/version/version.php'):
        file=site/path
        if not file.is_file():continue
        text=file.read_text(errors='replace');match=re.search(r'<version>([^<]+)</version>',text)
        if match:return 'joomla',match[1]
        major=re.search(r"(?:MAJOR_VERSION\s*=|\$RELEASE\s*=)\s*['\"]?([\d.]+)",text)
        minor=re.search(r'MINOR_VERSION\s*=\s*(\d+)',text);patch=re.search(r'PATCH_VERSION\s*=\s*(\d+)',text)
        if major:return 'joomla','.'.join([major[1]]+([minor[1],patch[1]] if minor and patch else []))
    return 'joomla','Backup'


def restore(name):
    import operations as op
    from shared_operations import ensure_database,rewrite_database
    from shared_runtime import database_info
    p=project(name);site=op.folder(p)/'site';cms,version=detect(site)
    with db() as c:c.execute('UPDATE projects SET cms=?,version=? WHERE slug=?',(cms,version,name))
    p=project(name)
    from compatibility import resolve
    source_php=None
    extra=site/'installation/extrainfo.json'
    if extra.is_file():
        try:
            match=re.match(r'^(\d+\.\d+)',str(json.loads(extra.read_text()).get('php_version','')))
            if match:source_php=match[1]
        except (ValueError,OSError):pass
    resolve(p,site,source_php)
    op.compatible(p,p['php']);op.ensure_runtime(p['php']);op.check_modules(p,p['php']);ensure_database(p)
    url='http://'+name+'.vmm.test:'+str(op.ports(p['php'])[0])
    op.write_tools(p)
    native=(site/'installation/src/Framework/Cli/InstallationQueue.php').is_file()
    original_config=(site/'wp-config.php').read_text() if cms=='wordpress' else None
    if native:
        op.exec_php(p,['php','installation/cli.php','config:make'],timeout=300)
    result=op.exec_php(p,['php','/vmm-tools/restore-backup.php'],input=json.dumps({'database':database_info(p),'url':url}).encode(),timeout=1800)
    expected=b'VMM_CONFIGURED' if native else b'VMM_DATABASE_RESTORED'
    if expected not in result:raise ValueError('Akeeba-Installer hat die automatische Wiederherstellung nicht bestätigt.')
    if native:
        output=op.exec_php(p,['php','installation/cli.php','execute'],timeout=1800)
        if b'Restoration complete' not in output:raise ValueError('Akeeba-Installer meldet keinen abgeschlossenen Import.')
    if original_config is not None:
        written=(site/'wp-config.php').read_text()
        # Some installer versions assume one define per line and truncate custom configs.
        if '<?php' not in written or any(not re.search(r"define\s*\(\s*['\"]"+key+r"['\"]\s*,",written) for key in ('DB_NAME','DB_USER','DB_PASSWORD','DB_HOST')):
            (site/'wp-config.php').write_text(original_config)
    rewrite_database(p)
    if cms=='joomla':
        file=site/'configuration.php';content=file.read_text()
        root='/vmm-projects/'+name+'/site'
        for key,value in (('log_path',root+'/administrator/logs'),('tmp_path',root+'/tmp')):
            content=re.sub(r'(public\s+\$'+key+r'\s*=\s*)[^;]*;',lambda m:m[1]+repr(value)+';',content)
        file.write_text(content)
    else:
        # wp-cli handles serialized data and quoted URLs safely, including old WP_HOME constants.
        source=op.exec_php(p,['wp','--allow-root','--skip-plugins','--skip-themes','option','get','siteurl']).decode().strip()
        if source and source!=url:
            op.exec_php(p,['wp','--allow-root','--skip-plugins','--skip-themes','search-replace',source,url,'--all-tables-with-prefix','--skip-columns=guid'],timeout=900)
        op.exec_php(p,['wp','--allow-root','--skip-plugins','--skip-themes','option','update','siteurl',url])
        op.exec_php(p,['wp','--allow-root','--skip-plugins','--skip-themes','option','update','home',url])
        conf=site/'wp-config.php'
        for key,value,raw in (('WP_HOME',url,False),('WP_SITEURL',url,False),('FORCE_SSL_ADMIN','false',True),('WP_ENVIRONMENT_TYPE','local',False)):
            text=conf.read_text()
            if re.search(r"define\s*\(\s*['\"]"+key+r"['\"]\s*,",text):
                args=['wp','--allow-root','config','set',key,value,'--type=constant']
                if raw:args.append('--raw')
                op.exec_php(p,args)
            else:
                # Custom configs may omit wp-cli's standard insertion comment.
                literal=value if raw else json.dumps(value)
                conf.write_text(text.replace('<?php',"<?php\ndefine('"+key+"',"+literal+");\n",1))
    # Only remove the installer after all restoration and configuration steps succeeded.
    shutil.rmtree(site/'installation')
    op.finalize_restore(name)
    op.transition(name,'start')
    return 'Backup vollständig wiederhergestellt. '+cms.title()+' '+version+' erkannt; Datenbank, lokale URLs und Konfiguration eingerichtet.'
