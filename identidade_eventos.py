"""Compatibilidade de identidade entre anúncios da mesma caminhada.

Uma semelhança de título/data não basta para fundir duas sessões.
Funções sem rede nem dependências para utilização em todas as fases.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit


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
        return host + path
    except ValueError:
        return ''


def sessoes_diferentes(first, second):
    """Só rejeita a fusão quando existem indícios concretos de sessões distintas.

    Datas e organizadores já são comparados pelo chamador; um campo desconhecido
    não deve ser tratado como contradição. Um URL de agenda genérica não é prova
    de identidade de duas edições.
    """
    first_time, second_time = _time(first), _time(second)
    if first_time and second_time and first_time != second_time:
        return True
    start_a, start_b = _place(first), _place(second)
    if start_a and start_b and start_a != start_b and (
            start_a not in start_b and start_b not in start_a):
        return True
    detail_a, detail_b = _detail_url(first), _detail_url(second)
    if detail_a and detail_b and detail_a != detail_b:
        return True
    return False


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
