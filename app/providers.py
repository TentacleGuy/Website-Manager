"""Explicit provider records instead of free-text identities."""
import json,secrets
from store import db


def init():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS providers (id TEXT PRIMARY KEY,name TEXT NOT NULL,website TEXT,scope TEXT)')
        for ident,name in [('yootheme','YOOtheme'),('zoolanders','ZOOlanders'),('akeeba','Akeeba'),('jce','JCE'),('wordpress.org','WordPress.org'),('custom','Andere / eigene Pakete')]:c.execute('INSERT OR IGNORE INTO providers VALUES (?,?,?,?)',(ident,name,'','extension'))
        for r in c.execute('SELECT DISTINCT provider FROM licenses UNION SELECT DISTINCT provider FROM extensions').fetchall():
            if r[0]:c.execute('INSERT OR IGNORE INTO providers VALUES (?,?,?,?)',(r[0],r[0],'','extension'))


def listing():
    with db() as c:return [dict(r) for r in c.execute('SELECT * FROM providers ORDER BY name')]


def save(body):
    name=str(body.get('name','')).strip();scope=body.get('scope','extension')
    if not name or len(name)>100 or scope not in ('provider','extension'):raise ValueError('Anbietername und Lizenzmodell angeben.')
    ident=body.get('id') or secrets.token_hex(12)
    with db() as c:c.execute('INSERT INTO providers VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,website=excluded.website,scope=excluded.scope',(ident,name,str(body.get('website','')),scope))
    return ident

init()
