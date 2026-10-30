"""Simple library operations; project-backed sources resolve fresh links on every use."""
import html
import json
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import extension_service as ext
from store import DATA, LOCK, db, project


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', html.unescape(re.sub('<[^>]+>', '', value)).lower())


def detect_origin(info):
    if info['cms'] != 'wordpress' or info['source_type'] != 'upload':
        return info
    hint=info.get('url','')
    parsed=urlsplit(hint)
    if hint and parsed.hostname not in ('wordpress.org','www.wordpress.org','w.org'):
        return info  # Update URI is an identity, not a metadata endpoint.
    if hint and parsed.hostname in ('wordpress.org','www.wordpress.org','w.org'):
        match=re.search(r'/(?:plugins?|themes)/([a-z0-9-]+)',parsed.path)
        if match:info={**info,'element':match[1]}
    kind='themes' if info['kind']=='theme' else 'plugins'
    url='https://api.wordpress.org/'+kind+'/info/1.2/?'+urlencode({'action':('theme' if kind=='themes' else 'plugin')+'_information','request[slug]':info['element']})
    try:
        with ext.remote(url) as response:data=json.loads(response.read(4*1024*1024))
        if isinstance(data,dict) and data.get('download_link') and normalized(data.get('name',''))==normalized(info['name']):
            author=info.get('author','')
            if hint or (author and normalized(author)==normalized(data.get('author',''))):
                return {**info,'source_type':'wordpress_org','url':''}
    except (ValueError,OSError):pass
    return info


def adopt(info):
    existing=next((s for s in ext.sources() if s['cms']==info['cms'] and s['kind']==info['kind'] and s['element']==info['element']),None)
    if existing:
        if (existing['source_type']=='upload' and info['source_type']!='upload') or (existing['source_type']=='project' and info['source_type']=='project'):
            return ext.save_source({**existing,**info,'id':existing['id'],'provider':existing['provider']})
        return existing['id']
    return ext.save_source({**info,'provider':'custom'})


def upload(path):
    info=ext.inspect_upload(path)
    ident=adopt(detect_origin(info))
    package=ext.register_package(path,ext.source(ident),info['version'])
    return {'id':package,'source':ident,'name':info['name'],'cms':info['cms'],'message':'Paket erkannt und gespeichert.'}


def edit(ident,body):
    s=ext.source(ident)
    name=str(body.get('name',s['name'])).strip()
    if not name or len(name)>200:raise ValueError('Einen Namen mit höchstens 200 Zeichen angeben.')
    if body.get('cms',s['cms'])!=s['cms']:raise ValueError('Das CMS wird aus dem Paket bestimmt. Für ein anderes CMS das passende Paket hochladen.')
    s['name']=name
    if 'key' in body:
        key=body['key']
        if not isinstance(key,str) or len(key)>4096:raise ValueError('Ungültiger Lizenzschlüssel.')
        old=s.get('license')
        if key.strip():
            license_body={'provider':s['provider'],'label':name+' · global','source':ident,'key':key}
            if old and ext.resolve_license(old).get('source')==ident:license_body['id']=old
            s['license']=ext.save_license(license_body)
        else:s['license']=''
    ext.save_source(s)
    return {'message':'Erweiterung gespeichert.'}


def package_file(ident):
    with db() as c:row=c.execute('SELECT * FROM extensions WHERE id=? AND archived=1',(ident,)).fetchone()
    if not row:raise ValueError('Gespeichertes Paket nicht gefunden.')
    file=DATA/'extensions'/row['filename']
    if file.is_symlink() or not file.is_file():raise ValueError('Paketdatei fehlt.')
    return dict(row),file


def delete_package(ident):
    with LOCK,db() as c:
        row,file=package_file(ident)
        if c.execute("SELECT 1 FROM jobs WHERE status IN ('running','queued') AND (resource=? OR kind IN ('extensions','install-extension','akeeba','provision'))",('extension-'+row['source_id'],)).fetchone():
            raise ValueError('Das Paket wird möglicherweise noch verwendet. Bitte den laufenden Vorgang abwarten.')
        file.unlink()
        c.execute('UPDATE extensions SET archived=0 WHERE id=?',(ident,))
    return {'message':'Paket gelöscht. Installierte Websites bleiben erhalten.'}


def bridge(name,action='list',key='',download_key=''):
    import operations as op
    p=project(name)
    if p.get('restore') or p['status']!='running':raise ValueError('Das vollständig eingerichtete Projekt zuerst starten.')
    op.write_tools(p)
    payload={'action':action,'key':key,'download_key':download_key,'token':secrets.token_hex(12)}
    args=['wp','--allow-root','--quiet','eval-file','/vmm-tools/library-project.php'] if p['cms']=='wordpress' else ['php','/vmm-tools/library-project.php']
    raw=op.exec_php(p,args,input=json.dumps(payload).encode(),timeout=300)
    # A distinct marker isolates the protocol from incidental plugin output.
    try:return json.loads(raw.decode(errors='replace').rsplit('VMM_LIBRARY_JSON:',1)[1])
    except (ValueError,IndexError):raise ValueError('Das CMS hat keine gültigen Paketinformationen geliefert.') from None


def candidates(name):
    rows=bridge(name)
    return [{k:r.get(k) for k in ('key','name','cms','kind','element','version','latest','can_download','origin','has_key')} for r in rows]


def project_key(name,ident,body):
    p=project(name);s=ext.source(ident)
    if p['cms']!=s['cms']:raise ValueError('Erweiterung passt nicht zum CMS.')
    key=body.get('key','')
    if not isinstance(key,str) or len(key)>4096:raise ValueError('Ungültiger Lizenzschlüssel.')
    existing=next((l for l in ext.licenses() if l.get('project')==name and l.get('source')==ident),None)
    if key.strip():
        value={'provider':s['provider'],'label':s['name']+' · '+name,'source':ident,'project':name,'key':key}
        if existing:value['id']=existing['id']
        lic=ext.save_license(value)
    else:
        lic=s.get('license') or None
        if existing:
            with db() as c:
                c.execute('UPDATE extension_plans SET license=? WHERE license=?',(lic,existing['id']))
                c.execute('UPDATE project_extensions SET license=? WHERE license=?',(lic,existing['id']))
                c.execute('DELETE FROM licenses WHERE id=?',(existing['id'],))
    with db() as c:c.execute('UPDATE extension_plans SET license=? WHERE project=? AND source=?',(lic,name,ident))
    return {'message':'Projektschlüssel gespeichert.' if key.strip() else 'Projekt verwendet wieder den globalen Schlüssel.'}


def import_project(name,key,download=True):
    p=project(name)
    row=next((r for r in bridge(name) if r['key']==key),None)
    if not row:raise ValueError('Erweiterung ist im Projekt nicht mehr vorhanden.')
    if not row.get('can_download'):raise ValueError('Noch keine nutzbare Update- oder Downloadquelle erkannt. Zuerst die Herstelleranbindung im CMS einrichten oder ein ZIP-Paket hochladen.')
    info={'name':row['name'],'cms':p['cms'],'kind':row['kind'],'element':row['element'],'source_type':'project','origin_project':name,'origin_key':key,'url':'','auth_type':'none'}
    ident=adopt(info)
    # Preserve native site credentials in their project; never promote them globally.
    if row.get('license_key'):project_key(name,ident,{'key':row['license_key']})
    if download:
        s=ext.source(ident)
        license_id=next((l['id'] for l in ext.licenses() if l.get('project')==name and l.get('source')==ident),None)
        ext.download_package(ident,license_id=license_id,p=p)
    return row['name']+(' übernommen; neuestes Paket gespeichert.' if download else ' und Updatequelle übernommen.')


def source_key(s):
    own=next((l for l in ext.licenses() if l.get('project')==s.get('origin_project') and l.get('source')==s['id']),None)
    return own.get('key','') if own else ext.license_value(s.get('license'),s['provider'],source_id=s['id']).get('key','')


def release(s,download=False,key=''):
    if s['cms']=='joomla':
        row=bridge(s['origin_project'],'resolve',s['origin_key'])
        params=dict(parse_qsl(row.get('extra_query','')))
        if key:
            parameter=next((k for k in ('dlid','download_id','downloadid','apikey','api_key','key') if k in params),None)
            if parameter:params[parameter]=key
        def authorized(url):
            parsed=urlsplit(url);query=dict(parse_qsl(parsed.query));query.update(params)
            return ext.safe_url(urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode(query),'')))
        with ext.remote(authorized(row['url'])) as response:data=response.read(4*1024*1024+1)
        if len(data)>4*1024*1024:raise ValueError('Updatequelle ist zu groß.')
        versions=ext.parse_updates(data,row['url'])
        versions=[v for v in versions if v.get('stability','stable').lower()=='stable' and not re.search('alpha|beta|rc|dev',v['version'],re.I)]
        if not versions:raise ValueError('Keine stabile Paketversion verfügbar.')
        latest=versions[0]
        if not download:return [{**latest,'url':''}]
        import tempfile
        with tempfile.TemporaryDirectory(dir=DATA) as tmp:
            file=Path(tmp)/'package.zip'
            with ext.remote(authorized(latest['url'])) as response,file.open('wb') as out:
                size=0
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    size+=len(chunk)
                    if size>ext.MAX_ARCHIVE:raise ValueError('Paket zu groß.')
                    out.write(chunk)
            if latest.get('sha256') and ext.digest(file).lower()!=latest['sha256'].lower():raise ValueError('Hersteller-Prüfsumme stimmt nicht.')
            info=ext.inspect_upload(file)
            if info['cms']!=s['cms'] or info['kind']!=s['kind'] or info['element']!=s['element']:raise ValueError('Heruntergeladenes Paket passt nicht zur ausgewählten Erweiterung.')
            return ext.register_package(file,s,info['version'])
    row=bridge(s['origin_project'],'download' if download else 'resolve',s['origin_key'],key)
    if not row.get('latest'):raise ValueError('Das Projekt meldet keine aktuelle Paketversion. Lizenz und Updateanbindung im CMS prüfen.')
    if download:
        token=row.get('token','')
        if not re.fullmatch(r'[a-f0-9]{24}',token):raise ValueError('Ungültige Downloadantwort.')
        file=DATA/'projects'/s['origin_project']/'tools'/('library-'+token+'.zip')
        try:
            if file.is_symlink() or not file.is_file() or file.stat().st_size>ext.MAX_ARCHIVE:raise ValueError('Das CMS hat kein gültiges Paket bereitgestellt.')
            info=ext.inspect_upload(file)
            if info['cms']!=s['cms'] or info['kind']!=s['kind'] or info['element']!=s['element']:
                raise ValueError('Heruntergeladenes Paket passt nicht zur ausgewählten Erweiterung.')
            if ext.version_key(info['version'])!=ext.version_key(row['latest']):raise ValueError('Paketversion stimmt nicht mit der vom CMS gemeldeten Version überein.')
            return ext.register_package(file,s,info['version'])
        finally:file.unlink(missing_ok=True)
    return [{'version':row['latest'],'url':'','stability':'stable'}]
