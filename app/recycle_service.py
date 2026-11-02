"""Recoverable deletion of stored assets with same-volume staging and durable metadata."""
import json,re,secrets,shutil,time
from pathlib import Path
from store import DATA,LOCK,db,job
import cleanup_service as cleanup

TABLES=('packages','extension_sources','extensions','extension_plans','project_extensions')


def init():
    with db() as c:c.execute('CREATE TABLE IF NOT EXISTS recycle_entries(id TEXT PRIMARY KEY,value TEXT NOT NULL)')


def settings():
    path=DATA/'deletion-settings.json'
    if not path.exists():return {'mode':'trash','days':30}
    value=json.loads(path.read_text());validate_settings(value);return value


def validate_settings(value):
    if value.get('mode') not in ('trash','permanent') or isinstance(value.get('days'),bool) or not isinstance(value.get('days'),int) or not 1<=value['days']<=3650:raise ValueError('Löschart und Aufbewahrung von 1 bis 3650 Tagen angeben.')


def save_settings(value):
    value={k:value.get(k) for k in ('mode','days')};validate_settings(value)
    with LOCK:
        init();path=DATA/'deletion-settings.json';temp=path.with_suffix('.new');temp.write_text(json.dumps(value));temp.replace(path)
        # Existing entries retain the deadline agreed when they were moved to trash.
    return {**value,'message':'Löscheinstellungen gespeichert. Die Dauer gilt für künftig gelöschte Dateien; bestehende Ablaufdaten bleiben erhalten.'}


def put(c,value):c.execute('INSERT OR REPLACE INTO recycle_entries VALUES(?,?)',(value['id'],json.dumps(value)))


def load(c,ident):
    if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{24}',ident):raise ValueError('Ungültiger Papierkorbeintrag.')
    row=c.execute('SELECT value FROM recycle_entries WHERE id=?',(ident,)).fetchone()
    if not row:raise ValueError('Papierkorbeintrag nicht gefunden.')
    return json.loads(row['value'])


def paths(value):
    result=[]
    for item in value['paths']:
        area=item['area']
        if area not in cleanup.roots():raise ValueError('Ungültiger Speicherbereich.')
        root=cleanup.roots()[area]
        original=cleanup.safe_file(root,item['original']);saved=cleanup.safe_file(root,item['saved'])
        if not value.get('legacy') and not re.fullmatch(r'\.vmm-trash-'+value['id']+r'-[0-9]+',item['saved']):raise ValueError('Ungültiger Papierkorbpfad.')
        if value.get('legacy') and (area!='trash' or not re.fullmatch(r'[a-z0-9][a-z0-9-]*-[0-9]+-[a-f0-9]{6}',item['saved'])):raise ValueError('Ungültiger Projektpapierkorbpfad.')
        result.append((original,saved))
    return result


def guards(c,working=False):
    import storage_service,system_service
    if storage_service.busy() or storage_service.ACTIVE_UPLOADS or system_service.SHUTTING_DOWN:raise ValueError('Eine Speicherumstellung, Übertragung oder Dienstaktion läuft noch.')
    if c.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running') AND (resource='manager-update' OR kind IN ('service-control','recycle-restore','recycle-purge')) AND (?=0 OR resource!='recycle-bin')",(int(working),)).fetchone():raise ValueError('Ein Update oder Papierkorbvorgang läuft noch.')


def snapshot(c,kind,ident):
    data={}
    def rows(table,where,args):return [dict(r) for r in c.execute('SELECT * FROM '+table+' WHERE '+where,args)]
    if kind=='cms':
        data['packages']=rows('packages','id=?',(ident,));data['package_projects']=[r['slug'] for r in c.execute('SELECT slug FROM projects WHERE package_id=?',(ident,))]
    if kind in ('extension','extension-package'):
        if kind=='extension':
            data['extension_sources']=rows('extension_sources','id=?',(ident,));data['extensions']=rows('extensions','source_id=?',(ident,));data['extension_plans']=rows('extension_plans','source=?',(ident,));data['project_extensions']=rows('project_extensions','extension IN (SELECT id FROM extensions WHERE source_id=?)',(ident,))
        else:
            data['extensions']=rows('extensions','id=?',(ident,));source=data['extensions'][0].get('source_id')
            if source:data['optional_sources']=rows('extension_sources','id=?',(source,))
    return data


def detach(c,kind,ident):
    if kind=='cms':c.execute('UPDATE projects SET package_id=NULL WHERE package_id=?',(ident,));c.execute('DELETE FROM packages WHERE id=?',(ident,))
    elif kind=='extension-package':c.execute('UPDATE extensions SET archived=0 WHERE id=?',(ident,))
    elif kind=='extension':
        c.execute('DELETE FROM extension_plans WHERE source=?',(ident,));c.execute('DELETE FROM project_extensions WHERE extension IN (SELECT id FROM extensions WHERE source_id=?)',(ident,));c.execute('DELETE FROM extensions WHERE source_id=?',(ident,));c.execute('DELETE FROM extension_sources WHERE id=?',(ident,))


def move(kind,ident):
    with LOCK:
        init()
        with db() as c:
            guards(c);info=cleanup.describe(c,kind,ident)
            if info['blocked']:raise ValueError(' '.join(info['blocked']))
            token=secrets.token_hex(12);now=int(time.time());items=[]
            for i,path in enumerate(info['_paths']):
                area=next((key for key,root in cleanup.roots().items() if path.parent.resolve()==root.resolve()),None)
                if not area:raise ValueError('Datei liegt außerhalb der verwalteten Speicherbereiche.')
                items.append({'area':area,'original':path.name,'saved':'.vmm-trash-'+token+'-'+str(i)})
            value={**cleanup.public(info),'id':token,'original_id':ident,'deleted':now,'expires':now+settings()['days']*86400,'paths':items,'metadata':snapshot(c,kind,ident),'status':'moving'}
            put(c,value)
        moved=[]
        try:
            for original,saved in paths(value):
                if saved.exists():raise ValueError('Papierkorbziel existiert bereits.')
                original.rename(saved);moved.append((original,saved))
            with db() as c:
                detach(c,kind,ident);value['status']='ready';put(c,value)
        except Exception:
            for original,saved in reversed(moved):saved.rename(original)
            with db() as c:c.execute('DELETE FROM recycle_entries WHERE id=?',(token,))
            raise
    return {'message':info['label']+' in den Papierkorb verschoben.','deleted':ident,'trash_id':token}


def insert(c,table,row,ignore=False):
    if table not in TABLES+('projects','credentials'):raise ValueError('Ungültige Metadaten.')
    columns={r['name'] for r in c.execute('PRAGMA table_info('+table+')')}
    if not row or not set(row)<=columns:raise ValueError('Unpassende Metadaten für '+table)
    c.execute('INSERT '+('OR IGNORE ' if ignore else '')+'INTO '+table+' ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))


def restore_metadata(c,value):
    data=value['metadata'];kind=value['kind']
    for row in data.get('optional_sources',[]):insert(c,'extension_sources',row,True)
    for table in TABLES:
        for row in data.get(table,[]):
            if table in ('extension_plans','project_extensions'):
                if not c.execute('SELECT 1 FROM projects WHERE slug=?',(row['project'],)).fetchone():continue
                if row.get('license') and not c.execute('SELECT 1 FROM licenses WHERE id=?',(row['license'],)).fetchone():row={**row,'license':None}
                insert(c,table,row,True);continue
            if table=='extensions' and kind=='extension-package':
                current=c.execute('SELECT * FROM extensions WHERE id=?',(row['id'],)).fetchone()
                if current:
                    if any(current[k]!=v for k,v in row.items() if k!='archived') or current['archived']:raise ValueError('Das Erweiterungspaket wurde inzwischen verändert oder erneut gespeichert.')
                    c.execute('UPDATE extensions SET archived=1 WHERE id=?',(row['id'],));continue
            insert(c,table,row)
    for slug in data.get('package_projects',[]):c.execute('UPDATE projects SET package_id=? WHERE slug=? AND package_id IS NULL',(value['original_id'],slug))


def restore(ident):
    with LOCK:
        init()
        with db() as c:
            guards(c);value=load(c,ident)
            if value.get('legacy'):return {'job':job('recycle-bin','recycle-restore',lambda:restore_project(ident))}
            if value['status']!='ready':raise ValueError('Papierkorbeintrag muss zuerst geprüft werden.')
            pairs=paths(value)
            if any(o.exists() for o,s in pairs):raise ValueError('Am ursprünglichen Speicherort existiert bereits eine Datei. Es wird nichts überschrieben.')
            if any(not s.exists() for o,s in pairs):raise ValueError('Dateien im Papierkorb fehlen.')
            value['status']='restoring';put(c,value)
        restored=[]
        try:
            for original,saved in pairs:saved.rename(original);restored.append((original,saved))
            with db() as c:
                restore_metadata(c,value);c.execute('DELETE FROM recycle_entries WHERE id=?',(ident,))
        except Exception:
            for original,saved in reversed(restored):original.rename(saved)
            with db() as c:value['status']='ready';put(c,value)
            raise
    return {'message':value['label']+' wiederhergestellt.'}


def purge(ident,automatic=False):
    with LOCK:
        init()
        with db() as c:
            guards(c,True);value=load(c,ident)
            if value['status'] not in ('ready','purging','restored'):raise ValueError('Eintrag ist noch in Bearbeitung.')
            if automatic and value['expires']>time.time():return False
            value['status']='purging';put(c,value)
        try:
            for _,saved in paths(value):
                if saved.is_dir():shutil.rmtree(saved)
                elif saved.exists():saved.unlink()
        except OSError as error:
            with db() as c:value['error']='Dateien konnten noch nicht vollständig entfernt werden: '+str(error);put(c,value)
            raise
        with db() as c:c.execute('DELETE FROM recycle_entries WHERE id=?',(ident,))
    return {'message':value['label']+' endgültig gelöscht.'}


def adopt_projects():
    root=DATA/'trash'
    if not root.is_dir():return
    with LOCK,db() as c:
        if c.execute("SELECT 1 FROM jobs WHERE kind='delete-project' AND status IN ('queued','running')").fetchone():return
        known={json.loads(r['value']).get('original_id') for r in c.execute('SELECT value FROM recycle_entries')}
        for path in root.iterdir():
            if path.name in known or path.is_symlink() or not path.is_dir() or not re.fullmatch(r'[a-z0-9][a-z0-9-]*-[0-9]+-[a-f0-9]{6}',path.name):continue
            info=cleanup.state(path/'metadata.json');name=info.get('project',{}).get('slug')
            if name and c.execute('SELECT 1 FROM projects WHERE slug=?',(name,)).fetchone():continue
            now=int(time.time());value={'id':secrets.token_hex(12),'kind':'trash','label':'Gelöschtes Projekt','name':name or path.name,'cms':info.get('project',{}).get('cms',''),'original_id':path.name,'legacy':True,'deleted':now,'expires':now+settings()['days']*86400,'paths':[{'area':'trash','original':path.name,'saved':path.name}],'metadata':{},'size':None,'status':'ready','restorable':bool(name and (path/'project').is_dir())}
            put(c,value)


def listing():
    with LOCK:
        init();adopt_projects()
        with db() as c:values=[json.loads(r['value']) for r in c.execute('SELECT value FROM recycle_entries')]
        return {'items':[{k:v for k,v in value.items() if k not in ('metadata','paths')} for value in values],'settings':settings()}


def recover():
    with LOCK:
        init()
        with db() as c:values=[json.loads(r['value']) for r in c.execute('SELECT value FROM recycle_entries')]
        for value in values:
            if value['status']=='project-restoring':
                try:
                    archive=paths(value)[0][1];meta=cleanup.state(archive/'metadata.json');p=meta.get('project',{});name=p.get('slug','')
                    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',name):raise ValueError('Projektmetadaten fehlen.')
                    target=DATA/'projects'/name;marker=target/'.vmm-recycle-restore.json'
                    if target.exists():
                        if cleanup.state(marker).get('id')!=value['id']:raise ValueError('Zielprojekt vor einem erneuten Versuch manuell prüfen.')
                        with db() as c:
                            for table in ('credentials','extension_plans','project_extensions'):c.execute('DELETE FROM '+table+' WHERE project=?',(name,))
                            c.execute('DELETE FROM projects WHERE slug=?',(name,))
                        shutil.rmtree(target)
                    staged=DATA/'projects'/('.vmm-restore-'+value['id'])
                    if staged.exists():
                        if cleanup.state(staged/'.vmm-recycle-restore.json').get('id')!=value['id']:raise ValueError('Temporäre Projektkopie muss geprüft werden.')
                        shutil.rmtree(staged)
                    value['status']='ready';value.pop('error',None)
                except (ValueError,OSError) as error:value['error']='Projektwiederherstellung unterbrochen. Original bleibt erhalten. '+str(error)
                with db() as c:put(c,value)
                continue
            if value['status'] not in ('moving','restoring'):continue
            if value.get('legacy'):continue
            try:
                for original,saved in paths(value):
                    source,target=(saved,original) if value['status']=='moving' else (original,saved)
                    if source.exists():
                        if target.exists():raise ValueError('Beide Dateistände vorhanden; manuelle Prüfung erforderlich.')
                        source.rename(target)
                with db() as c:
                    if value['status']=='moving':c.execute('DELETE FROM recycle_entries WHERE id=?',(value['id'],))
                    else:value['status']='ready';put(c,value)
            except (ValueError,OSError) as error:
                with db() as c:value['error']=str(error);put(c,value)


def tick():
    init();adopt_projects()
    with db() as c:
        # Do not compete with website/backup operations or an update worker.
        if c.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running')").fetchone():return
        ids=[json.loads(r['value']) for r in c.execute('SELECT value FROM recycle_entries')]
    expired=[value['id'] for value in ids if value['expires']<=time.time() and value['status'] in ('ready','purging','restored')]
    if expired:
        def clean():
            count=0
            for ident in expired:
                purge(ident,True);count+=1
            return str(count)+' abgelaufene Papierkorbeinträge endgültig gelöscht.'
        job('recycle-bin','recycle-purge',clean)


def monitor():
    recover()
    while True:
        try:tick()
        except Exception:pass
        time.sleep(60)


def restore_project(ident):
    """Copy retained project files; reuse the retained DB, or import the saved SQL if absent."""
    from store import project
    from runtime import slug
    import operations as op
    from shared_operations import context,ensure_database
    from database_profiles import profile,sql_command
    with LOCK,db() as c:
        value=load(c,ident)
        if not value.get('legacy') or value['status']!='ready':raise ValueError('Kein wiederherstellbares Projekt.')
        archive=paths(value)[0][1];meta=cleanup.state(archive/'metadata.json');p=meta.get('project',{});name=slug(p.get('slug'))
        if c.execute('SELECT 1 FROM projects WHERE slug=?',(name,)).fetchone():raise ValueError('Ein Projekt mit diesem Namen existiert bereits.')
        source=archive/'project';target=DATA/'projects'/name
        if source.is_symlink() or not source.is_dir() or target.exists():raise ValueError('Projektdateien fehlen oder der Zielordner ist bereits belegt.')
        value['status']='project-restoring';put(c,value)
    staged=DATA/'projects'/('.vmm-restore-'+ident);inserted=False;placed=False;copied=False
    try:
        if staged.exists():raise ValueError('Dateien einer früheren Wiederherstellung sind vorhanden. Bitte zuerst prüfen.')
        if any(path.is_symlink() for path in source.rglob('*')):raise ValueError('Verknüpfte Projektdateien zuerst manuell prüfen.')
        staged.mkdir(parents=True);copied=True;marker=staged/'.vmm-recycle-restore.json';marker.write_text(json.dumps({'id':ident}));shutil.copytree(source,staged,dirs_exist_ok=True);staged.rename(target);placed=True
        with LOCK,db() as c:
            insert(c,'projects',{**p,'status':'stopped','restore':1,'error':None})
            for table,key in (('credentials','credentials'),('extension_plans','plans'),('project_extensions','assignments')):
                for row in meta.get(key,[]):
                    if row.get('license') and not c.execute('SELECT 1 FROM licenses WHERE id=?',(row['license'],)).fetchone():row={**row,'license':None}
                    if table=='extension_plans' and not c.execute('SELECT 1 FROM extension_sources WHERE id=?',(row['source'],)).fetchone():continue
                    if table=='project_extensions' and not c.execute('SELECT 1 FROM extensions WHERE id=?',(row['extension'],)).fetchone():continue
                    insert(c,table,row)
        inserted=True
        _,args=context();op.command(args+['up','-d','--wait','--wait-timeout','180',profile(p)['service']],timeout=300)
        info=__import__('shared_runtime').database_info(p)
        exists=op.command(args+sql_command(p,extra=['-N']),input=("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='"+info['database']+"';").encode()).decode().strip()
        if meta.get('database_exists') and not exists:
            sql=archive/'database.sql'
            if sql.is_symlink() or not sql.is_file():raise ValueError('Die gesicherte Projektdatenbank fehlt.')
            ensure_database(p);op.command(args+sql_command(p,database=True),input=sql.read_bytes(),timeout=600)
        with LOCK,db() as c:
            c.execute('UPDATE projects SET status=\'stopped\',restore=? WHERE slug=?',(p.get('restore',0),name));value['status']='restored';put(c,value)
        context();(target/'.vmm-recycle-restore.json').unlink(missing_ok=True)
        try:purge(ident)
        except (ValueError,OSError):pass  # Only the old copy remains; the restored project is independent.
        return 'Projekt '+name+' wiederhergestellt. Es ist im Manager gestoppt und kann dort gestartet werden.'
    except Exception:
        if inserted:
            with LOCK,db() as c:
                for table in ('credentials','extension_plans','project_extensions'):c.execute('DELETE FROM '+table+' WHERE project=?',(name,))
                c.execute('DELETE FROM projects WHERE slug=?',(name,))
        if placed:shutil.rmtree(target)
        elif copied and staged.exists():shutil.rmtree(staged)
        with LOCK,db() as c:value['status']='ready';put(c,value)
        try:context()
        except Exception:pass
        raise


def describe(c,ident):
    init();value=load(c,ident)
    return {'kind':'recycle','id':ident,'label':value['label'],'name':value['name'],'cms':value.get('cms',''),'size':value.get('size'),'files':len(value['paths']),'projects':[],'blocked':[] if value['status'] in ('ready','purging','restored') else ['Eintrag ist noch in Bearbeitung.'],'note':'Diese Dateien liegen bereits im Papierkorb. Endgültiges Löschen kann nicht rückgängig gemacht werden.','_paths':[saved for _,saved in paths(value)],'_names':[original.name for original,_ in paths(value)],'deletion_mode':'permanent'}
