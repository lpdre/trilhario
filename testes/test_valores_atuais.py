import copy
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import recolher
import normalizar_eventos as n

class ValoresAtuais(unittest.TestCase):
    def event(self, ident, **fields):
        return dict(dict(id=ident,title='Caminhada das Faias',organizer='Clube Teste',
            url='https://clube.pt/eventos/faias',date=(date.today()+timedelta(days=20)).isoformat(),
            time='09:00',start='Praça da Vila',price=10,km=12,
            last_seen_at=(date.today()-timedelta(days=1)).isoformat()),**fields)

    def test_valores_novos_preservam_id_em_ambas_ordens(self):
        old=self.event('antigo')
        new=self.event('novo',price=20,km=14,last_seen_at=date.today().isoformat())
        for dedup in (recolher.deduplicate,n.merge_exact_duplicates):
            for records in ([old,new],[new,old]):
                with self.subTest(dedup=dedup.__name__, first=records[0]['id']):
                    result=dedup(copy.deepcopy(records),preferred_ids={'antigo'})
                    self.assertEqual(len(result),1)
                    self.assertEqual(result[0]['id'],'antigo')
                    self.assertEqual(result[0]['price'],20)
                    self.assertEqual(result[0]['km'],14)
                    self.assertIn('novo',result[0]['alias_ids'])

    def test_sem_prova_de_recencia_nao_substitui(self):
        for dedup in (recolher.deduplicate,n.merge_exact_duplicates):
            result=dedup([self.event('antigo'),self.event('novo',price=20)],preferred_ids={'antigo'})
            self.assertEqual(result[0]['price'],10)

    def test_valor_ausente_nao_apaga_e_zero_e_preservado(self):
        for dedup in (recolher.deduplicate,n.merge_exact_duplicates):
            result=dedup([self.event('antigo'),self.event('novo',price=0,km=None,
                last_seen_at=date.today().isoformat())],preferred_ids={'antigo'})
            self.assertEqual(result[0]['price'],0)
            self.assertEqual(result[0]['km'],12)

    def test_sessao_distinta_nao_e_fundida(self):
        for dedup in (recolher.deduplicate,n.merge_exact_duplicates):
            for change in ({'time':'15:00'}, {'date':(date.today()+timedelta(days=21)).isoformat()},
                           {'url':'https://clube.pt/eventos/outro'}):
                result=dedup([self.event('antigo'),self.event('novo',price=20,
                    last_seen_at=date.today().isoformat(),**change)],preferred_ids={'antigo'})
                self.assertEqual(len(result),2)

    def test_recolha_do_mesmo_dia_atualiza_sem_trocar_id(self):
        old=self.event('antigo',last_seen_at=date.today().isoformat())
        new=self.event('novo',price=20,km=14)
        with TemporaryDirectory() as folder:
            path=Path(folder)/'eventos.json'
            path.write_text(json.dumps({'events':[old]}),encoding='utf-8')
            with patch.object(recolher,'OUT',path),patch.object(recolher,'SOURCES',[{'organizer':'Clube Teste'}]),patch.object(recolher,'collect_source',return_value=[new]):
                self.assertEqual(recolher.main(),0)
            result=json.loads(path.read_text(encoding='utf-8'))['events']
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['id'],'antigo')
            self.assertEqual(result[0]['price'],20)
            self.assertEqual(result[0]['km'],14)

    def test_nao_sobrescreve_com_valor_invalido_ou_query_distinta(self):
        for dedup in (recolher.deduplicate,n.merge_exact_duplicates):
            for change in ({'price':-1}, {'price':float('nan')}, {'price':True},
                           {'url':'https://clube.pt/eventos/faias?sessao=2','price':20}):
                with self.subTest(dedup=dedup.__name__,change=change):
                    result=dedup([self.event('antigo'),self.event('novo',
                        last_seen_at=date.today().isoformat(),**change)],preferred_ids={'antigo'})
                    self.assertEqual(result[0]['price'],10)
