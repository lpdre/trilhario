"""Deduplicação, estabilidade de IDs e retenção de anúncios em falhas de fontes."""
import json
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import recolher
import normalizar_eventos as normalizar
from consolidar_catalogo import event_match, integrate
from identidade_eventos import sessoes_diferentes


def item(eid, **fields):
    return {'id':eid,'title':'Caminhada das Faias','organizer':'Organização X',
            'date':'2026-11-14','url':'https://clube.pt/agenda',
            'start':'Por confirmar','time':'',**fields}


class IdentidadeEvento(unittest.TestCase):
    def test_horas_diferentes_mesmo_titulo_e_data(self):
        morning=item('manha',time='09:00')
        afternoon=item('tarde',time='15:00')
        self.assertTrue(sessoes_diferentes(morning,afternoon))
        for deduper in (recolher.deduplicate,normalizar.merge_exact_duplicates):
            result=deduper([morning.copy(),afternoon.copy()])
            self.assertEqual({x['id'] for x in result},{'manha','tarde'})
        self.assertFalse(event_match(morning,afternoon))

    def test_inicio_distinto_mesmo_titulo_e_hora(self):
        a=item('a',start='Igreja Matriz de Seia',time='09:00')
        b=item('b',start='Largo da Câmara Municipal',time='09:00')
        for deduper in (recolher.deduplicate,normalizar.merge_exact_duplicates):
            self.assertEqual(len(deduper([a.copy(),b.copy()])),2)
        self.assertFalse(event_match(a,b))

    def test_urls_individuais_distintos_mesmo_titulo(self):
        a=item('a',url='https://clube.pt/eventos/faias-grupo-a')
        b=item('b',url='https://clube.pt/eventos/faias-grupo-b')
        self.assertTrue(sessoes_diferentes(a,b))
        self.assertEqual(len(recolher.deduplicate([a.copy(),b.copy()])),2)
        self.assertEqual(len(normalizar.merge_exact_duplicates([a.copy(),b.copy()])),2)
        self.assertFalse(event_match(a,b))

    def test_urls_de_calendario_nao_provam_duas_sessoes(self):
        a=item('a',url='https://clube.pt/agenda')
        b=item('b',url='https://clube.pt/calendario')
        self.assertFalse(sessoes_diferentes(a,b))
        self.assertEqual(len(recolher.deduplicate([a.copy(),b.copy()])),1)
        self.assertEqual(len(normalizar.merge_exact_duplicates([a.copy(),b.copy()])),1)

    def test_local_generico_e_detalhado_compativeis(self):
        a=item('a',start='Por confirmar')
        b=item('b',start='Parque Verde da Serra')
        self.assertFalse(sessoes_diferentes(a,b))
        c=item('c',start='Parque Verde da Serra, Arouca')
        self.assertFalse(sessoes_diferentes(b,c))

    def test_id_publicado_prevalece_e_gps_validado_nao_se_perde(self):
        old=item('id-original',km=None)
        updated=item('id-recolhido',km=15,lat=40.64,lon=-8.65,verified=True)
        for deduper in (recolher.deduplicate,normalizar.merge_exact_duplicates):
            result=deduper([old.copy(),updated.copy()],preferred_ids={'id-original'})
            self.assertEqual(len(result),1)
            e=result[0]
            self.assertEqual(e['id'],'id-original')
            self.assertEqual(e['km'],15)
            self.assertEqual(e.get('lat'),40.64)
            self.assertTrue(e.get('verified'))
            self.assertIn('id-recolhido',e['alias_ids'])

    def test_datas_diferentes_nao_se_fundem(self):
        a=item('a')
        b=item('b',date='2026-11-21')
        self.assertEqual(len(recolher.deduplicate([a.copy(),b.copy()])),2)
        self.assertEqual(len(normalizar.merge_exact_duplicates([a.copy(),b.copy()])),2)

    def test_organizador_distinto_nao_se_funde(self):
        a=item('a')
        b=item('b',organizer='Outro Clube')
        self.assertEqual(len(recolher.deduplicate([a.copy(),b.copy()])),2)
        self.assertEqual(len(normalizar.merge_exact_duplicates([a.copy(),b.copy()])),2)

    def test_registos_incompletos_nao_sao_apagados_silenciosamente(self):
        e=item('a',title='Passeio')
        other=item('b',title='')
        result=recolher.deduplicate([e,other])
        self.assertEqual(len(result),2)

    def test_excepcao_manual_nao_engloba_sessao_distinta(self):
        official=item('oficial',time='09:00')
        manual=item('manual',time='15:00')
        registry={'corrections':[],'fallback_events':[{'event':manual,
            'expires_on':manual['date'],'verified_at':'2026-10-21'}]}
        result,_,stats=integrate([official],registry,today=__import__('datetime').date(2026,10,26))
        self.assertEqual(len(result),2)
        self.assertEqual(stats['added'],1)

    def test_erro_de_fonte_preserva_anuncio_e_confirmacao(self):
        future=(recolher.TODAY+timedelta(days=16)).isoformat()
        old={'id':'historico','date':future,'title':'Caminhada das Faias',
             'organizer':'Clube Teste','url':'https://clube.pt/agenda',
             'last_seen_at':'2026-10-23',
             'last_confirmed_at':'2026-10-23T14:00:00+00:00'}
        with TemporaryDirectory() as folder:
            file=Path(folder)/'eventos.json'
            file.write_text(json.dumps({'events':[old],'sources_health':{}}),encoding='utf-8')
            with patch.object(recolher,'OUT',file),patch.object(recolher,'SOURCES',[
                 {'organizer':'Clube Teste','url':'https://clube.pt/agenda','path':r'^/evento/'}
            ]),patch.object(recolher,'collect_source',side_effect=OSError('falha temporária')):
                self.assertEqual(recolher.main(),0)
            refreshed=json.loads(file.read_text(encoding='utf-8'))
            self.assertEqual(len(refreshed['events']),1)
            self.assertEqual(refreshed['events'][0]['id'],'historico')
            self.assertEqual(refreshed['events'][0]['last_confirmed_at'],
                             '2026-10-23T14:00:00+00:00')
            self.assertEqual(refreshed['sources_health']['Clube Teste']['state'],'erro')


if __name__=='__main__':unittest.main()
