import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import recolher
import normalizar_eventos as n
from consolidar_catalogo import event_match
from identidade_eventos import sessoes_diferentes

class SessoesURL(unittest.TestCase):
    def event(self, ident, query):
        return dict(id=ident,title='Caminhada das Faias',organizer='Clube Teste',
            date='2026-11-14',time='09:00',start='Praça da Vila',
            url='https://clube.pt/eventos/faias'+query)

    def test_parametros_de_sessao_impedem_fusao(self):
        for query in ('?sessao=2','', '?sessao=1&grupo=b'):
            a,b=self.event('a','?sessao=1'),self.event('b',query)
            with self.subTest(query=query):
                self.assertTrue(sessoes_diferentes(a,b))
                self.assertFalse(event_match(a,b))
                for dedup in (recolher.deduplicate,n.merge_exact_duplicates):
                    for pair in ([a,b],[b,a]):
                        result=dedup(copy.deepcopy(pair),preferred_ids={'a'})
                        self.assertEqual({e['id'] for e in result},{'a','b'})

    def test_ordem_de_chaves_e_rastreio_nao_criam_sessoes(self):
        a=self.event('a','?sessao=1&grupo=a')
        b=self.event('b','?utm_source=mail&grupo=a&sessao=1&fbclid=abc#detalhes')
        self.assertFalse(sessoes_diferentes(a,b))
        self.assertTrue(event_match(a,b))
        for dedup in (recolher.deduplicate,n.merge_exact_duplicates):
            result=dedup(copy.deepcopy([a,b]),preferred_ids={'a'})
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['id'],'a')
            self.assertIn('b',result[0]['alias_ids'])

    def test_valor_vazio_e_maiusculas_nao_sao_descartados(self):
        for query in ('?Sessao=1','?sessao=', '?sessao=1&opcao='):
            a,b=self.event('a','?sessao=1'),self.event('b',query)
            self.assertTrue(sessoes_diferentes(a,b))

    def test_ordem_de_valores_repetidos_e_preservada(self):
        a=self.event('a','?sessao=1&sessao=2')
        b=self.event('b','?sessao=2&sessao=1')
        self.assertTrue(sessoes_diferentes(a,b))
