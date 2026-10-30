"""Host locations with stable /data/<area> paths inside the manager."""
import json
import os
from pathlib import PurePosixPath
import re

AREAS={'projects':'Projekte','extensions':'Erweiterungspakete','packages':'CMS-Archiv','backups':'Akeeba-Backups','exports':'Projektsicherungen'}
ENV_KEYS={key:'VMM_'+key.upper()+'_PATH' for key in AREAS}


def settings(data=None):
    if data is None:
        from store import DATA
        data=DATA
    file=data/'storage/settings.json'
    if not file.exists():return {}
    result=json.loads(file.read_text())
    if not isinstance(result,dict):raise ValueError('Ungültige Speicherort-Konfiguration.')
    return result


def host_location(key,host_data=None,data=None):
    from runtime import host_path
    if key not in AREAS:raise ValueError('Unbekannter Speicherbereich.')
    if host_data is None:
        from store import DATA
        host_data=os.environ.get('VMM_HOST_DATA',str(DATA))
    return host_path(settings(data).get(key,host_data.rstrip('/')+'/'+key))


def validate_paths(paths,current,host_data):
    from runtime import host_path
    if not isinstance(paths,dict) or set(paths)!=set(AREAS):raise ValueError('Alle fünf Speicherorte angeben.')
    result={}
    root=host_path(host_data)
    for key,value in paths.items():
        if not isinstance(value,str) or not value.strip():raise ValueError(AREAS[key]+': absoluten Ordnerpfad angeben.')
        value=value.strip().replace('\\','/')
        if any(c in value for c in ('\n','\r','\x00',',','$',"'",'"')):raise ValueError('Der Ordnerpfad enthält nicht unterstützte Zeichen.')
        if not value.startswith('/') and not re.match(r'^[A-Za-z]:/',value):raise ValueError('Einen absoluten Ordnerpfad auf dem Docker-Rechner angeben.')
        normalized=host_path(value)
        if '..' in PurePosixPath(normalized).parts or normalized in ('','/') or re.fullmatch(r'/run/desktop/mnt/host/[a-z]',normalized):raise ValueError('Kein Laufwerks- oder Wurzelverzeichnis als Speicherort verwenden.')
        if any(normalized==x or normalized.startswith(x+'/') for x in ('/proc','/sys','/dev','/etc','/usr','/bin','/sbin','/var/run')):raise ValueError('Kein Systemverzeichnis als Speicherort verwenden.')
        if normalized==root or (normalized.startswith(root+'/') and normalized!=root+'/'+key):raise ValueError('Innerhalb des Manager-Datenordners nur den ursprünglichen Bereichsordner verwenden.')
        result[key]=value.rstrip('/')
    targets={key:host_path(value) for key,value in result.items()}
    for key,value in targets.items():
        for other,other_value in targets.items():
            if key!=other and (value==other_value or value.startswith(other_value+'/')):raise ValueError('Die Speicherorte dürfen sich nicht überschneiden.')
        for other,old in current.items():
            old=host_path(old)
            if value!=old and (value.startswith(old+'/') or old.startswith(value+'/')):raise ValueError('Ein Ziel darf keinen bisherigen Speicherort enthalten oder darin liegen.')
            if key!=other and value==old:raise ValueError('Speicherorte können nicht miteinander vertauscht werden.')
    return result
