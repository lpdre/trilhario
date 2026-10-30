"""Variantes do mesmo ponto confirmado não criam duas sessões."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recolher
import normalizar_eventos as normalizar
from consolidar_catalogo import event_match
from identidade_eventos import sessoes_diferentes


class MonsantoIdentidade(unittest.TestCase):
    def setUp(self):
        # Fixture dos dois registos publicados; independente da agenda viva.
        self.official = {'id': 'web-3a53bbeacd76990',
            'title': 'Caminhando por Trilhos e Miradouros de Monsanto - 11kms',
            'date': '2026-11-01', 'time': '09:30', 'organizer': 'Caminhando.pt',
            'url': 'https://caminhando.pt/eventos/caminhando-por-trilhos-e-miradouros-de-monsanto-9kms',
            'start': 'R. A, 1500-640 Lisboa (Parque de Estacionamento - Campolide Este)',
            'lat': 38.73636111, 'lon': -9.17251667, 'verified': True, 'km': None,
            'alias_ids': ['caminhando-monsanto-20261101']}
        self.manual = {**self.official, 'id': 'caminhando-monsanto-20261101',
            'url': self.official['url'] + '/',
            'start': 'Parque de estacionamento, entrada do Parque Florestal de Monsanto, Campolide',
            'lat': 38.736361111111115, 'lon': -9.172516666666667, 'km': 11,
            'alias_ids': [self.official['id']]}

    def test_mesma_ficha_hora_e_gps_funde_variantes_do_local(self):
        self.assertFalse(sessoes_diferentes(self.official, self.manual))
        self.assertTrue(event_match(self.official, self.manual))
        for deduper in (recolher.deduplicate, normalizar.merge_exact_duplicates):
            for pair in ([self.official, self.manual], [self.manual, self.official]):
                with self.subTest(deduper=deduper.__name__, first=pair[0]['id']):
                    result = deduper(copy.deepcopy(pair), preferred_ids={self.official['id']})
                    self.assertEqual(len(result), 1)
                    self.assertEqual(result[0]['id'], self.official['id'])
                    self.assertEqual(result[0]['alias_ids'], [self.manual['id']])
                    self.assertEqual(result[0]['km'], 11)
                    self.assertEqual(deduper(copy.deepcopy(result)), result)

    def test_nao_funde_quando_falta_uma_confirmacao(self):
        for changes in ({'time': ''}, {'lat': None}, {'lon': None}, {'verified': False},
                        {'url': 'https://caminhando.pt/agenda'}, {'lat': 0, 'lon': 0},
                        {'lat': float('nan')}, {'lat': True}):
            with self.subTest(changes=changes):
                other = {**self.manual, **changes}
                self.assertTrue(sessoes_diferentes(self.official, other))
                self.assertFalse(event_match(self.official, other))

    def test_horas_fichas_e_edicoes_distintas_nao_se_fundem(self):
        for changes in ({'time': '15:00'}, {'date': '2026-11-02'},
                        {'organizer': 'Outro Clube'}, {'url': self.manual['url'] + '?sessao=2'},
                        {'url': 'https://caminhando.pt/eventos/outro'}):
            with self.subTest(changes=changes):
                other = {**self.manual, **changes}
                self.assertFalse(event_match(self.official, other))
                for deduper in (recolher.deduplicate, normalizar.merge_exact_duplicates):
                    self.assertEqual(len(deduper(copy.deepcopy([self.official, other]))), 2)

    def test_gps_confirmados_distintos_nao_se_fundem_mesmo_com_texto_igual(self):
        other = {**self.manual, 'start': self.official['start'], 'lat': 38.75}
        self.assertTrue(sessoes_diferentes(self.official, other))
        for deduper in (recolher.deduplicate, normalizar.merge_exact_duplicates):
            self.assertEqual(len(deduper(copy.deepcopy([self.official, other]))), 2)


if __name__ == '__main__':
    unittest.main()
