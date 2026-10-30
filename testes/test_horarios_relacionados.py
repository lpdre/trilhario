import sys
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import normalizar_eventos as n

URL='https://caminhando.pt/eventos/caminhada-da-serra'
SCHEDULE='Horário (Domingo) 09:00 - 13:00 Ponto de Encontro Praça da Vila Detalhes do Evento'

class HorariosRelacionados(unittest.TestCase):
    def test_nao_copia_horario_de_evento_relacionado(self):
        html='<main><h1>Caminhada da Serra</h1>Detalhes do Evento Sem horário publicado. Eventos relacionados '+SCHEDULE+'</main>'
        fields=n.parse_caminhando_detail(html,URL)
        for field in ('time','endTime','duration','start'):
            self.assertNotIn(field,fields)

    def test_nao_atravessa_descricao_a_procura_de_local(self):
        html='<main>Horário (Domingo) 09:00 - 13:00 Descrição do Evento Outro anúncio Ponto de Encontro Praça da Vila Detalhes do Evento</main>'
        fields=n.parse_caminhando_detail(html,URL)
        for field in ('time','endTime','duration','start'):
            self.assertNotIn(field,fields)

    def test_cabecalho_proprio_continua_a_ser_lido(self):
        fields=n.parse_caminhando_detail('<main>'+SCHEDULE+'Texto e outros eventos</main>',URL)
        self.assertEqual(fields['time'],'09:00')
        self.assertEqual(fields['endTime'],'13:00')
        self.assertEqual(fields['start'],'Praça da Vila')
        self.assertEqual(fields['duration'],4)

    def test_reparacao_nao_substitui_horario_valido_por_evento_relacionado(self):
        html='<main><h1>Caminhada da Serra</h1>Descrição do Evento Sem ponto de encontro. Eventos relacionados '+SCHEDULE+'</main>'
        response=Mock(text=html,url=URL,headers={'Content-Type':'text/html'})
        event=dict(organizer='Caminhando.pt',url=URL,title='Caminhada da Serra',time='10:00')
        with patch('requests.get',return_value=response):
            fields=n.repair_caminhando(event,{})
        self.assertNotIn('time',fields)
        self.assertNotIn('start',fields)
