"""Regressões da auditoria 5.4: distância anunciada e preço confirmado."""
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import recolher
import normalizar_eventos as normalizar
from consolidar_catalogo import load_registry


class QualidadeCampos(unittest.TestCase):
    def test_caminhando_nao_aproveita_distancia_geografica(self):
        html = BeautifulSoup(
            "<main><p>A cordilheira da Arrábida apresenta um comprimento "
            "de cerca de 35 km e uma largura média de 6 km.</p>"
            "<p>Características do Percurso: 0 km's Distância</p></main>",
            "html.parser")
        event = {"organizer": "Caminhando.pt", "km": None}
        recolher.parse_meta(html, event)
        self.assertIsNone(event["km"])

    def test_caminhando_aceita_apenas_distancia_rotulada(self):
        html = BeautifulSoup(
            "<main><p>A serra tem 35 km.</p>"
            "<p>Distância do percurso: 11,5 km</p></main>", "html.parser")
        event = {"organizer": "Caminhando.pt", "km": None}
        recolher.parse_meta(html, event)
        self.assertEqual(event["km"], 11.5)

    def test_outras_fontes_mantem_extraccao_generica(self):
        html = BeautifulSoup("<main>Trilho circular de 13 km</main>", "html.parser")
        event = {"organizer": "Outro organizador", "km": None}
        recolher.parse_meta(html, event)
        self.assertEqual(event["km"], 13)

    def test_caminhando_distancia_com_rotulo_depois_do_valor(self):
        for value, expected in (("12 km's", 12), ("11,5 km's", 11.5),
                                ("11.5 km", 11.5), ("12 km’s", 12)):
            with self.subTest(value=value):
                html = BeautifulSoup(
                    "<main><p>A serra tem 35 km.</p>"
                    "<section><h2>Características do Percurso</h2>"
                    f"<div><span>{value}</span><span>Distância</span></div>"
                    "</section></main>", "html.parser")
                event = {"organizer": "Caminhando.pt", "km": None}
                recolher.parse_meta(html, event)
                self.assertEqual(event["km"], expected)

    def test_caminhando_distancia_invalida_nao_aproveita_fragmentos(self):
        for value in ("0", "0,0", "-12", "161", "1000", "1000,5"):
            with self.subTest(value=value):
                html = BeautifulSoup(
                    f"<main><p>A serra tem 35 km.</p><div>{value} km's Distância</div></main>",
                    "html.parser")
                event = {"organizer": "Caminhando.pt", "km": None}
                recolher.parse_meta(html, event)
                self.assertIsNone(event["km"])

    def test_caminhando_distancia_existente_preservada(self):
        html = BeautifulSoup("<main>12 km's Distância</main>", "html.parser")
        event = {"organizer": "Caminhando.pt", "km": 14}
        recolher.parse_meta(html, event)
        self.assertEqual(event["km"], 14)

    def test_preco_hikeland_ancorado_no_valor_por_participante(self):
        html = (
            "<main><p>Preço: 15€ | Participante</p>"
            "<p>O Preço Inclui: guia e seguro</p>"
            "<p>O Preço Não Inclui: transporte</p></main>"
        )
        fields = normalizar.parse_official_listing(
            "Hike Land", html, "https://www.hikeland.pt/eventos/teste/")
        self.assertEqual(fields.get("price"), 15)

    def test_preco_hikeland_sem_valor_publicado_fica_desconhecido(self):
        fields = normalizar.parse_official_listing(
            "Hike Land", "<main>O Preço Inclui: seguro</main>",
            "https://www.hikeland.pt/eventos/teste/")
        self.assertNotIn("price", fields)

    def test_preco_greentrekker_formato_oficial(self):
        html = "<main>Faça Já A Sua Reserva 15,00€ Por Pessoa</main>"
        fields = normalizar.parse_official_listing(
            "GreenTrekker", html, "https://www.greentrekker.pt/agenda/teste/")
        self.assertEqual(fields.get("price"), 15)

    def test_preco_hikeland_fora_do_main(self):
        html = BeautifulSoup(
            "<main><p>Descrição da caminhada</p></main>"
            "<section>PREÇO: 12€ | Participante</section>", "html.parser")
        event = {"organizer": "Hike Land", "price": None}
        recolher.extra_source_meta(html, event, "Hike Land")
        self.assertEqual(event["price"], 12)

    def test_preco_greentrekker_fora_do_main(self):
        html = BeautifulSoup(
            "<main><p>Informação do trilho</p></main>"
            "<section>Faça Já A Sua Reserva 15,00€ Por Pessoa</section>",
            "html.parser")
        event = {"organizer": "GreenTrekker", "price": None}
        recolher.extra_source_meta(html, event, "GreenTrekker")
        self.assertEqual(event["price"], 15)

    def test_arrabida_corrigida_sem_inventar_quilometragem(self):
        registry = load_registry()
        entries = [r for r in registry["corrections"]
                   if r["organizer"] == "Caminhando.pt"
                   and r["slug"] == "caminhando-nas-maravilhas-da-arrabida"
                   and r["date"] == "2026-10-31"]
        self.assertEqual(len(entries), 1)
        self.assertIn("km", entries[0]["fields"])
        self.assertIsNone(entries[0]["fields"]["km"])


if __name__ == "__main__":
    unittest.main()
