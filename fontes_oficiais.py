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



# Preservar o anúncio bruto separadamente; coordenadas em graus/minutos/segundos
# não podem ser cortadas por expressões que dividem texto no ponto decimal.
def _plausible_coords(latitude,longitude):
    return 36 <= latitude <= 43.7 and -10 <= longitude <= -6


def _parse_published_coords(raw):
    """Par lat/lon completo em decimal ou DMS; nunca certificar um fragmento."""
    raw=str(raw or '').replace('−','-')
    decimal=re.search(r'(?<![\d.])(?P<lat>(?:3[6-9]|4[0-3])\.\d{3,8})\s*[,;]\s*(?P<lon>-(?:10|[6-9])\.\d{3,8})(?!\d)',raw,re.I)
    if decimal:
        lat=float(decimal['lat']);lon=float(decimal['lon'])
        if _plausible_coords(lat,lon):return lat,lon
    # Exemplos: N 41°46’24.5” W 8°12’33.2” ou Lat: 41°46'24" Long: W 8°12'33".
    def dms_one(segment,orientation):
        p=re.search(r'(?i)(?:\b(?:latitude|lat|longitude|long|lon)\s*[:=]\s*)?'
                    r'(?:[NSEWO]\s*)?(?P<deg>\d{1,3})\s*[°º]\s*'
                    r"(?P<min>[0-5]?\d)\s*['’′]\s*"
                    r'(?P<sec>[0-5]?\d(?:[.,]\d+)?)\s*(?:[\"”″]|\b)',segment,re.I)
        if not p:return None
        deg=int(p['deg']);minute=int(p['min']);sec=float(p['sec'].replace(',','.'))
        value=deg+minute/60+sec/3600
        return -value if orientation=='W' else value
    # Latitude e longitude têm de estar identificadas (não aceitar dois números quaisquer).
    latm=re.search(r'(?i)(?:\bLat(?:itude)?\s*[:=]\s*(?:N\s*)?|\bN\s*)(?P<part>\d{2}\s*[°º].{1,35}?[\"”″])',raw)
    lonm=re.search(r'(?i)(?:\bLon(?:gitude|g)?\s*[:=]\s*(?:W\s*|O\s*)?|\b[WO]\s*)(?P<part>\d{1,3}\s*[°º].{1,35}?[\"”″])',raw)
    if latm and lonm:
        lat=dms_one(latm['part'],'N');lon=dms_one(lonm['part'],'W')
        if lat is not None and lon is not None and _plausible_coords(lat,lon):return round(lat,8),round(lon,8)
    return None


def _meeting_description(raw):
    """Texto de encontro até à próxima linha do programa, sem coordenadas incrustadas."""
    raw=' '.join(str(raw or '').split())
    raw=re.split(r'(?i)\s+\d{1,2}\s*[:h]\s*[0-5]\d\s*[–—-]\s*(?:In[ií]cio|Fim|Hora|Final|Regresso|Chegada|Encontro)\b',raw,maxsplit=1)[0]
    raw=re.split(r'(?i)\s+(?:Percurso(?:\s+circular|\s+linear)?|Dura[cç][aã]o|Material\s+aconselhado|Valor\s+da\s+inscri[cç][aã]o)\s*[:–-]',raw,maxsplit=1)[0]
    raw=re.split(r'(?i)\s+(?:Coordenadas(?:\s+GPS)?\s*:?|VER\s+MAPA|Lat(?:itude)?\s*:|Long(?:itude|g)?\s*:)',raw,maxsplit=1)[0]
    raw=re.sub(r'(?<![\d.])(?:3[6-9]|4[0-3])\.\d{3,8}\s*[,;]\s*-?(?:10|[6-9])\.\d{3,8}(?!\d)','',raw)
    return raw.strip(' .,:;–—-')[:150]


def _parse_smile_details(page, event):
    body=_text(page.find('main') or page)
    m=re.search(r'Hora\s+e\s+local\s+de\s+encontro\s*:\s*(.{0,380}?)(?=\bDura[cç][aã]o\b|\bPercurso\s*:|\bPiquenique\s*:|$)',body,re.I)
    if m:
        meeting=m.group(1).strip(' -–. ')
        event['start_raw']=meeting
        coords=_parse_published_coords(meeting)
        if coords:event.update(lat=coords[0],lon=coords[1],verified=True,gpsFromAnnouncement=True)
        start=_meeting_description(meeting)
        start=re.sub(r'^\s*(?:[aà]s\s*)?\d{1,2}(?:h|:)\d{2}\s*h?\s*[–-]?\s*','',start,flags=re.I)
        if 5<=len(start)<=150:event['start']=start.strip('–- .')
        clock=re.search(r'\b(?:[aà]s\s*)?(\d{1,2})\s*[:h]\s*(\d{2})\b',meeting,re.I)
        if clock and int(clock[1])<=23 and int(clock[2])<60:event['time']=f'{int(clock[1]):02d}:{int(clock[2]):02d}'
    z=re.search(r'Zona\s+da\s+atividade\s*:\s*(.{4,75}?)(?=\bHora\s+e\s+local\b|\bDura[cç][aã]o\b|\bPercurso\b|[.;]|$)',body,re.I)
    if z:event['town']=z[1].strip(' –-')[:65]
    price=re.search(r'\bPre[cç]o\s+(?:\S+\s+){0,6}?(\d{1,3}(?:[.,]\d{1,2})?)\s*€',body,re.I)
    if price:
        v=float(price[1].replace(',','.'))
        if 0<=v<=500:event['price']=v
    km=re.search(r'\bPercurso\s*:\s*[^.;]{0,105}?\b(?:cerca\s+de\s+)?(\d{1,2}(?:[.,]\d)?)\s*km\b',body,re.I)
    if km:
        v=float(km[1].replace(',','.'))
        if 0<v<=40:event['km']=v


def _parse_rb_details(page,event):
    # Capturar o encontro a partir do texto ORIGINAL da ficha: um horário do
    # programa termina a descrição. Nunca cortar no ponto decimal do GPS.
    main=page.find('main') or page.find('article') or page
    body=_text(main)
    match=re.search(r'\bEncontro\s+em\s+(.{5,250}?)(?=\s+\d{1,2}\s*[:h]\s*[0-5]\d\s*[–—-]\s*(?:In[ií]cio|Hora|Final|Regresso|Chegada|Encontro)\b|\s+Percurso\s+(?:circular|linear)\b|$)',body,re.I)
    if not match:
        match=re.search(r'\blocal\s+de\s+encontro\s*:\s*(.{5,250}?)(?=\s+\d{1,2}\s*[:h]\s*[0-5]\d\s*[–—-]|\s+Percurso\s+(?:circular|linear)|$)',body,re.I)
    if match:
        meeting=match[1].strip()
        event['start_raw']=meeting
        gps=_parse_published_coords(meeting)
        if gps:event.update(lat=gps[0],lon=gps[1],verified=True,gpsFromAnnouncement=True)
        start=_meeting_description(meeting)
        if 5<=len(start)<=150:event['start']=start
    # Algumas fichas RB publicam latitude/longitude fora do bloco «Encontro».
    if not event.get('verified'):
        # Fora do encontro, só aceitar GPS se houver rótulo explícito no anúncio.
        label=re.search(r'(?i)(?:Coordenadas(?:\s+GPS)?|GPS|Lat(?:itude)?\s*:).{0,135}',body)
        gps=_parse_published_coords(label.group(0)) if label else None
        if gps:event.update(lat=gps[0],lon=gps[1],verified=True,gpsFromAnnouncement=True)
    clock=re.search(r'(?<!\d)(\d{1,2})\s*h\s*(\d{2})\s*[–—-]\s*(?:Encontro|In[ií]cio)',body,re.I)
    if clock and int(clock[1])<24 and int(clock[2])<60:event['time']=f'{int(clock[1]):02d}:{int(clock[2]):02d}'
    price=re.search(r'Valor\s+da\s+inscri[cç][aã]o\s+por\s+participante\s*:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€',body,re.I)
    if price:
        val=float(price[1].replace(',','.'))
        if 0<=val<=500:event['price']=val
    km=re.search(r'(?:Percurso\s+(?:circular|linear)\s*[–—-]\s*Dist[aâ]ncia|Dist[aâ]ncia\s+do\s+percurso)\s*[:]?\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*km\b',body,re.I)
    if km:
        val=float(km[1].replace(',','.'))
        if 0<val<=40:event['km']=val
    # A disponibilidade deixa de ser exposta pelo Trilhário (v41).


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
