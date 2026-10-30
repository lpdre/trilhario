import json
import sys
import unittest
from contextlib import ExitStack
from datetime import date,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import normalizar_eventos as n

class ValidacaoNumerica(unittest.TestCase):
    def run_event(self, **values):
        event=dict(id='teste',title='Caminhada pela Serra',organizer='Clube Teste',
                   url='https://clube.pt/eventos/serra',date=(date.today()+timedelta(days=10)).isoformat(),
                   start='Praça da Vila',**values)
        with TemporaryDirectory() as folder, ExitStack() as stack:
            path=Path(folder)/'eventos.json'
            original=json.dumps({'events':[event]})
            path.write_text(original,encoding='utf-8')
            stack.enter_context(patch.object(n,'CATALOG',path))
            stack.enter_context(patch.object(n,'git_previous',return_value=[]))
            stack.enter_context(patch.object(n,'enrich_official',return_value={}))
            stack.enter_context(patch.object(n,'PHOTO_VISITS_PER_RUN',0))
            report=stack.enter_context(patch.object(n,'report'))
            stack.enter_context(patch('consolidar_catalogo.load_registry',return_value={'schema':1,'corrections':[],'fallback_events':[]}))
            status=n.main()
            if status:
                self.assertEqual(path.read_text(encoding='utf-8'),original)
            return status, str(report.call_args)

    def test_invalidos_bloqueiam_publicacao_sem_reescrever_catalogo(self):
        for field in ('price','km','gain','duration'):
            for value in (-1,float('nan'),float('inf'),float('-inf'),True,'12'):
                with self.subTest(field=field,value=value):
                    status,report=self.run_event(**{field:value})
                    self.assertEqual(status,1)
                    self.assertIn(field,report)

    def test_zero_e_desconhecido_sao_legitimos(self):
        for value in (None,0,12.5):
            with self.subTest(value=value):
                self.assertEqual(self.run_event(price=value,km=value,gain=value,duration=value)[0],0)

    def test_programa_multidiario_sem_limite_artificial(self):
        self.assertEqual(self.run_event(multiDay=True,price=1200,km=120,gain=4000,duration=48)[0],0)
