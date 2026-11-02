"""Persistent, timezone-aware recurring manager jobs; orchestration stays outside the worker pool."""
import datetime as dt
import json,re,secrets,threading,time
from zoneinfo import ZoneInfo
from store import DATA,db,job,project,records,redact,LOCK
ACTIVE={}
KINDS={'updates':'Updates und Erreichbarkeit prüfen','snapshot':'Projektsicherung erstellen'}

def next_time(value,after=None):
    now=dt.datetime.fromtimestamp(time.time() if after is None else after,dt.timezone.utc)
    zone=ZoneInfo(value['timezone']);local=now.astimezone(zone);hour,minute=map(int,value['time'].split(':'))
    for day in range(9):
        date=local.date()+dt.timedelta(days=day)
        if value['frequency']=='weekly' and date.weekday()!=value['weekday']:continue
        candidate=dt.datetime.combine(date,dt.time(hour,minute),zone)
        # Normalize nonexistent DST wall times to the next valid local time.
        candidate=dt.datetime.fromtimestamp(candidate.timestamp(),zone)
        if candidate.timestamp()>now.timestamp():return int(candidate.timestamp())
    raise ValueError('Kein nächster Ausführungstermin gefunden.')

def init():
    with db() as c:
        existed=c.execute("SELECT 1 FROM sqlite_master WHERE name='scheduled_tasks'").fetchone()
        c.execute('CREATE TABLE IF NOT EXISTS scheduled_tasks(id TEXT PRIMARY KEY, config TEXT NOT NULL, next_run INTEGER, last_run INTEGER, last_job TEXT)')
        if not existed:
            value={'name':'Tägliche Projektprüfung','kind':'updates','frequency':'daily','time':'09:00','weekday':0,'timezone':'Europe/Berlin','projects':[],'enabled':True}
            previous=0
            try:previous=json.loads((DATA/'project-checks.json').read_text()).get('started',0)
            except (OSError,ValueError):pass
            c.execute('INSERT OR IGNORE INTO scheduled_tasks VALUES(?,?,?,?,NULL)',('daily-project-checks',json.dumps(value),next_time(value) if previous else int(time.time()),previous or None))

def listing():
    init()
    with db() as c:return [{**json.loads(r['config']),'id':r['id'],'next_run':r['next_run'],'last_run':r['last_run'],'last_job':r['last_job'],'running':r['id'] in ACTIVE} for r in c.execute('SELECT * FROM scheduled_tasks ORDER BY rowid')]

def save(body):
    init();ident=body.get('id') or secrets.token_hex(12)
    name=str(body.get('name','')).strip()
    if not name or len(name)>150:raise ValueError('Eine Bezeichnung mit maximal 150 Zeichen angeben.')
    value={k:body.get(k) for k in ('kind','frequency','time','timezone')}
    if value['kind'] not in KINDS or value['frequency'] not in ('daily','weekly'):raise ValueError('Ungültige Aufgabe oder Häufigkeit.')
    if not isinstance(value['time'],str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',value['time']):raise ValueError('Uhrzeit als HH:MM angeben.')
    try:ZoneInfo(value['timezone'])
    except (ValueError,KeyError,TypeError):raise ValueError('Ungültige Zeitzone.') from None
    weekday=body.get('weekday',0)
    if isinstance(weekday,bool) or not isinstance(weekday,int) or not 0<=weekday<=6:raise ValueError('Ungültiger Wochentag.')
    names=body.get('projects',[])
    if not isinstance(names,list) or len(names)>500 or any(not isinstance(x,str) for x in names):raise ValueError('Projekte auswählen.')
    for name_ in names:project(name_)
    if not isinstance(body.get('enabled',True),bool):raise ValueError('Ungültiger Aktivierungszustand.')
    value.update(name=name,weekday=weekday,projects=list(dict.fromkeys(names)),enabled=body.get('enabled',True))
    with db() as c:
        if body.get('id') and not c.execute('SELECT 1 FROM scheduled_tasks WHERE id=?',(ident,)).fetchone():raise ValueError('Aufgabe nicht gefunden.')
        c.execute('INSERT INTO scheduled_tasks VALUES(?,?,?,NULL,NULL) ON CONFLICT(id) DO UPDATE SET config=excluded.config,next_run=excluded.next_run',(ident,json.dumps(value),next_time(value)))
    return {'id':ident}

def delete(ident):
    init()
    with LOCK:
        if ident in ACTIVE:raise ValueError('Die laufende Aufgabe zuerst beenden.')
        with db() as c:c.execute('DELETE FROM scheduled_tasks WHERE id=?',(ident,))
    return {'ok':True}

def cancel(ident):
    with LOCK:
        event=ACTIVE.get(ident)
        if event:event.set()
    return {'message':'Abbruch angefordert. Der aktuelle Projektschritt wird noch abgeschlossen.'}

def start(ident):
    init()
    with LOCK,db() as c:
        row=c.execute('SELECT * FROM scheduled_tasks WHERE id=?',(ident,)).fetchone()
        if not row:raise ValueError('Aufgabe nicht gefunden.')
        if ident in ACTIVE:raise ValueError('Diese Aufgabe läuft bereits.')
        from storage_service import busy
        if busy():raise ValueError('Eine Speicherumstellung läuft.')
        value=json.loads(row['config']);event=threading.Event();ACTIVE[ident]=event;token=secrets.token_hex(12);now=int(time.time())
        c.execute("INSERT INTO jobs VALUES(?,?,'scheduled-task','queued','Wartet …',?,NULL)",(token,'schedule-'+ident,now))
        c.execute('UPDATE scheduled_tasks SET last_run=?,last_job=?,next_run=? WHERE id=?',(now,token,next_time(value),ident))
    def execute():
        errors=[];skipped=[];done=0
        try:
            with db() as c:c.execute("UPDATE jobs SET status='running' WHERE id=?",(token,))
            values=[p for p in records('projects') if not value['projects'] or p['slug'] in value['projects']]
            for i,p in enumerate(values):
                if event.is_set():break
                with db() as c:c.execute('UPDATE jobs SET message=? WHERE id=?',(str(i)+'/'+str(len(values))+' · '+p['slug'],token))
                if p.get('restore') or p['status']!='running':skipped.append(p['slug']);continue
                try:
                    def action(name=p['slug']):
                        if value['kind']=='updates':return __import__('project_workspace').check_project(name)
                        return __import__('operations').snapshot(name)
                    child=job(p['slug'],'scheduled-check' if value['kind']=='updates' else 'snapshot',action)
                    while True:
                        with db() as c:state=c.execute('SELECT status,message FROM jobs WHERE id=?',(child,)).fetchone()
                        if state['status'] not in ('queued','running'):break
                        time.sleep(.5)
                    if state['status']!='done':errors.append(p['slug']+': '+state['message'])
                    else:done+=1
                except Exception as e:errors.append(p['slug']+': '+redact(str(e)))
            status='interrupted' if event.is_set() else 'error' if errors else 'done'
            message=('Abgebrochen. ' if event.is_set() else '')+str(done)+'/'+str(len(values))+' Projekte abgeschlossen.'+ ('\nÜbersprungen (nicht bereit): '+', '.join(skipped) if skipped else '')+ ('\n'+'\n'.join(errors) if errors else '')
        except Exception as e:status='error';message=redact(str(e))
        finally:
            with db() as c:c.execute('UPDATE jobs SET status=?,message=?,finished=? WHERE id=?',(status,message,int(time.time()),token))
            with LOCK:ACTIVE.pop(ident,None)
    threading.Thread(target=execute,daemon=True).start()
    return {'job':token}

def tick():
    init();now=time.time()
    for task in listing():
        if not task['enabled'] or task['running'] or task['next_run']>now:continue
        try:start(task['id'])
        except (ValueError,RuntimeError):pass

def monitor():
    while True:
        try:tick()
        except Exception:pass
        time.sleep(30)
