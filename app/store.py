"""Persistent metadata and jobs; Fernet retained for legacy credential migration."""
import os
import re
from pathlib import Path
import sqlite3
import threading
import secrets
import time
from concurrent.futures import ThreadPoolExecutor

DATA = Path(os.environ.get('VMM_DATA', './data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
POOL = ThreadPoolExecutor(max_workers=2)
LOCK = threading.RLock()

def db():
    c = sqlite3.connect(DATA / 'manager.sqlite', timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init():
    with db() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('CREATE TABLE IF NOT EXISTS projects (slug TEXT PRIMARY KEY, cms TEXT, php TEXT, status TEXT, created INTEGER, db_password TEXT, db_root_password TEXT, error TEXT)')
        columns = {r['name'] for r in c.execute('PRAGMA table_info(projects)')}
        for key, definition in {'version': "TEXT DEFAULT ''", 'package_id': 'TEXT', 'storage': "TEXT DEFAULT 'legacy'", 'restore': 'INTEGER DEFAULT 0', 'backup_group': 'TEXT', 'backup_archive': 'TEXT', 'kickstart': "TEXT DEFAULT 'auto'", 'restore_phase': "TEXT DEFAULT ''", 'database_profile': "TEXT DEFAULT 'existing'", 'php_mode': "TEXT DEFAULT 'manual'"}.items():
            if key not in columns: c.execute('ALTER TABLE projects ADD COLUMN ' + key + ' ' + definition)
        c.execute('CREATE TABLE IF NOT EXISTS packages (id TEXT PRIMARY KEY, cms TEXT, version TEXT, filename TEXT, sha256 TEXT, size INTEGER, source TEXT, created INTEGER)')
        c.execute('CREATE TABLE IF NOT EXISTS releases (cms TEXT, version TEXT, url TEXT, PRIMARY KEY(cms,version))')
        c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, resource TEXT, kind TEXT, status TEXT, message TEXT, created INTEGER, finished INTEGER)')
        c.execute('CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created DESC)')
        c.execute('CREATE TABLE IF NOT EXISTS extensions (id TEXT PRIMARY KEY, name TEXT, cms TEXT, kind TEXT, provider TEXT, version TEXT, filename TEXT, sha256 TEXT, created INTEGER)')
        c.execute('CREATE TABLE IF NOT EXISTS licenses (id TEXT PRIMARY KEY, provider TEXT, label TEXT, secret TEXT, created INTEGER)')
        c.execute('CREATE TABLE IF NOT EXISTS project_extensions (project TEXT REFERENCES projects(slug), extension TEXT REFERENCES extensions(id), license TEXT REFERENCES licenses(id), status TEXT, PRIMARY KEY(project,extension))')
        c.execute('CREATE TABLE IF NOT EXISTS credentials (id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(slug), secret TEXT NOT NULL, created INTEGER, archived INTEGER DEFAULT 0)')
        # A separate storage worker owns this job while the manager is restarted.
        storage_job=''
        try:
            import json
            state=json.loads((DATA/'storage/apply-status.json').read_text())
            if state.get('status') in ('queued','running') and time.time()-state.get('time',0)<7200:storage_job=state.get('id','')
        except (OSError,ValueError):pass
        c.execute("UPDATE jobs SET status='interrupted', message='Manager wurde während des Vorgangs beendet.', finished=? WHERE status IN ('queued','running') AND id!=?", (int(time.time()),storage_job))
        c.execute("UPDATE projects SET status='unknown' WHERE status IN ('starting','stopping','preparing')")


def records(table):
    if table not in ('projects','packages','jobs','extensions','licenses'): raise ValueError('Unbekannte Tabelle.')
    with db() as c: return [dict(r) for r in c.execute('SELECT * FROM ' + table + ' ORDER BY created DESC')]

def project(name):
    with db() as c: p = c.execute('SELECT * FROM projects WHERE slug=?', (name,)).fetchone()
    if not p: raise ValueError('Projekt nicht gefunden.')
    return dict(p)

def redact(message):
    message = str(message)
    with db() as c:
        for r in c.execute('SELECT db_password,db_root_password FROM projects'):
            for value in r:
                if value: message = message.replace(value, '[redacted]')
    with db() as c:
        keys=c.execute('SELECT secret FROM licenses').fetchall()
    for key in keys:
        try:
            secret=cipher().decrypt(key['secret'].encode()).decode()
            if secret: message=message.replace(secret,'[redacted]')
        except Exception:
            pass
    shared_secret=DATA/'shared/secrets.json'
    if shared_secret.is_file():
        try:
            import json
            value=json.loads(shared_secret.read_text())['root_password']
            message=message.replace(value,'[redacted]')
        except Exception:pass
    message=re.sub(r'(https?://[^\s?]+)\?[^\s]+',r'\1?[redacted]',message)
    return message[-3000:]

def job(resource, kind, fn):
    from storage_service import busy
    with LOCK, db() as c:
        if busy():raise ValueError('Die Speicherorte werden gerade umgestellt. Bitte den Abschluss abwarten.')
        if c.execute("SELECT 1 FROM jobs WHERE resource=? AND status IN ('queued','running')", (resource,)).fetchone():
            raise ValueError('Für diesen Eintrag läuft bereits ein Vorgang.')
        ident = secrets.token_hex(12)
        c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,NULL)', (ident,resource,kind,'queued','Wartet …',int(time.time())))
    def run():
        with db() as c: c.execute("UPDATE jobs SET status='running', message='Vorgang läuft …' WHERE id=?", (ident,))
        try:
            result = fn()
            status, message = 'done', redact(result or 'Abgeschlossen.')
        except Exception as e:
            status, message = 'error', redact(e)
        with db() as c: c.execute('UPDATE jobs SET status=?, message=?, finished=? WHERE id=?', (status,message,int(time.time()),ident))
    POOL.submit(run)
    return ident


def cipher():
    try: from cryptography.fernet import Fernet
    except ImportError: raise ValueError('Schlüsselspeicher benötigt: pip install -r requirements.txt')
    keyfile = DATA / 'vault.key'
    with LOCK:
        if not keyfile.exists():
            fd = os.open(str(keyfile), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as f: f.write(Fernet.generate_key())
        return Fernet(keyfile.read_bytes())

init()
