"""Short-lived native directory picker hand-off; a selection never applies storage changes."""
import re,secrets,time,threading
from store import DATA
from desktop_service import native_path
import json
PENDING={};LOCK=threading.RLock()

def create(mode='choose'):
    if mode not in ('choose','repair'):raise ValueError('Ungültige Ordneranfrage.')
    try:registered=json.loads((DATA/'desktop-integration.json').read_text()).get('scheme')=='tentacle-project'
    except (OSError,ValueError):registered=False
    if not registered:raise ValueError('Den Manager einmal über die lokale Starten-Datei starten, um die Ordnerauswahl einzurichten.')
    token=secrets.token_hex(16)
    with LOCK:
        for key in list(PENDING):
            if PENDING[key]['expires']<time.time():PENDING.pop(key)
        PENDING[token]={'status':'waiting','path':'','expires':time.time()+180}
    return {'id':token,'url':'tentacle-project://'+mode+'/'+token}

def result(token):
    with LOCK:
        if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{32}',token) or token not in PENDING or PENDING[token]['expires']<time.time():raise ValueError('Ordnerauswahl abgelaufen. Bitte erneut öffnen.')
        return {k:v for k,v in PENDING[token].items() if k!='expires'}

def complete(token,path):
    with LOCK:
        result(token)
        if PENDING[token]['status']!='waiting':raise ValueError('Die Ordnerauswahl ist bereits abgeschlossen.')
        if not isinstance(path,str) or len(path)>4096 or any(x in path for x in ('\r','\n','\x00')):raise ValueError('Ungültiger Ordnerpfad.')
        path=native_path(path) if path else ''
        PENDING[token].update(status='done' if path else 'cancelled',path=path)
        report=DATA/'desktop-access.json';temp=report.with_suffix('.new');temp.write_text(json.dumps({'checked':int(time.time()),'status':'selected' if path else 'cancelled'}));temp.replace(report)
    return {'ok':True}
