#!/usr/bin/env python3
"""Fontes oficiais RB Hiking e Caminhadas Smile para o Trilhário.

Sem importação circular do recolher.py: o colector principal fornece os seus
validadores e a função fetch. Só publica caminhadas de UM dia com página
individual e data identificável nessa mesma página. Nunca lê o agregador.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date
from urllib.parse import urljoin, urlparse, urldefrag

ORGANIZERS = {
    'rb': ('RB Hiking & Trekking', 'barbosa-trekking.pt'),
    'smile': ('Caminhadas Smile', 'caminhadassmile.pt'),
}
NON_HIKE = re.compile(
    r'\b(?:pedalar|bicicleta|btt|ciclismo|viagem|voucher|carnaval|p[aá]scoa|'
    r'excurs[aã]o|cruzeiro|tour\s+de\s+autocarro|passagem\s+de\s+ano)\b', re.I
)
WALKING = re.compile(
    r'caminhad|trekking|trilho|percurso\s+pedestre|rota\s+pedestre|levada|'
    r'\bmonte\b|\bserra\b|\bcascata\b|\bbosques\b|\bmoinhos\b|'
    r'\bmiradouros\b|\bformosinho\b|\bcampos\s+de\s+lapi[aá]s\b|\bGR\s+Peneda', re.I
)
STATIC_SLUGS = {'', 'contactos', 'contacto', 'home', 'inscricoes',
                'calendario-de-eventos', 'politica-de-privacidade',
                'experiencia', 'quem-somos', 'loja', 'sobre-nos', 'galeria-de-fotos',
                'blog', 'normas-de-seguranca', 'atividades', 'actividades',
                'normas-de-seguranca-em-caminhadas', 'parceiros', 'comments',
                'comentarios', 'siga-nos', 'eventos', 'faq'}
# Não aceitar intervalos explícitos de vários dias logo junto da data do evento.
DATE_RANGE = re.compile(r'(?:\d{1,2}\s*[-–—]\s*\d{1,2}\s+[a-zA-ZÀ-ÿ]+|'
                        r'\d{1,2}\s+[a-zA-ZÀ-ÿ]+\s*(?:a|até|[-–—])\s*\d{1,2})',re.I)
DATE_TOKEN = re.compile(r'(?<!\d)\d{1,2}\s+(?:de\s+)?(?:jan(?:eiro)?|fev(?:ereiro)?|'
                        r'mar(?:[cç]o)?|abr(?:il)?|mai(?:o)?|jun(?:ho)?|jul(?:ho)?|'
                        r'ago(?:sto)?|set(?:embro)?|out(?:ubro)?|nov(?:embro)?|'
                        r'dez(?:embro)?)\s*(?:de\s+)?(?:20\d{2}|\d{2})?\b', re.I)


def _text(tag):
    return ' '.join(tag.get_text(' ', strip=True).split()) if tag else ''


def _page_head(page):
    # Muitas páginas duplicam o H1; procurar a data na vizinhança do primeiro.
    h1=page.find('h1')
    if not h1:return '', ''
    title=_text(h1)
    text=_text(page.find('main') or page.find('article') or page)
    idx=text.find(title)
    context=text[idx:idx+420] if idx>=0 else title
    return title, context


def _event_date(title, context, parser, today):
    # Título oficial da RB costuma anunciar a data; Smile escreve-a sob o H1.
    for segment in (title, context[:235]):
        if DATE_RANGE.search(segment[:180]):return None
        match=DATE_TOKEN.search(segment)
        if not match:continue
        value=match.group(0).strip()
        # 26 -> 2026 sem inferências sobre anos do evento.
        if re.search(r'\s\d{2}$',value) and not re.search(r'20\d{2}$',value):
            value=re.sub(r'\s(\d{2})$',lambda m:' 20'+m[1],value)
        dt=parser(value,short_year=today.year)
        if dt:return dt
    return None


def _candidate_urls(listing, source_url, host):
    seen=set()
    for a in listing.find_all('a',href=True):
        raw=urldefrag(urljoin(source_url,a['href']))[0].rstrip('/')
        p=urlparse(raw)
        if p.scheme not in ('http','https') or (p.hostname or '').removeprefix('www.').lower()!=host:
            continue
        # As fichas destes dois sites têm slugs de raiz. Excluir pesquisa,
        # calendário e navegação; confirmar o tipo de evento no detalhe.
        path=p.path.strip('/')
        if not path or '/' in path or path.casefold() in STATIC_SLUGS:
            continue
        if p.query:continue
        if raw in seen:continue
        seen.add(raw)
        yield raw


def _parse_smile_details(page, event):
    body=_text(page.find('main') or page)
    # A página oficial apresenta os detalhes sob 'Programa'; preferir esse
    # segmento e não as notas de boleias que repetem outros contactos.
    m=re.search(r'Hora\s+e\s+local\s+de\s+encontro\s*:\s*(.{0,270}?)(?=\bDura[cç][aã]o\b|\bPercurso\s*:|\bPiquenique\s*:|$)',body,re.I)
    if m:
        meeting=m.group(1).strip(' -–. ')
        # Duas localizações numa página (boleia + início): só usar a principal.
        coords=re.search(r'(?<!\d)(3[6-9]|4[0-3])\.\d{3,8}\s*[,;]\s*(-(?:[6-9]|10))\.\d{3,8}',meeting)
        if coords:
            try:
                lat=float(coords.group(0).split(',')[0]);lon=float(coords.group(0).split(',')[1])
                if 36<=lat<=43 and -10<=lon<=-6:event.update(lat=lat,lon=lon,verified=True)
            except (ValueError,IndexError):pass
        start=re.sub(r'\b(?:Coordenadas(?:\s+GPS)?|VER MAPA)\s*[:\-]?.*$', '',meeting,flags=re.I)
        start=re.sub(r'^\s*(?:[aà]s\s*)?\d{1,2}(?:h|:)\d{2}\s*h?\s*[–-]?\s*','',start,flags=re.I)
        if 5<=len(start)<=160:event['start']=start.strip('–- .')
        clock=re.search(r'\b(?:[aà]s\s*)?(\d{1,2})\s*[:h]\s*(\d{2})\b',meeting,re.I)
        if clock and int(clock[1])<=23 and int(clock[2])<60:event['time']=f'{int(clock[1]):02d}:{int(clock[2]):02d}'
    z=re.search(r'Zona\s+da\s+atividade\s*:\s*(.{4,75}?)(?=\bHora\s+e\s+local\b|\bDura[cç][aã]o\b|\bPercurso\b|[.;]|$)',body,re.I)
    if z:event['town']=z[1].strip(' –-')[:65]
    # Determinar preço a partir da secção Preço, nunca IBAN/telefone.
    price=re.search(r'\bPre[cç]o\s+(?:\S+\s+){0,6}?(\d{1,3}(?:[.,]\d{1,2})?)\s*€',body,re.I)
    if price:
        v=float(price[1].replace(',','.'))
        if 0<=v<=500:event['price']=v
    km=re.search(r'\bPercurso\s*:\s*[^.;]{0,105}?\b(?:cerca\s+de\s+)?(\d{1,2}(?:[.,]\d)?)\s*km\b',body,re.I)
    if km:
        v=float(km[1].replace(',','.'))
        if 0<v<=40:event['km']=v


def _parse_rb_details(page,event):
    body=_text(page.find('main') or page)
    match=re.search(r'\b(?:Encontro\s+em|local\s+de\s+encontro\s*:)\s*([^.;:]{5,110})',body,re.I)
    if match:event['start']=match[1].strip(' –-')
    clock=re.search(r'(?<!\d)(\d{1,2})\s*h\s*(\d{2})\s*[–-]\s*(?:Encontro|In[ií]cio)',body,re.I)
    if clock and int(clock[1])<24 and int(clock[2])<60:event['time']=f'{int(clock[1]):02d}:{int(clock[2]):02d}'
    price=re.search(r'Valor\s+da\s+inscri[cç][aã]o\s+por\s+participante\s*:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€',body,re.I)
    if price:
        val=float(price[1].replace(',','.'))
        if 0<=val<=500:event['price']=val
    km=re.search(r'(?:Percurso\s+(?:circular|linear)\s*[–-]\s*Dist[aâ]ncia|Dist[aâ]ncia\s+do\s+percurso)\s*[:]?\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*km\b',body,re.I)
    if km:
        val=float(km[1].replace(',','.'))
        if 0<val<=40:event['km']=val
    if re.search(r'este evento encontra-se esgotado',body[:900],re.I):event['status']='Esgotado'


def collect_official(source, *, fetch, date_from, new_event, valid_new_event, parse_meta,
                     enrich_jsonld, today:date):
    """Devolve anúncios oficiais completos; respostas em erro nunca criam dados."""
    kind=source.get('mode')
    if kind not in ORGANIZERS:return []
    organizer,host=ORGANIZERS[kind]
    if source.get('organizer')!=organizer:return []
    listing=fetch(source['url'])
    if listing is None:return []
    result=[]
    urls=list(_candidate_urls(listing,source['url'],host))[:65]
    for link in urls:
        page=fetch(link)
        if page is None:continue
        title,context=_page_head(page)
        if not title or NON_HIKE.search(title) or not WALKING.search(title):continue
        when=_event_date(title,context,date_from,today)
        if when is None:continue
        item=new_event(organizer,link,title,when,date_verified='official_detail')
        # Só a ficha oficial individual contribui com informações da caminhada.
        enrich_jsonld(page,item)
        # Não permitir que o JSON-LD de um evento relacionado mude a data
        # que foi anunciada no próprio cabeçalho.
        item['date']=when.isoformat()
        if kind=='smile':_parse_smile_details(page,item)
        else:_parse_rb_details(page,item)
        parse_meta(page,item)
        if valid_new_event(item):result.append(item)
        time.sleep(0.08)
    logging.info('%s: %d caminhadas oficiais de um dia (de %d fichas potenciais)',organizer,len(result),len(urls))
    return result
