"""Falhas temporárias de fotografia não são uma ausência confirmada."""
import json
import sys
import unittest
from contextlib import ExitStack
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import normalizar_eventos as normalizar


class FotografiasRetentativa(unittest.TestCase):
    photo = 'https://www.hikeland.pt/fotos/serra.jpg'

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        folder = self.stack.enter_context(TemporaryDirectory())
        self.path = Path(folder) / 'eventos.json'
        self.event = {'id': 'id-publicado', 'title': 'Caminhada pela Serra',
                      'date': (date.today() + timedelta(days=10)).isoformat(),
                      'organizer': 'Hike Land', 'url': 'https://www.hikeland.pt/eventos/serra',
                      'start': 'Posto de Turismo de Óbidos', 'town': 'Óbidos'}
        self.save([self.event])
        for name, value in (('CATALOG', self.path), ('PHOTO_VISITS_PER_RUN', 2)):
            self.stack.enter_context(patch.object(normalizar, name, value))
        self.stack.enter_context(patch.object(normalizar, 'git_previous', return_value=[]))
        self.stack.enter_context(patch('consolidar_catalogo.load_registry', return_value={
            'schema': 1, 'corrections': [], 'fallback_events': []}))
        self.stack.enter_context(patch.object(normalizar, 'enrich_official', return_value={}))
        self.stack.enter_context(patch.object(normalizar, 'report'))

    def save(self, events):
        self.path.write_text(json.dumps({'events': events}), encoding='utf-8')

    def events(self):
        return json.loads(self.path.read_text(encoding='utf-8'))['events']

    def response(self, html):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {'content-type': 'text/html'}
        response.encoding = 'utf-8'
        response.url = self.event['url']
        response.iter_content.return_value = [html.encode('utf-8')]
        return response

    def test_timeout_permite_recuperar_foto_na_execucao_seguinte(self):
        with patch('requests.get', side_effect=requests.Timeout('temporário')) as get:
            self.assertEqual(normalizar.main(), 0)
            get.assert_called_once()
        self.assertNotIn('image_checked_at', self.events()[0])
        response = self.response(f'<meta property="og:image" content="{self.photo}">')
        with patch('requests.get', return_value=response) as get:
            self.assertEqual(normalizar.main(), 0)
            get.assert_called_once()
        event = self.events()[0]
        self.assertEqual(event['image'], self.photo)
        self.assertEqual(event['image_checked_at'], date.today().isoformat())
        self.assertEqual(event['id'], 'id-publicado')

    def test_sucesso_sem_foto_mantem_intervalo_longo(self):
        with patch('requests.get', return_value=self.response('<main>Sem fotografia</main>')) as get:
            self.assertEqual(normalizar.main(), 0)
            self.assertEqual(normalizar.main(), 0)
            get.assert_called_once()
        self.assertEqual(self.events()[0]['image_checked_at'], date.today().isoformat())
        self.assertNotIn('image', self.events()[0])

    def test_erros_http_e_stream_nao_marcam_ausencia(self):
        for stage in ('raise_for_status', 'iter_content'):
            with self.subTest(stage=stage):
                self.save([self.event])
                response = self.response('')
                getattr(response, stage).side_effect = requests.RequestException('temporário')
                with patch('requests.get', return_value=response):
                    self.assertEqual(normalizar.main(), 0)
                self.assertNotIn('image_checked_at', self.events()[0])

    def test_falhas_respeitam_limite_de_visitas(self):
        self.save([{**self.event, 'id': f'evento-{i}', 'title': f'Caminhada pela Serra {i}',
                    'url': self.event['url'] + f'-{i}'} for i in range(4)])
        with patch('requests.get', side_effect=requests.Timeout('temporário')) as get:
            self.assertEqual(normalizar.main(), 0)
            self.assertEqual(get.call_count, 2)
        self.assertTrue(all('image_checked_at' not in event for event in self.events()))

    def test_fotografia_valida_guardada_nao_e_consultada_nem_apagada(self):
        self.save([{**self.event, 'image': self.photo}])
        with patch('requests.get', side_effect=requests.Timeout('temporário')) as get:
            self.assertEqual(normalizar.main(), 0)
            get.assert_not_called()
        self.assertEqual(self.events()[0]['image'], self.photo)


if __name__ == '__main__':
    unittest.main()
