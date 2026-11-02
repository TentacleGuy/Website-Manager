"""Validate the maintained changelog and produce release notes from its version entry."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
HEADER=re.compile(r'^## \[([^\]]+)\](?: - (\d{4}-\d{2}-\d{2}))?$',re.M)
VERSION=re.compile(r'\d+\.\d+\.\d+')


def sections(text):
    headers=list(HEADER.finditer(text));result={};last=None
    if not headers or headers[0][1]!='Unveröffentlicht':raise ValueError('Der erste Abschnitt muss [Unveröffentlicht] heißen.')
    for index,header in enumerate(headers):
        name,date=header.groups()
        if name in result:raise ValueError('Doppelter Changelog-Abschnitt: '+name)
        body=text[header.end():headers[index+1].start() if index+1<len(headers) else len(text)].strip()
        if name=='Unveröffentlicht':
            if date:raise ValueError('Unveröffentlicht erhält noch kein Releasedatum.')
            if not body:raise ValueError('Unveröffentlicht braucht Einträge oder „Noch keine Änderungen.“.')
        else:
            if not VERSION.fullmatch(name) or not date:raise ValueError('Version und Releasedatum fehlen: '+name)
            datetime.date.fromisoformat(date)
            number=tuple(map(int,name.split('.')))
            if last is not None and number>=last:raise ValueError('Versionen müssen absteigend sortiert sein.')
            last=number
            if not re.search(r'^- \S',body,re.M):raise ValueError('Änderungen fehlen für Version '+name)
        result[name]={'date':date,'body':body}
    return result


def check_changes(root,base):
    if not base or not base.strip('0'):return
    if not re.fullmatch(r'[a-fA-F0-9]{40,64}',base):raise ValueError('Ungültiger Vergleichscommit für die Changelog-Prüfung.')
    process=subprocess.run(['git','diff','--name-only',base,'HEAD'],cwd=root,capture_output=True,text=True,check=True)
    files=process.stdout.splitlines()
    relevant=any(name.startswith(('app/','installer/','infra/','scripts/')) or name in ('Dockerfile','compose.yaml','requirements.txt','scripts/setup.py','scripts/installer_config.py') for name in files)
    if relevant and 'CHANGELOG.md' not in files:raise ValueError('Programmänderungen benötigen einen Eintrag in CHANGELOG.md.')


def validate(root=ROOT,tag=None,base=None):
    entries=sections((root/'CHANGELOG.md').read_text(encoding='utf-8'))
    current=json.loads((root/'app/release.json').read_text(encoding='utf-8'))['version']
    if current not in entries:raise ValueError('Changelog-Eintrag für app/release.json fehlt: '+current)
    if next(name for name in entries if name!='Unveröffentlicht')!=current:raise ValueError('Die neueste Changelog-Version muss app/release.json entsprechen.')
    if tag:
        if tag!='v'+current:raise ValueError('Git-Tag, app/release.json und Changelog müssen dieselbe Version haben.')
        if entries['Unveröffentlicht']['body']!='Noch keine Änderungen.':raise ValueError('Vor dem Release die offenen Änderungen versionieren und Unveröffentlicht auf „Noch keine Änderungen.“ setzen.')
    check_changes(root,base)
    return entries,current


def notes(root=ROOT,tag=None):
    entries,current=validate(root,tag=tag)
    entry=entries[current]
    return '# Website Manager '+current+'\n\n'+entry['date']+'\n\n'+entry['body']+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag');parser.add_argument('--base',default=os.environ.get('CHANGELOG_BASE'));parser.add_argument('--notes',type=Path);args=parser.parse_args()
    try:
        validate(tag=args.tag,base=args.base)
        if args.notes:
            args.notes.parent.mkdir(parents=True,exist_ok=True);args.notes.write_text(notes(tag=args.tag),encoding='utf-8')
        print('Changelog geprüft.')
    except (ValueError,OSError,subprocess.CalledProcessError) as error:raise SystemExit(str(error))
