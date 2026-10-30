"""Central sources, version archive, credentials and project installations."""
import base64
import json
import re
import secrets
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler
from store import DATA, LOCK, db, project, cipher
import providers
from catalog import valid_cms, validate_zip, digest, MAX_ARCHIVE


def decode_secret(text):
    try:
        value=json.loads(text)
        return value if isinstance(value,dict) else {'key':str(value)}
    except (ValueError, TypeError):
        raw=cipher().decrypt(text.encode()).decode()
        try:
            value=json.loads(raw)
            return value if isinstance(value,dict) else {'key':raw}
        except ValueError:return {'key':raw}


def init():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS extension_sources (id TEXT PRIMARY KEY, config TEXT NOT NULL, available TEXT DEFAULT \'[]\', checked INTEGER, error TEXT)')
        cols={r['name'] for r in c.execute('PRAGMA table_info(extensions)')}
        if 'source_id' not in cols:c.execute('ALTER TABLE extensions ADD COLUMN source_id TEXT')
        if 'archived' not in cols:c.execute('ALTER TABLE extensions ADD COLUMN archived INTEGER DEFAULT 1')
        c.execute('CREATE TABLE IF NOT EXISTS extension_plans (project TEXT REFERENCES projects(slug), source TEXT REFERENCES extension_sources(id), license TEXT REFERENCES licenses(id), version TEXT, status TEXT, error TEXT, PRIMARY KEY(project,source))')
        c.execute("UPDATE extension_plans SET status='error',error='Manager während Installation beendet. Bitte erneut installieren.' WHERE status='installing'")
        for table in ('licenses','credentials'):
            for row in c.execute('SELECT id,secret FROM '+table).fetchall():
                c.execute('UPDATE '+table+' SET secret=? WHERE id=?',(json.dumps(decode_secret(row['secret']),ensure_ascii=False),row['id']))


def resolve_license(ident,seen=None):
    seen=set() if seen is None else set(seen)
    if ident in seen:raise ValueError('Zyklische Lizenzvererbung ist nicht erlaubt.')
    seen.add(ident)
    with db() as c:row=c.execute('SELECT * FROM licenses WHERE id=?',(ident,)).fetchone()
    if not row:raise ValueError('Lizenz nicht gefunden.')
    raw=decode_secret(row['secret']);parent=raw.get('parent','');base=resolve_license(parent,seen) if parent else {}
    value={**base,**raw,'provider':row['provider'],'label':row['label'],'id':row['id'],'created':row['created']}
    if parent:
        for key in ('username','password','owner'):
            if not raw.get(key):value[key]=base.get(key,'')
        value['extra']={**base.get('extra',{}),**raw.get('extra',{})}
        if not raw.get('key'):value['key']=base.get('key','')
        if not raw.get('source'):value['source']=base.get('source','')
    value['overrides']=raw
    return value


def licenses():
    with db() as c:ids=[r['id'] for r in c.execute('SELECT id FROM licenses ORDER BY created DESC')]
    return [resolve_license(ident) for ident in ids]


def save_license(body):
    provider=str(body.get('provider','custom')).strip();label=str(body.get('label','')).strip()
    if not provider or len(provider)>100 or not label:raise ValueError('Anbieter und Bezeichnung angeben.')
    values={k:body.get(k,'') for k in ('key','username','password')}
    if any(not isinstance(v,str) or len(v)>4096 for v in values.values()):raise ValueError('Ungültige Zugangsdaten.')
    values['key']=values['key'].strip()
    values['username']=values['username'].strip()
    extra=body.get('extra',{})
    if isinstance(extra,str):
        try:extra=json.loads(extra or '{}')
        except ValueError:raise ValueError('Weitere Zugangsdaten müssen ein JSON-Objekt sein.')
    if not isinstance(extra,dict) or any(not isinstance(v,str) for v in extra.values()):raise ValueError('Weitere Zugangsdaten als Name/Text-Paare angeben.')
    values['extra']=extra
    values['parent']=str(body.get('parent',''))
    values['owner']=str(body.get('owner','')).strip()
    if values['parent']:
        parent=resolve_license(values['parent'])
        if parent.get('parent'):raise ValueError('Seitenschlüssel direkt unter einer Hauptlizenz anlegen.')
        if parent['provider']!=provider:raise ValueError('Hauptlizenz und Anbieter passen nicht zusammen.')
        if values['parent']==body.get('id'):raise ValueError('Lizenz darf nicht ihr eigenes Elternobjekt sein.')
    values['project']=str(body.get('project','')).strip()
    values['site']=str(body.get('site','')).strip()
    values['source']=str(body.get('source','')).strip()
    if values['project'] and not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',values['project']):raise ValueError('Projektbindung als gültigen Projektnamen angeben.')
    if values['parent'] and not values['project']:raise ValueError('Für einen Seitenschlüssel das Projekt angeben.')
    if values['site']:
        url=urlsplit(values['site'])
        if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:raise ValueError('Website muss eine HTTP-/HTTPS-Adresse ohne Zugangsdaten sein.')
    if values['source'] and source(values['source'])['provider']!=provider:raise ValueError('Erweiterung und Anbieter passen nicht zusammen.')

    ident=body.get('id') or secrets.token_hex(12)
    with db() as c:
        if body.get('id') and not c.execute('SELECT 1 FROM licenses WHERE id=?',(ident,)).fetchone():raise ValueError('Lizenz nicht gefunden.')
        if body.get('id'):
            for plan in c.execute('SELECT project,source FROM extension_plans WHERE license=?',(ident,)):
                if values['project'] and values['project']!=plan['project'] or values['source'] and values['source']!=plan['source']:raise ValueError('Lizenz ist bereits anderen Projekten/Erweiterungen zugeordnet. Dafür einen separaten Zugang anlegen.')
            for entry in c.execute('SELECT id,config FROM extension_sources'):
                cfg=json.loads(entry['config'])
                if cfg.get('license')==ident and (values['project'] or values['source'] and values['source']!=entry['id']):raise ValueError('Diese Lizenz wird als globale Standardlizenz verwendet. Zuerst den Standard in der Erweiterungsquelle ändern.')
        c.execute('INSERT INTO licenses VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,label=excluded.label,secret=excluded.secret',(ident,provider,label,json.dumps(values),int(time.time())))
    return ident


def license_value(ident,provider=None,project_name=None,source_id=None):
    if not ident:return {'key':'','username':'','password':'','extra':{}}
    with db() as c:row=c.execute('SELECT * FROM licenses WHERE id=?',(ident,)).fetchone()
    if not row or provider and row['provider']!=provider:raise ValueError('Lizenz passt nicht zum Anbieter.')
    value=resolve_license(ident)
    if project_name is not None and value.get('project') and value['project']!=project_name:raise ValueError('Dieser Schlüssel ist an ein anderes Projekt gebunden.')
    if source_id is not None and value.get('source') and value['source']!=source_id:raise ValueError('Dieser Schlüssel ist an eine andere Erweiterung gebunden.')
    return value


def sources():
    with db() as c:
        rows=c.execute('SELECT * FROM extension_sources ORDER BY id').fetchall()
    return [{**json.loads(r['config']),'id':r['id'],'available':json.loads(r['available']),'checked':r['checked'],'error':r['error']} for r in rows]


def source(ident):
    found=next((s for s in sources() if s['id']==ident),None)
    if not found:raise ValueError('Erweiterungsquelle nicht gefunden.')
    return found


def safe_url(url):
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):raise ValueError('Herstellerquelle muss eine HTTPS-Adresse ohne eingebettete Zugangsdaten sein.')
    return url


def save_source(body):
    ident=body.get('id') or secrets.token_hex(12)
    if not re.fullmatch(r'[a-f0-9]{24}',ident):raise ValueError('Ungültige Quellenkennung.')
    config={k:body.get(k,'') for k in ('name','cms','kind','provider','element','source_type','url','auth_type','auth_parameter','license','fixed_version','origin_project','origin_key')}
    if any(not isinstance(v,str) or len(v)>4096 for v in config.values()):raise ValueError('Quellenfelder müssen Text sein (max. 4096 Zeichen).')
    valid_cms(config['cms'])
    if not config['name'] or not config['provider']:raise ValueError('Name und Anbieter angeben.')
    if config['kind'] not in ('plugin','theme','package'):raise ValueError('Pakettyp auswählen.')
    if config['source_type'] not in ('upload','update_xml','direct','wordpress_org','project'):raise ValueError('Unbekannte Downloadquelle.')
    if config['source_type'] in ('update_xml','direct'):safe_url(config['url'])
    if config['cms']=='wordpress' and config['kind']=='package':raise ValueError('Für WordPress Plugin oder Theme auswählen.')
    if config['source_type']=='wordpress_org' and (config['cms']!='wordpress' or not re.fullmatch(r'[a-z0-9-]+',config['element']) or config['kind']=='package'):raise ValueError('WordPress.org benötigt Plugin-/Theme-Slug und passenden Pakettyp.')
    if config['source_type']=='project':
        p=project(config['origin_project'])
        if p['cms']!=config['cms'] or not config['origin_key']:raise ValueError('Passendes Herkunftsprojekt auswählen.')
    if config['auth_type'] not in ('','none','query','bearer','basic','headers'):raise ValueError('Unbekannte Anmeldung.')
    if config['auth_type']=='query' and not config['auth_parameter']:raise ValueError('Name des Schlüsselparameters fehlt.')
    config['auth_metadata']=bool(body.get('auth_metadata'))
    mapping=body.get('cms_config',{})
    if isinstance(mapping,str):
        try:mapping=json.loads(mapping or '{}')
        except ValueError:raise ValueError('CMS-Konfiguration muss ein JSON-Objekt sein.')
    if not isinstance(mapping,dict):raise ValueError('CMS-Konfiguration muss ein Objekt sein.')
    config['cms_config']=mapping
    from compatibility import clean
    declared=body.get('requirements',{})
    if declared:config['requirements']=clean(declared,config['name'])
    elif body.get('id') and 'requirements' not in body:
        previous=source(ident)
        if previous.get('requirements'):config['requirements']=previous['requirements']
    if config['license']:
        cred=license_value(config['license'],config['provider'],source_id=ident)
        if cred.get('project'):raise ValueError('Als globalen Standard nur eine projektunabhängige Lizenz wählen. Seitenschlüssel bei der Projektinstallation auswählen.')
    with db() as c:c.execute('INSERT INTO extension_sources (id,config) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET config=excluded.config',(ident,json.dumps(config)))
    return ident


def authenticated(url,s,credentials):
    headers={'User-Agent':'VMM-Local/0.3'};kind=s.get('auth_type');key=credentials.get('key','')
    if kind=='query':
        p=urlsplit(url);pairs=dict(parse_qsl(p.query,keep_blank_values=True));pairs.update(credentials.get('extra',{}));pairs[s['auth_parameter']]=key
        url=urlunsplit((p.scheme,p.netloc,p.path,urlencode(pairs),p.fragment))
    elif kind=='bearer':headers['Authorization']='Bearer '+key
    elif kind=='basic':headers['Authorization']='Basic '+base64.b64encode((credentials.get('username','')+':'+credentials.get('password','')).encode()).decode()
    elif kind=='headers':headers.update(credentials.get('extra',{}));headers[s.get('auth_parameter') or 'X-API-Key']=key
    if any('\n' in str(v) or '\r' in str(v) for v in [*headers.keys(),*headers.values()]):raise ValueError('Ungültiger HTTP-Header.')
    return url,headers


class Redirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        safe_url(newurl)
        result=super().redirect_request(req,fp,code,msg,headers,newurl)
        if urlsplit(req.full_url).hostname!=urlsplit(newurl).hostname:
            # Do not forward authorization headers to an unrelated redirect host.
            result.headers={'User-agent':'VMM-Local/0.3'}
        return result


def remote(url,s=None,credentials=None):
    safe_url(url)
    target,headers=authenticated(url,s,credentials) if s else (url,{'User-Agent':'VMM-Local/0.3'})
    try:return build_opener(Redirects()).open(Request(target,headers=headers),timeout=90)
    except Exception:raise ValueError('Herstelleranfrage fehlgeschlagen. Quelle, Lizenz und Internetverbindung prüfen.') from None


def version_key(value):
    parts=[(0,int(x)) if x.isdigit() else (1,x.lower()) for x in re.findall(r'\d+|[a-zA-Z]+',str(value))]
    while parts and parts[-1]==(0,0):parts.pop()
    return tuple(parts)


def parse_updates(data,base):
    try:root=ET.fromstring(data)
    except ET.ParseError:raise ValueError('Hersteller liefert keine gültige Update-XML.')
    for node in root.iter():node.tag=node.tag.split('}')[-1]
    items=[]
    for node in ([root] if root.tag=='update' else root.findall('.//update')):
        v=node.findtext('version');downloads=node.findall('./downloads/downloadurl')
        link=next((d.text for d in downloads if d.get('format','zip')=='zip' and d.text),None)
        if not v or not link:continue
        targets=[{'name':n.get('name',''),'version':n.get('version','')} for n in node.findall('targetplatform')]
        items.append({'version':v.strip(),'url':safe_url(urljoin(base,link.strip())),'php_min':node.findtext('php_minimum',''),'targets':targets,'stability':node.findtext('stability','stable'),'sha256':node.findtext('sha256','')})
    if not items:raise ValueError('Keine ZIP-Downloads in der Updatequelle gefunden.')
    return sorted(items,key=lambda x:version_key(x['version']),reverse=True)


def check(ident,license_id=None):
    s=source(ident);cred=license_value(s.get('license') if license_id is None else license_id,s['provider'],source_id=ident);kind=s['source_type']
    try:
        if kind=='project':
            from extension_library import release,source_key
            items=release(s,key=source_key(s))
        elif kind=='upload':items=[]
        elif kind=='update_xml':
            with remote(s['url'],s if s['auth_metadata'] else None,cred) as r:data=r.read(4*1024*1024+1)
            if len(data)>4*1024*1024:raise ValueError('Update-XML zu groß.')
            items=parse_updates(data,s['url'])
        elif kind=='direct':
            if not s.get('fixed_version'):raise ValueError('Für direkte Downloads eine feste Version angeben.')
            items=[{'version':s['fixed_version'],'url':s['url']}]
        else:
            kind='theme' if s['kind']=='theme' else 'plugin';url='https://api.wordpress.org/'+('themes' if kind=='theme' else 'plugins')+'/info/1.2/?'+urlencode({'action':kind+'_information','request[slug]':s['element']})
            with remote(url) as r:data=json.loads(r.read(4*1024*1024))
            if not data.get('download_link') or not data.get('version'):raise ValueError('WordPress.org-Erweiterung nicht gefunden.')
            versions=data.get('versions',{}) if kind=='plugin' else {}
            items=[{'version':v,'url':safe_url(u)} for v,u in versions.items() if u and re.fullmatch(r'\d+(?:\.\d+)*',v)]
            if not any(x['version']==data['version'] for x in items):items.append({'version':data['version'],'url':safe_url(data['download_link']),'php_min':data.get('requires_php',''),'cms_min':data.get('requires','')})
            items.sort(key=lambda x:version_key(x['version']),reverse=True)
        with db() as c:c.execute('UPDATE extension_sources SET available=?,checked=?,error=NULL WHERE id=?',(json.dumps(items),int(time.time()),ident))
        return 'Versionen geprüft: '+s['name']+' · '+str(len(items))+' verfügbar.'
    except Exception as exc:
        with db() as c:c.execute('UPDATE extension_sources SET checked=?,error=? WHERE id=?',(int(time.time()),str(exc),ident))
        raise


def package_version(path,cms):
    import zipfile
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if cms=='joomla' and name.lower().endswith('.xml') and '/' not in name.strip('/'):
                try:root=ET.fromstring(archive.read(name))
                except ET.ParseError:continue
                if root.tag in ('extension','install') and root.findtext('version'):return root.findtext('version').strip()
            if cms=='wordpress' and (name.endswith('/style.css') or name.endswith('.php')) and name.count('/')<=1:
                with archive.open(name) as entry:data=entry.read(16384).decode(errors='replace')
                if re.search(r'(?:Plugin|Theme) Name\s*:',data,re.I):
                    found=re.search(r'^\s*(?:\*\s*)?Version\s*:\s*(.+)$',data,re.M|re.I)
                    if found:return found[1].strip().rstrip(' */')
    return ''


def register_package(path,s,v):
    validate_zip(path);v=package_version(path,s['cms']) or v;sha=digest(path)
    with LOCK,db() as c:
        existing=c.execute('SELECT id FROM extensions WHERE source_id=? AND version=? AND sha256=? AND archived=1',(s['id'],v,sha)).fetchone()
        if existing:return existing['id']
        ident=secrets.token_hex(12);root=DATA/'extensions';root.mkdir(exist_ok=True);shutil.copyfile(path,root/(ident+'.zip'))
        c.execute('INSERT INTO extensions (id,name,cms,kind,provider,version,filename,sha256,created,source_id) VALUES (?,?,?,?,?,?,?,?,?,?)',(ident,s['name'],s['cms'],s['kind'],s['provider'],v,ident+'.zip',sha,int(time.time()),s['id']))
    return ident


def compatible(item,p):
    if item.get('php_min') and version_key(p['php'])<version_key(item['php_min']):return False
    if item.get('cms_min') and version_key(p['version'])<version_key(item['cms_min']):return False
    targets=[t for t in item.get('targets',[]) if t['name'].lower()==p['cms']]
    if any(t['name'].lower() in ('joomla','wordpress') for t in item.get('targets',[])) and not targets:return False
    if targets:
        try:
            if not any(re.match(t['version'],p['version']) for t in targets):return False
        except re.error:return False
    return item.get('stability','stable').lower() in ('stable','') and not re.search(r'(?:alpha|beta|rc|dev)',item.get('version',''),re.I)


def download_package(ident,v='latest',license_id=None,p=None):
    s=source(ident)
    license_value(s.get('license') if license_id is None else license_id,s['provider'],p['slug'] if p else None,ident)
    if s['source_type']=='project' and v=='latest':
        from extension_library import release,source_key
        return release(s,download=True,key=source_key(s))
    if s['source_type']=='project':
        with db() as c:row=c.execute('SELECT * FROM extensions WHERE source_id=? AND version=? AND archived=1 ORDER BY created DESC',(ident,v)).fetchone()
        if not row:raise ValueError('Diese Version ist nicht gespeichert. Neueste Version herunterladen.')
        if digest(DATA/'extensions'/row['filename'])!=row['sha256']:raise ValueError('Archiv-Prüfsumme stimmt nicht.')
        return row['id']
    if s['source_type']!='upload':check(ident,license_id);s=source(ident)
    candidates=[i for i in s['available'] if (v=='latest' or i['version']==v) and (v!='latest' or i.get('stability','stable').lower() in ('stable','') and not re.search(r'alpha|beta|rc|dev',i['version'],re.I)) and (not p or compatible(i,p))]
    if s['source_type']=='upload':
        with db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM extensions WHERE source_id=? AND archived=1',(ident,))]
        rows=[r for r in rows if v=='latest' or r['version']==v];rows.sort(key=lambda r:version_key(r['version']),reverse=True)
        if not rows:raise ValueError('Zuerst ein ZIP-Paket für diese Erweiterung hochladen.')
        row=rows[0]
        if digest(DATA/'extensions'/row['filename'])!=row['sha256']:raise ValueError('Archiv-Prüfsumme stimmt nicht.')
        return row['id']
    if not candidates:raise ValueError('Keine passende stabile Version für CMS/PHP gefunden.')
    item=candidates[0]
    with db() as c:rows=c.execute('SELECT * FROM extensions WHERE source_id=? AND version=? AND archived=1',(ident,item['version'])).fetchall()
    for row in rows:
        f=DATA/'extensions'/row['filename']
        if f.is_file() and digest(f)==row['sha256']:return row['id']
    cred=license_value(s.get('license') if license_id is None else license_id,s['provider'])
    with tempfile.TemporaryDirectory(dir=DATA) as tmp:
        path=__import__('pathlib').Path(tmp)/'package.zip'
        with remote(item['url'],s,cred) as response,path.open('wb') as out:
            size=0
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                size+=len(chunk)
                if size>MAX_ARCHIVE:raise ValueError('Erweiterungspaket zu groß.')
                out.write(chunk)
        if item.get('sha256') and digest(path).lower()!=item['sha256'].lower():raise ValueError('Hersteller-Prüfsumme stimmt nicht.')
        return register_package(path,s,item['version'])


def validate_plans(cms,items,project_name=None):
    if not isinstance(items,list) or len(items)>100:raise ValueError('Ungültige Erweiterungsauswahl.')
    result=[]
    for item in items:
        s=source(item['source'])
        if s['cms']!=cms:raise ValueError('Erweiterung passt nicht zum CMS.')
        if 'license' in item:lic=item.get('license') or None
        else:
            matching=[l for l in licenses() if project_name and l.get('project')==project_name and l['provider']==s['provider'] and (not l.get('source') or l['source']==s['id'])]
            matching.sort(key=lambda l:bool(l.get('source')),reverse=True)
            lic=matching[0]['id'] if matching else s.get('license') or None
        if lic:license_value(lic,s['provider'],project_name,s['id'])
        result.append({'source':s['id'],'license':lic,'version':str(item.get('version') or 'latest')})
    return result


def assign(name,items):
    p=project(name);items=validate_plans(p['cms'],items,name)
    with db() as c:
        for item in items:c.execute('INSERT INTO extension_plans VALUES (?,?,?,?,?,NULL) ON CONFLICT(project,source) DO UPDATE SET license=excluded.license,version=excluded.version,status=excluded.status,error=NULL',(name,item['source'],item['license'],item['version'],'pending'))


def installed(name):
    import operations as op
    p=project(name)
    op.write_tools(p)
    if p['cms']=='wordpress':
        result=[]
        for kind in ('plugin','theme'):
            raw=op.exec_php(p,['wp','--allow-root',kind,'list','--format=json'],timeout=90)
            for x in json.loads(raw):result.append({'name':x['name'],'element':x['name'],'kind':kind,'version':x['version'],'enabled':x['status'] in ('active','must-use','dropin'),'update':x.get('update',''),'available':x.get('update_version','')})
        save_inventory(name,result)
        return result
    result=json.loads(op.exec_php(p,['php','/vmm-tools/extension-bridge.php','inventory'],timeout=90))
    save_inventory(name,result)
    return result


def ready(p):
    import operations as op
    if p['status']!='running' or p.get('restore'):return False
    if p['cms']=='joomla':return (op.folder(p)/'site/configuration.php').is_file() and not (op.folder(p)/'site/installation').exists()
    try:op.exec_php(p,['wp','--allow-root','core','is-installed'],timeout=30);return True
    except Exception:return False


def configure_license(p,s,lic):
    if not lic:return 'Ohne Lizenz.'
    import operations as op
    cred=license_value(lic,s['provider'],p['slug'],s['id']);payload={'source':s,'credentials':cred}
    op.write_tools(p)
    # stdin avoids shell interpolation and command-line disclosure.
    args=['php','/vmm-tools/extension-bridge.php','license'] if p['cms']=='joomla' else ['wp','--allow-root','eval-file','/vmm-tools/extension-bridge.php','license']
    return op.exec_php(p,args,input=json.dumps(payload).encode(),timeout=90).decode().strip()


def install_plan(name,source_id):
    import operations as op
    p=project(name)
    with db() as c:row=c.execute('SELECT * FROM extension_plans WHERE project=? AND source=?',(name,source_id)).fetchone()
    if not row:raise ValueError('Erweiterung zuerst zuordnen.')
    if not ready(p):raise ValueError('Zuerst CMS-Einrichtung bzw. Wiederherstellung abschließen und Projekt starten.')
    try:
        s=source(source_id);ident=download_package(source_id,row['version'],row['license'] or '',p)
        with db() as c:c.execute("INSERT OR REPLACE INTO project_extensions VALUES (?,?,?,'assigned')",(name,ident,row['license']));c.execute("UPDATE extension_plans SET status='installing',error=NULL WHERE project=? AND source=?",(name,source_id))
        op.install_extension(name,ident)
        notice=configure_license(p,s,row['license'])
        with db() as c:c.execute("UPDATE extension_plans SET status='installed',error=NULL WHERE project=? AND source=?",(name,source_id))
        return s['name']+' installiert. '+notice
    except Exception as exc:
        with db() as c:c.execute("UPDATE extension_plans SET status='error',error=? WHERE project=? AND source=?",(str(exc),name,source_id))
        raise


def process_pending(name):
    with db() as c:rows=c.execute("SELECT source FROM extension_plans WHERE project=? AND status='pending'",(name,)).fetchall()
    results=[];errors=[]
    for r in rows:
        try:results.append(install_plan(name,r['source']))
        except Exception as exc:errors.append(str(exc))
    if errors:raise ValueError('\n'.join(results+errors))
    return '\n'.join(results)


def queue_pending():
    from store import job
    with db() as c:rows=c.execute("SELECT DISTINCT p.* FROM projects p JOIN extension_plans e ON e.project=p.slug WHERE e.status='pending' AND p.status='running' AND p.restore=0 AND NOT EXISTS (SELECT 1 FROM jobs j WHERE j.resource=p.slug AND j.status IN ('running','queued'))").fetchall()
    for r in rows:
        p=dict(r)
        if ready(p):
            try:job(p['slug'],'extensions',lambda name=p['slug']:process_pending(name))
            except ValueError:pass

init()
# Adopt packages uploaded before source-based catalogues existed.
with db() as _c:
    _legacy=_c.execute('SELECT * FROM extensions WHERE source_id IS NULL').fetchall()
for _row in _legacy:
    _id=save_source({'name':_row['name'],'cms':_row['cms'],'kind':_row['kind'],'provider':_row['provider'],'element':'','source_type':'upload','auth_type':'none'})
    with db() as _c:_c.execute('UPDATE extensions SET source_id=? WHERE id=?',(_id,_row['id']))


def inspect_upload(path):
    """Read trusted package metadata without executing PHP."""
    import zipfile
    validate_zip(path)
    with zipfile.ZipFile(path) as archive:
        names=sorted(archive.namelist(),key=lambda name:(name.count('/'),name))
        for name in names:
            if name.lower().endswith('.xml') and name.count('/')<=1:
                if archive.getinfo(name).file_size>1024*1024:continue
                try:root=ET.fromstring(archive.read(name))
                except ET.ParseError:continue
                if root.tag not in ('extension','install') or not root.findtext('version'):continue
                kind=root.get('type','package');label=root.findtext('name') or name.rsplit('/',1)[-1][:-4];element=name.rsplit('/',1)[-1][:-4]
                if kind=='package':element='pkg_'+(root.findtext('packagename') or element.removeprefix('pkg_'))
                if kind=='template' and re.fullmatch(r'[A-Za-z0-9_-]+',label):element=label
                if kind=='plugin':element=next((n.get('plugin') for n in root.findall('./files/filename') if n.get('plugin')),element)
                url=root.findtext('./updateservers/server','').strip()
                return {'name':label,'cms':'joomla','kind':'theme' if kind=='template' else kind if kind in ('plugin','package') else 'package','element':element,'version':root.findtext('version'),'url':url,'source_type':'update_xml' if url.startswith('https://') else 'upload','auth_type':'query' if root.find('dlid') is not None else 'none','auth_parameter':(root.find('dlid').get('prefix','').rstrip('=') if root.find('dlid') is not None else '')}
        for name in names:
            if name.endswith('.php') or name.endswith('style.css'):
                if name.count('/')>1:continue
                with archive.open(name) as stream:text=stream.read(16384).decode(errors='replace')
                found=re.search(r'^[ \t/*]*(Plugin|Theme) Name:\s*(.+)$',text,re.M|re.I)
                if not found:continue
                author=re.search(r'^[ \t/*]*Author:\s*(.+)$',text,re.M|re.I)
                version=re.search(r'^[ \t/*]*Version:\s*(.+)$',text,re.M|re.I);update=re.search(r'^[ \t/*]*Update URI:\s*(.+)$',text,re.M|re.I)
                return {'author':author[1].strip() if author else '', 'name':found[2].strip(),'cms':'wordpress','kind':found[1].lower(),'element':name.split('/')[0] if '/' in name else name[:-4],'version':version[1].strip() if version else '1.0.0','source_type':'upload','auth_type':'none','url':update[1].strip() if update else ''}
    raise ValueError('CMS-Paketdaten konnten nicht erkannt werden. Quelle manuell anlegen und dieses ZIP zuordnen.')


def is_core_update(item):
    return item.get('core', False) or (item.get('kind') == 'file' and item.get('element') == 'joomla')


def inventory_counts(items):
    available = {str(x.get('id', x.get('kind', '') + ':' + x.get('element', x.get('name', '')))): x
                 for x in items if x.get('update') == 'available'}
    core = sum(bool(is_core_update(x)) for x in available.values())
    return {'updates':len(available), 'extension_updates':len(available)-core, 'core_updates':core}


def save_inventory(name,items):
    from store import DATA
    root=DATA/'projects'/name
    payload={'checked':int(time.time()),**inventory_counts(items),'items':items}
    (root/'extension-inventory.json').write_text(json.dumps(payload))

def inventory_summary(name):
    from store import DATA
    try:
        data=json.loads((DATA/'projects'/name/'extension-inventory.json').read_text())
        return {'checked':data['checked'],**inventory_counts(data['items'])}
    except (OSError,ValueError,KeyError):return None


def project_updates(name,apply=False):
    import operations as op
    result=op.wp_updates(name,apply)
    try:
        items=installed(name)
        counts=inventory_counts(items)
        result+='\n'+str(counts['extension_updates'])+' Erweiterungsupdates · '+str(counts['core_updates'])+(' CMS-Update' if counts['core_updates']==1 else ' CMS-Updates')
        for item in items:
            if is_core_update(item) and item.get('update')=='available':
                result+='\nCMS: '+item['name']+': '+item.get('version','')+' → '+item.get('available','')+' (im CMS-Backend aktualisieren)'
    except Exception as exc:result+='\nInventar konnte nicht aktualisiert werden: '+str(exc)
    return result


def update_single(name,ident):
    import operations as op
    p=project(name)
    items=installed(name)
    item=next((x for x in items if str(x.get('id',x.get('element')))==str(ident)),None)
    if not item:raise ValueError('Erweiterung nicht im Projekt gefunden.')
    if is_core_update(item):raise ValueError('CMS-Updates bitte im CMS-Backend installieren.')
    op.snapshot(name)
    if p['cms']=='wordpress':
        result=op.exec_php(p,['wp','--allow-root',item['kind'],'update',item['element']],timeout=900)
    else:
        op.write_tools(p)
        result=op.exec_php(p,['php','/vmm-tools/joomla-updates.php','vmm:updates','--apply','--extension',str(int(item['id']))],timeout=900)
    installed(name)
    return result.decode(errors='replace')[-3000:]
