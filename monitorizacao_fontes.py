#!/usr/bin/env python3
"""Recolha com diagnóstico, sem alterar o código do colector.

Executa recolher.main() já versionado, acompanha pedidos HTTP das fontes,
regista falhas por fonte e identifica apenas os anúncios vistos NESTA execução.
Mantém eventos anteriores quando uma fonte fica temporariamente inacessível.
Não faz pedidos adicionais e não declara 'sem caminhadas' quando o parser falha.
"""
from __future__ import annotations

from collections import defaultdict
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import functools
import json
import sys

CURRENT_SOURCE: ContextVar[str | None] = ContextVar('trilhario_source', default=None)
SOURCE_STATES = (
    'com_eventos', 'recolha_parcial', 'sem_anuncios_reconhecidos',
    'erro_http', 'erro_rede', 'erro_resposta', 'erro_extraccao',
    'erro_parcial', 'nao_verificada',
)


def empty_metrics() -> dict:
    return {'http_ok': 0, 'http_errors': [], 'network_errors': 0,
            'usable_pages': 0, 'unusable_pages': 0, 'exceptions': 0,
            'seen': [], 'requests': 0}


def classify_source(metrics: dict, original: dict) -> str:
    """Classificação conservadora baseada no que foi efectivamente observado."""
    if metrics.get('exceptions') or original.get('state') == 'erro':
        return 'erro_extraccao'
    n = len(metrics.get('seen') or ())
    failures = len(metrics.get('http_errors', [])) + metrics.get('network_errors', 0) + metrics.get('unusable_pages', 0)
    if n:
        return 'recolha_parcial' if failures else 'com_eventos'
    if metrics.get('usable_pages', 0):
        return 'erro_parcial' if failures else 'sem_anuncios_reconhecidos'
    if metrics.get('http_errors'):
        return 'erro_http'
    if metrics.get('network_errors'):
        return 'erro_rede'
    if metrics.get('unusable_pages'):
        return 'erro_resposta'
    return 'nao_verificada'


def enrich_catalog(catalog: dict, observations: dict, checked_at: str) -> dict:
    """Anota verificação real, sem confundir publicação e confirmação por fonte."""
    previous_health = catalog.get('sources_health')
    if not isinstance(previous_health, dict):
        previous_health = {}
    health = {}
    confirmed_ids: set[str] = set()
    confirmed_urls: set[tuple] = set()
    checked_date = checked_at[:10]
    for name in sorted(set(previous_health) | set(observations)):
        before = previous_health.get(name) or {}
        if not isinstance(before, dict):
            before = {}
        if name not in observations:
            # Fonte removida do código: não fingir uma consulta que não ocorreu.
            health[name] = {**before, 'state': 'nao_verificada'}
            continue
        stats = observations[name]
        status = classify_source(stats, before)
        hits = stats.get('seen') or []
        for item in hits:
            if not isinstance(item, dict):
                continue
            ident = item.get('id')
            if ident:
                confirmed_ids.add(str(ident))
            key = (item.get('organizer'), item.get('url'), item.get('date'))
            if all(key):
                confirmed_urls.add(key)
        http_codes = [int(x) for x in stats.get('http_errors', [])]
        entry = {**before, 'state': status, 'count': len(hits),
                 'last_checked': checked_at, 'requests': int(stats.get('requests', 0)),
                 'http_errors': len(http_codes), 'network_errors': int(stats.get('network_errors', 0)),
                 'pages_read': int(stats.get('usable_pages', 0)),
                 'pages_unreadable': int(stats.get('unusable_pages', 0))}
        if http_codes:
            entry['last_http_error'] = http_codes[-1]
        else:
            entry.pop('last_http_error', None)
        if hits:
            entry['last_success'] = checked_at
        health[name] = entry
    events = catalog.get('events') or []
    for item in events:
        if not isinstance(item, dict):
            continue
        aliases = item.get('alias_ids') or []
        if not isinstance(aliases, list):
            aliases = []
        key = (item.get('organizer'), item.get('url'), item.get('date'))
        confirmed = (str(item.get('id')) in confirmed_ids
                     or any(str(ident) in confirmed_ids for ident in aliases)
                     or key in confirmed_urls)
        if confirmed:
            item['last_confirmed_at'] = checked_at
            item['last_seen_at'] = checked_date
        # Se não foi visto hoje, NÃO mudar a data da última confirmação.
    catalog['sources_health'] = health
    return catalog


def run() -> int:
    import recolher
    import fontes_oficiais

    metrics: dict[str, dict] = defaultdict(empty_metrics)
    before_get = recolher.SESSION.get
    before_fetch = recolher.fetch

    def observed_get(url, *args, **kwargs):
        label = CURRENT_SOURCE.get()
        if label:
            metrics[label]['requests'] += 1
        try:
            response = before_get(url, *args, **kwargs)
        except Exception:
            if label:
                metrics[label]['network_errors'] += 1
            raise
        if label:
            status = int(getattr(response, 'status_code', 0) or 0)
            if status >= 400:
                metrics[label]['http_errors'].append(status)
            elif 200 <= status < 400:
                metrics[label]['http_ok'] += 1
        return response

    def observed_fetch(url, *args, **kwargs):
        label = CURRENT_SOURCE.get()
        result = before_fetch(url, *args, **kwargs)
        if label:
            metrics[label]['usable_pages' if result is not None else 'unusable_pages'] += 1
        return result

    def observe(fn):
        @functools.wraps(fn)
        def wrapped(source, *args, **kwargs):
            name = source.get('organizer', 'Fonte desconhecida')
            token = CURRENT_SOURCE.set(name)
            metrics[name]
            try:
                result = fn(source, *args, **kwargs)
                if isinstance(result, list):
                    # Contar apenas anúncios que possam passar os filtros de
                    # publicação aplicados a seguir pelo colector principal.
                    accepted = []
                    for item in result:
                        if not isinstance(item, dict) or not item.get('id'):
                            continue
                        if recolher.is_disallowed_aggregator_event(item):
                            continue
                        if recolher.excluded_organizer(item.get('organizer')):
                            continue
                        if (item.get('organizer') == recolher.MONTANHAS_ORG
                                and item.get('date_verified') != 'official_detail'):
                            continue
                        if recolher.header_date_conflicts(item):
                            continue
                        accepted.append(item)
                    # Uma fonte pode apresentar o mesmo anúncio em várias secções.
                    seen = {str(x['id']): x for x in accepted}
                    metrics[name]['seen'] = list(seen.values())
                return result
            except Exception:
                metrics[name]['exceptions'] += 1
                raise
            finally:
                CURRENT_SOURCE.reset(token)
        return wrapped

    recolher.SESSION.get = observed_get
    recolher.fetch = observed_fetch
    handlers = ('collect_source', 'collect_aggregator', 'collect_ndesafios',
                'collect_drenergies', 'collect_sal', 'collect_simple_program')
    for name in handlers:
        fn = getattr(recolher, name, None)
        if callable(fn):
            setattr(recolher, name, observe(fn))
    fontes_oficiais.collect_official = observe(fontes_oficiais.collect_official)

    result = recolher.main()
    if result:
        return int(result)
    file = Path(recolher.OUT)
    if not file.exists():
        print('ERRO: o colector não produziu nem preservou um catálogo.', file=sys.stderr)
        return 1
    data = json.loads(file.read_text(encoding='utf-8'))
    if not isinstance(data.get('events'), list) or not data['events']:
        print('ERRO: catálogo de eventos vazio; não substituir o catálogo anterior.', file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    enrich_catalog(data, metrics, now)
    data['updated_at'] = now
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    states = {state: sum(x.get('state') == state for x in data['sources_health'].values())
              for state in SOURCE_STATES}
    print('Diagnóstico das fontes: ' + ', '.join(f'{n} {k}' for k, n in states.items() if n))
    confirmed = sum(bool(x.get('last_confirmed_at') == now) for x in data['events'])
    print(f'Anúncios confirmados nesta execução: {confirmed}/{len(data["events"])}.')
    return 0


if __name__ == '__main__':
    sys.exit(run())
