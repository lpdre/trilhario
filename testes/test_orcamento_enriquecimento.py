import copy
import json
import sys
import unittest
from contextlib import ExitStack
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import normalizar_eventos as n

class OrcamentoEnriquecimento(unittest.TestCase):
    def event(self, index):
        return dict(id=str(index), title='Caminhada na Serra '+str(index),
                    date=(date.today()+timedelta(days=index+1)).isoformat(),
                    organizer='Hike Land', url='https://hikeland.pt/eventos/serra-'+str(index),
                    start='Praça da Vila', time='09:00', price=15, km=12, gain=300, duration=4)

    def run_catalog(self, events, response):
        with TemporaryDirectory() as folder, ExitStack() as stack:
            path=Path(folder)/'eventos.json'
            path.write_text(json.dumps({'events':events}), encoding='utf-8')
            for attr, value in [('CATALOG',path), ('PHOTO_VISITS_PER_RUN',0)]:
                stack.enter_context(patch.object(n,attr,value))
            stack.enter_context(patch.object(n,'git_previous',return_value=[]))
            stack.enter_context(patch.object(n,'report'))
            stack.enter_context(patch('consolidar_catalogo.load_registry',return_value={'schema':1,'corrections':[],'fallback_events':[]}))
            request=stack.enter_context(patch('requests.get',return_value=response))
            self.assertEqual(n.main(),0)
            return json.loads(path.read_text(encoding='utf-8'))['events'], request.call_count

    def test_completos_nao_esgotam_orcamento(self):
        events=[self.event(i) for i in range(36)]
        events[-1]['price']=None
        response=Mock(text='<main>Preço: 20€ | Participante</main>',headers={'Content-Type':'text/html'})
        result, calls=self.run_catalog(events,response)
        self.assertEqual(calls,1)
        self.assertEqual(result[-1]['price'],20)

    def test_limite_de_pedidos_mantido(self):
        events=[dict(self.event(i),price=None) for i in range(40)]
        response=Mock(text='<main>Sem preço publicado</main>',headers={'Content-Type':'text/html'})
        _, calls=self.run_catalog(events,response)
        self.assertEqual(calls,35)

    def test_fonte_completa_nao_consulta_campos_sem_extrator(self):
        event=self.event(1)
        event.update(gain=None,duration=None)
        with patch('requests.get') as request:
            self.assertEqual(n.enrich_official(event,{}),{})
        request.assert_not_called()
