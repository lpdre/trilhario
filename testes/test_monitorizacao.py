"""Testes offline, determinísticos, sem consultas a organizadores."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitorizacao_fontes import classify_source, empty_metrics, enrich_catalog


class HealthTests(unittest.TestCase):
    def stats(self, **kw):
        result = empty_metrics()
        result.update(kw)
        return result

    def test_fonte_acessivel_sem_anuncios_reconhecidos(self):
        self.assertEqual(classify_source(self.stats(usable_pages=2), {}), 'sem_anuncios_reconhecidos')

    def test_erro_http_com_codigo(self):
        self.assertEqual(classify_source(self.stats(http_errors=[403]), {}), 'erro_http')

    def test_erro_de_rede(self):
        self.assertEqual(classify_source(self.stats(network_errors=1), {}), 'erro_rede')

    def test_html_inutilizavel(self):
        self.assertEqual(classify_source(self.stats(unusable_pages=1), {}), 'erro_resposta')

    def test_fonte_parcial(self):
        self.assertEqual(classify_source(self.stats(seen=[{'id': 'x'}], http_errors=[404]), {}), 'recolha_parcial')

    def test_erro_no_parser(self):
        self.assertEqual(classify_source(self.stats(exceptions=1), {}), 'erro_extraccao')

    def test_nao_afirmar_sem_eventos_quando_erro_parcial(self):
        self.assertEqual(classify_source(self.stats(usable_pages=1, network_errors=1), {}), 'erro_parcial')

    def test_nao_verificada(self):
        self.assertEqual(classify_source(self.stats(), {}), 'nao_verificada')

    def test_confirmacao_real_sem_falsa_reconfirmacao(self):
        first = {'id':'1', 'date':'2026-11-01', 'organizer':'Oficial', 'url':'https://exemplo.pt/1'}
        second = {'id':'2', 'date':'2026-11-02', 'organizer':'Oficial', 'url':'https://exemplo.pt/2',
                  'last_confirmed_at':'2026-10-17T09:00:00+00:00'}
        data={'events':[first,second], 'sources_health':{'Oficial': {'state':'com_eventos'}}}
        m={'Oficial':self.stats(seen=[dict(first)],usable_pages=1,requests=2)}
        enrich_catalog(data,m,'2026-10-23T18:00:00+00:00')
        self.assertEqual(data['events'][0]['last_confirmed_at'],'2026-10-23T18:00:00+00:00')
        self.assertEqual(data['events'][1]['last_confirmed_at'],'2026-10-17T09:00:00+00:00')
        self.assertEqual(data['sources_health']['Oficial']['state'],'com_eventos')
        self.assertEqual(data['sources_health']['Oficial']['last_success'],'2026-10-23T18:00:00+00:00')

    def test_falha_fonte_preserva_catalogo(self):
        event = {'id':'x', 'date':'2026-11-09', 'organizer':'X','url':'https://site.pt/x',
                 'last_confirmed_at':'2026-10-21T08:00:00+00:00'}
        data={'events':[event], 'sources_health':{'X': {'last_success':'2026-10-21','state':'com_eventos'}}}
        enrich_catalog(data, {'X':self.stats(http_errors=[503],requests=1)}, '2026-10-23T19:00:00+00:00')
        self.assertEqual(data['events'][0]['last_confirmed_at'],'2026-10-21T08:00:00+00:00')
        self.assertEqual(data['sources_health']['X']['last_success'],'2026-10-21')
        self.assertEqual(data['sources_health']['X']['state'],'erro_http')

    def test_renamed_id_via_alias(self):
        event = {'id':'new','alias_ids':['old'], 'date':'2026-11-01',
                 'organizer':'X','url':'https://site.pt/x'}
        data={'events':[event]}
        enrich_catalog(data, {'X':self.stats(seen=[{'id':'old'}], usable_pages=1)}, '2026-10-23T18:00:00+00:00')
        self.assertEqual(data['events'][0]['last_confirmed_at'], '2026-10-23T18:00:00+00:00')

    def test_sem_fontes_nao_inventa_sucesso(self):
        data={'events':[{'id':'x'}], 'sources_health':{'Desactivada':{'state':'com_eventos'}}}
        enrich_catalog(data, {}, '2026-10-23T18:00:00+00:00')
        self.assertEqual(data['sources_health']['Desactivada']['state'],'nao_verificada')


if __name__ == '__main__': unittest.main()
