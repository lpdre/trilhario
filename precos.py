"""Normalização conservadora do texto de montantes publicados."""
import re


def normalizar_texto_precos(text: str) -> str:
    """Reunir unidades e cêntimos separados pelo HTML, junto da moeda.

    Exige separador decimal e duas casas explícitas: não cria cêntimos,
    não junta números soltos e não altera distâncias ou outros campos.
    """
    return re.sub(
        r'(?<![\d.,])(\d{1,3})\s*([.,])\s*(\d{2})(?=\s*(?:€|euros?\b))',
        r'\1\2\3', text, flags=re.I)
