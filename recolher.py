#!/usr/bin/env python3
"""Recolhe anúncios públicos de caminhadas; nunca inventa datas nem detalhes.

Este é um colector experimental, com fontes de HTML públicas. Os sites podem
mudar de estrutura, bloquear pedidos automáticos ou ter condições de acesso.
Executa diariamente através do GitHub Actions.
"""

# TRILHARIO FASE 2 — EXTRACCAO E CONTROLO DE FONTES
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from qualidade_anuncios import MULTIDAY, GENERIC_TITLE, title_date_conflicts, is_multiday_program
from identidade_eventos import sessoes_diferentes

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "eventos.json"
TODAY = date.today()
LIMIT_DATE = TODAY + timedelta(days=150)
# Os caminhos das páginas dos eventos não são iguais entre os organizadores.
# Se uma fonte não responder, as restantes continuam a ser consultadas.
SOURCES = [
    {"organizer": "Hiking Around Adventures", "url": "https://www.hikingaround.pt/aventurasnacionais",
     "path": r"^/informa-es-do-evento-e-registro/[^/]+/?$"},
    {"organizer": "Mais Trilhos", "url": "https://maistrilhos.pt/caminhadas", "path": r"^/caminhadas/[^/]+"},
    {"organizer": "Indoeu", "url": "https://indoeu.pt/caminhadas/", "path": r"^/[a-z0-9-]+/?$"},
    {"organizer": "GreenTrekker", "url": "https://www.greentrekker.pt/agenda/", "path": r"^/agenda/[^/]+"},
    {"organizer": "Trekking Roots", "url": "https://trekkingroots.pt/calendario-caminhadas/", "path": r"^/caminhada/[^/]+"},
    {"organizer": "Hike Land", "url": "https://www.hikeland.pt/atividades-1-dia/",
     "fallback": ["https://www.hikeland.pt/atividades/", "https://www.hikeland.pt/eventos/categorias/1-dia/"],
     "path": r"^/eventos/(?!categorias/|etiquetas/|locais/|page/)[^/]+/?$"},
    {"organizer": "Montanhas Dentro", "url": "https://montanhasdentro.pt/",
     "path": r"^/evento/\d+/[^/]+/?$"},
    {"organizer": "Trekkin", "url": "https://www.trekkin.pt/eventos/",
     "path": r"^/evento/[^/]+/[^/]+/?$"},
    {"organizer": "Basto Trekking", "url": "https://bastotrekking.pt/",
     "path": r"^/caminhada/[^/]+/?$"},
    {"organizer": "NDesafios — Natureza e Desafios", "url": "https://ndesafios.pt/",
     "mode": "ndesafios"},
    # Trekking4Life: site Wix oficial sem calendário de saídas parseável.
    # Sem extractor oficial fiável; não importar resultados de agregadores.
    # Agendas oficiais adicionais. Só são importados anúncios com data validada.
    {"organizer": "Montanhas do Norte", "url": "https://montanhasdonorte.pt/percursos-1-dia/",
     "path": r"^/(?:tour|percursos|percurso|produto|atividade|actividade)/[^/]+/?$"},
    {"organizer": "Clube de Montanhismo da Guarda", "url": "https://www.montanhismo-guarda.pt/portal/eventos/lista/",
     "path": r"^/portal/evento/[^/]+/?$"},
    {"organizer": "Amigos da Montanha", "url": "https://amigosdamontanha.com/",
     "fallback": ["https://amigosdamontanha.com/agenda/", "https://amigosdamontanha.com/eventos/"],
     "path": r"^/(?:evento|eventos|atividade|actividade|caminhada|pedestrianismo)/[^/]+/?$"},
    {"organizer": "Caminhando.pt", "url": "https://caminhando.pt/agenda-eventos/caminhadas/",
     "fallback": ["https://caminhando.pt/"],
     "path": r"^/eventos/[^/]+/?$", "required_keyword": "caminhada"},
    {"organizer": "Pé no Mundo", "url": "https://penomundo.pt/",
     "path": r"^/(?:evento|eventos|caminhada|caminhadas|experiencias|experiencia)/[^/]+/?$"},
    {"organizer": "CAAL — Clube de Actividades de Ar Livre", "url": "https://clubearlivre.org/",
     "fallback": ["https://clubearlivre.org/actividades/proximas/"],
     "path": r"^/produto/[^/]+/?$"},
    {"organizer": "Trilhos Nocturnos", "url": "https://trilhosnocturnos.com/eventos-agenda/",
     "path": r"^/eventos/[^/]+/?$", "required_keyword": "caminhada"},
    {"organizer": "Associação Geopark Estrela", "url": "https://geoparkestrela.pt/atividades",
     "path": r"^/atividades/[^/]+/?$", "required_keyword": "caminhada"},
    # Agendas de página única / programas municipais: extractores próprios.
    {"organizer": "DRenergies", "url": "https://www.drenergies.com/calendario-inscricoes-caminhadas", "mode": "drenergies"},
    {"organizer": "SAL — Sistemas de Ar Livre", "url": "https://www.sal.pt/", "mode": "sal"},
    {"organizer": "Gerês Viver Turismo", "url": "https://geres.pt/programa-anual-de-caminhadas-2026/", "mode": "programa"},
    {"organizer": "Programa Municipal de Caminhadas de Lousada", "url": "https://app.cm-lousada.pt/servicos/cultura-desporto-e-lazer/desporto/atividades/galeria-39", "mode": "lousada"},
    # Recolha directa das fontes oficiais de RB e Smile.
    {"organizer": "RB Hiking & Trekking", "url": "https://barbosa-trekking.pt/", "mode": "rb"},
    {"organizer": "Caminhadas Smile", "url": "https://www.caminhadassmile.pt/", "mode": "smile"},
]

MONTHS = {
    "jan": 1, "janeiro": 1, "fev": 2, "fevereiro": 2,
    "mar": 3, "marco": 3, "abr": 4, "abril": 4, "mai": 5, "maio": 5,
    "jun": 6, "junho": 6, "jul": 7, "julho": 7, "ago": 8, "agosto": 8,
    "set": 9, "setembro": 9, "out": 10, "outubro": 10,
    "nov": 11, "novembro": 11, "dez": 12, "dezembro": 12,
}

HEADERS = {"User-Agent": "TrilharioAgenda/0.1 (+https://github.com/lpdre/trilhario; pesquisa-publica; sem-login)",
           "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.6"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def folded(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def date_from(text: str, *, short_year: int | None = None) -> date | None:
    """ISO (incluindo timestamps) e datas em português, com ano implícito."""
    s = folded(str(text or ''))
    m=re.search(r'(?<!\d)(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])(?=T|\D|$)',s,re.I)
    if m:
        try:return date(int(m[1]),int(m[2]),int(m[3]))
        except ValueError:return None
    m=re.search(r'(?<!\d)(0?[1-9]|[12]\d|3[01])[-/](0?[1-9]|1[0-2])[-/](20\d{2})(?=\D|$)',s)
    if m:
        try:return date(int(m[3]),int(m[2]),int(m[1]))
        except ValueError:return None
    m=re.search(r'\b(\d{1,2})\s+(?:de\s+)?(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\b(?:\s+(?:de\s+)?(20\d{2}))?',s)
    if not m:return None
    day,month=int(m[1]),MONTHS[m[2]]
    year=int(m[3]) if m[3] else (short_year or TODAY.year)
    try:
        d=date(year,month,day)
        if not m[3] and short_year is None and d<TODAY-timedelta(days=7):d=date(year+1,month,day)
        return d
    except ValueError:return None



def fetch(url: str) -> BeautifulSoup | None:
    try:
        response = SESSION.get(url, timeout=18, allow_redirects=True)
        response.raise_for_status()
        # Não interpretar páginas anti-bot como catálogos válidos.
        if "text/html" not in response.headers.get("Content-Type", "text/html"):
            return None
        if len(response.content) < 1000:
            return None
        html = response.text
        if "please wait while your request is being verified" in html.lower():
            logging.warning("Fonte bloqueou a consulta: %s", url)
            return None
        return BeautifulSoup(html, "html.parser")
    except requests.RequestException as exc:
        logging.warning("Consulta falhou (%s): %s", url, exc)
        return None


def canonical(base: str, href: str) -> str | None:
    """Normaliza links sem deixar um URL mal formado interromper a fonte."""
    try:
        url = urldefrag(urljoin(base, href))[0].rstrip("/")
        p = urlparse(url)
        if p.scheme not in ("https", "http") or not p.hostname:
            return None
        return p._replace(query="").geturl()
    except (TypeError, ValueError):
        return None


def smallest_context(anchor) -> str:
    """Texto do bloco do anúncio, não de toda a página."""
    best = clean(anchor.get_text(" ", strip=True))
    for parent in list(anchor.parents)[:5]:
        if parent.name in ("body", "html"):
            break
        content = clean(parent.get_text(" ", strip=True))
        if 30 <= len(content) <= 900:
            if date_from(content) is not None:
                return content
            if len(content) > len(best) and len(content) < 400:
                best = content
    return best


def title_from(anchor, block: str, organizer: str) -> str:
    title = clean(anchor.get_text(" ", strip=True))
    if len(title) < 8 or folded(title) in {"ver detalhes", "mais informacoes", "ver mais", "+info", "informacoes", "visualizar evento", "ver evento", "consultar", "saber mais"}:
        for parent in list(anchor.parents)[:5]:
            heading = parent.find(re.compile(r"^h[1-6]$"))
            if heading:
                title = clean(heading.get_text(" ", strip=True))
                break
    title = re.sub(r"^(?:new!?|novo!?|esgotado!?|últimas vagas!?|ultimas vagas!?|\s)+", "", title, flags=re.I)
    title = re.sub(r"\s*(?:\+INFO|Mais Informações|Ver Detalhes)\s*$", "", title, flags=re.I)
    title = re.sub(r"^(?:\d{1,2}\s+(?:Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez)\s+)", "", title, flags=re.I)
    title = re.sub(r"\s*20\d{2}-\d{2}-\d{2}\s*$", "", title)
    title = re.sub(r"^\d{1,2}\s+(?:de\s+)?(?:janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+20\d{2}\s+", "", title, flags=re.I)
    return title.strip(" -—|")[:140]


def number(pattern: str, content: str, max_value: float) -> float | None:
    m = re.search(pattern, content, re.I)
    if m:
        try:
            x = float(m.group(1).replace(",", "."))
            if 0 < x <= max_value:
                return x
        except ValueError:
            pass
    return None


def parse_meta(html: BeautifulSoup, event: dict) -> None:
    """Páginas individuais: escolher apenas números com contexto inequívoco."""
    main=html.find('main') or html.find('article') or html
    text=clean(main.get_text(' ',strip=True))[:12000]
    if event.get('km') is None:
        # Caminhando.pt publica descrições geográficas com distâncias que não
        # correspondem ao percurso. Só aceitar quilómetros com rótulo explícito.
        if event.get('organizer') == 'Caminhando.pt':
            km_pattern = r'\bDist[aâ]ncia(?:\s+do\s+percurso)?\s*[:\-]?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*km\b'
        else:
            km_pattern = r'\b(\d{1,3}(?:[.,]\d{1,2})?)\s*km\b'
        event['km'] = number(km_pattern, text, 160)
    if event.get('gain') is None:
        gain=number(r'(?:D\+|desn[ií]vel(?: positivo| acumulado)?|ascens[aã]o)\s*[:\-]?\s*(\d{2,4})\s*m',text,4500)
        if gain is None:gain=number(r'\b(\d{2,4})\s*m\s*d\+(?=\s|$)',text+' ',4500)
        if gain is not None:event['gain']=round(gain)
    if event.get('price') is None:
        # Primeiro tarifa de participante/adulto; não adoptar o preço de criança.
        sections=[r'\bpre[cç]o\s+(?:por\s+)?participante\s*[:\-]?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€',
                  r'\b(?:pre[cç]o|valor|inscri[cç][aã]o)\s*[:\-]?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€',
                  r'\b(?:adultos?|participantes?)\s*[:\-]?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€']
        for pat in sections:
            m=re.search(pat,text,re.I)
            if m:
                val=float(m[1].replace(',','.'))
                if 0<=val<=500:event['price']=val;break
        if event.get('price') is None:
            # Não tomar o preço de crianças como preço geral.
            prices=list(re.finditer(r'(?<!\d)(\d{1,3}(?:[.,]\d{1,2})?)\s*€',text,re.I))
            adult=[m for m in prices if not re.search(r'\b(?:crian[cç]as?|menores?|infantil)\b',text[max(0,m.start()-45):m.start()],re.I)]
            if len(adult)==1:
                val=float(adult[0][1].replace(',','.'))
                if 0<=val<=500:event['price']=val
            elif re.search(r'\b(?:pre[cç]o|inscri[cç][aã]o|participa[cç][aã]o)\s*[:\-]?\s*gratuit[oa]\b',text,re.I):
                event['price']=0.0
    if not event.get('duration'):
        dm=re.search(r'\b(?:dura[cç][aã]o|tempo previsto|tempo estimado)\s*[:\-]?\s*(\d{1,2})\s*h\s*(\d{1,2})(?:\s*min(?:utos?)?)?\b',text,re.I)
        if dm:
            hours=int(dm[1])+int(dm[2])/60
            if 0<hours<=24 and int(dm[2])<60:event['duration']=round(hours,3)
        if not event.get('duration'):
            event['duration']=number(r'(?:dura[cç][aã]o|tempo previsto|tempo estimado)\s*[:\-]?\s*(\d{1,2}(?:[.,]\d)?)\s*(?:h\b|horas?)',text,24)
    if not event.get('time'):
        m=re.search(r'(?:in[ií]cio|partida|hora de encontro|concentra[cç][aã]o|data)\s*[:\-]?\s*(?:\d{1,2}/\d{1,2}/20\d{2}\s*,?\s*)?(\d{1,2})[:h](\d{2})',text,re.I)
        if m and int(m[1])<=23 and int(m[2])<=59:event['time']=f'{int(m[1]):02d}:{m[2]}'
    if event.get('start')=='Por confirmar':
        m=re.search(r'(?:local de (?:partida|encontro)|ponto de encontro)\s*[:\-]\s*([^.;]{5,95})',text,re.I)
        if m:event['start']=clean(m[1])
    if event.get('town')=='Por confirmar':
        m=re.search(r'(?:localiza[cç][aã]o|localidade|local)\s*[:\-]\s*([^.;,]{3,55})',text,re.I)
        if m:event['town']=clean(m[1])
    if event.get('difficulty') is None:
        t=folded(text[:2200])
        for level,pats in ((5,['muito dificil']),(4,['dificil']),(3,['exigente']),(2,['moderada','moderado']),(1,['facil'])):
            if any(p in t for p in pats):event['difficulty']=level;break



def enrich_jsonld(html: BeautifulSoup, event: dict) -> None:
    """O JSON-LD só pode corrigir a ficha do evento a que o URL corresponde."""
    nodes=[]
    for tag in html.select('script[type="application/ld+json"]'):
        try:root=json.loads(tag.string or tag.get_text())
        except (ValueError,TypeError):continue
        queue=[root]
        while queue:
            obj=queue.pop()
            if isinstance(obj,list):queue.extend(obj);continue
            if not isinstance(obj,dict):continue
            if '@graph' in obj:queue.append(obj['@graph'])
            typ=obj.get('@type',[])
            if isinstance(typ,str):typ=[typ]
            if any(str(x).split('/')[-1]=='Event' for x in typ):nodes.append(obj)
    if not nodes:return
    url=str(event.get('url') or '').split('#')[0].rstrip('/')
    def node_url(node):
        x=node.get('url') or node.get('@id') or ''
        return str(x).split('#')[0].rstrip('/') if isinstance(x,str) else ''
    matches=[n for n in nodes if node_url(n)==url and url]
    if len(matches)==1:node=matches[0]
    elif len(nodes)==1 and (not node_url(nodes[0]) or node_url(nodes[0])==url):node=nodes[0]
    else:return  # Metadados de outros eventos não são informação desta página.
    iso=node.get('startDate')
    if isinstance(iso,str):
        dt=date_from(iso)
        if dt:event['date']=dt.isoformat()
        timem=re.search(r'T(\d{2}:\d{2})',iso)
        if timem:event['time']=timem[1]
    # Apenas uma data final publicada no Event da própria ficha.
    # Nunca inferir o fim a partir de duração, alojamento ou texto livre.
    end_iso=node.get('endDate')
    if isinstance(end_iso,str) and event.get('date'):
        try:
            start_day=date.fromisoformat(str(event['date']))
        except ValueError:
            start_day=None
        end_day=date_from(end_iso)
        if start_day and end_day and end_day>start_day:
            event['endDate']=end_day.isoformat()
            event['multiDay']=True
    status=str(node.get('eventStatus') or '')
    if status.endswith('EventCancelled'):
        event['status']='Cancelado';event['status_checked_at']=TODAY.isoformat()
    elif status.endswith('EventPostponed'):
        event['status']='Adiado';event['status_checked_at']=TODAY.isoformat()
    elif status.endswith('EventScheduled'):
        event['status']='';event['status_checked_at']=TODAY.isoformat()
    loc=node.get('location') or {}
    if isinstance(loc,list):loc=next((x for x in loc if isinstance(x,dict)),{})
    if isinstance(loc,dict):
        name=loc.get('name')
        if isinstance(name,str) and name.strip():event['start']=clean(name)
        addr=loc.get('address') or {}
        if isinstance(addr,dict):
            town=addr.get('addressLocality')
            if isinstance(town,str) and town.strip():event['town']=clean(town)
        geo=loc.get('geo') or {}
        if isinstance(geo,dict):
            try:
                lat,lon=float(geo['latitude']),float(geo['longitude'])
                if 36<lat<43 and -10<lon<-6:event.update(lat=lat,lon=lon,verified=True)
            except (KeyError,ValueError,TypeError):pass
    offers=node.get('offers') or []
    if isinstance(offers,dict):offers=[offers]
    values=[]
    for offer in offers:
        if not isinstance(offer,dict):continue
        try:
            if str(offer.get('priceCurrency','EUR')).upper()!='EUR':continue
            v=float(str(offer['price']).replace(',','.'))
            if 0<=v<=500:values.append(v)
        except (KeyError,ValueError,TypeError):continue
    if len(set(values))==1:event['price']=values[0]



def extra_source_meta(html: BeautifulSoup, item: dict, organizer: str) -> None:
    """Campos específicos de eventos de organizadores com estruturas próprias."""
    scope = html.find("main") or html.find("article") or html
    value = clean(scope.get_text(" ", strip=True))[:16000]
    if organizer == "GreenTrekker":
        # Os preços surgem normalmente em «Faça Já A Sua Reserva», frequentemente
        # depois dos 12 000 caracteres lidos por parse_meta. Procurar o valor
        # APENAS nessa secção evita confundir preços de anúncios relacionados.
        if item.get("price") is None or item.get("price") == 0:
            full_text = clean(html.get_text(" ", strip=True))
            for heading in re.finditer(r"(?:fa[cç]a\s+j[aá]\s+a\s+sua\s+reserva|reservas\s+fechadas!?)", full_text, re.I):
                booking = full_text[heading.end():heading.end() + 240]
                m_price = re.search(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:€|euros?)", booking, re.I)
                if m_price:
                    price = float(m_price[1].replace(",", "."))
                    if 0 < price <= 500:
                        item["price"] = price
                        break
    elif organizer == "Indoeu":
        # Neste site o ponto de encontro surge como título e depois um item de lista,
        # sem dois pontos, pelo que não era detectado pelo colector genérico.
        for heading in scope.find_all(re.compile(r"^h[1-6]$")):
            if folded(clean(heading.get_text(" ", strip=True))) != "ponto de encontro":
                continue
            following = heading.find_next(["li", "p"])
            if following:
                place = clean(following.get_text(" ", strip=True))
                if 4 <= len(place) <= 110 and "coordenadas" not in folded(place):
                    item["start"] = place
                    item["town"] = place
                break
        # Hora no formato «Início: 9:15 horas» (extractor genérico aceita-o).
    elif organizer == "Hike Land":
        # O preço da ficha pode estar fora do <main>, no bloco de inscrição.
        # A exigência de «€ | Participante» evita preços de ofertas relacionadas.
        if item.get("price") is None:
            full_text = clean(html.get_text(" ", strip=True))
            mprice = re.search(
                r"\bpre[cç]o\s*[:–—-]?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*\|\s*participante\b",
                full_text, re.I)
            if mprice:
                item["price"] = float(mprice[1].replace(",", "."))
        if not item.get("time"):
            mtime = re.search(r"in[ií]cio\s*:\s*\d{1,2}\s+de\s+\w+\s*[|–-]\s*(\d{1,2}):(\d{2})", value, re.I)
            if mtime and int(mtime[1]) < 24 and int(mtime[2]) < 60:
                item["time"] = f"{int(mtime[1]):02d}:{mtime[2]}"
        m = re.search(r"(?:ponto de encontro)\s+(?:localiza[cç][aã]o\s*[:\-]\s*)?(.{5,105}?)(?:\s+o pre[cç]o|\s+pre[cç]o inclui|\s+o pre[cç]o inclui|\s+inscreva-se|$)", value, re.I)
        if m and "localiza" not in folded(m[1][:10]):
            place = clean(m[1]).rstrip('. ')
            if len(place) <= 105:
                item["start"] = place
        if item.get("duration") is None:
            m = re.search(r"dura[cç][aã]o\s*[:\-]?\s*(\d{1,2})h(\d{2})", value, re.I)
            if m:
                item["duration"] = int(m[1]) + int(m[2]) / 60
    elif organizer == "Montanhas Dentro":
        if not item.get("time"):
            mtime = re.search(r"(?:segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)\s*,?\s*\d{1,2}\s+de\s+\w+\s*[,.]?\s*(\d{1,2}):(\d{2})", value, re.I)
            if mtime and int(mtime[1]) < 24 and int(mtime[2]) < 60:
                item["time"] = f"{int(mtime[1]):02d}:{mtime[2]}"
        if item.get("town") == "Por confirmar":
            m = re.search(r"localiza[cç][aã]o\s+([^.;]{3,70}?)(?:\s+como chegar|\s+ver no google maps|\s+programa)", value, re.I)
            if m:
                item["town"] = clean(m[1])
        # É habitual o local de encontro só ser comunicado após a inscrição.
        if item.get("km") is None:
            m = re.search(r"\b(\d{1,2}(?:[,.]\d)?)\s*km\b", value, re.I)
            if m:
                item["km"] = float(m[1].replace(',', '.'))
    elif organizer == "Trekkin":
        m = re.search(r"\blocal\s*:\s*([^.;]{3,80}?)(?:\s+pre[cç]o\s*:|\s+descri[cç][aã]o)", value, re.I)
        if m:
            place = clean(m[1])
            if folded(place) != "local por definir":
                item["town"] = place
                item["start"] = place
        # Data «15/11/2026, 10:00», que não existia no date_from original.
    elif organizer == "Caminhadas Smile":
        if not item.get("time"):
            mtime = re.search(r"hora e local de encontro\s*:\s*(\d{1,2}):(\d{2})", value, re.I)
            if mtime and int(mtime[1]) < 24 and int(mtime[2]) < 60:
                item["time"] = f"{int(mtime[1]):02d}:{mtime[2]}"
        if item.get("start") == "Por confirmar" or re.match(r"^\d{1,2}:\d{2}\s*h?\s*[–-]", item.get("start") or ""):
            mplace = re.search(r"hora e local de encontro\s*:\s*\d{1,2}:\d{2}\s*h?\s*[–\-]\s*(.{5,120}?)(?:\s+coordenadas gps|\s+\|\s+ver mapa|\s+percurso\s*:)", value, re.I)
            if mplace:
                item["start"] = clean(mplace[1]).strip(' .')
        if item.get("town") == "Por confirmar":
            mloc = re.search(r"zona da atividade\s*:\s*([^.;]{4,70})", value, re.I)
            if mloc:
                item["town"] = clean(mloc[1])
    elif organizer == "Hiking Around Adventures":
        title = scope.find("h1") or html.find("h1")
        if title:
            item["title"] = clean(title.get_text(" ", strip=True))[:140]
        # Wix inclui a data e hora em «Horário e local».
        when = re.search(r"\b(\d{1,2}/\d{1,2}/20\d{2}),?\s*(\d{1,2}:\d{2})(?:\s*[–-]\s*(\d{1,2}:\d{2}))?", value)
        if when:
            parsed = date_from(when[1])
            if parsed:
                item["date"] = parsed.isoformat()
            item["time"] = when[2].zfill(5)
            if when[3]:
                t1,t2=when[2],when[3]
                h1,m1=map(int,t1.split(':'));h2,m2=map(int,t2.split(':'))
                mins=(h2*60+m2)-(h1*60+m1)
                if 0<mins<=14*60:
                    item["duration"] = mins/60
        # Na descrição pode aparecer a tarifa com transfer; usar o preço base.
        mprice = re.search(r"\b(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:euros?|€)\s+por\s+pessoa", value, re.I)
        if mprice:
            item["price"] = float(mprice[1].replace(',', '.'))
        # Consumir também a data final dos programas de vários dias antes do local.
        # Sem local, não permitir que o intervalo opcional seja capturado como morada.
        start = re.search(
            r"Horário e local\s+\d{1,2}/\d{1,2}/20\d{2},?\s*\d{1,2}:\d{2}"
            r"(?:\s*[–—-]\s*(?:\d{1,2}/\d{1,2}/20\d{2},?\s*)?\d{1,2}:\d{2})?"
            r"\s+(?![–—-]|\d{1,2}/\d{1,2}/20\d{2})(.{8,105}?)(?:\s+Sobre o evento|\s+Descrição)",
            value, re.I)
        if start:
            item["start"] = clean(start[1])
        if 'esgotado' in folded(value[:1600]):
            item["status"] = "Esgotado"
        elif 'registo encerrado' in folded(value[:1600]):
            item["status"] = "Inscrições encerradas"
    elif organizer == "Basto Trekking":
        if item.get("price") is None:
            m = re.search(r"(?:inscri[cç][oõ]es|custo)\s*[:\-]?\s*(\d{1,3}(?:[,.]\d{1,2})?)\s*euros?", value, re.I)
            if m:
                item["price"] = float(m[1].replace(',', '.'))



# Filtragem prudente: não usar anúncios de BTT, trails competitivos,
# eventos de sala ou datas fora da janela de recolha.
NON_WALK_TITLES = re.compile(
    r"\b(?:btt|bike|bicicleta|pedalar|ciclismo|maratona|ultra\s?trail|"
    r"trail\s?running|corrida|jipes?|bugg?ys?|visita\s+guiada\s+ao\s+museu|"
    r"jantar|workshop|formac[aã]o|confer[eê]ncia|semin[aá]rio|mercados?\s+de\s+natal)\b", re.I
)
WALK_TERMS = re.compile(r"caminhad|pedestr|trekking|marcha|trilho|rota|levada|percurs|passeio", re.I)


def valid_new_event(item: dict) -> bool:
    try:
        dt = date.fromisoformat(item.get("date", ""))
    except (TypeError, ValueError):
        return False
    if not TODAY <= dt <= LIMIT_DATE:
        return False
    # Uma data final explícita tem de pertencer à mesma edição e ser válida.
    # A permanência na agenda continua a depender apenas da data inicial.
    if item.get('endDate') is not None:
        try:
            if date.fromisoformat(str(item['endDate'])) < dt:
                return False
        except (TypeError, ValueError):
            return False
    title = clean(item.get("title", ""))
    if not 7 <= len(title) <= 140 or NON_WALK_TITLES.search(title):
        return False
    multi = is_multiday_program(item)
    if item.get("km") is not None and not (0 < float(item["km"]) <= (250 if multi else 40)):
        return False
    if item.get("duration") is not None and not (0 < float(item["duration"]) <= (168 if multi else 14)):
        return False
    return True


def new_event(organizer: str, url: str, title: str, dt: date, **fields) -> dict:
    return {
        "id": "web-" + hashlib.sha256(f"{organizer}|{url}|{dt.isoformat()}|{folded(title)}".encode()).hexdigest()[:15],
        "title": clean(title)[:140], "date": dt.isoformat(), "organizer": organizer,
        "url": url, "town": "Por confirmar", "start": "Por confirmar",
        "region": "", "area": "", "time": "", "km": None, "gain": None,
        "duration": None, "price": None, "difficulty": None,
        "description": "Consultar informações e inscrições junto do organizador.",
        "tag": "Caminhada", **fields,
    }


def collect_drenergies(source: dict) -> list[dict]:
    """Agenda por meses: criar evento só quando título e data estão contíguos."""
    html = fetch(source['url'])
    if html is None:
        return []
    result = []
    year = TODAY.year
    for heading in html.find_all(re.compile(r'^h[1-6]$')):
        t = clean(heading.get_text(' ', strip=True))
        match = re.search(r'\b(\d{1,2})\s+de\s+(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b',folded(t))
        if not match:
            continue
        dateobj = date_from(t,short_year=year)
        if not dateobj:
            continue
        nxt = heading.find_next(re.compile(r'^h[1-6]$'))
        if not nxt:
            continue
        title = clean(nxt.get_text(' ', strip=True))
        if not (WALK_TERMS.search(title) or re.search('faias|covao|castelo|tun[eé]is|azeitona|ribeira',folded(title))):
            continue
        e = new_event(source['organizer'],source['url'],title,dateobj)
        if valid_new_event(e):
            result.append(e)
    return result


def collect_sal(source: dict) -> list[dict]:
    """Homepage apresenta datas e ligações de percursos curtos; tratar só passeios de um dia."""
    html = fetch(source['url'])
    if html is None:
        return []
    found=[]
    for a in html.find_all('a',href=True):
        url=canonical(source['url'],a['href'])
        if not url or urlparse(url).hostname not in ('www.sal.pt','sal.pt') or not re.search(r'\.shtml$',urlparse(url).path):
            continue
        title=clean(a.get_text(' ',strip=True))
        if len(title)<7 or not re.search(r'rota|passeio|caminhad|percurso|trilho',folded(title)):
            continue
        detail=fetch(url)
        if detail is None:
            continue
        content=clean(detail.get_text(' ',strip=True))
        # Sites SAL podem publicar datas de edições distintas na mesma página.
        for m in re.finditer(r'Data\s*:\s*(?:Segunda|Ter[cç]a|Quarta|Quinta|Sexta|S[aá]bado|Domingo)?\s*(\d{1,2})\s+(?:de\s+)?(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+(20\d{2})\s*(\d{1,2})[:h](\d{2})',content,re.I):
            dt=date_from(f'{m[1]} {m[2]} {m[3]}')
            if not dt: continue
            item=new_event(source['organizer'],url,title,dt,time=f'{int(m[4]):02d}:{m[5]}')
            parse_meta(detail,item)
            # O preço 0 só é usado quando está explicitamente marcado como gratuito.
            if re.search(r'pre[cç]o\s*:\s*gratuito',content,re.I): item['price']=0
            if valid_new_event(item):found.append(item)
    return found


def collect_simple_program(source: dict) -> list[dict]:
    """Agenda informativa: exigir datas individuais para não inventar saídas."""
    # O programa é um PDF sem datas e ligações individuais utilizáveis.
    # Evitar pedidos ao site quando sabemos que não podemos importar anúncios.
    if source['mode']=='programa':
        logging.info('%s: programa PDF apenas para consulta; sem anúncios confirmados.',source['organizer'])
        return []
    html=fetch(source['url'])
    if html is None:return []
    result=[]
    for a in html.find_all('a',href=True):
        parent=a.parent
        block=clean(parent.get_text(' ',strip=True)) if parent else ''
        dt=date_from(block)
        title=clean(a.get_text(' ',strip=True))
        url=canonical(source['url'],a['href'])
        if dt and url and 7<=len(title)<=110 and WALK_TERMS.search(title) and urlparse(url).hostname==urlparse(source['url']).hostname:
            item=new_event(source['organizer'],url,title,dt,town='Lousada',start='Lousada (local exacto a confirmar)')
            if valid_new_event(item):result.append(item)
    return result


def similarity_key(item: dict) -> tuple[str,str,str]:
    title = folded(item.get('title', ''))
    title = re.sub(r'[^a-z0-9 ]', ' ', title)
    title = re.sub(r'\b(?:caminhada|trilho|trekking|rota|passeio|ao|aos|da|das|de|do|dos|pela|pelas|pelo|pelos|na|no|em)\b',' ', title)
    title = re.sub(r'\s+',' ',title).strip()
    org = re.sub(r'[^a-z0-9]','',folded(item.get('organizer','')))
    return (item.get('date',''),org,title)


def deduplicate(events: list[dict], preferred_ids=None) -> list[dict]:
    """Fundir apenas anúncios compatíveis da mesma data e organizador.

    IDs já publicados têm prioridade sobre IDs novos gerados por uma alteração
    de título ou metadados. Hora, ponto de partida ou duas fichas oficiais
    individuais contraditórias impedem a fusão.
    """
    from difflib import SequenceMatcher
    preferred_ids = set(preferred_ids or ())
    grouped = {}
    ungrouped = []
    def rank(item):
        return (item.get('id') in preferred_ids,
                bool(item.get('verified')),
                sum(item.get(k) is not None for k in ('km','gain','price','time','duration')))
    for item in sorted(events, key=rank, reverse=True):
        day,org,title=similarity_key(item)
        if not day or not org or not title:
            # Deixar o validador sinalizar registos incompletos, em vez de
            # os apagar silenciosamente durante a deduplicação.
            ungrouped.append(item)
            continue
        group=grouped.setdefault((day,org),[])
        def duplicates(previous):
            if sessoes_diferentes(item,previous):
                return False
            old_title=similarity_key(previous)[2]
            if old_title==title:return True
            a,b=set(old_title.split()),set(title.split())
            if not a or not b:return False
            overlap=len(a&b)/max(len(a),len(b))
            return overlap>=0.86 and SequenceMatcher(None,old_title,title).ratio()>=0.94
        prev=next((x for x in group if duplicates(x)),None)
        if prev is None:group.append(item);continue
        aliases=set(prev.get('alias_ids') or [])|set(item.get('alias_ids') or [])
        if item.get('id') and item.get('id')!=prev.get('id'):aliases.add(item['id'])
        aliases.discard(prev.get('id'))
        if aliases:prev['alias_ids']=sorted(x for x in aliases if x)
        for field in ('km','gain','price','duration','time','town','start','image'):
            if prev.get(field) in (None,'','Por confirmar') and item.get(field) not in (None,'','Por confirmar'):
                prev[field]=item[field]
        # Um ID antigo não impede o aproveitamento de GPS confirmado agora.
        if not prev.get('verified') and item.get('verified') is True and (
                item.get('lat') is not None and item.get('lon') is not None):
            for field in ('lat','lon','verified','gpsFromAnnouncement'):
                if field in item:prev[field]=item[field]
    return [item for group in grouped.values() for item in group]+ungrouped


def collect_ndesafios(source: dict) -> list[dict]:
    """Consulta apenas os cartões de 1 dia do site oficial.

    O site reutiliza por vezes links de páginas antigas. Quando a data no
    detalhe não coincide com a anunciada na página inicial, rejeitar o anúncio
    em vez de misturar anos ou publicar uma data inferida.
    """
    html = fetch(source['url'])
    if html is None:
        return []
    heading = next((h for h in html.find_all(re.compile(r'^h[1-6]$'))
                    if folded(clean(h.get_text(' ', strip=True))) == 'atividades de um dia'), None)
    if heading is None:
        logging.warning('NDesafios: secção de actividades de um dia não encontrada')
        return []
    result, visited = [], set()
    datepat = re.compile(r'(\d{1,2}\s+de\s+(?:janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+20\d{2})?)\b', re.I)
    for node in heading.next_elements:
        if getattr(node, 'name', None) in ('h1','h2','h3','h4','h5','h6'):
            head=folded(clean(node.get_text(' ',strip=True)))
            if head in ('aventuras','workshops e formacoes'):
                break
        if getattr(node, 'name', None) != 'a' or not node.get('href'):
            continue
        href=canonical(source['url'],node['href'])
        if not href or urlparse(href).hostname not in ('ndesafios.pt','www.ndesafios.pt') or href in visited:
            continue
        visited.add(href)
        raw=clean(node.get_text(' ',strip=True))
        match=datepat.search(raw)
        if not match:
            continue
        announced=date_from(match[1],short_year=TODAY.year)
        if not announced or not TODAY<=announced<=LIMIT_DATE:
            continue
        title=clean(raw[:match.start()]).strip(' –-:|')
        if not 7<=len(title)<=140 or NON_WALK_TITLES.search(title):
            continue
        detail=fetch(href)
        if detail is None: # Não inventar metadados com uma página indisponível.
            continue
        main=detail.find('main') or detail.find('article') or detail
        title_tag=main.find('h1') or detail.find('h1')
        if title_tag:
            t=clean(title_tag.get_text(' ',strip=True))
            if 7<=len(t)<=140:
                title=t
        if NON_WALK_TITLES.search(title):
            continue
        # A data mais próxima do título costuma estar no h2/h3 do anúncio.
        heading_date=next((h for h in main.find_all(['h2','h3','h4'])[:8]
                           if datepat.search(clean(h.get_text(' ',strip=True)))),None)
        if heading_date:
            m=datepat.search(clean(heading_date.get_text(' ',strip=True)))
            detail_date=date_from(m[1],short_year=announced.year) if m else None
            if detail_date and detail_date!=announced:
                logging.warning('NDesafios: data divergente %s (lista %s, detalhe %s)',href,announced,detail_date)
                continue
        item={'id':'web-'+hashlib.sha256(f"{source['organizer']}|{href}".encode()).hexdigest()[:15],
              'title':title,'date':announced.isoformat(),'organizer':source['organizer'],
              'url':href,'town':'Por confirmar','start':'Por confirmar','region':'',
              'area':'','time':'','km':None,'gain':None,'duration':None,
              'price':None,'difficulty':None,'description':'Consultar detalhes no organizador.',
              'tag':'Caminhada'}
        enrich_jsonld(detail,item)
        item['date']=announced.isoformat() # Data de destaque da agenda prevalece.
        parse_meta(detail,item)
        opening=clean(main.get_text(' ',strip=True))[:600]
        clock=re.search(r'\b(?:[àa]s|inicio:?)\s*(\d{1,2})[h:](\d{2})\b',opening,re.I)
        if clock and int(clock[1])<24 and int(clock[2])<60:
            item['time']=f"{int(clock[1]):02d}:{clock[2]}"
        if item.get('km') is not None and item['km']>(250 if is_multiday_program(item) else 40):
            continue
        if not valid_new_event(item):
            continue
        result.append(item)
        time.sleep(0.12)
    logging.info('NDesafios: %d eventos futuros de um dia validados',len(result))
    return result



# A data de um evento não pode ser copiada de cartões adjacentes.
# Montanhas Dentro: consultar a página INDIVIDUAL e validar a data e o tipo
# no cabeçalho do evento, antes da secção «Outros eventos».
MONTANHAS_ORG = "Montanhas Dentro"
MONTANHAS_MONTHS = (
    r"janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|"
    r"setembro|outubro|novembro|dezembro"
)
MONTANHAS_WD = r"segunda(?:-feira)?|ter[cç]a(?:-feira)?|quarta(?:-feira)?|quinta(?:-feira)?|sexta(?:-feira)?|s[aá]bado|domingo"
MONTANHAS_HEAD_DATE = re.compile(
    rf"\b(?P<weekday>{MONTANHAS_WD})\s*,?\s*(\d{{1,2}})\s+de\s+({MONTANHAS_MONTHS})\b(?:\s+de\s+(20\d{{2}}))?",
    re.I,
)
MONTANHAS_MULTIDAY = re.compile(
    rf"\b\d{{1,2}}\s+de\s+(?:{MONTANHAS_MONTHS})\s+a\s+\d{{1,2}}\s+de\s+(?:{MONTANHAS_MONTHS})\b"
    r"|\b(?:fim de semana|\d+\s*(?:dias|noites))\b",
    re.I,
)
MONTANHAS_PREFIX_DATE = re.compile(r"^\s*(?:seg|ter|qua|qui|sex|s[aá]b|dom)[a-zçãé-]*\s*,?\s*(\d{1,2})\s+(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\b", re.I)


def header_date_conflicts(item: dict) -> bool:
    """Detecta datas contraditórias em saídas individuais.

    Títulos multidiários podem mencionar a data de fim e a de início.
    """
    if is_multiday_program(item):
        return False
    if title_date_conflicts(item):
        return True
    m = MONTANHAS_PREFIX_DATE.search(item.get('title') or '')
    if not m:
        return False
    try:
        dt = date.fromisoformat(item['date'])
    except (ValueError, KeyError, TypeError):
        return True
    return (dt.day != int(m[1]) or dt.month != MONTHS[folded(m[2])])


def parse_montanhas_detail(soup: BeautifulSoup, url: str) -> dict | None:
    """Só aceita caminhadas de 1 dia, com data/hora no cabeçalho da página oficial.

    Não usa o texto de «Outros eventos», não infere datas a partir da
    homepage e não confunde o preço de membro com a tarifa de adulto.
    """
    # Se não há conteúdo oficial verificável, falhar fechado.
    main = soup.find('main') or soup.find('article') or soup
    heading = main.find('h1') or soup.find('h1')
    if heading is None:
        return None
    title = clean(heading.get_text(' ', strip=True))
    if not title or not 7 <= len(title) <= 140:
        return None
    full = clean(main.get_text(' ', strip=True))
    pos = full.find(title)
    if pos < 0:
        return None
    # A área do cabeçalho termina antes da apresentação detalhada da actividade.
    beginning = full[pos + len(title):pos + len(title) + 1200]
    if 'Adicionar ao calendário' in beginning:
        beginning = beginning.split('Adicionar ao calendário', 1)[0]
    if 'Outros eventos' in beginning:
        beginning = beginning.split('Outros eventos', 1)[0]
    m = MONTANHAS_HEAD_DATE.search(beginning)
    if m is None:
        logging.warning('Montanhas Dentro: sem data principal inequívoca: %s', url)
        return None
    # Os programas pedestres de vários dias são elegíveis.
    if NON_WALK_TITLES.search(title):
        logging.info('Montanhas Dentro: actividade não pedestre: %s', title)
        return None
    after_date = beginning[m.end():m.end() + 115]
    # É um campo de tipo do anúncio: '19:00 Caminhada 4,5 km'.
    if not re.search(r'^\s*(?:[012]?\d:[0-5]\d\s+)?Caminhada\b', after_date, re.I):
        logging.info('Montanhas Dentro: não é caminhada: %s', title)
        return None
    date_text = f'{m[2]} de {m[3]}' + (f' de {m[4]}' if m[4] else '')
    d = date_from(date_text)
    if d is None or not TODAY <= d <= LIMIT_DATE:
        return None
    weekdays = {'segunda': 0, 'terca': 1, 'quarta': 2, 'quinta': 3,
                'sexta': 4, 'sabado': 5, 'domingo': 6}
    announced_weekday = folded(m['weekday']).split('-')[0]
    if weekdays.get(announced_weekday) != d.weekday():
        logging.warning('Montanhas Dentro: dia da semana contradiz a data (%s)', url)
        return None
    time_match = re.match(r'\s*([01]?\d|2[0-3]):([0-5]\d)\s+', after_date)
    time_str = f'{int(time_match[1]):02d}:{time_match[2]}' if time_match else ''
    km_match = re.search(r'\bCaminhada\s+(\d{1,2}(?:[,.]\d{1,2})?)\s*km\b', after_date, re.I)
    kms = float(km_match[1].replace(',', '.')) if km_match else None
    # Tarifa base do adulto, não a de membro/criança.
    pm = re.search(r'\bAdulto\s+(\d{1,3}(?:[,.]\d{1,2})?)\s*€', beginning, re.I)
    price = float(pm[1].replace(',', '.')) if pm else None
    prog_idx = full.find('Programa', pos + len(title))
    outro_idx = full.find('Outros eventos', pos + len(title))
    prog = full[prog_idx:(outro_idx if outro_idx > prog_idx else prog_idx + 1600)] if prog_idx >= 0 else ''
    gain_match = re.search(r'\+\s*(\d{2,4})\s*m\b', prog, re.I)
    gain = int(gain_match[1]) if gain_match else None
    town = 'Por confirmar'
    loc_idx = full.find('Localização', pos + len(title))
    if loc_idx >= 0 and (outro_idx < 0 or loc_idx < outro_idx):
        loc = full[loc_idx + len('Localização'):loc_idx + len('Localização')+145]
        loc = re.split(r'Como chegar|Ver no Google Maps|Programa|O que',loc,maxsplit=1)[0]
        if 3 <= len(clean(loc)) <= 105:
            town = clean(loc).split(' · ')[0]
    start = 'Por confirmar'
    start_match = re.search(r'Início\s+Início de caminhada em\s+(.{5,100}?)(?:\.|\s+Faremos|\s+Piquenique|$)', prog, re.I)
    if start_match:
        start = clean(start_match[1])
    item = {
        'id': 'web-' + hashlib.sha256(f'{MONTANHAS_ORG}|{url}'.encode()).hexdigest()[:15],
        'title': title,
        'date': d.isoformat(),
        'time': time_str,
        'organizer': MONTANHAS_ORG,
        'url': url,
        'town': town,
        'start': start,
        'region': '',
        'area': '',
        'km': kms,
        'gain': gain,
        'duration': None,
        'price': price,
        'difficulty': None,
        'description': 'Ver programa e confirmação de detalhes no site do organizador.',
        'tag': 'Caminhada',
        'date_verified': 'official_detail',
    }
    if re.search(r'\bEsgotado\b', beginning, re.I):
        item['status'] = 'Esgotado'
    if not valid_new_event(item):
        return None
    return item


def collect_montanhas_dentro(source: dict) -> list[dict]:
    """Anúncios oficiais, com cada data obtida da sua própria página."""
    base = source['url']
    listing = fetch(base)
    if listing is None:
        logging.warning('Montanhas Dentro: consulta falhou, não reutilizar dados antigos')
        return []
    domain = urlparse(base).hostname.removeprefix('www.')
    found = {}
    for a in listing.find_all('a',href=True):
        link = canonical(base,a['href'])
        if not link:
            continue
        parsed = urlparse(link)
        if parsed.hostname.removeprefix('www.') == domain and re.fullmatch(r'/evento/\d+/[^/]+', parsed.path.rstrip('/')):
            found[link] = None
    result = []
    for link in list(found)[:90]:
        detail = fetch(link)
        if detail is None:
            continue
        e = parse_montanhas_detail(detail, link)
        if e is not None:
            result.append(e)
        time.sleep(.12)
    logging.info('Montanhas Dentro: %d caminhadas de 1 dia confirmadas em %d anúncios',len(result),len(found))
    return result


def collect_source(source: dict) -> list[dict]:
    if source["organizer"] == MONTANHAS_ORG:
        return collect_montanhas_dentro(source)
    domain = urlparse(source["url"]).hostname.removeprefix("www.")
    links: dict[str, tuple[str, str]] = {}
    for listing_url in [source["url"], *source.get("fallback", [])]:
        html = fetch(listing_url)
        if html is None:
            continue
        for anchor in html.find_all("a", href=True):
            url = canonical(listing_url, anchor["href"])
            if not url:
                continue
            parsed = urlparse(url)
            if parsed.hostname.removeprefix("www.") != domain:
                continue
            if not re.match(source["path"], parsed.path) or parsed.path.rstrip("/") == urlparse(source["url"]).path.rstrip("/"):
                continue
            block = smallest_context(anchor)
            title = title_from(anchor, block, source["organizer"])
            if len(title) < 7 or title.lower().startswith(("contact", "inscrev", "ler mais")):
                continue
            # Excluir links repetidos na mesma listagem.
            if url not in links or len(block) < len(links[url][1]):
                links[url] = (title, block)
        # A listagem principal pode conter apenas anúncios antigos ou links
        # de navegação. Continuar a consultar as alternativas documentadas;
        # os URLs repetidos continuam a ser eliminados pelo dicionário.
    logging.info("%s: %d possíveis anúncios", source["organizer"], len(links))
    result = []
    for url, (title, block) in list(links.items())[:75]:
        # Links genéricos na navegação destas páginas não são caminhadas.
        if source["organizer"] in {"Indoeu", "Caminhadas Smile"} and not date_from(block):
            continue
        event_date = date_from(block) or date_from(url)
        if event_date and (event_date < TODAY or event_date > LIMIT_DATE):
            continue
        if NON_WALK_TITLES.search(title):
            continue
        # Fontes recentes têm elementos fora de contexto: exigir pelo menos
        # terminologia de marcha no cartão ou título, salvo paginação datada.
        if source.get('required_keyword') and not (WALK_TERMS.search(title) or
                                                   WALK_TERMS.search(block[:300])):
            continue
        # Sem data na lista, consulta-se a página individual antes de aceitar.
        item = {
            "id": "web-" + hashlib.sha256(f"{source['organizer']}|{url}".encode()).hexdigest()[:15],
            "title": title, "date": event_date.isoformat() if event_date else "",
            "organizer": source["organizer"], "url": url,
            "town": "Por confirmar", "start": "Por confirmar", "region": "",
            "area": "", "time": "", "km": None, "gain": None,
            "duration": None, "price": None, "difficulty": None,
            "description": "Consultar os detalhes na página do organizador.",
            "tag": "Caminhada"
        }
        # Em cartões de Trekking Roots os números vêm na ordem "km", "m D+", localidade.
        if source["organizer"] == "Trekking Roots":
            matching = re.search(r"\b(\d{1,3}(?:[.,]\d{1,2})?)\s*km\s+(\d{2,4})\s*m\s+([^.;]{3,45}?)\s+(?:Prepara|Descubra|Venha|A\s|O\s|Os\s|As\s|\d+[.,]\d+\s*€)", block, re.I)
            if matching:
                item["km"] = float(matching[1].replace(",", "."))
                item["gain"] = int(matching[2])
                item["town"] = clean(matching[3])
        # Campos extraídos da listagem, se for um bloco isolado e inequívoco.
        if event_date and len(block) < 650:
            parse_meta(BeautifulSoup(f"<main>{block}</main>", "html.parser"), item)
        if source["organizer"] == "Trekkin":
            mloc = re.search(r"\blocal\s*:\s*([^.;]{4,90}?)(?=\s+(?:ver detalhes|descri[cç][aã]o|pre[cç]o|visualizar evento)|$)", block, re.I)
            if mloc and folded(clean(mloc[1])) != "local por definir":
                item["town"] = clean(mloc[1])
        detail = fetch(url)
        if detail is not None:
            enrich_jsonld(detail, item)
            parse_meta(detail, item)
            extra_source_meta(detail, item, source["organizer"])
            # Os cartões podem apresentar só «Muito Difícil 21/11/2026 21 km»
            # em vez do nome. Nestes casos, ler o H1 da ficha oficial.
            if (folded(item["title"]) in {"ver detalhes", "mais informacoes", "ver mais",
                                          "visualizar evento", "ver evento", "saber mais"}
                    or GENERIC_TITLE.match(item["title"])):
                scope = detail.find("main") or detail.find("article") or detail
                h = scope.find("h1") or detail.find("h1")
                if h:
                    official_title = clean(h.get_text(" ", strip=True))[:140]
                    if 12 <= len(official_title) <= 140 and not GENERIC_TITLE.match(official_title):
                        item["title"] = official_title
            # Datas sem ano em páginas dos organizadores: confirmar no conteúdo.
            if not item["date"]:
                main = detail.find("main") or detail.find("article") or detail
                dt = date_from(clean(main.get_text(" ", strip=True))[:1500])
                if dt:
                    item["date"] = dt.isoformat()
            meta = detail.find("meta", attrs={"name":"description"})
            if meta and meta.get("content"):
                item["description"] = clean(meta["content"])[:260]
        # Registar só eventos com data real explicitamente encontrada.
        if not item["date"]:
            continue
        dt = date.fromisoformat(item["date"])
        if not TODAY <= dt <= LIMIT_DATE:
            continue
        if not (7 <= len(item["title"]) <= 140):
            continue
        if "via ferrata" in folded(item["title"]):
            continue
        if item["duration"] is not None and item["duration"] > (168 if is_multiday_program(item) else 14):
            continue
        if item["km"] is not None and item["km"] > (250 if is_multiday_program(item) else 40):
            continue
        if not is_multiday_program(item) and header_date_conflicts(item):
            logging.warning("Data do título não coincide com a data recolhida: %s", url)
            continue
        if not valid_new_event(item):
            continue
        result.append(item)
        time.sleep(0.12)
    logging.info("%s: %d caminhadas futuras validadas", source["organizer"], len(result))
    return result


# TRILHARIO V39 — AGREGADOR TRILHOS CAMINHADAS DESACTIVADO
# TRILHARIO V40 — RB E SMILE COM FONTES OFICIAIS
def is_disallowed_aggregator_event(item):
    host = (urlparse(str(item.get('url') or '')).hostname or '').removeprefix('www.').lower()
    return (host == 'trilhosecaminhadas.pt' or
            str(item.get('source') or '').strip().casefold() == 'trilhos & caminhadas')


def main() -> int:
    aggregated: dict[str, dict] = {}
    published_ids = set()
    if OUT.exists():
        try:
            saved = json.loads(OUT.read_text(encoding="utf-8"))
            if saved.get("mode") != "demo":
                for item in saved.get("events", []):
                    if is_disallowed_aggregator_event(item):
                        logging.info('A excluir registo antigo da fonte desactivada: %s',item.get('url'))
                        continue
                    # Preservar apenas anúncios que já tinham sido confirmados
                    # na página oficial; não reintroduzir registos suspeitos.
                    if item.get("organizer") == MONTANHAS_ORG and item.get('date_verified') != 'official_detail':
                        continue
                    if not is_multiday_program(item) and header_date_conflicts(item):
                        logging.warning('Registo antigo com data contraditória eliminado: %s',item.get('url'))
                        continue
                    if item.get("id") and item.get("date", "") >= TODAY.isoformat():
                        aggregated[item["id"]] = item
                        published_ids.add(item["id"])
        except (ValueError, OSError, AttributeError) as exc:
            logging.warning("Catálogo anterior inválido: %s", exc)
    new_ids = []
    succeeded = 0
    sources_health = {}
    previous_health = (saved.get('sources_health',{}) if 'saved' in locals() and isinstance(saved,dict) else {})
    observation_day = datetime.now(timezone.utc).date().isoformat()
    for source in SOURCES:
        try:
            mode=source.get('mode')
            if mode in ('rb','smile'):
                from fontes_oficiais import collect_official
                found=collect_official(source,fetch=fetch,date_from=date_from,
                    new_event=new_event,valid_new_event=valid_new_event,
                    parse_meta=parse_meta,enrich_jsonld=enrich_jsonld,today=TODAY)
            elif mode=='ndesafios': found=collect_ndesafios(source)
            elif mode=='drenergies': found=collect_drenergies(source)
            elif mode=='sal': found=collect_sal(source)
            elif mode in ('programa','lousada'): found=collect_simple_program(source)
            else: found=collect_source(source)
            name=source['organizer']
            if found:
                succeeded += 1
                sources_health[name]={'state':'com_eventos','count':len(found),'last_success':observation_day}
            else:
                older=previous_health.get(name,{})
                sources_health[name]={'state':'sem_eventos_ou_indisponivel','count':0,
                    'last_success':older.get('last_success')}
                # Um [] pode significar 0 eventos ou erro: nunca declarar êxito.
                logging.warning('Fonte %s: sem resultados confirmados (ausência ou falha)',name)
            for item in found:
                if is_disallowed_aggregator_event(item):
                    continue
                if item.get('organizer') == MONTANHAS_ORG and item.get('date_verified') != 'official_detail':
                    # Não aceitar datas desta empresa reenviadas por agregadores.
                    continue
                if not is_multiday_program(item) and header_date_conflicts(item):
                    continue
                if item["id"] not in aggregated:
                    new_ids.append(item["id"])
                if found:
                    item['last_seen_at']=observation_day
                    item['source_name']=source['organizer']
                    if item.get('status_checked_at') and item.get('status')=='':
                        # A ausência de esgotado deve ser revalidada, não herdada.
                        item['status']=''
                aggregated[item["id"]] = item
        except Exception:
            sources_health[source['organizer']]={'state':'erro','count':0,
               'last_success':previous_health.get(source['organizer'],{}).get('last_success')}
            logging.exception("Erro ao processar %s", source["organizer"])
    if not aggregated:
        logging.warning("Não foram encontrados eventos válidos; não substituir o site por uma lista vazia.")
        return 0
    ordered = sorted(deduplicate(list(aggregated.values()), preferred_ids=published_ids), key=lambda x:(x["date"],x.get("time") or "99:99",x["title"]))
    # O relatório de cada fonte acompanha o catálogo, mesmo com recolha parcial.
    # Não declarar que uma agenda foi cancelada apenas por não ter sido lida.
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "sources_health":sources_health,"events": ordered}
    # Só reescrever quando os dados do catálogo mudam; evitar commits desnecessários.
    if OUT.exists():
        try:
            before = json.loads(OUT.read_text(encoding="utf-8"))
            if before.get("events") == ordered and before.get('sources_health') == sources_health:
                logging.info("Sem alterações no catálogo (%d eventos).", len(ordered))
                return 0
        except (ValueError, OSError):
            pass
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    logging.info("Catálogo escrito: %d eventos; novos: %d; fontes com resultados: %d/%d",len(ordered),len(new_ids),succeeded,len(SOURCES))
    if succeeded < len(SOURCES):logging.warning('RECOLHA PARCIAL: %d/%d fontes com eventos; consultar sources_health no JSON',succeeded,len(SOURCES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
