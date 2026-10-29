"""Read declared CMS/extension requirements without executing downloaded code."""
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET


def parts(value):
    found=re.match(r'^v?(\d+(?:\.\d+){0,3})',str(value))
    if not found:raise ValueError('Ungültige Versionsanforderung: '+str(value))
    values=tuple(map(int,found[1].split('.')))
    return values+(0,)*(4-len(values))


def satisfies(actual,expression):
    if not isinstance(expression,str) or len(expression)>200:raise ValueError('Versionsanforderung muss Text sein (max. 200 Zeichen).')
    if expression.strip() in ('','*'):return True
    current=parts(actual)
    alternatives=expression.split('||')
    def branch(value):
        tokens=re.findall(r'(>=|<=|!=|==|>|<|=|\^|~)?\s*(v?\d+(?:\.\d+){0,3}(?:\.[xX*])?|\*)',value)
        remainder=re.sub(r'(>=|<=|!=|==|>|<|=|\^|~)?\s*(v?\d+(?:\.\d+){0,3}(?:\.[xX*])?|\*)','',value)
        if not tokens or remainder.strip(' ,'):raise ValueError('Nicht unterstützte Versionsanforderung: '+expression)
        for operator,target in tokens:
            if target=='*':continue
            if target.endswith(('.x','.X','.*')):
                prefix=target[:-2];v=parts(prefix);n=len(prefix.split('.'))
                if current[:n]!=v[:n]:return False
                continue
            v=parts(target);operator=operator or '='
            if operator in ('^','~'):
                n=len(target.lstrip('v').split('.'));index=(next((i for i,x in enumerate(v[:3]) if x),2) if operator=='^' else (0 if n<3 else 1))
                maximum=list(v);maximum[index]+=1
                maximum[index+1:]=[0]*(3-index)
                if not v<=current<tuple(maximum):return False
            elif not {'>=':current>=v,'<=':current<=v,'>':current>v,'<':current<v,'=':current==v,'==':current==v,'!=':current!=v}[operator]:return False
        return True
    return any(branch(value) for value in alternatives)


def clean(body,label='Projekt'):
    if not isinstance(body,dict):raise ValueError('Systemanforderungen müssen ein Objekt sein.')
    out={'label':label}
    if body.get('php'):
        satisfies('8.4',body['php']);out['php']=body['php']
    databases=body.get('database',{})
    if not isinstance(databases,dict) or any(k not in ('mysql','mariadb') for k in databases):raise ValueError('Datenbankanforderungen für mysql und/oder mariadb angeben.')
    for value in databases.values():satisfies('11.4',value)
    if databases:out['database']=databases
    modules=body.get('php_extensions',[])
    if not isinstance(modules,list) or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9_]+',x) for x in modules):raise ValueError('Ungültige Liste benötigter PHP-Module.')
    if modules:out['php_extensions']=[x.lower() for x in modules]
    return out


def read_json(path):
    if path.is_file() and not path.is_symlink():
        if path.stat().st_size>1024*1024:raise ValueError('Anforderungsdatei zu groß: '+path.name)
        return json.loads(path.read_text())
    return {}


def requirements(site,cms,version=''):
    site=Path(site);result=[]
    major=parts(version)[0] if re.match(r'^\d',str(version)) else 0
    if cms=='joomla':
        baseline={'php':'>=8.3','database':{'mariadb':'>=10.6','mysql':'>=8.0.13'}} if major>=6 else {'php':'>=8.1','database':{'mariadb':'>=10.4','mysql':'>=8.0.13'}} if major>=5 else {'php':'>=7.4'} if major==4 or not major else {'php':'>=7.4 <8.1'}
        result.append(clean(baseline,'Joomla '+str(version)))
    for path,pattern in ((site/'wp-includes/version.php',r"\$required_php_version\s*=\s*['\"]([^'\"]+)"),(site/'cli/joomla.php',r"JOOMLA_MINIMUM_PHP\s*=\s*['\"]([^'\"]+)")):
        if path.is_file():
            match=re.search(pattern,path.read_text(errors='replace'))
            if match:result.append(clean({'php':'>='+match[1]},'CMS'))
    roots=[site]
    for pattern in ('wp-content/plugins/*','wp-content/themes/*','administrator/components/*','plugins/*/*','modules/*','templates/*'):
        roots.extend(path for path in site.glob(pattern) if path.is_dir() and not path.is_symlink())
    if len(roots)>3000:raise ValueError('Zu viele Erweiterungsverzeichnisse für die automatische Anforderungsprüfung.')
    for root in roots:
        label='Projekt' if root==site else root.name
        sidecar=read_json(root/'.tentacle-requirements.json')
        if sidecar:result.append(clean(sidecar,label))
        composer=read_json(root/'composer.json').get('require',{})
        if isinstance(composer,dict):
            declared={'php':composer.get('php',''),'php_extensions':[k[4:] for k in composer if k.startswith('ext-')]}
            if declared['php'] or declared['php_extensions']:result.append(clean(declared,label))
        files=list(root.glob('*.php'))[:30]+list(root.glob('style.css')) if 'wp-content' in root.parts else []
        for file in files:
            if file.is_symlink():continue
            with file.open(errors='replace') as stream:header=stream.read(8192)
            match=re.search(r'^\s*(?:/\*+|\*)?\s*Requires PHP:\s*([\d.]+)',header,re.M|re.I)
            if match:result.append(clean({'php':'>='+match[1]},label))
        for file in list(root.glob('*.xml'))[:15] if root!=site else []:
            if file.is_symlink() or file.stat().st_size>1024*1024:continue
            try:tree=ET.parse(file)
            except ET.ParseError:continue
            minimum=tree.findtext('.//php_minimum') or tree.findtext('.//minimum_php')
            if minimum:result.append(clean({'php':'>='+minimum.strip()},label))
    return result


def choose_php(items,preferred='8.4'):
    from runtime import PHP
    order=list(dict.fromkeys([preferred,'8.4','8.3','8.5','8.2','8.1','8.0','7.4']))
    for value in order:
        if value in PHP and all(series_possible(value,r['php']) for r in items if r.get('php')):return value
    raise ValueError('Keine gemeinsame PHP-Version für CMS und Erweiterungen verfügbar. Deklarierte Anforderungen prüfen.')


def validate_php(items,php):
    for req in items:
        if req.get('php') and not series_possible(php,req['php']):raise ValueError(req['label']+' benötigt PHP '+req['php']+'; gewählt ist '+php+'.')


def resolve(p,site,source_php=None):
    from database_profiles import select
    from store import db
    items=requirements(site,p['cms'],p.get('version',''))+pending_requirements(p)
    if p.get('php_mode')=='auto':
        preferred=source_php or ('7.4' if p['cms']=='joomla' and str(p.get('version','')).startswith('3.') else '8.2' if p['cms']=='joomla' and str(p.get('version','')).startswith('4.') else '8.4')
        p['php']=choose_php(items,preferred)
    validate_php(items,p['php'])
    p['database_profile']=select(items,p.get('database_profile') or 'existing')
    with db() as c:c.execute('UPDATE projects SET php=?,database_profile=? WHERE slug=?',(p['php'],p['database_profile'],p['slug']))
    return items


def series_possible(series,expression):
    """Choose a minor series provisionally; verify the real server/CLI patch later."""
    points={0,999}
    for value in re.findall(r'(?<![0-9.])'+re.escape(series)+r'\.(\d+)',expression):
        patch=int(value);points.update((max(0,patch-1),patch,patch+1))
    return any(satisfies(series+'.'+str(patch),expression) for patch in points)


def package_requirements(path):
    import zipfile
    found=[]
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            parts=Path(item.filename).parts
            if item.is_dir() or item.file_size>1024*1024 or any(v in parts for v in ('vendor','tests','node_modules')) or len(parts)>3:continue
            name=Path(item.filename).name
            if name in ('.tentacle-requirements.json','composer.json'):
                data=json.loads(archive.read(item))
                if name=='composer.json':
                    require=data.get('require',{});data={'php':require.get('php',''),'php_extensions':[k[4:] for k in require if k.startswith('ext-')]}
                found.append(clean(data,item.filename))
            elif name.endswith('.php') or name=='style.css':
                with archive.open(item) as stream:text=stream.read(8192).decode(errors='replace')
                match=re.search(r'^\s*(?:/\*+|\*)?\s*Requires PHP:\s*([\d.]+)',text,re.M|re.I)
                if match:found.append(clean({'php':'>='+match[1]},item.filename))
            elif name.endswith('.xml'):
                try:tree=ET.fromstring(archive.read(item))
                except ET.ParseError:continue
                minimum=tree.findtext('.//php_minimum') or tree.findtext('.//minimum_php')
                if minimum:found.append(clean({'php':'>='+minimum.strip()},item.filename))
    return found


def pending_requirements(p):
    """Use already archived selected packages and declared source metadata, without network I/O."""
    from store import db,DATA
    import extension_service as extensions
    from catalog import digest
    result=[]
    with db() as connection:
        plans=connection.execute('SELECT * FROM extension_plans WHERE project=?',(p['slug'],)).fetchall()
        for plan in plans:
            source=extensions.source(plan['source'])
            declared=source.get('requirements',{})
            if declared:result.append(clean(declared,source['name']))
            packages=[dict(r) for r in connection.execute('SELECT * FROM extensions WHERE source_id=?',(plan['source'],))]
            packages=[r for r in packages if plan['version']=='latest' or r['version']==plan['version']]
            if packages:
                package=max(packages,key=lambda r:extensions.version_key(r['version']));file=DATA/'extensions'/package['filename']
                if digest(file)!=package['sha256']:raise ValueError('Prüfsumme der ausgewählten Erweiterung stimmt nicht: '+source['name'])
                result.extend(package_requirements(file))
            else:
                releases=[r for r in source.get('available',[]) if (plan['version']=='latest' or r['version']==plan['version']) and extensions.compatible(r,{**p,'php':'999.0'})]
                if releases:
                    release=max(releases,key=lambda r:extensions.version_key(r['version']))
                    if release.get('php_min'):result.append(clean({'php':'>='+release['php_min']},source['name']))
    return result
