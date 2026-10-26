import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import normalizar_eventos as normalizar

class AuditoriaNormalizacao(unittest.TestCase):
    def test_gps_valido_e_invalidos(self):
        self.assertTrue(normalizar.valid_gps_pair({'lat':40.64,'lon':-8.65}))
        self.assertTrue(normalizar.valid_gps_pair({'lat':'40.64','lon':'-8.65'}))
        for value in ({'lat':None,'lon':-8},{'lat':'N 40','lon':-8},
                      {'lat':float('nan'),'lon':-8},{'lat':40,'lon':float('inf')},
                      {'lat':100,'lon':-8},{'lat':40,'lon':-200},{'lat':40}):
            with self.subTest(value=value):
                self.assertFalse(normalizar.valid_gps_pair(value))

    def test_limpeza_de_campos_antigos(self):
        item={'organizer':'Clube X Contacto: telefone','town':'Vila-real (Ver no Google Maps)','start':'Fundao'}
        normalizar.tidy_event_fields(item)
        self.assertEqual(item['organizer'],'Clube X')
        self.assertEqual(item['town'],'Vila Real')
        self.assertEqual(item['start'],'Fundão')

    def test_mesmo_url_datas_diferentes_nao_funde(self):
        a={'id':'a','title':'Trilho do Rio','date':'2026-11-01','organizer':'Clube X','url':'https://clube.pt/agenda'}
        b={**a,'id':'b','date':'2026-11-08'}
        self.assertEqual(len(normalizar.merge_exact_duplicates([a,b])),2)

    def test_duplicados_guardam_id_alternativo(self):
        a={'id':'a','title':'Trilho do Rio','date':'2026-11-01','organizer':'Clube X','km':None}
        b={**a,'id':'b','km':13,'verified':True}
        items=normalizar.merge_exact_duplicates([a,b])
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['km'],13)
        self.assertIn('a',items[0]['alias_ids'])

if __name__ == '__main__':
    unittest.main()
