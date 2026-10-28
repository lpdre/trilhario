"""Recuperação de campos pelo normalizador, com catálogo e rede isolados."""
import copy
import json
import sys
import unittest
from contextlib import ExitStack
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import normalizar_eventos as normalizar


class RecuperacaoEdicoes(unittest.TestCase):
    def setUp(self):
        day = date.today() + timedelta(days=20)
        self.current = {
            'id': 'id-publicado', 'title': 'Caminhada pela Serra',
            'organizer': 'Clube X', 'url': 'https://clube.pt/eventos/serra',
            'date': day.isoformat(),
        }
        self.fields = {
            'start': 'Posto de Turismo de Óbidos', 'town': 'Óbidos',
            'time': '09:00', 'endTime': '13:00', 'km': 12, 'gain': 300,
            'duration': 4, 'price': 15, 'lat': 39.35, 'lon': -9.15,
            'verified': True, 'gps_checked_at': date.today().isoformat(),
            'image': 'https://clube.pt/fotos/serra.jpg',
            'image_checked_at': date.today().isoformat(), 'status': 'Esgotado',
            'endDate': (day + timedelta(days=1)).isoformat(),
        }
        self.old = {**self.current, **self.fields}

    def normalize(self, current, old):
        with TemporaryDirectory() as folder, ExitStack() as stack:
            catalog = Path(folder) / 'eventos.json'
            catalog.write_text(json.dumps({'events': [current]}), encoding='utf-8')
            stack.enter_context(patch.object(normalizar, 'CATALOG', catalog))
            stack.enter_context(patch.object(normalizar, 'git_previous', return_value=[copy.deepcopy(old)]))
            stack.enter_context(patch('consolidar_catalogo.load_registry', return_value={
                'schema': 1, 'corrections': [], 'fallback_events': []}))
            stack.enter_context(patch.object(normalizar, 'enrich_official', return_value={}))
            stack.enter_context(patch.object(normalizar, 'repair_caminhando', return_value={}))
            stack.enter_context(patch.object(normalizar, 'PHOTO_VISITS_PER_RUN', 0))
            stack.enter_context(patch.object(normalizar, 'report'))
            stack.enter_context(patch('requests.get', side_effect=AssertionError('Rede não autorizada no teste')))
            self.assertEqual(normalizar.main(), 0)
            result = json.loads(catalog.read_text(encoding='utf-8'))['events']
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], current['id'])
        return result[0]

    def test_nova_data_nao_recupera_campos_de_outra_edicao(self):
        old = {**self.old, 'date': (date.today() - timedelta(days=1)).isoformat()}
        result = self.normalize(self.current, old)
        for field in self.fields:
            with self.subTest(field=field):
                self.assertFalse(normalizar.meaningful(result.get(field)))

    def test_mesma_edicao_recupera_campos_validos(self):
        result = self.normalize(self.current, self.old)
        for field, value in self.fields.items():
            with self.subTest(field=field):
                self.assertEqual(result.get(field), value)

    def test_outro_organizador_ou_url_nao_recupera(self):
        for change in ({'organizer': 'Outro Clube'},
                       {'url': 'https://clube.pt/eventos/outra-serra'},
                       {'url': 'https://clube.pt/eventos/serra?edicao=anterior'},
                       {'url': ''}, {'organizer': ''}):
            with self.subTest(change=change):
                result = self.normalize(self.current, {**self.old, **change})
                self.assertIsNone(result.get('price'))
                self.assertIsNone(result.get('lat'))

    def test_variantes_canonicas_da_mesma_ficha_recuperam(self):
        old = {**self.old, 'url': 'https://www.clube.pt/eventos/serra/',
               'organizer': 'CLUBE X'}
        self.assertEqual(self.normalize(self.current, old)['price'], 15)

    def test_dados_atuais_prevalecem_na_mesma_edicao(self):
        current = {**self.current, 'price': 20, 'km': 14, 'time': '10:00'}
        result = self.normalize(current, self.old)
        for field in ('price', 'km', 'time'):
            self.assertEqual(result[field], current[field])

    def test_nova_edicao_nao_invalida_gps_recolhido_agora(self):
        current = {**self.current, 'start': 'Entrada do Castelo de Óbidos',
                   'lat': 39.35, 'lon': -9.15, 'verified': True}
        old = {**self.old, 'date': (date.today() - timedelta(days=1)).isoformat()}
        result = self.normalize(current, old)
        for field in ('start', 'lat', 'lon', 'verified'):
            self.assertEqual(result.get(field), current[field])


if __name__ == '__main__':
    unittest.main()
