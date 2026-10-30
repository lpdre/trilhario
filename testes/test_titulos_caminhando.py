import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import normalizar_eventos as n

URL = 'https://caminhando.pt/eventos/caminhada-na-rota-dos-castanheiros'
TITLE = 'Caminhada na Rota dos Castanheiros'

class TitulosCaminhando(unittest.TestCase):
    def test_seccoes_nao_sao_titulos(self):
        for heading in ('Localização', 'Alguns dos pontos de interesse deste evento:'):
            with self.subTest(heading=heading):
                self.assertNotIn('title', n.parse_caminhando_detail('<main><h1>'+heading+'</h1></main>', URL))

    def test_titulo_relacionado_com_ficha(self):
        html = '<main><h1>Localização</h1><h1>'+TITLE+'</h1></main>'
        self.assertEqual(n.parse_caminhando_detail(html, URL).get('title'), TITLE)

    def test_outro_evento_nao_substitui_titulo(self):
        html = '<main><h1>Caminhada pelas praias da Arrábida</h1></main>'
        self.assertNotIn('title', n.parse_caminhando_detail(html, URL))

    def test_reparacao_preserva_nome_e_recupera_horas(self):
        html = '<main><h1>Localização</h1>Horário (Domingo) 9:20 - 14:00 Ponto de Encontro Praça da Vila Detalhes do Evento</main>'
        response = Mock(text=html, url=URL, headers={'Content-Type':'text/html'})
        with patch('requests.get', return_value=response):
            fields = n.repair_caminhando({'organizer':'Caminhando.pt','url':URL,'title':TITLE}, {})
        self.assertNotIn('title', fields)
        self.assertEqual(fields['time'], '09:20')
        self.assertEqual(fields['start'], 'Praça da Vila')
