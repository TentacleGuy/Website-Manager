"""Describe host project folders for the narrowly scoped native URL handler."""
import json
import os
from pathlib import PurePosixPath, PureWindowsPath
import re
from store import DATA,project
from storage_paths import settings

SCHEME='tentacle-project'


def native_path(value):
    value=value.replace('\\','/').rstrip('/')
    match=re.match(r'^/(?:run/desktop/mnt/host|host_mnt)/([a-zA-Z])/(.*)$',value)
    if match:value=match[1].upper()+':/'+match[2]
    elif value.startswith('/host_mnt/'):value=value[len('/host_mnt'):]
    if value.startswith('//') or re.match(r'^[A-Za-z]:/',value):return str(PureWindowsPath(value))
    if not value.startswith('/'):raise ValueError('Der Projektpfad ist nicht absolut.')
    return str(PurePosixPath(value))


def folder(p):
    if isinstance(p,str):p=project(p)
    name=p['slug']
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',name):raise ValueError('Ungültiger Projektname.')
    result={'available':False,'path':'','url':SCHEME+'://open/'+name,'registered':False,'reason':''}
    if p.get('storage')=='legacy':
        return {**result,'reason':'Dieses Projekt liegt noch in einem Docker-Volume. Erst auf gemeinsame Laufzeiten umstellen.'}
    base=DATA/'projects';site=base/name/'site'
    if not site.is_dir():return {**result,'reason':'Der Projektordner wurde noch nicht angelegt.'}
    # Never let a project symlink turn this into an arbitrary host-folder opener.
    try:relative=site.resolve().relative_to(base.resolve())
    except ValueError:return {**result,'reason':'Der Projektordner verweist außerhalb des Projektspeichers.'}
    if relative.parts!=(name,'site'):return {**result,'reason':'Verknüpfte Projektordner werden nicht geöffnet.'}
    root=settings(DATA).get('projects',os.environ.get('VMM_HOST_DATA',str(DATA)).replace('\\','/').rstrip('/')+'/projects')
    result.update(available=True,path=native_path(root.replace('\\','/').rstrip('/')+'/'+name+'/site'))
    try:
        integration=json.loads((DATA/'desktop-integration.json').read_text())
        result['registered']=integration.get('scheme')==SCHEME and integration.get('version')==1
        result['platform']=integration.get('platform','')
    except (OSError,ValueError):pass
    return result
