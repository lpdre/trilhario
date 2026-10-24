#!/usr/bin/env python3
"""Pós-processamento conservador e auditoria do catálogo recolhido pelo Trilhário.

Só reconstitui títulos oficiais a partir da ligação original, conserva valores
anteriores válidos quando uma nova recolha omitiu um campo e rejeita catálogos
claramente danificados. Não inventa coordenadas, horários, preços ou lugares.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, unquote, urljoin
import time

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / 'eventos.json'
PLACEHOLDERS = {'', 'por confirmar', 'a confirmar', 'por definir', 'desconhecido'}
GENERIC_TITLE = re.compile(r'^(?:f[aá]cil|moderad[oa]|desafiante|dif[ií]cil|exigente)\s+\d{1,2}/\d{1,2}/20\d{2}\b', re.I)
JOINERS = {'da', 'de', 'do', 'das', 'dos', 'e', 'a', 'o', 'ao', 'em', 'na', 'no', 'nas', 'nos', 'por', 'pelo', 'pelos', 'entre'}


def folded(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value or '')) if unicodedata.category(c) != 'Mn').casefold().strip()


def meaningful(value):
    return value is not None and (not isinstance(value, str) or folded(value) not in PLACEHOLDERS)


def location_identity(event):
    """Identidade normalizada do início anunciado, para validar GPS herdado.

    Uma nova designação concreta substitui a anterior; alterações de espaços,
    pontuação e acentos não bastam para invalidar um ponto.
    """
    def clean(value):
        if not meaningful(value):
            return ''
        return re.sub(r'[^a-z0-9]+', ' ', folded(value)).strip()
    return clean(event.get('start')), clean(event.get('town'))


def invalidate_stale_coordinates(event, old):
    """Nunca certificar coordenadas antigas após alteração do ponto anunciado."""
    if not isinstance(old, dict) or not old:
        return False
    new_start, new_town = location_identity(event)
    old_start, old_town = location_identity(old)
    changed = ((new_start and old_start and new_start != old_start) or
               (new_town and old_town and new_town != old_town))
    if not changed:
        return False
    # Coordenadas novas, diferentes das anteriores e explicitamente verificadas
    # pelo organizador não devem ser apagadas por uma mudança legítima de lugar.
    coords_new = (meaningful(event.get('lat')) and meaningful(event.get('lon')))
    coords_old = (meaningful(old.get('lat')) and meaningful(old.get('lon')))
    new_gps = (coords_new and event.get('verified') is True and
               (event.get('gpsFromAnnouncement') is True or
                not coords_old or (str(event['lat']),str(event['lon'])) !=
                (str(old['lat']),str(old['lon']))))
    if new_gps:
        return False
    had_stale = any(event.get(key) is not None for key in ('lat','lon','gps_checked_at')) or bool(event.get('verified'))
    for field in ('lat', 'lon', 'gps_checked_at'):
        event.pop(field, None)
    event['verified'] = False
    return had_stale


def title_from_official_url(url):
    """Só recuperar título se o URL fornecer um nome de percurso inteligível."""
    try:
        parsed = urlsplit(url)
        if not parsed.hostname or parsed.hostname not in {'hikeland.pt', 'www.hikeland.pt'}:
            return None
        slug = unquote(parsed.path.rstrip('/').split('/')[-1])
        slug = re.sub(r'-\d+$', '', slug)
        if len(slug) < 15 or '-' not in slug:
            return None
        words = slug.split('-')
        return ' '.join(w if i and w in JOINERS else w[:1].upper()+w[1:] for i,w in enumerate(words))[:140]
    except (ValueError, UnicodeError):
        return None


def official_hikeland_title(url):
    """Preferir o título visível no anúncio oficial ao resumo imperfeito do cartão."""
    try:
        import requests
        from bs4 import BeautifulSoup
        page = requests.get(url, timeout=12, headers={'User-Agent': 'TrilharioAgenda/0.1'})
        page.raise_for_status()
        scope = BeautifulSoup(page.text, 'html.parser')
        head = (scope.find('main') or scope).find('h1')
        if not head:
            return None
        title = ' '.join(head.get_text(' ', strip=True).split())[:140]
        path = urlsplit(url).path.rstrip('/').split('/')[-1]
        important = [word for word in re.split(r'[^a-z0-9]+', folded(path)) if len(word) >= 5]
        matches = sum(w in folded(title) for w in important)
        return title if 12 <= len(title) <= 140 and matches >= 2 and not GENERIC_TITLE.match(title) else None
    except Exception:
        return None




# Caminhando.pt usa cartões cujo texto reúne duas cópias do horário, o nome do
# evento e o ponto de encontro. O extractor da listagem conservava tudo no título.
# Esta leitura dos cartões antigos permite corrigi-los sem depender da rede.
CAMINHANDO_CARD = re.compile(
    r"^\s*(?P<begin>(?:[01]?\d|2[0-3]):[0-5]\d)\s+"
    r"(?P<end>(?:[01]?\d|2[0-3]):[0-5]\d)\s+"
    r"(?P<title>.+?)\s+(?P=begin)\s*[-–—]\s*(?P=end)\s+"
    r"(?P<place>.*)$", re.I)

def clock_valid(value):
    return isinstance(value,str) and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value) is not None

def hours_between(begin,end):
    if not (clock_valid(begin) and clock_valid(end)):
        return None
    h1,m1=map(int,begin.split(':'));h2,m2=map(int,end.split(':'))
    d=(h2*60+m2)-(h1*60+m1)
    # Não inferir duração quando a hora pertence ao dia seguinte ou está errada.
    return round(d/60,4) if 15 <= d <= 14*60 else None

def tidy_meeting(value):
    t=' '.join(str(value or '').split())
    t=re.split(r'\s+Tipo\s+Evento\s*:',t,maxsplit=1,flags=re.I)[0]
    t=re.split(r'\s+(?:Hor[aá]rio|Detalhes do Evento|Descri[cç][aã]o do Evento)\b',t,maxsplit=1,flags=re.I)[0]
    t=re.sub(r'\s+\.\s+', ', ', t)
    t=t.strip(' .,:;-')
    return t if 5<=len(t)<=180 and not t.endswith(('...', '…')) else None

def parse_caminhando_card(title):
    """Extrai título, hora e local de anúncio já guardado no JSON.

    Se o cartão truncou o ponto de encontro, não o publica como morada válida;
    nesse caso o extractor da página oficial completa-o.
    """
    raw=' '.join(str(title or '').split())
    m=CAMINHANDO_CARD.match(raw)
    if not m:return {}
    name=m['title'].strip(' -–,')
    if not 8<=len(name)<=140:return {}
    begin,end=m['begin'].zfill(5),m['end'].zfill(5)
    out={'title':name,'time':begin,'endTime':end}
    duration=hours_between(begin,end)
    if duration is not None:out['duration']=duration
    place=tidy_meeting(m['place'])
    # Alguns cartões são cortados exactamente aos 140 caracteres.
    if place and ('Tipo Evento' in raw or re.search(r'\)\s*$',place)):
        out['start']=place
    return out

def caminhar_dms_coordinate(text, label):
    """Lê DMS com os hemisférios N/S/E/W, devolvendo um número ou None."""
    q=re.search(r'\b'+label+r'\s*:\s*(.{1,90})',text,re.I)
    if not q:return None
    m=re.search(r'(\d{1,3})\s*[º°]\s*(\d{1,2})\s*[’′\x27]\s*'
                r'(\d{1,2}(?:[.,]\d+)?)\s*[″”"\x27]?\s*([NSEW])\b',q[1],re.I)
    if not m:return None
    deg,minutes,seconds=int(m[1]),int(m[2]),float(m[3].replace(',','.'))
    if minutes>=60 or seconds>=60:return None
    val=deg+minutes/60+seconds/3600
    return -val if m[4].upper() in ('S','W') else val

def parse_caminhando_detail(html,url):
    """Extrai os campos publicados na página individual do Caminhando.pt.

    Processa apenas o cabeçalho do evento, antes do bloco de descrição;
    assim não confunde horas e moradas das caminhadas relacionadas.
    """
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    main=soup.find('main') or soup.find('article') or soup
    txt=' '.join(main.get_text(' ',strip=True).split())
    # O site imprime "Horário (Domingo) 9:20 - 14:00 Ponto de Encontro ...".
    head=txt[:13000]
    match=re.search(
        r'\bHor[aá]rio\s+(?:\([^)]{2,30}\)\s*)?'
        r'(?P<begin>(?:[01]?\d|2[0-3]):[0-5]\d)\s*[-–—]\s*'
        r'(?P<end>(?:[01]?\d|2[0-3]):[0-5]\d)\s+'
        r'Ponto de Encontro\s+(?P<place>.+?)\s+'
        r'(?:Detalhes do Evento|Descri[cç][aã]o do Evento|Tipo Evento)',head,re.I)
    out={}
    if match:
        begin,end=match['begin'].zfill(5),match['end'].zfill(5)
        out.update(time=begin,endTime=end)
        duration=hours_between(begin,end)
        if duration is not None:out['duration']=duration
        place=tidy_meeting(match['place'])
        if place:out['start']=place
    # Algumas páginas oficiais publicam coordenadas GPS completas na secção
    # «Localização». Validar ambos os valores antes de assinalar confirmado.
    lat=caminhar_dms_coordinate(head,'Latitude')
    lon=caminhar_dms_coordinate(head,'Longitude')
    if lat is not None and lon is not None and 36<=lat<=43 and -10<=lon<=-6:
        out.update(lat=round(lat,8),lon=round(lon,8),verified=True)
    # O H1 contém exclusivamente o nome, ao contrário da âncora do calendário.
    h1=main.find('h1') or soup.find('h1')
    if h1:
        title=' '.join(h1.get_text(' ',strip=True).split())
        if 7<=len(title)<=140 and not re.search(r'\b(?:agenda|eventos|pesquisa livre)\b',title,re.I):
            out['title']=title
    return out

def repair_caminhando(event, old):
    """Normaliza o Caminhando.pt e recupera campos na fonte, quando necessário."""
    if event.get('organizer')!='Caminhando.pt':return {}
    url=str(event.get('url') or '')
    if urlsplit(url).hostname not in {'caminhando.pt','www.caminhando.pt'}:
        return {}
    raw_title=str(event.get('title') or '')
    cached=parse_caminhando_card(raw_title)
    # Correcção sem pedidos HTTP se o título continha os dados completos.
    out=dict(cached)
    # Evitar novos pedidos quando uma execução anterior já publicou todos os campos.
    if (not cached and meaningful(event.get('start')) and clock_valid(event.get('time'))
        and clock_valid(event.get('endTime')) and not re.match(r'^\s*\d{1,2}:\d{2}\b', raw_title)):
        return {}
    # Também corrigir anúncios que já chegam limpos do colector.
    # O cartão antigo pode perder o local ao ser limitado a 140 caracteres:
    # nesse caso tenta a página oficial, sem inventar uma morada.
    has_coords = all(isinstance((event.get(k) if event.get(k) is not None else old.get(k)),(float,int))
                     for k in ('lat','lon'))
    need_detail=(not cached.get('start') or not cached.get('title') or
                 not cached.get('time') or not cached.get('endTime') or
                 (not has_coords and not old.get('gps_checked_at')))
    if need_detail:
        try:
            import requests
            resp=requests.get(url,timeout=(4,9),headers={'User-Agent':'TrilharioAgenda/0.1 (+https://github.com/lpdre/trilhario)'},allow_redirects=True)
            resp.raise_for_status()
            if (resp.url.startswith(('https://caminhando.pt/eventos/','https://www.caminhando.pt/eventos/'))
                    and 'text/html' in resp.headers.get('Content-Type','text/html').lower()):
                details=parse_caminhando_detail(resp.text,resp.url)
                # Um cabeçalho genérico de uma página alterada não deve substituir
                # um nome completo e coerente que o próprio cartão publicou.
                if cached.get('title') and details.get('title'):
                    old_words=set(re.findall(r'[a-z]{4,}',folded(cached['title'])))
                    new_words=set(re.findall(r'[a-z]{4,}',folded(details['title'])))
                    if old_words and len(old_words & new_words)/len(old_words)<0.55:
                        details.pop('title',None)
                out.update(details)
                out['gps_checked_at']=date.today().isoformat()
        except Exception as exc:
            print('Caminhando.pt: não foi possível consultar',url,type(exc).__name__)
    return out

# O Trilhário apresenta caminhadas de um só dia. Alguns anúncios têm
# também a categoria Caminhada mas descrevem um pacote de vários dias.
# Não basta testar a categoria: evitar fins-de-semana, viagens e programas
# explicitamente assinalados como multidiários pelo organizador.
CAMINHANDO_MULTIDAY_URL = re.compile(
    r'(?:^|/)(?:fim-de-semana|viagem|escapadinha|expedicao)(?:-|/|$)', re.I)
CAMINHANDO_MULTIDAY_TITLE = re.compile(
    r'\b(?:fim[ -]de[ -]semana|viagem\s+(?:a|ao|pela|pelos|de)|'
    r'escapadinha|expedi[cç][aã]o|\d+\s*(?:dias|noites))\b',re.I)
CAMINHANDO_MULTIDAY_DATES = re.compile(
    r'^\s*\(\s*[a-z]{3,4}\s+\d{1,2}\)\s*\d{1,2}:\d{2}\s+'
    r'\d{1,2}\s*\(\s*[a-z]{3,4}\s+\d{1,2}\)', re.I)

def is_caminhando_multiday(event):
    if event.get('organizer') != 'Caminhando.pt':return False
    title=' '.join(str(event.get('title') or '').split())
    path=urlsplit(str(event.get('url') or '')).path.lower()
    return bool(CAMINHANDO_MULTIDAY_URL.search(path)
                or CAMINHANDO_MULTIDAY_TITLE.search(title)
                or CAMINHANDO_MULTIDAY_DATES.search(title))

def git_previous():
    try:
        raw = subprocess.check_output(['git', 'show', 'HEAD:eventos.json'], cwd=ROOT, stderr=subprocess.DEVNULL)
        return json.loads(raw).get('events', [])
    except (OSError, subprocess.CalledProcessError, ValueError):
        return []


def report(lines):
    print('\n'.join(lines))
    summary = __import__('os').environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write('\n### Auditoria automática do Trilhário\n\n')
            f.write('\n'.join('- '+line for line in lines)+'\n')



# Valores confirmados em 22-10-2026 nas páginas oficiais indicadas. Aplicados
# apenas a estas edições para evitar usar preços/horários antigos em anos futuros.
# As correcções verificadas estão em excepcoes_catalogo.json.

OFFICIAL_DOMAINS = {'greentrekker.pt':'GreenTrekker',
                    'maistrilhos.pt':'Mais Trilhos',
                    'hikeland.pt':'Hike Land'}

def number(text):
    try:
        return float(text.replace(',','.'))
    except (AttributeError,ValueError):
        return None


def parse_official_listing(organizer, html, url):
    """Extrai campos dos detalhes, não do cartão de navegação da agenda.
    Não confunde a hora da caminhada com o tempo de condução.
    """
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    main=soup.find('main') or soup.find('article') or soup
    txt=' '.join(main.get_text(' ',strip=True).split())
    found={}
    if organizer=='Mais Trilhos':
        # Há dois rótulos iguais: título da secção (com iframe) e campo real.
        # Ancorar no bloco 'Hora de encontro HH:MM -> Ponto de encontro -> Distância'
        # evita consumir o rótulo do título e descartar o valor correcto.
        meeting = re.search(
            r'\bHora de encontro\s*[:–—-]?\s*([01]?\d|2[0-3]):([0-5]\d)\s+'
            r'Ponto de encontro\s*[:–—-]?\s*(.{4,175}?)\s+'
            r'(?:Dist[âa]ncia|Dura[cç][aã]o|Desn[ií]vel|Grau de dificuldade|Guia|Pre[cç]o por participante)\b',
            txt, re.I)
        # Fallback if the hour is not in the usual location. The first
        # 'Ponto de encontro' is a heading, often followed by an iframe.
        # The last properly bounded *field* contains the actual place.
        places = [m.group(1).strip(' .,:;') for m in re.finditer(
            r'\bPonto de encontro\s*[:–—-]?\s*(.{4,175}?)\s+'
            r'(?:Dist[âa]ncia|Dura[cç][aã]o|Desn[ií]vel|Grau de dificuldade|Guia|Pre[cç]o por participante)\b',
            txt, re.I)]
        candidate = meeting[3].strip(' .,:;') if meeting else (places[-1] if places else '')
        if (4 <= len(candidate) <= 145 and
            not re.search(r'\b(?:iframe|Ponto de encontro|Hora de encontro|Data)\b', candidate, re.I)):
            found['start'] = candidate
            if meeting:
                found['time'] = f'{int(meeting[1]):02d}:{meeting[2]}'
        m=re.search(r'Hora de encontro\s+(\d{1,2}):(\d{2})\b',txt,re.I)
        if m and int(m[1])<24 and int(m[2])<60:found['time']=f'{int(m[1]):02d}:{m[2]}'
        m=re.search(r'\bDura[cç][aã]o\s+(\d{1,2}):(\d{2})\b',txt,re.I)
        if m and 0<int(m[1])<=14 and int(m[2])<60:found['duration']=int(m[1])+int(m[2])/60
        m=re.search(r'\bDesn[ií]vel\s+(\d{2,4})\s*m\b',txt,re.I)
        if m:found['gain']=int(m[1])
        m=re.search(r'\bDist[aâ]ncia\s+(\d{1,2}(?:[.,]\d+)?)\s*km\b',txt,re.I)
        if m:found['km']=number(m[1])
        m=re.search(r'Pre[cç]o por participante\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*€',txt,re.I)
        if m:found['price']=number(m[1])
        m=re.search(r'Grau de dificuldade\s+Dificuldade\s+(\d)\b',txt,re.I)
        if m:found['difficulty']=int(m[1])
    elif organizer=='GreenTrekker':
        m=re.search(r'Ponto de encontro\s*:\s*(.{5,185}?)(?=\s+(?:Coordenadas GPS|Hora de Fim|Abrir mapa|Percurso|\d{1,2}\s+Out)\b)',txt,re.I)
        if m:
            v=m[1].strip(' ,.');
            if len(v)<145:found['start']=v
        m=re.search(r'\bLocaliza[cç][aã]o\s+\d{1,2}\s+[A-Za-zçãéú]+\s+-\s+(\d{1,2}:\d{2})\s+Ponto de encontro',txt,re.I)
        if m:found['time']=m[1]
        m=re.search(r'\bDura[cç][aã]o\s+(\d{1,2})\s*h(?:\s*(\d{1,2})\s*m)?\b',txt,re.I)
        if m and 0<int(m[1])<=14:found['duration']=int(m[1])+(int(m[2]) if m[2] else 0)/60
        m=re.search(r'\bDist[aâ]ncia\s+(\d{1,2}(?:[.,]\d+)?)\s*Km\b',txt,re.I)
        if m:found['km']=number(m[1])
        m=re.search(r'\bDesn[ií]vel\s+(\d{2,4})\s*m\b',txt,re.I)
        if m:found['gain']=int(m[1])
        m=re.search(r'Fa[cç]a J[aá] A Sua Reserva\s+(\d{1,3}(?:[.,]\d{1,2})?)\s*€',txt,re.I)
        if m:found['price']=number(m[1])
        # O formato GPS tem dois valores completos: nunca usar apenas latitude.
        dms=re.search(r'Lat:\s*N\s*(\d{1,2})[°º]\s*(\d{1,2})\s*[\'’′]\s*(\d{1,2}(?:[.,]\d+)?)\s*["”″]\s*Long:\s*W\s*(\d{1,3})[°º]\s*(\d{1,2})\s*[\'’′]\s*(\d{1,2}(?:[.,]\d+)?)\s*["”″]',txt,re.I)
        if dms:
            lat=int(dms[1])+int(dms[2])/60+number(dms[3])/3600
            lon=-(int(dms[4])+int(dms[5])/60+number(dms[6])/3600)
            if 36<=lat<=43 and -10<=lon<=-6:
                found.update(lat=round(lat,8),lon=round(lon,8),verified=True)
    return found


def enrich_official(e, previous):
    """Códigos e limites defensivos para páginas oficiais com formatos conhecidos."""
    try:
        parsed=urlsplit(str(e.get('url') or ''))
        host=(parsed.hostname or '').removeprefix('www.')
        if host not in OFFICIAL_DOMAINS or OFFICIAL_DOMAINS[host]!=e.get('organizer'):
            return {}
        # Só verificar campos cuja extracção ainda está incompleta, para reduzir consultas.
        required=('start','km','gain','duration','price','time')
        if (all(meaningful(e.get(k)) for k in required)
            and not GENERIC_TITLE.match(str(e.get('title') or ''))):
            return {}
        import requests
        response=requests.get(e['url'],timeout=9,headers={'User-Agent':'TrilharioAgenda/0.1 (+https://github.com/lpdre/trilhario)'})
        response.raise_for_status()
        if 'text/html' not in response.headers.get('Content-Type','text/html'):
            return {}
        return parse_official_listing(e['organizer'],response.text,e['url'])
    except Exception as exc:
        print('Página oficial não verificada:',e.get('url'),type(exc).__name__)
        return {}




# As imagens são referenciadas a partir do anúncio original (sem copiar ficheiros
# de terceiros para o GitHub). Alguns organizadores impedem hotlink: nesse caso
# a foto é omitida pelo browser e o cartão permanece utilizável.
PHOTO_FIRST_EVENTS = 50  # Primeiro grupo de caminhadas futuras por data
PHOTO_VISITS_PER_RUN = 50  # Máximo de novas consultas por execução
PHOTO_RETRY_DAYS = 28
PHOTO_MAX_HTML_BYTES = 800_000
PHOTO_AGENT = {'User-Agent':'TrilharioAgenda/0.1 (+https://github.com/lpdre/trilhario)',
               'Accept-Language':'pt-PT,pt;q=0.9'}


def valid_event_image(image_url, page_url):
    """URL http(s) de imagem, externa ou CDN, sem credenciais e sem esquemas activos."""
    try:
        from urllib.parse import urljoin, urlsplit, urlunsplit
        raw=str(image_url or '').strip()
        if not raw or raw.startswith(('data:', 'blob:', 'javascript:')):
            return None
        url=urljoin(page_url,raw)
        parts=urlsplit(url)
        hostname=(parts.hostname or '').lower()
        if parts.scheme!='https' or not hostname or parts.username or parts.password:
            return None
        if hostname in {'localhost','127.0.0.1','0.0.0.0'} or hostname.endswith(('.local','.internal','.test','.invalid')):
            return None
        try:
            from ipaddress import ip_address
            if not ip_address(hostname).is_global:return None
        except ValueError:pass
        if re.search(r'\.(?:svg|gif|pdf|ico)(?:$|[?#])',parts.path,re.I):
            return None
        # Evitar marcas gráficas e imagens partilhadas por todos os anúncios.
        if re.search(r'(?:^|[\/_.-])(?:logo|favicon|avatar|placeholder|default-image|no-photo)(?:[\/_.-]|$)',parts.path,re.I):
            return None
        return urlunsplit((parts.scheme,parts.netloc,parts.path,parts.query,''))
    except (ValueError, UnicodeError):
        return None


def extract_event_image(html, source_url):
    """Escolhe uma única foto do anúncio oficial, preferindo metadados sociais."""
    from bs4 import BeautifulSoup
    import json as _json
    soup=BeautifulSoup(html,'html.parser')
    image_candidates=[]
    for prop in ('og:image:secure_url','og:image','twitter:image','twitter:image:src'):
        tag=soup.find('meta',attrs={'property':prop}) or soup.find('meta',attrs={'name':prop})
        if tag and tag.get('content'):
            image_candidates.append(tag['content'])
    # JSON-LD também publica a fotografia do evento sem depender dos selectores visuais.
    for tag in soup.select('script[type="application/ld+json"]')[:10]:
        try: root=_json.loads(tag.string or tag.get_text())
        except (ValueError,TypeError):continue
        queue=[root]
        while queue:
            node=queue.pop()
            if isinstance(node,list):queue.extend(node);continue
            if not isinstance(node,dict):continue
            graph=node.get('@graph')
            if graph:queue.append(graph)
            typ=node.get('@type')
            if isinstance(typ,str):typ=[typ]
            if any(str(t).endswith('Event') for t in (typ or [])):
                val=node.get('image')
                if isinstance(val,list):image_candidates.extend(val)
                elif val:image_candidates.append(val)
    # Não procurar imagens aleatórias no rodapé, anúncios de outros eventos ou logótipos.
    for cand in image_candidates:
        if isinstance(cand,dict):cand=cand.get('url') or cand.get('contentUrl')
        url=valid_event_image(cand,source_url)
        if url:return url
    return None


def read_official_photo(event):
    """Consultar só o site original do evento (nunca descarregar a imagem)."""
    import requests
    try:
        target=str(event.get('url') or '')
        parts=urlsplit(target)
        if parts.scheme!='https' or not parts.hostname:
            return None
        # Evitar sondar páginas não-oficiais ou endereços introduzidos livremente.
        allowed=('greentrekker.pt','maistrilhos.pt','hikeland.pt','indoeu.pt',
                 'montanhasdentro.pt','trekkingroots.pt','trekkin.pt','bastotrekking.pt',
                 'hikingaround.pt','ndesafios.pt','montanhasdonorte.pt',
                 'montanhismo-guarda.pt','amigosdamontanha.com','caminhando.pt',
                 'penomundo.pt','clubearlivre.org','trilhosnocturnos.com',
                 'geoparkestrela.pt','drenergies.com','sal.pt','geres.pt',
                 'trilhosecaminhadas.pt','barbosa-trekking.pt','caminhadassmile.pt')
        domain=parts.hostname.lower().removeprefix('www.')
        if domain not in allowed:
            return None
        with requests.get(target,timeout=(4,8),headers=PHOTO_AGENT,stream=True) as resp:
            resp.raise_for_status()
            if 'text/html' not in resp.headers.get('content-type','text/html').lower():
                return None
            buf=bytearray()
            for chunk in resp.iter_content(chunk_size=32_768):
                buf.extend(chunk)
                if len(buf)>PHOTO_MAX_HTML_BYTES:break
            encoding=resp.encoding or 'utf-8'
            return extract_event_image(bytes(buf).decode(encoding,errors='replace'),resp.url)
    except requests.RequestException:
        return None

def tidy_aggregator_fields(event):
    """Limpa rótulos do agregador que não fazem parte do organizador/morada."""
    org=str(event.get('organizer') or '')
    org=re.sub(r'\s+Contacto\s*:\s*.*$', '',org,flags=re.I).strip()
    if org: event['organizer']=org
    for field in ('start','town'):
        raw=str(event.get(field) or '')
        fixed=re.sub(r'\s*\(\s*Ver\s+no\s+Google\s+Maps\s*\)', '',raw,flags=re.I)
        fixed=re.sub(r'\s+Ver\s+no\s+Google\s+Maps\b.*$', '',fixed,flags=re.I)
        fixed=re.sub(r'\bVila[\s-]*real\b','Vila Real',fixed,flags=re.I)
        fixed=re.sub(r'\bCastelo[\s-]*branco\b','Castelo Branco',fixed,flags=re.I)
        fixed=re.sub(r'\bFundao\b','Fundão',fixed,flags=re.I)
        fixed=fixed.strip(' \t.,;–-')
        if fixed: event[field]=fixed
    # Aspas de cp1252 tratadas como caracteres de controlo por alguns agregadores.
    title=str(event.get('title') or '')
    event['title']=title.replace('\u0093','“').replace('\u0094','”').replace('\u0096','–')
    return event


def remove_aggregator_duplicates(events):
    """Fundir duplicados exactos com preferência pela fonte oficial.

    Nunca usar apenas o URL como identidade: calendários podem conter várias
    caminhadas na mesma página. Conservar IDs alternativos para os favoritos.
    """
    by_key={}
    for entry in events:
        if not isinstance(entry,dict):continue
        key=(str(entry.get('date') or ''),
             re.sub(r'[^a-z0-9]','',folded(entry.get('organizer'))),
             re.sub(r'[^a-z0-9]','',folded(entry.get('title'))))
        old=by_key.get(key)
        if old is None:
            by_key[key]=entry
            continue
        agg=lambda x:(urlsplit(str(x.get('url') or '')).hostname or '').removeprefix('www.')=='trilhosecaminhadas.pt'
        winner=entry if ((agg(old) and not agg(entry)) or
            (agg(old)==agg(entry) and not old.get('verified') and entry.get('verified'))) else old
        loser=old if winner is entry else entry
        aliases=set(winner.get('alias_ids') or []) | set(loser.get('alias_ids') or [])
        if loser.get('id') and loser.get('id')!=winner.get('id'):
            aliases.add(loser['id'])
        aliases.discard(winner.get('id'))
        if aliases:winner['alias_ids']=sorted(aliases)
        # Completar apenas atributos publicados inequívocos. Não copiar GPS
        # entre pontos de encontro diferentes (protecção da Fase 1).
        for field in ('km','gain','price','duration','time','image'):
            if not meaningful(winner.get(field)) and meaningful(loser.get(field)):
                winner[field]=loser[field]
        by_key[key]=winner
    return list(by_key.values())


def is_trilhos_caminhadas_record(event):
    """A origem é o URL/source, não o organizador mencionado no anúncio."""
    if not isinstance(event, dict):
        return False
    host = (urlsplit(str(event.get('url') or '')).hostname or '').removeprefix('www.').lower()
    return (host == 'trilhosecaminhadas.pt' or
            str(event.get('source') or '').strip().casefold() == 'trilhos & caminhadas')


def suppress_non_walks(event):
    """Apenas exclusões verificadas: não apagar caminhadas por terem oficinas no programa."""
    return (event.get('date')=='2026-10-24'
            and urlsplit(str(event.get('url') or '')).path=='/percursos/evento_info.php'
            and 'id=555' in str(event.get('url') or '')
            and 'vamos ao barro e a azeitona' in folded(event.get('title')))


def main():
    if not CATALOG.is_file():
        print('ERRO: catálogo inexistente', file=sys.stderr)
        return 1
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    events = data.get('events')
    if not isinstance(events, list) or not events:
        print('ERRO: catálogo sem eventos', file=sys.stderr)
        return 1
    # Aplicar à lista nova em cada execução, inclusive quando os anúncios
    # chegam repetidos ou a fonte tem rótulos extra.
    for item in events:
        if isinstance(item,dict): tidy_aggregator_fields(item)
    initial_count=len(events)
    # Uma caminhada da RB ou de outro organizador só fica se tiver fonte
    # própria; as ligações antigas ao agregador não são reutilizadas.
    events[:]=remove_aggregator_duplicates([e for e in events if isinstance(e,dict)
        and not is_trilhos_caminhadas_record(e) and not suppress_non_walks(e)])
    removed_aggregator=initial_count-len(events)
    # Só aqui entram as excepções antigas que continuam confirmadas. Nunca
    # acrescentar dados por JavaScript depois de publicar o JSON.
    from consolidar_catalogo import integrate, load_registry
    events[:], verified_corrections, exception_report = integrate(events, load_registry())
    events[:]=remove_aggregator_duplicates(events)
    if isinstance(data.get('sources_health'),dict):
        data['sources_health'].pop('Trilhos & Caminhadas',None)
    previous = git_previous()
    by_id = {e.get('id'): e for e in previous if isinstance(e, dict) and e.get('id')}
    errors = []
    changed = 0
    generic = 0
    missing_departure = 0
    no_gps = 0
    truncated = 0
    seen = set()
    removed_multiday = [e for e in events if isinstance(e, dict) and is_caminhando_multiday(e)]
    if removed_multiday:
        # Retirar antes de validar/publicar e sem perturbar os IDs dos outros eventos.
        events[:] = [e for e in events if not (isinstance(e, dict) and is_caminhando_multiday(e))]
        print('Caminhando.pt: {} excursões de vários dias retiradas da agenda'.format(len(removed_multiday)))
    # Dar prioridade aos pontos de encontro em falta na Mais Trilhos.
    # A verificação normal tinha um orçamento global de 35 consultas e podia
    # gastá-lo antes de chegar às caminhadas de Novembro e Dezembro.
    prioritized = {}
    prioritized_attempted = set()
    for entry in sorted((x for x in events if isinstance(x,dict)), key=lambda x: str(x.get('date',''))):
        if len(prioritized_attempted) >= 15:
            break
        if (entry.get('organizer') == 'Mais Trilhos'
            and folded(entry.get('start')) in PLACEHOLDERS
            and str(entry.get('url') or '').startswith('https://maistrilhos.pt/caminhadas/')
            and str(entry.get('date') or '') >= datetime.now(timezone.utc).date().isoformat()):
            ident = entry.get('id')
            prioritized_attempted.add(ident)
            prioritized[ident] = enrich_official(entry, {})
    network_lookups = 0
    for e in events:
        if not isinstance(e, dict):
            errors.append('Evento sem estrutura JSON válida')
            continue
        ident = e.get('id')
        if not ident or ident in seen:
            errors.append('ID vazio ou duplicado')
        seen.add(ident)
        try:
            if date.fromisoformat(e['date']) < datetime.now(timezone.utc).date():
                errors.append('Evento com data no passado: '+str(ident))
        except (ValueError, TypeError, KeyError):
            errors.append('Data inválida: '+str(ident))
        if not e.get('url', '').startswith(('https://', 'http://')):
            errors.append('Ligação inválida: '+str(ident))
        official_key=(e.get('organizer'), urlsplit(str(e.get('url') or '')).path.rstrip('/').split('/')[-1])
        verified=verified_corrections.get((*official_key, str(e.get('date') or '')))
        if verified:
            for field,value in verified.items():
                if e.get(field)!=value:
                    e[field]=value;changed+=1
        old = by_id.get(ident, {})
        # Caminhando.pt: corrigir título poluído, horas e encontro a partir do
        # próprio cartão e, quando preciso, da página original da actividade.
        if e.get('organizer') == 'Caminhando.pt':
            repaired=repair_caminhando(e,old)
            for field,value in repaired.items():
                # O título do calendário é claramente inválido quando contém
                # repetição de horas e o local no meio.
                if value is not None and e.get(field)!=value:
                    if field=='title' or not meaningful(e.get(field)) or field in ('start','time','endTime','duration'):
                        e[field]=value;changed+=1
            # Não reproduzir o texto "00:00" em anúncios sem hora publicada.
            if e.get('time')=='00:00' and e.get('endTime') is None:
                e['time']='';changed+=1
        # Eventos de dia inteiro do calendário Tribe podem ter 00:00, que não
        # é a hora real da caminhada. Só apresentar se existir hora publicada.
        if e.get('organizer') == 'Clube de Montanhismo da Guarda':
            if (e.get('date')=='2026-10-25' and
                urlsplit(str(e.get('url') or '')).path.rstrip('/').endswith('/marcha-outubro-2026')):
                for field,value in {'start':'Largo da Igreja, Prados, Celorico da Beira',
                                    'town':'Prados, Celorico da Beira',
                                    'time':'09:00','endTime':'12:45','duration':4}.items():
                    if e.get(field)!=value:e[field]=value;changed+=1
            elif e.get('time')=='00:00':
                e['time']='';changed+=1
        # Conservar valores antigos APENAS se a identidade do ponto de partida se mantiver.
        # Caso contrário não voltar a confirmar GPS do evento antigo com uma morada nova.
        if invalidate_stale_coordinates(e, old):
            changed += 1
        new_start,new_town=location_identity(e)
        old_start,old_town=location_identity(old)
        place_changed = ((new_start and old_start and new_start != old_start) or
                         (new_town and old_town and new_town != old_town))
        old_fields=('start', 'town', 'time', 'endTime', 'km', 'gain', 'duration', 'price', 'image', 'image_checked_at')
        # 'status' antigo apenas se a fonte não foi confirmada nesta recolha.
        # Evita conservar "Esgotado" após uma nova listagem sem esse estado.
        if str(e.get('last_seen_at') or '') != datetime.now(timezone.utc).date().isoformat():
            old_fields+=('status',)
        if not place_changed:
            old_fields+=('lat', 'lon', 'verified', 'gps_checked_at')
        for field in old_fields:
            if not meaningful(e.get(field)) and meaningful(old.get(field)):
                e[field] = old[field]
                changed += 1
        # Verificação nas páginas originais para os eventos que têm informação em falta.
        # Limite global de visitas controlado por main() para não bloquear o workflow.
        if not verified and (ident in prioritized_attempted or network_lookups < 35):
            if ident in prioritized_attempted:
                fetched = prioritized.get(ident) or {}
            else:
                if e.get('organizer') in ('Mais Trilhos','GreenTrekker','Hike Land'):
                    network_lookups += 1
                fetched = enrich_official(e, old)
            if fetched:
                for field,value in fetched.items():
                    from_official_meeting = (e.get('organizer') == 'Mais Trilhos'
                                             and field == 'start' and meaningful(value)
                                             and value != e.get('start'))
                    was_missing = not meaningful(e.get(field))
                    more_complete = (field == 'start' and len(str(e.get('start') or '')) >= 80
                                     and len(str(value)) > len(str(e.get('start') or ''))
                                     and str(value).startswith(str(e.get('start') or '')[:60]))
                    if value is not None and (was_missing or more_complete or from_official_meeting):
                        e[field] = value
                        changed += 1
        if e.get('organizer')=='Clube de Montanhismo da Guarda' and e.get('time')=='00:00':
            e['time']='';changed+=1
        # A consulta ao anúncio oficial pode ter actualizado o ponto após a
        # recuperação dos campos antigos. Verificar novamente antes de publicar.
        if invalidate_stale_coordinates(e,old):changed+=1
        if e.get('lat') is not None and e.get('lon') is not None:
            if not (-90 <= float(e['lat']) <= 90 and -180 <= float(e['lon']) <= 180):
                # Coordenadas geograficamente impossíveis não são consideradas válidas.
                errors.append('Coordenadas GPS inválidas: '+str(ident))
        else:
            no_gps += 1
        title = str(e.get('title') or '')
        if GENERIC_TITLE.match(title):
            older_title = str(old.get('title') or '')
            alternative = older_title if older_title and not GENERIC_TITLE.match(older_title) else (official_hikeland_title(e.get('url', '')) or title_from_official_url(e.get('url', '')))
            if alternative and alternative != title:
                e['title'] = alternative
                changed += 1
            else:
                generic += 1
        start = str(e.get('start') or '')
        if folded(start) in PLACEHOLDERS:
            town = str(e.get('town') or '')
            # Localidade claramente legível, mesmo quando o colector a guardou em town.
            if meaningful(town) and len(town) <= 65 and not re.search(r'[,:-]\s*[A-Za-zÀ-ÿ]{1,2}$', town):
                e['start'] = town
                changed += 1
            else:
                missing_departure += 1
        elif re.search(r'[,\s]+[A-Za-zÀ-ÿ]{1,2}$', start) or start.endswith('('):
            truncated += 1

    # Dar prioridade às primeiras 50 caminhadas futuras. Fotografias válidas
    # guardadas no eventos.json nunca são procuradas novamente. Preservar
    # igualmente fotografias de eventos fora deste grupo.
    image_visits=0
    image_added=0
    today=date.today()
    future_events = sorted(
        (e for e in events if isinstance(e, dict) and str(e.get('date', '')) >= today.isoformat()),
        key=lambda e: (str(e.get('date', '9999')), str(e.get('time', '')), str(e.get('title', ''))))
    for e in future_events[:PHOTO_FIRST_EVENTS]:
        if meaningful(e.get('image')):
            if not valid_event_image(e.get('image'),e.get('url','')):
                e.pop('image',None)
            else:
                continue
        checked=str(e.get('image_checked_at') or '')
        try: recently_checked=(today-date.fromisoformat(checked)).days < PHOTO_RETRY_DAYS
        except ValueError:recently_checked=False
        if recently_checked or image_visits>=PHOTO_VISITS_PER_RUN:
            continue
        image_visits+=1
        photo=read_official_photo(e)
        e['image_checked_at']=today.isoformat()
        if photo:
            e['image']=photo
            image_added+=1
            changed+=1
    if previous and len(previous) >= 30 and len(events) < int(len(previous)*0.45):
        errors.append('Queda anormal no catálogo: '+str(len(previous))+' → '+str(len(events)))
    health=data.get('sources_health') or {}
    state_counts={name:sum(1 for item in health.values() if isinstance(item,dict) and item.get('state')==name)
                  for name in ('com_eventos','sem_eventos_ou_indisponivel','erro')}
    lines = [f'Excepções verificadas: {exception_report["added"]} importadas; {exception_report["already_collected"]} já presentes; {exception_report["expired"]} caducadas',
             f'Fontes: {state_counts["com_eventos"]} com eventos; {state_counts["sem_eventos_ou_indisponivel"]} sem confirmação; {state_counts["erro"]} com erro',
             f'Limpeza de anúncios: {removed_aggregator} duplicados, não caminhadas e registos de agregador retirados',
             f'Caminhando.pt: {len(removed_multiday)} excursões multidiárias excluídas',
             f'Fotografias nos primeiros {PHOTO_FIRST_EVENTS} eventos futuros: {image_added} novas, {image_visits} páginas consultadas (máx. {PHOTO_VISITS_PER_RUN}); imagens anteriores preservadas',
             f'{len(events)} eventos analisados; {changed} campos recuperados/corrigidos',
             f'{missing_departure} sem local publicado utilizável; {no_gps} sem coordenadas',
             f'{truncated} locais aparentemente truncados; {generic} títulos genéricos por resolver']
    if errors:
        report(lines + ['ERROS: '+ '; '.join(errors[:12])])
        print('Recusada publicação por inconsistência grave.', file=sys.stderr)
        return 1
    # Não actualizar metadata em execuções sem alterações de conteúdo.
    before = json.loads(CATALOG.read_text(encoding='utf-8'))
    if events != before['events']:
        data['events'] = events
        CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    report(lines)
    return 0

if __name__ == '__main__':
    sys.exit(main())
