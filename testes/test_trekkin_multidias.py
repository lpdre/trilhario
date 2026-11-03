"""Regressão: programas multidiários da Trekkin e locais oficiais."""
import unittest
from bs4 import BeautifulSoup
from qualidade_anuncios import is_multiday_program
from recolher import extra_source_meta

class TrekkinMultidias(unittest.TestCase):
    def test_castro_laboreiro_dois_dias_publicados(self):
        event = {
            'date': '2026-11-07',
            'title': 'Castro Laboreiro Micológico',
            'url': 'https://www.trekkin.pt/evento/castro-laboreiro-micologico/-P294wZOdE3jxr_XSmeu',
        }
        page = BeautifulSoup(
            '<main>Local: Picotim, Melgaço Preço: 50,00 € '
            'Dias do evento Dia 1 — 2026-11-07 Hora: 08:00 '
            'Dia 2 — 2026-11-08 Hora: 08:00</main>', 'html.parser')
        extra_source_meta(page, event, 'Trekkin')
        self.assertEqual(event['start'], 'Picotim, Melgaço')
        self.assertTrue(event['multiDay'])
        self.assertEqual(event['endDate'], '2026-11-08')
        self.assertTrue(is_multiday_program(event))

    def test_caminhos_de_outono_confirmado_na_ficha(self):
        event = {
            'date': '2026-11-21',
            'title': 'Caminhos de Outono',
            'url': 'https://www.trekkin.pt/evento/caminhos-de-outono/-P3CRBifIIOCxstnKezb',
        }
        page = BeautifulSoup(
            '<main>Dias do evento Dia 1 — 2026-11-21 '
            'Dia 2 — 2026-11-22</main>', 'html.parser')
        extra_source_meta(page, event, 'Trekkin')
        self.assertTrue(event['multiDay'])
        self.assertEqual(event['endDate'], '2026-11-22')

    def test_uma_saida_nao_se_torna_multidias(self):
        event = {
            'date': '2026-11-15',
            'title': 'Subida ao Alto da Pedrada',
            'url': 'https://www.trekkin.pt/evento/subida-ao-alto-da-pedrada-o-cume-da-serra-do-soajo/-P494gCXsWGtH4ksqOuo',
        }
        page = BeautifulSoup(
            '<main>Dias do evento Dia 1 — 2026-11-15</main>', 'html.parser')
        extra_source_meta(page, event, 'Trekkin')
        self.assertNotIn('multiDay', event)
        self.assertFalse(is_multiday_program(event))

    def test_urls_confirmados_quando_ficha_indisponivel(self):
        self.assertTrue(is_multiday_program({
            'date': '2026-11-07',
            'title': 'Castro Laboreiro Micológico',
            'url': 'https://www.trekkin.pt/evento/castro-laboreiro-micologico/-P294wZOdE3jxr_XSmeu'
        }))

if __name__ == '__main__':
    unittest.main()
