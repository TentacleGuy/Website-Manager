"""Authorize a single native service action and read the macOS helper's heartbeat."""

import json
import secrets
import threading
import time

from desktop_service import SCHEME
from store import DATA


LOCAL_HOSTS = frozenset({'localhost:8090', '127.0.0.1:8090', '[::1]:8090'})
TOKEN_LIFETIME = 180
ACTIONS = ('start', 'restart', 'stop')
PENDING = {}
LOCK = threading.Lock()


def read_state(filename):
    try:
        value = json.loads((DATA / filename).read_text())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def status(host):
    if host not in LOCAL_HOSTS:
        return {'available': False, 'running': False}
    integration = read_state('desktop-integration.json')
    available = (integration.get('platform') == 'macos' and integration.get('scheme') == SCHEME
                 and integration.get('version') == 1)
    if not available:
        return {'available': False, 'running': False}
    state = read_state('safari-alarm.json')
    pid, heartbeat = state.get('pid'), state.get('time')
    running = (type(pid) is int and pid > 0 and type(heartbeat) is int
               and -5 <= time.time() - heartbeat < 20)
    if running:
        return {'available': True, 'running': True, 'pid': pid}
    return {'available': True, 'running': False}


def create(host, action='start'):
    if not status(host)['available']:
        raise ValueError('Der Tentacle Helfer ist nur im lokal eingerichteten macOS-Manager verfügbar.')
    if action not in ACTIONS:
        raise ValueError('Unbekannte Aktion für den Tentacle Helfer.')
    token = secrets.token_hex(16)
    now = int(time.time())
    expires = now + TOKEN_LIFETIME
    with LOCK:
        for key, (deadline, _) in list(PENDING.items()):
            if deadline <= now:
                del PENDING[key]
        PENDING[token] = (expires, action)
    return {'url': f'{SCHEME}://safari-alarm/{token}', 'expires': expires}


def claim(token):
    with LOCK:
        expires, action = PENDING.pop(token, (0, None))
    if expires <= time.time():
        raise ValueError('Die Anfrage ist abgelaufen. Bitte wiederhole die Aktion.')
    return action
