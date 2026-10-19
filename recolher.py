#!/usr/bin/env python3
"""Recolhe anúncios públicos de caminhadas; nunca inventa datas nem detalhes.

Este é um colector experimental, com fontes de HTML públicas. Os sites podem
mudar de estrutura, bloquear pedidos automáticos ou ter condições de acesso.
Executa duas vezes por semana através do GitHub Actions.
"""

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

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "eventos.json"
TODAY = date.today()
LIMIT_DATE = TODAY + timedelta(days=150)
# Os caminhos das páginas dos eventos não são iguais entre os organizadores.
# Se uma fonte não responder, as restantes continuam a ser consultadas.
SOURCES = [
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
    {"organizer": "Caminhadas Smile", "url": "https://www.caminhadassmile.pt/experiencia/",
     "path": r"^/[a-z0-9-]+/?$"},
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
    """Reconhece ISO e datas escritas por extenso em português.

    Datas sem ano usam o próximo acontecimento plausível, nunca um ano passado.
    """
    s = folded(text)
    m = re.search(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    # Em especial para Trekkin e outras agendas no formato DD/MM/AAAA.
    m = re.search(r"\b(0?[1-9]|[12]\d|3[01])[-/](0?[1-9]|1[0-2])[-/](20\d{2})\b", s)
    if m:
        try:
            return date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})\s+(?:de\s+)?(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\b(?:\s+(?:de\s+)?(20\d{2}))?", s)
    if not m:
        return None
    day, month = int(m[1]), MONTHS[m[2]]
    year = int(m[3]) if m[3] else (short_year or TODAY.year)
    try:
        candidate = date(year, month, day)
        if not m[3] and short_year is None and candidate < TODAY - timedelta(days=7):
            candidate = date(year + 1, month, day)
        return candidate
    except ValueError:
        return None


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
    url = urldefrag(urljoin(base, href))[0].rstrip("/")
    p = urlparse(url)
    if p.scheme not in ("https", "http"):
        return None
    return p._replace(query="").geturl()


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
    """Preenche campos opcionais quando aparecem explicitamente na página."""
    main = html.find("main") or html.find("article") or html
    text = clean(main.get_text(" ", strip=True))[:12000]
    # Não usar valores de uma listagem com muitos anúncios: só páginas de evento.
    if not event.get("km"):
        event["km"] = number(r"\b(\d{1,3}(?:[.,]\d{1,2})?)\s*km\b", text, 160)
    if not event.get("gain"):
        gain = number(r"(?:D\+|desn[ií]vel(?: positivo| acumulado)?|ascens[aã]o)\s*[:\-]?\s*(\d{2,4})\s*m", text, 4500)
        if gain is None:
            gain = number(r"\b(\d{2,4})\s*m\s*d\+(?=\s|$)", text + ' ', 4500)
        if gain is not None:
            event["gain"] = round(gain)
    if event.get("price") is None:
        price = number(r"\b(\d{1,3}(?:[.,]\d{1,2})?)\s*€", text, 500)
        if price is not None:
            event["price"] = price
    if not event.get("duration"):
        event["duration"] = number(r"(?:dura[cç][aã]o|tempo previsto|tempo estimado)\s*[:\-]?\s*(\d{1,2}(?:[.,]\d)?)\s*(?:h|horas?)", text, 24)
    if not event.get("time"):
        m = re.search(r"(?:in[ií]cio|partida|hora de encontro|concentra[cç][aã]o|data)\s*[:\-]?\s*(?:\d{1,2}/\d{1,2}/20\d{2}\s*,?\s*)?(\d{1,2})[:h](\d{2})", text, re.I)
        if m and int(m[1]) <= 23 and int(m[2]) <= 59:
            event["time"] = f"{int(m[1]):02d}:{m[2]}"
    if event.get("start") == "Por confirmar":
        m = re.search(r"(?:local de (?:partida|encontro)|ponto de encontro)\s*[:\-]\s*([^.;]{5,95})", text, re.I)
        if m:
            event["start"] = clean(m[1])
    if event.get("town") == "Por confirmar":
        m = re.search(r"(?:localiza[cç][aã]o|localidade|local)\s*[:\-]\s*([^.;,]{3,55})", text, re.I)
        if m:
            event["town"] = clean(m[1])
    if event.get("difficulty") is None:
        t = folded(text[:2200])
        for level, patterns in [(5,["muito dificil"]),(4,["dificil"]),(3,["exigente"]),(2,["moderada", "moderado"]),(1,["facil"] )]:
            if any(p in t for p in patterns):
                event["difficulty"] = level
                break


def enrich_jsonld(html: BeautifulSoup, event: dict) -> None:
    for tag in html.select('script[type="application/ld+json"]'):
        try:
            root = json.loads(tag.string or tag.get_text())
        except (ValueError, TypeError):
            continue
        queue = [root]
        while queue:
            node = queue.pop()
            if isinstance(node, list):
                queue.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            if "@graph" in node:
                queue.append(node["@graph"])
            typ = node.get("@type", [])
            if ("Event" in typ if isinstance(typ, list) else typ == "Event"):
                iso = node.get("startDate")
                if isinstance(iso, str):
                    dt = date_from(iso)
                    if dt:
                        event["date"] = dt.isoformat()
                    timem = re.search(r"T(\d{2}:\d{2})", iso)
                    if timem:
                        event["time"] = timem[1]
                loc = node.get("location", {})
                if isinstance(loc, list):
                    loc = next((x for x in loc if isinstance(x, dict)), {})
                if isinstance(loc, dict):
                    name = loc.get("name")
                    if isinstance(name, str) and name.strip():
                        event["start"] = clean(name)
                    address = loc.get("address", {})
                    if isinstance(address, dict):
                        town = address.get("addressLocality")
                        if isinstance(town, str) and town.strip():
                            event["town"] = clean(town)
                    geo = loc.get("geo", {})
                    if isinstance(geo, dict):
                        try:
                            lat, lon = float(geo["latitude"]), float(geo["longitude"])
                            if 36 < lat < 43 and -10 < lon < -6:
                                event.update(lat=lat,lon=lon,verified=True)
                        except (KeyError, ValueError, TypeError):
                            pass
                price = node.get("offers")
                if isinstance(price, dict) and price.get("price") is not None:
                    try:
                        event["price"] = float(price["price"])
                    except (TypeError, ValueError):
                        pass


def extra_source_meta(html: BeautifulSoup, item: dict, organizer: str) -> None:
    """Campos específicos de eventos de organizadores com estruturas próprias."""
    scope = html.find("main") or html.find("article") or html
    value = clean(scope.get_text(" ", strip=True))[:16000]
    if organizer == "Indoeu":
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
    elif organizer == "Basto Trekking":
        if item.get("price") is None:
            m = re.search(r"(?:inscri[cç][oõ]es|custo)\s*[:\-]?\s*(\d{1,3}(?:[,.]\d{1,2})?)\s*euros?", value, re.I)
            if m:
                item["price"] = float(m[1].replace(',', '.'))


def collect_source(source: dict) -> list[dict]:
    domain = urlparse(source["url"]).hostname.removeprefix("www.")
    links: dict[str, tuple[str, str]] = {}
    for listing_url in [source["url"], *source.get("fallback", [])]:
        html = fetch(listing_url)
        if html is None:
            continue
        for anchor in html.find_all("a", href=True):
            url = canonical(source["url"], anchor["href"])
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
        if links:
            break  # usar só a primeira listagem que forneça eventos
    logging.info("%s: %d possíveis anúncios", source["organizer"], len(links))
    result = []
    for url, (title, block) in list(links.items())[:75]:
        # Links genéricos na navegação destas páginas não são caminhadas.
        if source["organizer"] in {"Indoeu", "Caminhadas Smile"} and not date_from(block):
            continue
        if source["organizer"] == "Caminhadas Smile" and re.search(r"\b\d{1,2}\s*[-–]\s*\d{1,2}\s+(?:JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\b", block, re.I):
            continue  # excursões com vários dias
        event_date = date_from(block) or date_from(url)
        if event_date and (event_date < TODAY or event_date > LIMIT_DATE):
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
            # Usar o nome real do anúncio se o link apenas disser «Ver detalhes».
            if folded(item["title"]) in {"ver detalhes", "mais informacoes", "ver mais", "visualizar evento", "ver evento", "saber mais"}:
                h = detail.find("h1")
                if h:
                    item["title"] = clean(h.get_text(" ", strip=True))[:140]
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
        if source["organizer"] in {"Trekkin", "Montanhas Dentro"} and re.search(r"\b(?:dois dias|2 dias|3 dias|fim de semana|noites?)\b", folded(block)):
            continue  # não misturar viagens de vários dias com caminhadas de um dia
        if "via ferrata" in folded(item["title"]):
            continue
        if item["duration"] is not None and item["duration"] > 14:
            continue  # para já, apenas saídas de um dia
        if item["km"] is not None and item["km"] > 40:
            continue
        result.append(item)
        time.sleep(0.25)
    logging.info("%s: %d caminhadas futuras validadas", source["organizer"], len(result))
    return result


def main() -> int:
    aggregated: dict[str, dict] = {}
    if OUT.exists():
        try:
            saved = json.loads(OUT.read_text(encoding="utf-8"))
            if saved.get("mode") != "demo":
                for item in saved.get("events", []):
                    if item.get("id") and item.get("date", "") >= TODAY.isoformat():
                        aggregated[item["id"]] = item
        except (ValueError, OSError, AttributeError) as exc:
            logging.warning("Catálogo anterior inválido: %s", exc)
    new_ids = []
    succeeded = 0
    for source in SOURCES:
        try:
            found = collect_source(source)
            if found:
                succeeded += 1
            for item in found:
                if item["id"] not in aggregated:
                    new_ids.append(item["id"])
                aggregated[item["id"]] = item
        except Exception:
            logging.exception("Erro ao processar %s", source["organizer"])
    if not aggregated:
        logging.warning("Não foram encontrados eventos válidos; não substituir o site por uma lista vazia.")
        return 0
    ordered = sorted(aggregated.values(), key=lambda x:(x["date"],x.get("time") or "99:99",x["title"]))
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "events": ordered}
    # Só reescrever quando os dados do catálogo mudam; evitar commits desnecessários.
    if OUT.exists():
        try:
            before = json.loads(OUT.read_text(encoding="utf-8"))
            if before.get("events") == ordered:
                logging.info("Sem alterações no catálogo (%d eventos).", len(ordered))
                return 0
        except (ValueError, OSError):
            pass
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    logging.info("Catálogo escrito: %d eventos; novos: %d; fontes com resultados: %d/%d",len(ordered),len(new_ids),succeeded,len(SOURCES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
