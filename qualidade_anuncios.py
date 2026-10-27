#!/usr/bin/env python3
"""Critérios conservadores de elegibilidade e coerência de títulos e datas.

Sem consultas externas: a data só é comparada com aquilo que aparece
explicitamente no título. Não é inferida uma data nova.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import urlsplit
import re

# A agenda inclui caminhadas individuais e programas pedestres multidiários.
# Detectar programas serve para os identificar, nunca para os excluir.
MULTIDAY = re.compile(
    r"\b(?:fim\s+de\s+semana|viagem|expedi[cç][aã]o|"
    r"\d+\s*(?:dias|noites)|de\s+\d{1,2}\s+a\s+\d{1,2}\s+de)\b", re.I,
)

# Programas comprovadamente multidiários cuja ficha usa o nome de um trilho,
# sem indicar no título os dias de viagem. Correspondências restritas ao URL
# individual do anúncio oficial; não usar critérios genéricos de preço.
VERIFIED_MULTIDAY_URLS = frozenset({
    ('trekkingroots.pt', '/caminhada/rota-das-faias-e-o-melhor-do-outono-de-manteigas'),
    ('trekkingroots.pt', '/caminhada/bosques-magicos-do-courel'),
    ('maistrilhos.pt', '/caminhadas/parque-nacional-de-monfrague'),
    ('caminhando.pt', '/eventos/caminhando-em-aracena-gruta-das-maravilhas-e-parque-mineiro-de-rio-tinto'),
})


def is_multiday_program(event: dict) -> bool:
    """Reconhece também programas explicitamente identificados na ficha oficial.

    A data final identifica o programa, mas nunca prolonga a sua presença
    na agenda: a elegibilidade temporal depende sempre da data de início.
    """
    if event.get('multiDay') is True:
        return True
    try:
        start = date.fromisoformat(str(event.get('date') or ''))
        end = date.fromisoformat(str(event.get('endDate') or ''))
        if end > start:
            return True
    except (TypeError, ValueError):
        pass
    if MULTIDAY.search(str(event.get('title') or '')):
        return True
    try:
        parsed = urlsplit(str(event.get('url') or ''))
        host = (parsed.hostname or '').casefold().removeprefix('www.')
        path = parsed.path.rstrip('/').casefold()
    except ValueError:
        return False
    return (host, path) in VERIFIED_MULTIDAY_URLS


# Certos cartões de organizadores dão o nível, a data e os quilómetros como
# título, apesar de existir um H1 correcto na ficha individual.
GENERIC_TITLE = re.compile(
    r"^\s*(?:muito[\s-]*dif[ií]cil|f[aá]cil|moderad[oa]|"
    r"desafiante|dif[ií]cil|exigente)\s+"
    r"\d{1,2}[/-]\d{1,2}[/-]20\d{2}\b", re.I,
)

MONTH_NAMES = {
    'janeiro':1, 'fevereiro':2, 'março':3, 'abril':4, 'maio':5,
    'junho':6, 'julho':7, 'agosto':8, 'setembro':9, 'outubro':10,
    'novembro':11, 'dezembro':12,
}
DATE_WORDS = re.compile(
    r"(?<!\d)(\d{1,2})\s+(?:de\s+)?"
    r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|"
    r"setembro|outubro|novembro|dezembro)\b"
    r"(?:\s+(?:de\s+)?(20\d{2}))?", re.I,
)
DATE_SLASH = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](20\d{2})(?!\d)")
DATE_ISO = re.compile(r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)")


def title_date_conflicts(event: dict) -> bool:
    """Contradição explícita entre título e data; nunca corrige por aproximação.

    Um ano omitido em «7 de Novembro» é interpretado segundo o ano do evento
    publicado. Não se utiliza a data que apareça num slug/URL reaproveitado.
    """
    try:
        planned = date.fromisoformat(str(event.get('date') or ''))
    except ValueError:
        return True
    title = str(event.get('title') or '')
    try:
        for m in DATE_ISO.finditer(title):
            if date(int(m[1]), int(m[2]), int(m[3])) != planned:
                return True
        for m in DATE_SLASH.finditer(title):
            if date(int(m[3]), int(m[2]), int(m[1])) != planned:
                return True
        for m in DATE_WORDS.finditer(title):
            year = int(m[3]) if m[3] else planned.year
            month = MONTH_NAMES[m[2].lower()]
            if date(year, month, int(m[1])) != planned:
                return True
    except ValueError:
        # Uma data impossível escrita no título nunca é aceite como confirmação.
        return True
    return False
