#!/usr/bin/env python3
"""Trilhário — Fase 2: aplica correcções auditáveis ao recolher.py existente.

Executar na raiz do repositório, após colocar este script na mesma pasta.
Não faz downloads nem altera outros ficheiros. Cria recolher.py.bak antes de gravar.
"""
from __future__ import annotations
import ast
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
PATH=ROOT/'recolher.py'
MARKER='# TRILHARIO FASE 2 — EXTRACCAO E CONTROLO DE FONTES'


def replace_func(src,name,new_code):
    tree=ast.parse(src)
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    if len(nodes)!=1:
        raise ValueError(f'Esperada exactamente uma função {name}; encontradas {len(nodes)}')
    n=nodes[0]; lines=src.splitlines(keepends=True)
    return ''.join(lines[:n.lineno-1])+new_code.rstrip()+'\n\n'+''.join(lines[n.end_lineno:])

NEW_DATE=r'''def date_from(text: str, *, short_year: int | None = None) -> date | None:
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
'''

NEW_PARSE=r'''def parse_meta(html: BeautifulSoup, event: dict) -> None:
    """Páginas individuais: escolher apenas números com contexto inequívoco."""
    main=html.find('main') or html.find('article') or html
    text=clean(main.get_text(' ',strip=True))[:12000]
    if event.get('km') is None:
        event['km']=number(r'\b(\d{1,3}(?:[.,]\d{1,2})?)\s*km\b',text,160)
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
            elif re.search(r'\b(?:gratuit[oa]|participa[cç][aã]o\s+gratuita)\b',text,re.I):
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
'''

NEW_LD=r'''def enrich_jsonld(html: BeautifulSoup, event: dict) -> None:
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
'''

NEW_DEDUP=r'''def deduplicate(events: list[dict]) -> list[dict]:
    """Mesmo URL não implica o mesmo evento; título e data são obrigatórios."""
    from difflib import SequenceMatcher
    grouped={}
    for item in sorted(events,key=lambda e:(bool(e.get('source')=='Trilhos & Caminhadas'),-sum(e.get(k) is not None for k in ('km','gain','price','time','duration')))):
        day,org,title=similarity_key(item)
        if not day or not org or not title:continue
        group=grouped.setdefault((day,org),[])
        def duplicates(previous):
            old_title=similarity_key(previous)[2]
            if old_title==title:return True
            # Títulos diferentes não são duplicados apenas por partilharem página.
            a,b=set(old_title.split()),set(title.split())
            if not a or not b:return False
            overlap=len(a&b)/max(len(a),len(b))
            return overlap>=0.86 and SequenceMatcher(None,old_title,title).ratio()>=0.94
        prev=next((x for x in group if duplicates(x)),None)
        if prev is None:group.append(item);continue
        aliases=set(prev.get('alias_ids') or [])|set(item.get('alias_ids') or [])
        if item.get('id')!=prev.get('id'):aliases.add(item.get('id'))
        aliases.discard(prev.get('id'))
        if aliases:prev['alias_ids']=sorted(x for x in aliases if x)
        for field in ('km','gain','price','duration','time','town','start','image'):
            if prev.get(field) in (None,'','Por confirmar') and item.get(field) not in (None,'','Por confirmar'):
                prev[field]=item[field]
    return [item for group in grouped.values() for item in group]
'''

# Inserção cirúrgica no main, conservando os extractores/formatos existentes.
def patch_main(src):
    tree=ast.parse(src)
    n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    lines=src.splitlines(keepends=True)
    block=''.join(lines[n.lineno-1:n.end_lineno])
    old='''                    if item.get("organizer") == MONTANHAS_ORG:
                        # Recatalogar EXCLUSIVAMENTE através da página oficial;
                        # entradas antigas contêm datas erradas e tipo mal identificado.
                        continue
'''
    if old not in block:raise ValueError('main: protecção antiga de Montanhas Dentro não encontrada')
    block=block.replace(old,'''                    # Preservar apenas anúncios que já tinham sido confirmados
                    # na página oficial; não reintroduzir registos suspeitos.
                    if item.get("organizer") == MONTANHAS_ORG and item.get('date_verified') != 'official_detail':
                        continue
''')
    block=block.replace('''    new_ids = []
    succeeded = 0
''','''    new_ids = []
    succeeded = 0
    sources_health = {}
    previous_health = (saved.get('sources_health',{}) if 'saved' in locals() and isinstance(saved,dict) else {})
    observation_day = datetime.now(timezone.utc).date().isoformat()
''')
    block=block.replace('''            if found:
                succeeded += 1
''','''            name=source['organizer']
            if found:
                succeeded += 1
                sources_health[name]={'state':'com_eventos','count':len(found),'last_success':observation_day}
            else:
                older=previous_health.get(name,{})
                sources_health[name]={'state':'sem_eventos_ou_indisponivel','count':0,
                    'last_success':older.get('last_success')}
                # Um [] pode significar 0 eventos ou erro: nunca declarar êxito.
                logging.warning('Fonte %s: sem resultados confirmados (ausência ou falha)',name)
''')
    block=block.replace('''                aggregated[item["id"]] = item
        except Exception:
            logging.exception("Erro ao processar %s", source["organizer"])
''','''                if found:
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
''')
    block=block.replace('''    payload = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "events": ordered}''','''    # O relatório de cada fonte acompanha o catálogo, mesmo com recolha parcial.
    # Não declarar que uma agenda foi cancelada apenas por não ter sido lida.
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "sources_health":sources_health,"events": ordered}''')
    block=block.replace('''            if before.get("events") == ordered:
''','''            if before.get("events") == ordered and before.get('sources_health') == sources_health:
''')
    block=block.replace('''    logging.info("Catálogo escrito: %d eventos; novos: %d; fontes com resultados: %d/%d",len(ordered),len(new_ids),succeeded,len(SOURCES))''','''    logging.info("Catálogo escrito: %d eventos; novos: %d; fontes com resultados: %d/%d",len(ordered),len(new_ids),succeeded,len(SOURCES))
    if succeeded < len(SOURCES):logging.warning('RECOLHA PARCIAL: %d/%d fontes com eventos; consultar sources_health no JSON',succeeded,len(SOURCES))''')
    for required in ('sources_health = {}','observation_day =','RECOLHA PARCIAL'):
        if required not in block:raise ValueError('main: inserção obrigatória falhou: '+required)
    return ''.join(lines[:n.lineno-1])+block.rstrip()+'\n'+''.join(lines[n.end_lineno:])


AGGREGATOR_DISABLED_MARKER = '# TRILHARIO V39 — AGREGADOR TRILHOS CAMINHADAS DESACTIVADO'

def disable_aggregator(src):
    """Desactivar fonte e descartar entradas herdadas. Aplicação idempotente."""
    if AGGREGATOR_DISABLED_MARKER in src:
        return src
    # Tem de existir exactamente uma fonte configurada; falhar de forma explícita
    # se o colector for modificado no futuro, em vez de publicar uma alteração parcial.
    source_line = '    {"organizer": "Trilhos & Caminhadas", "url": "https://www.trilhosecaminhadas.pt/percursos/calendario.php", "mode": "agregador"},\n'
    if src.count(source_line) != 1:
        raise ValueError('Fonte do agregador não encontrada no catálogo SOURCES')
    src = src.replace(source_line, '    # Agregador Trilhos & Caminhadas desactivado; utilizar apenas as fontes oficiais.\n')
    helper = '''def is_disallowed_aggregator_event(item):
    host = (urlparse(str(item.get('url') or '')).hostname or '').removeprefix('www.').lower()
    return (host == 'trilhosecaminhadas.pt' or
            str(item.get('source') or '').strip().casefold() == 'trilhos & caminhadas')


'''
    anchor='def main() -> int:\n'
    if src.count(anchor)!=1:raise ValueError('Função main do colector não encontrada')
    src=src.replace(anchor,AGGREGATOR_DISABLED_MARKER+'\n'+helper+anchor)
    # Tanto ao reler o JSON como ao importar novos anúncios, impedir reentrada.
    old="if excluded_organizer(item.get('organizer')):"
    if src.count(old)!=2:raise ValueError('Guardas de eventos no main foram alteradas')
    src=src.replace(old,"if is_disallowed_aggregator_event(item) or excluded_organizer(item.get('organizer')):")
    ast.parse(src)
    return src



OFFICIAL_SOURCES_MARKER = '# TRILHARIO V40 — RB E SMILE COM FONTES OFICIAIS'


def enable_official_sources(src):
    # Idempotente: recolha directa; não volta a abrir o agregador.
    if OFFICIAL_SOURCES_MARKER in src:
        return src
    import ast
    # A v39 deve ter eliminado a fonte do agregador primeiro.
    anchor='    # Agregador Trilhos & Caminhadas desactivado; utilizar apenas as fontes oficiais.\n'
    if src.count(anchor)!=1:
        raise ValueError('v40 exige exclusão v39 do agregador já aplicada')
    sources='''    {"organizer": "RB Hiking & Trekking", "url": "https://barbosa-trekking.pt/", "mode": "rb"},
    {"organizer": "Caminhadas Smile", "url": "https://www.caminhadassmile.pt/", "mode": "smile"},
'''
    src=src.replace(anchor,sources+anchor,1)
    # Os anúncios Smile que vinham do agregador já são recusados por URL/source.
    # As novas páginas oficiais da Smile não devem ser rejeitadas pelo nome.
    src=replace_func(src,'excluded_organizer','''def excluded_organizer(name: str) -> bool:
    # A exclusão antiga da Smile era por má qualidade dos dados do agregador;
    # a v40 admite apenas anúncios recolhidos directamente no site oficial.
    return False
''')
    tree=ast.parse(src)
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    lines=src.splitlines(keepends=True)
    block=''.join(lines[main.lineno-1:main.end_lineno])
    call="            if mode=='ndesafios': found=collect_ndesafios(source)\n"
    if block.count(call)!=1:raise ValueError('Ramo de fontes do colector não encontrado')
    branch='''            if mode in ('rb','smile'):
                from fontes_oficiais import collect_official
                found=collect_official(source,fetch=fetch,date_from=date_from,
                    new_event=new_event,valid_new_event=valid_new_event,
                    parse_meta=parse_meta,enrich_jsonld=enrich_jsonld,today=TODAY)
            elif mode=='ndesafios': found=collect_ndesafios(source)
'''
    block=block.replace(call,branch,1)
    src=''.join(lines[:main.lineno-1])+block+''.join(lines[main.end_lineno:])
    # Guardar versão no código para execução repetida sem duplicar fontes.
    needle='def is_disallowed_aggregator_event(item):\n'
    if src.count(needle)!=1:raise ValueError('Guarda do agregador ausente')
    src=src.replace(needle,OFFICIAL_SOURCES_MARKER+'\n'+needle,1)
    ast.parse(src)
    return src


def apply(src):
    if MARKER not in src:
        for name,replacement in [('date_from',NEW_DATE),('parse_meta',NEW_PARSE),('enrich_jsonld',NEW_LD),('deduplicate',NEW_DEDUP)]:
            src=replace_func(src,name,replacement)
        src=patch_main(src)
        pos=src.index('from __future__ import annotations')
        src=src[:pos]+MARKER+'\n'+src[pos:]
    src=disable_aggregator(src)
    src=enable_official_sources(src)
    ast.parse(src)
    return src


def main():
    if not PATH.exists():raise SystemExit('ERRO: recolher.py não existe nesta pasta.')
    original=PATH.read_text(encoding='utf-8')
    modified=apply(original)
    if modified==original:
        print('Fases 2/v39 já aplicadas; nenhum ficheiro alterado.')
        return 0
    backup=ROOT/'recolher.py.bak'
    if not backup.exists():backup.write_text(original,encoding='utf-8')
    PATH.write_text(modified,encoding='utf-8')
    print('recolher.py actualizado com êxito. Cópia anterior: recolher.py.bak')
    return 0

if __name__=='__main__':sys.exit(main())
