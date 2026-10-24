#!/usr/bin/env python3
"""Única fonte da agenda: integrar excepções documentadas antes da publicação.

O HTML nunca acrescenta eventos ao catálogo online. As excepções são auditáveis,
restritas à edição e não substituem anúncios confirmados pelo colector.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
import json
import re
import unicodedata

ROOT = Path(__file__).resolve().parent
EXCEPTIONS_PATH = ROOT / 'excepcoes_catalogo.json'


def folded(v):
    return ''.join(c for c in unicodedata.normalize('NFD', str(v or ''))
                   if unicodedata.category(c) != 'Mn').casefold().strip()


def normalized_title(v):
    return re.sub(r'[^a-z0-9]+', '', folded(v))


def url_key(value):
    try:
        u = urlsplit(str(value or ''))
        if u.scheme not in ('https', 'http') or not u.hostname:
            return ''
        return (u.hostname.lower().removeprefix('www.') + u.path.rstrip('/').lower())
    except ValueError:
        return ''


def record_key(item):
    return (str(item.get('date') or ''), normalized_title(item.get('organizer')),
            normalized_title(item.get('title')))


def event_match(item, existing):
    if item.get('date') != existing.get('date') or normalized_title(item.get('organizer')) != normalized_title(existing.get('organizer')):
        return False
    if record_key(item) == record_key(existing):
        return True
    # Somente URLs de eventos individuais. Não fundir duas actividades do
    # mesmo dia anunciadas numa página de calendário partilhada.
    k1, k2 = url_key(item.get('url')), url_key(existing.get('url'))
    if k1 != k2 or not k1:
        return False
    path = urlsplit(str(item.get('url'))).path.strip('/')
    wrapped = '/' + path + '/'
    return len(path) >= 13 and any(part in wrapped for part in (
        '/eventos/', '/evento/', '/produto/', '/informa-es-do-evento-e-registro/',
        'trilhodasbruxas'))


def load_registry(path=EXCEPTIONS_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema') != 1:
        raise ValueError('Registo de excepções incompatível')
    corrections = data.get('corrections')
    fallback = data.get('fallback_events')
    if not isinstance(corrections, list) or not isinstance(fallback, list):
        raise ValueError('Correcções e eventos têm de ser listas')
    for row in corrections:
        if (not isinstance(row, dict) or not isinstance(row.get('fields'), dict)
                or not all(row.get(k) for k in ('organizer', 'date', 'slug', 'verified_at'))):
            raise ValueError('Correcção sem identidade/proveniência')
    for row in fallback:
        e = row.get('event') if isinstance(row, dict) else None
        if (not isinstance(e, dict) or not all(e.get(k) for k in ('id','title','date','organizer','url'))
                or not row.get('verified_at') or not row.get('origin')
                or url_key(e['url']) == '' or url_key(e['url']) != url_key(row['origin'])):
            raise ValueError('Evento manual sem identidade, data ou origem válida')
        if (urlsplit(e['url']).hostname or '').removeprefix('www.') == 'trilhosecaminhadas.pt':
            raise ValueError('Não admitir anúncios do agregador desactivado')
        if row['expires_on'] != e['date']:
            raise ValueError('A validade deve terminar no dia do evento')
        date.fromisoformat(e['date'])
    return data


def integrate(events, registry, today=None):
    today = today or date.today()
    output = list(events)
    corrections = {}
    for row in registry['corrections']:
        key = (row['organizer'], row['slug'], row['date'])
        if key in corrections:
            raise ValueError('Correcção duplicada: '+str(key))
        corrections[key] = row['fields']
    inserted = 0
    matched = 0
    expired = 0
    for row in registry['fallback_events']:
        event = row['event']
        if date.fromisoformat(row['expires_on']) < today:
            expired += 1
            continue
        existing = next((old for old in output if event_match(event, old)), None)
        if existing:
            matched += 1
            if existing.get('id') != event['id']:
                aliases = set(existing.get('alias_ids') or [])
                aliases.update(event.get('alias_ids') or [])
                aliases.add(event['id'])
                aliases.discard(existing.get('id'))
                existing['alias_ids'] = sorted(aliases)
        else:
            # Não confundir uma conferência manual antiga com uma recolha recente.
            record = dict(event)
            record['last_seen_at'] = row['verified_at']
            record['source_name'] = 'excepcao_confirmada'
            output.append(record)
            inserted += 1
    return output, corrections, {'added': inserted, 'already_collected': matched, 'expired': expired}
