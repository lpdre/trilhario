import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_deduplicacao_preserva_evento_mais_completo(self):
        base={'date':'2026-11-12','title':'Trilho do Rio','organizer':'Clube X','url':'https://clube.pt/agenda/'}
        weak={**base,'id':'a','km':None,'gain':None}
        rich={**base,'id':'b','km':12,'gain':400}
        events=recolher.deduplicate([weak,rich])
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['km'],12)
        self.assertEqual(events[0]['gain'],400)

if __name__=='__main__':unittest.main()
