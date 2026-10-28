"""Preços cujas unidades e casas decimais estão em elementos HTML separados."""
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recolher
import normalizar_eventos as normalizar


class PrecosFragmentados(unittest.TestCase):
    url = 'https://www.greentrekker.pt/agenda/caminhada-serra/'

    def page(self, amount, outside=False):
        booking = '<section>Faça Já A Sua Reserva ' + amount + ' Por Pessoa</section>'
        return '<main>Descrição da caminhada' + ('' if outside else booking) + '</main>' + (booking if outside else '')

    def test_recolha_e_normalizacao_leem_o_mesmo_preco(self):
        for amount, expected in (('<span>15</span><span>,00</span> €', 15),
                                 ('<span>15</span><span>,50</span> €', 15.5),
                                 ('<span>15</span><span>,</span><span>50</span><span>€</span>', 15.5),
                                 ('15\u00a0,50 €', 15.5), ('15 .50 €', 15.5), ('15,50€', 15.5)):
            with self.subTest(amount=amount):
                html = self.page(amount)
                soup = BeautifulSoup(html, 'html.parser')
                item = {'organizer': 'GreenTrekker', 'price': None}
                recolher.parse_meta(soup, item)
                self.assertEqual(item['price'], expected)
                recolher.extra_source_meta(soup, item, 'GreenTrekker')
                self.assertEqual(item['price'], expected)
                fields = normalizar.parse_official_listing('GreenTrekker', html, self.url)
                self.assertEqual(fields.get('price'), expected)

    def test_preco_de_reserva_fora_do_main(self):
        html = self.page('<span>15</span><span>,50</span> €', outside=True)
        item = {'organizer': 'GreenTrekker', 'price': None}
        soup = BeautifulSoup(html, 'html.parser')
        recolher.parse_meta(soup, item)
        self.assertIsNone(item['price'])
        recolher.extra_source_meta(soup, item, 'GreenTrekker')
        self.assertEqual(item['price'], 15.5)

    def test_tarifa_de_adulto_nao_e_substituida_pela_de_crianca(self):
        soup = BeautifulSoup('<main>Preço participante: <span>15</span><span>,50</span> € '
                             'Crianças: <span>5</span><span>,00</span> €</main>', 'html.parser')
        item = {'organizer': 'GreenTrekker', 'price': None}
        recolher.parse_meta(soup, item)
        self.assertEqual(item['price'], 15.5)

    def test_sem_preco_publicado_permanece_desconhecido(self):
        html = self.page('Consulte o organizador')
        soup = BeautifulSoup(html, 'html.parser')
        item = {'organizer': 'GreenTrekker', 'price': None}
        recolher.parse_meta(soup, item)
        recolher.extra_source_meta(soup, item, 'GreenTrekker')
        self.assertIsNone(item['price'])
        self.assertNotIn('price', normalizar.parse_official_listing('GreenTrekker', html, self.url))

    def test_preco_existente_nao_e_substituido(self):
        soup = BeautifulSoup(self.page('15 ,50 €'), 'html.parser')
        item = {'organizer': 'GreenTrekker', 'price': 20}
        recolher.parse_meta(soup, item)
        recolher.extra_source_meta(soup, item, 'GreenTrekker')
        self.assertEqual(item['price'], 20)

    def test_parcela_decimal_isolada_nao_e_um_preco(self):
        for amount in (',50 €', '.50 €', '15,500 €'):
            with self.subTest(amount=amount):
                html = self.page(amount)
                soup = BeautifulSoup(html, 'html.parser')
                item = {'organizer': 'GreenTrekker', 'price': None}
                recolher.parse_meta(soup, item)
                recolher.extra_source_meta(soup, item, 'GreenTrekker')
                self.assertIsNone(item['price'])
                self.assertNotIn('price', normalizar.parse_official_listing('GreenTrekker', html, self.url))


if __name__ == '__main__':
    unittest.main()
