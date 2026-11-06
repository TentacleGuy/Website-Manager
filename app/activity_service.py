"""Bounded activity queries and explicit retention by an absolute timestamp."""
from datetime import datetime
import json
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import time
from store import DATA, db, redact


def timestamp(value):
    if isinstance(value, bool):
        raise ValueError('Datum und Uhrzeit angeben.')
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ValueError('Ungültiges Datum oder Uhrzeit.') from None
    if not math.isfinite(result) or result < 0 or result > 253402300799:
        raise ValueError('Ungültiges Datum oder Uhrzeit.')
    return result


def listing(query):
    start = timestamp(query.get('from', [time.time() - 7 * 86400])[0])
    end = timestamp(query.get('to', [time.time()])[0])
    if start > end:
        raise ValueError('Der Beginn muss vor dem Ende liegen.')
    try:
        limit = int(query.get('limit', ['100'])[0])
        offset = int(query.get('offset', ['0'])[0])
    except (ValueError, TypeError):
        raise ValueError('Ungültige Seitenauswahl.') from None
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError('Ungültige Seitenauswahl.')
    sort = query.get('sort', ['created'])[0]
    direction = query.get('direction', ['desc'])[0]
    if sort not in ('resource', 'created', 'kind', 'status') or direction not in ('asc', 'desc'):
        raise ValueError('Ungültige Sortierung.')
    try:
        zone = ZoneInfo(query.get('timezone', ['UTC'])[0])
    except (ValueError, ZoneInfoNotFoundError):
        zone = ZoneInfo('UTC')

    def date_text(value):
        date = datetime.fromtimestamp(value, zone)
        return f'{date:%d.%m.%Y} · {date:%H:%M}'

    where = ['created >= ?', 'created <= ?']
    values = [start, end]
    status = query.get('status', [''])[0]
    if status:
        if status not in ('queued', 'running', 'done', 'error', 'interrupted'):
            raise ValueError('Ungültiger Status.')
        where.append('status = ?')
        values.append(status)
    search = query.get('search', [''])[0].strip()
    if search:
        kinds = query.get('kind', [])[:30]
        match = "instr(lower(resource || ' ' || kind || ' ' || coalesce(message,'') || ' ' || status || ' ' || activity_date(created)), lower(?)) > 0"
        values.append(search)
        if kinds:
            match += ' OR kind IN (' + ','.join('?' for _ in kinds) + ')'
            values.extend(kinds)
        status_matches = [value for value in query.get('search_status', []) if value in ('queued','running','done','error','interrupted')]
        if status_matches:
            match += ' OR status IN (' + ','.join('?' for _ in status_matches) + ')'
            values.extend(status_matches)
        where.append('(' + match + ')')
    condition = ' AND '.join(where)
    with db() as c:
        c.create_function('activity_date', 1, date_text)
        total = c.execute('SELECT COUNT(*) FROM jobs WHERE ' + condition, values).fetchone()[0]
        rows = c.execute('SELECT * FROM jobs WHERE ' + condition + f' ORDER BY {sort} {direction}, id DESC LIMIT ? OFFSET ?', values + [limit, offset]).fetchall()
        newest_update = c.execute("SELECT id FROM jobs WHERE kind='manager-install' ORDER BY created DESC, id DESC LIMIT 1").fetchone()
    jobs = [dict(row) for row in rows]
    installs = {job['id']: job for job in jobs if job['kind'] == 'manager-install'}
    if installs:
        for marker in (DATA/'updates').glob('*/activity.json'):
            try:
                ident = json.loads(marker.read_text(encoding='utf-8')).get('job')
                if ident not in installs:
                    continue
                with marker.with_name('update.log').open('rb') as stream:
                    stream.seek(max(0, marker.with_name('update.log').stat().st_size - 16000))
                    installs[ident]['log'] = redact(stream.read().decode(errors='replace'))
            except (OSError, ValueError):
                continue
        if newest_update and newest_update['id'] in installs:
            newest = installs[newest_update['id']]
            if 'log' not in newest:
                from update_service import installation_status
                installation = installation_status() or {}
                if installation.get('job') in (None, newest['id']):
                    newest['log'] = installation.get('log', '')
    return {'jobs': jobs, 'total': total, 'offset': offset, 'limit': limit}


def delete_before(value):
    cutoff = timestamp(value)
    if cutoff > time.time():
        raise ValueError('Der Löschzeitpunkt darf nicht in der Zukunft liegen.')
    with db() as c:
        deleted = c.execute("DELETE FROM jobs WHERE created < ? AND finished IS NOT NULL AND status IN ('done','error','interrupted')", (cutoff,)).rowcount
    return {'deleted': deleted}
