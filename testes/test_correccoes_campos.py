"""As exceções protegem campos concretos sem bloquear os restantes."""
import json
import sys
import unittest
from contextlib import ExitStack
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import normalizar_eventos as normalizar


class CorreccoesCampos(unittest.TestCase):
    def normalize(self, protected, fetched, organizer='Hike Land'):
        event = {'id': 'id-publicado', 'title': 'Caminhada pela Serra',
                 'date': (date.today() + timedelta(days=20)).isoformat(),
                 'organizer': organizer,
                 'url': ('https://maistrilhos.pt/caminhadas/serra' if organizer == 'Mais Trilhos'
                         else 'https://www.hikeland.pt/eventos/serra'),
                 'town': 'Óbidos', 'price': None, 'km': 9}
        registry = {'schema': 1, 'fallback_events': [], 'corrections': [{
            'organizer': organizer, 'slug': 'serra', 'date': event['date'], 'fields': protected}]}
        with TemporaryDirectory() as folder, ExitStack() as stack:
            path = Path(folder) / 'eventos.json'
            path.write_text(json.dumps({'events': [event]}), encoding='utf-8')
            stack.enter_context(patch.object(normalizar, 'CATALOG', path))
            stack.enter_context(patch.object(normalizar, 'git_previous', return_value=[]))
            stack.enter_context(patch('consolidar_catalogo.load_registry', return_value=registry))
            enrich = stack.enter_context(patch.object(normalizar, 'enrich_official', return_value=fetched))
            stack.enter_context(patch.object(normalizar, 'PHOTO_VISITS_PER_RUN', 0))
            stack.enter_context(patch.object(normalizar, 'report'))
            self.assertEqual(normalizar.main(), 0)
            result = json.loads(path.read_text(encoding='utf-8'))['events'][0]
        enrich.assert_called_once()
        self.assertEqual(result['id'], event['id'])
        for field, value in protected.items():
            self.assertEqual(result[field], value)
        return result

    def test_titulo_corrigido_nao_bloqueia_preco(self):
        result = self.normalize({'title': 'Nome oficial corrigido'},
                                {'title': 'Outro nome', 'price': 15})
        self.assertEqual(result['price'], 15)

    def test_distancia_nula_corrigida_nao_e_reposta_pela_fonte(self):
        result = self.normalize({'km': None}, {'km': 35, 'price': 15})
        self.assertEqual(result['price'], 15)

    def test_programa_multidiario_pode_recuperar_preco(self):
        result = self.normalize({'multiDay': True,
                                 'endDate': (date.today() + timedelta(days=22)).isoformat()},
                                {'multiDay': False, 'endDate': '2099-01-01', 'price': 150})
        self.assertEqual(result['price'], 150)

    def test_prioridade_mais_trilhos_respeita_local_corrigido(self):
        result = self.normalize({'start': 'Posto de Turismo de Óbidos'},
                                {'start': 'Outro ponto de encontro', 'price': 15}, 'Mais Trilhos')
        self.assertEqual(result['price'], 15)


if __name__ == '__main__':
    unittest.main()
