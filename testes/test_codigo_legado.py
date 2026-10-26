import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import timedelta
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import recolher

class AuditoriaCodigoLegado(unittest.TestCase):
    def test_agregador_desactivado_sem_extractor(self):
        self.assertFalse(any(s.get('mode') == 'agregador' for s in recolher.SOURCES))
        self.assertFalse(hasattr(recolher,'collect_aggregator'))
        self.assertFalse(hasattr(recolher,'excluded_organizer'))

    def test_evento_antigo_agregador_continua_bloqueado(self):
        self.assertTrue(recolher.is_disallowed_aggregator_event(
            {'url':'https://trilhosecaminhadas.pt/percursos/evento_info.php?id=56'}))
        self.assertTrue(recolher.is_disallowed_aggregator_event(
            {'source':'Trilhos & Caminhadas','url':'https://outro-site.pt/abc'}))
        self.assertFalse(recolher.is_disallowed_aggregator_event(
            {'url':'https://barbosa-trekking.pt/caminhada/oficial/'}))

    def test_programa_pdf_nao_consulta_rede(self):
        source={'organizer':'Gerês Viver Turismo','mode':'programa','url':'https://example.org/programa'}
        with patch.object(recolher,'fetch',side_effect=AssertionError('rede desnecessária')) as fetch:
            self.assertEqual(recolher.collect_simple_program(source),[])
            fetch.assert_not_called()

    def test_fallback_tem_eventos_mesmo_quando_principal_tem_links_antigos(self):
        """Uma página com links não prova que encontrou caminhadas válidas."""
        future = (recolher.TODAY + timedelta(days=14)).isoformat()
        old = (recolher.TODAY - timedelta(days=50)).isoformat()
        main_url = 'https://exemplo.pt/agenda/'
        other_url = 'https://exemplo.pt/alternativa/'
        event_url = 'https://exemplo.pt/alternativa/evento/mata'
        pages = {
            main_url: f'<article>Data: {old} <a href="/agenda/evento/antigo">Caminhada Antiga</a></article>',
            other_url: f'<article>Data: {future} <a href="evento/mata">Caminhada da Mata</a></article>',
            event_url: '<main><h1>Caminhada da Mata</h1><p>Distância: 13 km. Duração: 4 h.</p></main>',
        }
        def fake_fetch(url):
            body = pages.get(url)
            return BeautifulSoup(body, 'html.parser') if body is not None else None
        source = {'organizer':'Clube de Teste', 'url':main_url,
                  'fallback':[other_url], 'path':r'^/(?:agenda|alternativa)/evento/[^/]+/?$'}
        with patch.object(recolher,'fetch',side_effect=fake_fetch) as fetch:
            with patch.object(recolher.time,'sleep'):
                found = recolher.collect_source(source)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['url'], event_url,
                         'o link relativo deve usar a página alternativa como base')
        self.assertEqual(found[0]['date'], future)
        self.assertIn(main_url, [x.args[0] for x in fetch.call_args_list])
        self.assertIn(other_url, [x.args[0] for x in fetch.call_args_list])

    def test_link_mal_formado_nao_interrompe_recolha(self):
        self.assertIsNone(recolher.canonical('https://exemplo.pt/agenda/','https://[ipv6-invalido'))
        self.assertIsNone(recolher.canonical('https://exemplo.pt/agenda/','javascript:alert(1)'))
        self.assertEqual(recolher.canonical('https://exemplo.pt/agenda/','evento/1?origem=lista'),
                         'https://exemplo.pt/agenda/evento/1')

    def test_deduplicacao_preserva_evento_mais_completo(self):
        base={'date':'2026-11-12','title':'Trilho do Rio','organizer':'Clube X','url':'https://clube.pt/agenda/'}
        weak={**base,'id':'a','km':None,'gain':None}
        rich={**base,'id':'b','km':12,'gain':400}
        events=recolher.deduplicate([weak,rich])
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['km'],12)
        self.assertEqual(events[0]['gain'],400)

if __name__=='__main__':unittest.main()
