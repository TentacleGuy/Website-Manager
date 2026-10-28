"""Project-scoped, openly visible local credentials."""
import json
import secrets
import time
from urllib.parse import urlparse
from store import db, project
from extension_service import decode_secret


def listing(name):
    project(name)
    with db() as c:
        rows=c.execute('SELECT * FROM credentials WHERE project=? ORDER BY created',(name,)).fetchall()
    result=[]
    for row in rows:
        value=decode_secret(row['secret'])
        password=value.get('password','')
        result.append({**value,'id':row['id'],'has_password':bool(password),'archived':bool(row['archived'])})
    return result


def change(name,body):
    project(name)
    ident=body.get('id');action=body.get('action','save')
    if action not in ('save','reveal','archive','restore'): raise ValueError('Unbekannte Zugangsdaten-Aktion.')
    with db() as c:
        row=c.execute('SELECT * FROM credentials WHERE id=? AND project=?',(ident,name)).fetchone() if isinstance(ident,str) else None
        if ident is not None and not row: raise ValueError('Zugangsdaten nicht gefunden.')
        if action!='save' and not row: raise ValueError('Zugangsdaten auswählen.')
        previous=decode_secret(row['secret']) if row else {}
        if action=='reveal': return {'password':previous.get('password','')}
        if action in ('archive','restore'):
            c.execute('UPDATE credentials SET archived=? WHERE id=? AND project=?',(int(action=='archive'),ident,name))
            return {'ok':True}
        value={}
        for key,limit in (('label',150),('username',500),('password',4096),('url',2048),('note',8000)):
            text=body.get(key,'')
            if key=='password' and text is None: text=previous.get(key,'')
            if not isinstance(text,str) or len(text)>limit: raise ValueError('Ungültiges Feld: '+key)
            value[key]=text.strip() if key in ('label','url') else text
        if not value['label']: raise ValueError('Bezeichnung fehlt.')
        if value['url']:
            url=urlparse(value['url'])
            if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:
                raise ValueError('URL muss mit http:// oder https:// beginnen und darf keine Zugangsdaten enthalten.')
        secret=json.dumps(value,ensure_ascii=False)
        ident=ident or secrets.token_hex(12)
        c.execute('INSERT INTO credentials (id,project,secret,created,archived) VALUES (?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET secret=excluded.secret',
                  (ident,name,secret,int(time.time())))
    return {'id':ident}
