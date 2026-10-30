"""Separar intervalos multidiários do local publicado pela Hiking Around."""
import json
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recolher


class HikingLocal(unittest.TestCase):
    url = 'https://www.hikingaround.pt/informa-es-do-evento-e-registro/serra-da-estrela-geopark-2-dias'
    place = 'Serra da Estrela, Estr. da Torre, 6215 Covilhã, Portugal'

    def parse(self, schedule, end_date=None, place=None):
        node = {'@type': 'Event', 'url': self.url, 'startDate': '2026-12-05T09:00:00'}
        if end_date:
            node['endDate'] = end_date
        html = ('<main><h1>Serra da Estrela Geopark (2 dias)</h1>'
                '<h2>Horário e local</h2><p>' + schedule + '</p><p>'
                + (self.place if place is None else place) + '</p>'
                '<h2>Sobre o evento</h2><p>Caminhada na serra.</p></main>'
                '<script type="application/ld+json">' + json.dumps(node) + '</script>')
        item = {'id': 'id-publicado', 'organizer': 'Hiking Around Adventures',
                'url': self.url, 'date': '2026-12-05', 'start': 'Por confirmar'}
        soup = BeautifulSoup(html, 'html.parser')
        recolher.enrich_jsonld(soup, item)
        recolher.parse_meta(soup, item)
        recolher.extra_source_meta(soup, item, item['organizer'])
        return item

    def test_intervalo_com_data_final_nao_contamina_local(self):
        # Formato do cabeçalho oficial da ficha Serra da Estrela, consultada em 28/10/2026.
        for separator in ('–', '-', '—'):
            with self.subTest(separator=separator):
                item = self.parse(f'05/12/2026, 09:00 {separator} 06/12/2026, 18:00',
                                  '2026-12-06T18:00:00')
                self.assertEqual(item['start'], self.place)
                self.assertEqual(item['date'], '2026-12-05')
                self.assertEqual(item['endDate'], '2026-12-06')
                self.assertEqual(item['time'], '09:00')
                self.assertTrue(item['multiDay'])
                self.assertIsNone(item.get('duration'))
                self.assertEqual(item['id'], 'id-publicado')

    def test_caminhada_de_um_dia_mantem_local_e_duracao(self):
        item = self.parse('05/12/2026, 09:00 – 13:00')
        self.assertEqual(item['start'], self.place)
        self.assertEqual(item['duration'], 4)
        self.assertEqual(item['time'], '09:00')

    def test_sem_hora_final_mantem_local_sem_inventar_duracao(self):
        item = self.parse('05/12/2026, 09:00')
        self.assertEqual(item['start'], self.place)
        self.assertIsNone(item.get('duration'))

    def test_sem_local_nao_publica_a_data_final_como_local(self):
        item = self.parse('05/12/2026, 09:00 – 06/12/2026, 18:00', place='')
        self.assertEqual(item['start'], 'Por confirmar')


if __name__ == '__main__':
    unittest.main()
