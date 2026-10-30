"""Compatibilidade de identidade entre anúncios da mesma caminhada.

Uma semelhança de título/data não basta para fundir duas sessões.
Funções sem rede nem dependências para utilização em todas as fases.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit, parse_qsl, urlencode


UNKNOWN_PLACES = {'', 'por confirmar', 'a confirmar', 'por definir',
                  'desconhecido', 'local a definir', 'nao definido', 'a definir'}
DETAIL_PATH = re.compile(
    r'/(?:evento|eventos|produto|caminhada|caminhadas|tour|informa-es-do-evento-e-registro)/[^/]+',
    re.I,
)


def _fold(value):
    text = unicodedata.normalize('NFD', str(value or ''))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text.casefold())).strip()


def _time(event):
    raw = str(event.get('time') or '').strip().lower()
    match = re.fullmatch(r'(\d{1,2})[:h](\d{2})', raw)
    if not match:
        return ''
    hour, minute = int(match[1]), int(match[2])
    return f'{hour:02d}:{minute:02d}' if hour < 24 and minute < 60 else ''


def _place(event):
    value = _fold(event.get('start'))
    return '' if value in UNKNOWN_PLACES or len(value) < 5 else value


def _detail_url(event):
    try:
        parsed = urlsplit(str(event.get('url') or ''))
        host = (parsed.hostname or '').lower().removeprefix('www.')
        path = parsed.path.rstrip('/').lower()
        if parsed.scheme not in ('https', 'http') or not host or not DETAIL_PATH.search(path):
            return ''
        # A ficha pode distinguir sessões na query. Só retirar rastreio conhecido.
        params = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                  if not key.lower().startswith('utm_')
                  and key.lower() not in {'fbclid', 'gclid', 'msclkid'}]
        # Ordenar chaves, preservando a ordem dos valores de chaves repetidas.
        query = urlencode(sorted(params, key=lambda pair: pair[0]))
        return host + path + ('?' + query if query else '')
    except ValueError:
        return ''


def _confirmed_gps(event):
    if event.get('verified') is not True:
        return None
    try:
        if isinstance(event.get('lat'), bool) or isinstance(event.get('lon'), bool):
            return None
        lat, lon = float(event['lat']), float(event['lon'])
        if ((36 <= lat <= 43 and -10 <= lon <= -6)
                or (31.8 <= lat <= 33.6 and -18 <= lon <= -15.5)
                or (36.5 <= lat <= 40.1 and -32 <= lon <= -24)):
            return lat, lon
    except (ValueError, TypeError, KeyError):
        pass
    return None


def sessoes_diferentes(first, second):
    """Só rejeita a fusão quando existem indícios concretos de sessões distintas.

    Datas e organizadores já são comparados pelo chamador; um campo desconhecido
    não deve ser tratado como contradição. Um URL de agenda genérica não é prova
    de identidade de duas edições.
    """
    first_time, second_time = _time(first), _time(second)
    if first_time and second_time and first_time != second_time:
        return True
    detail_a, detail_b = _detail_url(first), _detail_url(second)
    if detail_a and detail_b and detail_a != detail_b:
        return True
    gps_a, gps_b = _confirmed_gps(first), _confirmed_gps(second)
    same_gps = bool(gps_a and gps_b and all(abs(a-b) <= 0.000001 for a,b in zip(gps_a,gps_b)))
    if gps_a and gps_b and not same_gps:
        return True
    # A mesma ficha, edição, hora e GPS confirmado permitem designações
    # diferentes do mesmo ponto. A tolerância cobre apenas arredondamentos.
    same_meeting = (same_gps and detail_a and detail_a == detail_b
                    and first_time and first_time == second_time
                    and first.get('date') and first.get('date') == second.get('date')
                    and _fold(first.get('organizer'))
                    and _fold(first.get('organizer')) == _fold(second.get('organizer'))
                    and urlsplit(str(first.get('url'))).query == urlsplit(str(second.get('url'))).query)
    start_a, start_b = _place(first), _place(second)
    if not same_meeting and start_a and start_b and start_a != start_b and (
            start_a not in start_b and start_b not in start_a):
        return True
    return False


def event_aliases(event):
    values = event.get('alias_ids')
    return {value for value in values if isinstance(value, str) and value} if isinstance(values, list) else set()


def sanitize_aliases(events):
    """Conservar aliases inequívocos sem roubar IDs de outros anúncios."""
    primary_ids = {event.get('id') for event in events}
    owners = {}
    for event in events:
        for alias in event_aliases(event):
            owners.setdefault(alias, set()).add(event.get('id'))
    for event in events:
        aliases = sorted(alias for alias in event_aliases(event)
                         if alias not in primary_ids and len(owners[alias]) == 1)
        if aliases:
            event['alias_ids'] = aliases
        else:
            event.pop('alias_ids', None)


def refresh_observed_values(target, candidate, current_ids=None):
    """Separar o ID canónico dos valores explicitamente recolhidos mais tarde."""
    from datetime import date
    import math
    detail = _detail_url(target)
    if (not detail or detail != _detail_url(candidate)
            or target.get('date') != candidate.get('date')
            or not _fold(target.get('organizer'))
            or _fold(target.get('organizer')) != _fold(candidate.get('organizer'))
            or sessoes_diferentes(target, candidate)
            or urlsplit(str(target.get('url'))).query != urlsplit(str(candidate.get('url'))).query):
        return
    current_ids = current_ids if current_ids is not None else set()
    target_current = target.get('id') in current_ids
    candidate_current = candidate.get('id') in current_ids
    if target_current != candidate_current:
        newer = candidate_current
    else:
        try:
            before = date.fromisoformat(str(target.get('last_seen_at')))
            after = date.fromisoformat(str(candidate.get('last_seen_at')))
            newer = before < after <= date.today()
        except ValueError:
            newer = False
    if not newer:
        return
    for field in ('price', 'km', 'gain', 'duration', 'difficulty'):
        value = candidate.get(field)
        if (type(value) in (int, float) and value >= 0
                and (type(value) is int or math.isfinite(value))):
            if field == 'difficulty' and (type(value) is not int or not 1 <= value <= 5):
                continue
            target[field] = value
    if candidate.get('last_seen_at'):
        target['last_seen_at'] = candidate['last_seen_at']
    if candidate_current:
        current_ids.add(target.get('id'))
