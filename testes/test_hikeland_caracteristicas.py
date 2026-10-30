"""Características oficiais Hike Land fora do primeiro main da página."""
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recolher
import normalizar_eventos as normalizar


class HikelandCaracteristicas(unittest.TestCase):
    url = 'https://www.hikeland.pt/eventos/pelo-trilho-secular-dos-moleiros-e-aldeias-de-xisto-da-lousa'

    def page(self, fields):
        # Estrutura e valores do cabeçalho oficial consultado em 28/10/2026.
        return ('<main><p>Descrição do percurso</p></main>'
                '<header class="page-header-portfolio"><div class="page-header-portfolio__content">'
                '<h2 class="page-header-portfolio__title">Trilho dos Moleiros</h2>'
                '<div>O nível de dificuldade pode incluir D+1000m e 30 km.</div>'
                + fields + '</div></header>'
                '<aside><p>DURAÇÃO: 12H00</p><p>DISTÂNCIA: 40km</p>'
                '<p>DESNÍVEL ACUMULADO: D+1200m</p></aside>')

    def test_recolha_e_normalizacao_extraem_o_bloco_oficial(self):
        html = self.page('<p><i></i>DURAÇÃO: 7H00</p><p>DISTÂNCIA: 14km</p>'
                         '<p>DESNÍVEL ACUMULADO: D+700m</p><p>PREÇO: 15€ | Participante</p>')
        item = {'organizer': 'Hike Land', 'km': None, 'gain': None, 'duration': None, 'price': None}
        soup = BeautifulSoup(html, 'html.parser')
        recolher.parse_meta(soup, item)
        recolher.extra_source_meta(soup, item, 'Hike Land')
        found = normalizar.parse_official_listing('Hike Land', html, self.url)
        for field, value in {'km': 14, 'gain': 700, 'duration': 7, 'price': 15}.items():
            self.assertEqual(item[field], value)
            self.assertEqual(found.get(field), value)

    def test_decimal_e_meia_hora_sem_inventar_campos_ausentes(self):
        html = self.page('<p>DURAÇÃO: 3H30</p><p>DISTÂNCIA: 11,5km</p>')
        found = normalizar.parse_official_listing('Hike Land', html, self.url)
        self.assertEqual(found.get('duration'), 3.5)
        self.assertEqual(found.get('km'), 11.5)
        self.assertNotIn('gain', found)
        self.assertNotIn('price', found)

    def test_ignora_valores_invalidos_e_numeros_da_descricao(self):
        html = self.page('<p>DURAÇÃO: 3H99</p><p>DISTÂNCIA: 0km</p>'
                         '<p>DESNÍVEL ACUMULADO: D+99999m</p>')
        self.assertEqual(normalizar.parse_official_listing('Hike Land', html, self.url), {})

    def test_recolha_preserva_dados_validos_ja_presentes(self):
        html = self.page('<p>DURAÇÃO: 7H00</p><p>DISTÂNCIA: 14km</p>'
                         '<p>DESNÍVEL ACUMULADO: D+700m</p><p>PREÇO: 15€ | Participante</p>')
        item = {'organizer': 'Hike Land', 'km': 13, 'gain': 600, 'duration': 6, 'price': 12}
        recolher.extra_source_meta(BeautifulSoup(html, 'html.parser'), item, 'Hike Land')
        self.assertEqual({k: item[k] for k in ('km', 'gain', 'duration', 'price')},
                         {'km': 13, 'gain': 600, 'duration': 6, 'price': 12})

    def test_sem_bloco_nao_usa_caracteristicas_de_outros_anuncios(self):
        html = '<main>Descrição</main><aside><p>DURAÇÃO: 7H00</p><p>DISTÂNCIA: 14km</p></aside>'
        self.assertEqual(normalizar.parse_official_listing('Hike Land', html, self.url), {})


if __name__ == '__main__':
    unittest.main()
