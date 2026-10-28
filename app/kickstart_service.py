"""Versioned official Kickstart downloads, cached outside the source tree."""
import hashlib
import io
import json
import re
import threading
import time
import zipfile
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
from store import DATA

BASE='https://www.akeeba.com/download/akeeba-kickstart.html'
LOCK=threading.RLock()


def fetch(url,limit=8*1024*1024):
    if urlparse(url).scheme!='https' or urlparse(url).hostname not in ('www.akeeba.com','cdn.akeeba.com'):
        raise ValueError('Nur offizielle Akeeba-Downloads erlaubt.')
    with urlopen(Request(url,headers={'User-Agent':'Tentacle-Website-Manager/1.0'}),timeout=45) as response:
        final=urlparse(response.url)
        if final.scheme!='https' or final.hostname not in ('www.akeeba.com','cdn.akeeba.com'):raise ValueError('Unerwartete Downloadumleitung.')
        value=response.read(limit+1)
    if len(value)>limit:raise ValueError('Kickstart-Download ist zu groß.')
    return value


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            self.links.append(urljoin(BASE,href))


def catalog(refresh=False):
    cache=DATA/'tools/kickstart-catalog.json'
    with LOCK:
        if cache.is_file() and not refresh:return json.loads(cache.read_text())
        todo=[BASE];seen=set();versions={}
        while todo and len(seen)<12:
            url=todo.pop(0)
            if url in seen:continue
            seen.add(url);parser=Links();parser.feed(fetch(url).decode())
            for link in parser.links:
                match=re.fullmatch(r'https://www\.akeeba\.com/download/akeeba-kickstart/(\d+(?:-\d+){2})\.html',link)
                if match:versions[match[1].replace('-','.')]=link
                elif link.startswith(BASE+'?start=') and link not in seen:todo.append(link)
        if not versions:raise ValueError('Akeeba-Versionsliste konnte nicht gelesen werden.')
        rows=[{'version':v,'page':versions[v]} for v in sorted(versions,key=lambda s:tuple(map(int,s.split('.'))),reverse=True)]
        cache.parent.mkdir(exist_ok=True);cache.write_text(json.dumps(rows));return rows


def available():
    path=DATA/'tools/kickstart-catalog.json'
    return catalog() if path.is_file() else []


def ensure(version='auto',php='8.4'):
    with LOCK:
        if version=='manual':
            path=DATA/'tools/kickstart.php'
            if not path.is_file():raise ValueError('Manuell hinterlegte kickstart.php fehlt.')
            return path
        rows=catalog()
        # Latest Core supports PHP 5.6–8.5; older versions remain selectable per project.
        selected=rows[0]['version'] if version in ('auto','latest','') else version
        if not any(r['version']==selected for r in rows):raise ValueError('Kickstart-Version nicht im offiziellen Katalog.')
        path=DATA/'tools/kickstart'/selected/'kickstart.php'
        if path.is_file():return path
        page=next(r['page'] for r in rows if r['version']==selected)
        parser=Links();parser.feed(fetch(page).decode())
        url=next((u for u in parser.links if re.search(r'/kickstart-core-[\d.-]+-zip\.zip$',u)),None)
        if not url:raise ValueError('Kein öffentlicher Kickstart-Core-Download für diese Version verfügbar.')
        with zipfile.ZipFile(io.BytesIO(fetch(url))) as archive:
            entries=[i for i in archive.infolist() if i.filename=='kickstart.php']
            if len(entries)!=1 or entries[0].file_size>20*1024*1024:raise ValueError('Ungültiges Kickstart-Paket.')
            content=archive.read(entries[0])
        if b'<?php' not in content[:2048]:raise ValueError('Kickstart-PHP fehlt im Download.')
        path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix('.partial');temp.write_bytes(content);temp.replace(path)
        path.with_suffix('.json').write_text(json.dumps({'version':selected,'url':url,'sha256':hashlib.sha256(content).hexdigest(),'downloaded':int(time.time())}))
        return path
