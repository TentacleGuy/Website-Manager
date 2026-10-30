"""Bounded activity queries and explicit retention by an absolute timestamp."""
import math
import time
from store import db


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
        match = "instr(lower(resource || ' ' || kind || ' ' || coalesce(message,'')), lower(?)) > 0"
        values.append(search)
        if kinds:
            match += ' OR kind IN (' + ','.join('?' for _ in kinds) + ')'
            values.extend(kinds)
        where.append('(' + match + ')')
    condition = ' AND '.join(where)
    with db() as c:
        total = c.execute('SELECT COUNT(*) FROM jobs WHERE ' + condition, values).fetchone()[0]
        rows = c.execute('SELECT * FROM jobs WHERE ' + condition + ' ORDER BY created DESC, id DESC LIMIT ? OFFSET ?', values + [limit, offset]).fetchall()
    return {'jobs': [dict(row) for row in rows], 'total': total, 'offset': offset, 'limit': limit}


def delete_before(value):
    cutoff = timestamp(value)
    if cutoff > time.time():
        raise ValueError('Der Löschzeitpunkt darf nicht in der Zukunft liegen.')
    with db() as c:
        deleted = c.execute("DELETE FROM jobs WHERE created < ? AND finished IS NOT NULL AND status IN ('done','error','interrupted')", (cutoff,)).rowcount
    return {'deleted': deleted}
