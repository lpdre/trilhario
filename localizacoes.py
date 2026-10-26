"""Limpeza conservadora dos locais anunciados de partida (sem inventar moradas).

Os horários, coordenadas soltas e texto copiado de outras secções não são
endereços geocodificáveis. Quando só resta uma referência incompleta, manter
«Por confirmar», em vez de enviar texto enganador a um geocodificador.
"""
import re


def limpar_local(valor, organizador=''):
    s = ' '.join(str(valor or '').split()).strip(' .,:;–—-')
    if not s or s.casefold() in ('por confirmar', 'a confirmar', 'por definir', 'desconhecido'):
        return None
    # Algumas páginas começam com o horário completo e só depois dizem o local.
    s = re.sub(r'^Hor[aá]rio\s+IN[IÍ]CIO\s*:?\s*\d{1,2}:\d{2}\s*H?\s+FINAL\s*:?\s*\d{1,2}:\d{2}\s*H?\s*', '', s, flags=re.I)
    s = re.sub(r'^Ponto\s+de\s+encontro\s*[:\-–—]\s*', '', s, flags=re.I)
    # Informação logística que vem *depois* do local (não pertence à morada).
    s = re.split(r'\s+(?:Coordenadas(?:\s+GPS)?|GPS|Latitude|Longitude|Lat\s*:|Long\s*:|Hora\s+de\s+Fim|Hora\s+de\s+In[ií]cio|A\s+hora\s+de\s+fim)\b', s, maxsplit=1, flags=re.I)[0]
    s = re.split(r'\s+\d{1,2}(?:[:hH])[0-5]\d\s*[–—-]\s*(?:In[ií]cio|Fim|Hora)\b', s, maxsplit=1, flags=re.I)[0]
    s = re.split(r'\s+pelas\s+\d{1,2}\s*[hH:]\s*[0-5]\d\b', s, maxsplit=1, flags=re.I)[0]
    s = re.sub(r'\s*\(\s*(?:Localiza[cç][aã]o|Ver\s+no\s+Google\s+Maps)\b.*$', '', s, flags=re.I)
    s = re.sub(r'\s*\bVer\s+no\s+Google\s+Maps\b.*$', '', s, flags=re.I)
    # Finais cortados pela recolha não são moradas; conservar o topónimo útil.
    s = re.sub(r'\s+(?:Hora\s+de|Coo)\s*$', '', s, flags=re.I)
    s = re.sub(r'(?:\s*[,;–—-]\s*|\s+)(?:R\.?|Rua|Av\.?|Avenida|n\.?|n[º°]\.?)\s*$', '', s, flags=re.I)
    # Um parêntese cortado pela recolha não é um dado geográfico.
    if s.count('(') > s.count(')'):
        s = s[:s.rfind('(')]
    s = s.strip(' .,:;–—-')
    if not s or re.fullmatch(r'[\d\sº°\x27’′″”.,:NSEW+-]+', s, flags=re.I):
        return None
    if re.match(r'^(?:Hor[aá]rio|In[ií]cio\s*:|Final\s*:|Coordenadas|Latitude|Longitude)\b', s, re.I):
        return None
    if re.fullmatch(r'Parque de Merendas|Estacionamento', s, re.I):
        return None
    # Fragmentos que perderam a localidade (não têm suficiente informação
    # para apontar uma localização rodoviária).
    if organizador == 'Montanhas do Norte' and re.fullmatch(
        r'(?:Em frente ao caf[eé]|Junto ao cruzeiro|Parque de Merendas|'
        r'Pequeno largo em \w{1,2}|Estacionamento(?:\s+jun|\s+à\s+fa|\s+a\s+\d+))', s, re.I
    ):
        return None
    if re.search(r'(?:\b(?:jun|per|fa)\s*$|\.\.\.$|…$)', s, re.I) and len(s) < 40:
        return None
    return s if 3 <= len(s) <= 180 else None


def normalizar_local_evento(evento):
    """Corrige apenas os campos de local; conserva horas em time e os URLs."""
    alterados = 0
    org = str(evento.get('organizer') or '')
    for field in ('start', 'town'):
        valor = evento.get(field)
        limpo = limpar_local(valor, org) or 'Por confirmar'
        if limpo != valor:
            evento[field] = limpo
            alterados += 1
    return alterados
