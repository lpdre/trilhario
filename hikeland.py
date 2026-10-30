"""Características explícitas do cabeçalho da ficha Hike Land, sem rede."""
import re


def parse_characteristics(soup):
    blocks = soup.select('header.page-header-portfolio .page-header-portfolio__content')
    if len(blocks) != 1:
        return {}
    fields = {}
    for paragraph in blocks[0].find_all('p'):
        text = ' '.join(paragraph.get_text(' ', strip=True).split())
        distance = re.fullmatch(r'DISTÂNCIA:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*km', text, re.I)
        gain = re.fullmatch(r'DESNÍVEL ACUMULADO:\s*D\+\s*(\d{1,4})\s*m', text, re.I)
        duration = re.fullmatch(r'DURAÇÃO:\s*(\d{1,3})\s*H\s*(\d{2})', text, re.I)
        price = re.fullmatch(r'PREÇO:\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*\|\s*Participante', text, re.I)
        if distance:
            value = float(distance[1].replace(',', '.'))
            if 0 < value <= 250:
                fields['km'] = value
        if gain and 0 <= int(gain[1]) <= 4500:
            fields['gain'] = int(gain[1])
        if duration and int(duration[2]) < 60:
            value = int(duration[1]) + int(duration[2]) / 60
            if 0 < value <= 168:
                fields['duration'] = value
        if price:
            value = float(price[1].replace(',', '.'))
            if 0 <= value <= 500:
                fields['price'] = value
    return fields
