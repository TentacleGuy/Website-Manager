"""Official release catalogue and immutable package archive."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import tempfile
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
import zipfile
from store import DATA, db

MAX_ARCHIVE = 1024 * 1024 * 1024
MAX_EXTRACTED = 3 * MAX_ARCHIVE
HOSTS = ('wordpress.org','downloads.wordpress.org','api.wordpress.org','downloads.joomla.org','api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com')

def valid_cms(cms):
    if cms not in ('wordpress','joomla'): raise ValueError('CMS muss Joomla oder WordPress sein.')
    return cms

def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}(?:[-a-zA-Z0-9.]*)?', value): raise ValueError('Ungültige Versionsnummer.')
    return value

def checked_url(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname not in HOSTS or p.username or p.password or p.port not in (None,443):
        raise ValueError('Download nur von offiziellen CMS-Quellen erlaubt.')
    return url

class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def remote(url):
    checked_url(url)
    try:
        return build_opener(Redirects()).open(Request(url, headers={'User-Agent':'VMM-Local/0.2','Accept':'application/json,text/html,*/*'}), timeout=45)
    except Exception:
        raise ValueError('Offizielle Downloadquelle nicht erreichbar. Internetverbindung oder API-Limit prüfen.') from None

def sync(cms):
    valid_cms(cms)
    found = {}
    if cms == 'wordpress':
        with remote('https://wordpress.org/download/releases/') as response: html = response.read(8*1024*1024).decode()
        for url, v in re.findall(r'(https://(?:downloads\.)?wordpress\.org/(?:release/)?wordpress-([0-9]+(?:\.[0-9]+){1,3})\.zip)', html):
            found[v] = url
    else:
        # GitHub's official repository exposes installable Full_Package assets.
        for page in range(1, 31):
            with remote('https://api.github.com/repos/joomla/joomla-cms/releases?per_page=100&page=' + str(page)) as response:
                releases = json.load(response)
            if not isinstance(releases, list): raise ValueError('Unerwartete Antwort des Joomla-Katalogs.')
            for release in releases:
                if release.get('draft') or release.get('prerelease'): continue
                v = release.get('tag_name','').lstrip('v')
                if not re.fullmatch(r'\d+(?:\.\d+){1,3}', v): continue
                for asset in release.get('assets', []):
                    if asset['name'].lower().endswith('full_package.zip'):
                        found[v] = asset['browser_download_url']; break
            if len(releases) < 100: break
    if not found: raise ValueError('Keine Installationspakete gefunden; bestehender Katalog bleibt erhalten.')
    with db() as c:
        for v, url in found.items(): c.execute('INSERT OR REPLACE INTO releases VALUES (?,?,?)', (cms,v,checked_url(url)))
    return str(len(found)) + ' Versionen im Katalog.'

def validate_zip(path):
    total = 0
    with zipfile.ZipFile(path) as z:
        if len(z.infolist()) > 200000: raise ValueError('Archiv enthält zu viele Dateien.')
        for info in z.infolist():
            name = info.filename
            parts = PurePosixPath(name).parts
            if '\\' in name or not parts or name.startswith('/') or '..' in parts or ':' in name:
                raise ValueError('Archiv enthält unsichere Dateipfade.')
            if stat.S_ISLNK(info.external_attr >> 16): raise ValueError('Symbolische Links im Archiv sind nicht erlaubt.')
            total += info.file_size
            if total > MAX_EXTRACTED: raise ValueError('Entpacktes Archiv ist zu groß.')
        bad = z.testzip()
        if bad: raise ValueError('Archiv ist beschädigt.')

def unpack(path, target):
    validate_zip(path)
    target = Path(target)
    if target.exists() and any(target.iterdir()): raise ValueError('Zielverzeichnis ist nicht leer.')
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as z: z.extractall(target)
    # WordPress's official archive has one enclosing directory.
    if (target/'wordpress'/'wp-includes'/'version.php').is_file():
        nested = target/'wordpress'
        for item in nested.iterdir(): item.rename(target/item.name)
        nested.rmdir()

def digest(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def register(path, cms, v, source):
    valid_cms(cms); version(v); validate_zip(path)
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if cms == 'wordpress' and not any(n.endswith('wp-includes/version.php') for n in names): raise ValueError('Kein WordPress-Installationspaket.')
        if cms == 'joomla' and not any(n.endswith('installation/index.php') for n in names): raise ValueError('Kein vollständiges Joomla-Installationspaket.')
    sha = digest(path)
    with db() as c:
        existing = c.execute('SELECT id FROM packages WHERE cms=? AND version=? AND sha256=?',(cms,v,sha)).fetchone()
        if existing: return existing['id']
    ident = secrets.token_hex(12)
    folder = DATA/'packages'; folder.mkdir(exist_ok=True)
    filename = ident+'.zip'
    shutil.copyfile(path,folder/filename)
    with db() as c: c.execute('INSERT INTO packages VALUES (?,?,?,?,?,?,?,?)',(ident,cms,v,filename,sha,Path(path).stat().st_size,source,int(time.time())))
    return ident

def download(cms,v):
    valid_cms(cms); version(v)
    with db() as c: row = c.execute('SELECT url FROM releases WHERE cms=? AND version=?',(cms,v)).fetchone()
    if not row: raise ValueError('Version nicht im Katalog. Zuerst Versionen abrufen oder Paket importieren.')
    with tempfile.TemporaryDirectory(dir=DATA) as tmp:
        path = Path(tmp)/'package.zip'
        with remote(row['url']) as response, path.open('wb') as out:
            size=0
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                size+=len(chunk)
                if size>MAX_ARCHIVE: raise ValueError('Download ist zu groß.')
                out.write(chunk)
        register(path,cms,v,row['url'])
    return 'Installationspaket dauerhaft archiviert.'
