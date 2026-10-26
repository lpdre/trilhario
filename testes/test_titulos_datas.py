"""Auditoria offline de títulos, datas e programas de vários dias."""
import json
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import recolher
import normalizar_eventos as normalizar
from qualidade_anuncios import GENERIC_TITLE, MULTIDAY, title_date_conflicts


class TitulosDatas(unittest.TestCase):
    def test_titulo_generico_hikeland_muito_dificil(self):
        self.assertTrue(GENERIC_TITLE.match('muito-dificil 21/11/2026 21 km NOVIDADE'))
        self.assertTrue(GENERIC_TITLE.match('Muito Difícil 21-11-2026 21 km'))
        self.assertFalse(GENERIC_TITLE.match('Montemuro: O Vale do Bestança | Cinfães'))

    def test_programas_multidiarios_detectados(self):
        for title in ('Expedição Outonal a Ordesa e Monte Perdido',
                      'Fim de Semana Passagem de Ano - Douro Internacional',
                      'Travessia de 3 dias na Serra',
                      'Viagem às Dolomitas'):
            with self.subTest(title=title):
                self.assertTrue(MULTIDAY.search(title))
                self.assertFalse(recolher.valid_new_event({
                    'title':title,'date':(recolher.TODAY+timedelta(days=8)).isoformat()}))
        self.assertFalse(MULTIDAY.search('GR Peneda-Gerês Etapas 18 e 19'))
        self.assertFalse(MULTIDAY.search('Caminhada no Bosque das Faias — Sábado Manhã'))

    def test_datas_do_titulo_coincidentes(self):
        for title in ('Trilho da Serra (21 de Novembro)',
                      'Passeio de 21/11/2026',
                      'Percurso 2026-11-21',
                      'Trekking 21 de Novembro de 2026'):
            self.assertFalse(title_date_conflicts({'date':'2026-11-21','title':title}))

    def test_datas_contraditorias_bloqueadas(self):
        for title in ('Trilho da Serra (22 de Novembro)',
                      'Passeio de 21/11/2025',
                      'Percurso 2026-11-22',
                      'Trekking 21 de Novembro de 2027',
                      'Passeio 31/02/2026'):
            with self.subTest(title=title):
                self.assertTrue(title_date_conflicts({'date':'2026-11-21','title':title}))
                self.assertTrue(recolher.header_date_conflicts({
                    'date':'2026-11-21','title':title}))
        # O nome do URL pode corresponder a uma edição anterior.
        self.assertFalse(title_date_conflicts({'date':'2026-11-07',
            'title':'GR Peneda-Gerês Etapas 18 e 19 (7 de Novembro)',
            'url':'https://barbosa-trekking.pt/gr-peneda-geres-etapas-18-e-19-18-de-julho'}))

    def test_colector_recupera_h1_oficial_em_cartao_generico(self):
        day=(recolher.TODAY+timedelta(days=17))
        date_text=day.strftime('%d/%m/%Y')
        listing_url='https://www.hikeland.pt/atividades-1-dia/'
        detail_url='https://www.hikeland.pt/eventos/montemuro-o-vale-do-bestanca-cinfaes'
        listing=BeautifulSoup(
            f'<article><time>{date_text}</time><a href="/eventos/montemuro-o-vale-do-bestanca-cinfaes">'
            f'muito-dificil {date_text} 21 km NOVIDADE</a></article>','html.parser')
        detail=BeautifulSoup('<main><h1>Montemuro: O Vale do Bestança | Cinfães</h1>'
                             '<p>Distância 21 km. Duração 8 h.</p></main>','html.parser')
        def fetch(url):
            return {listing_url:listing,detail_url:detail}.get(url)
        source={'organizer':'Hike Land','url':listing_url,'path':r'^/eventos/[^/]+/?$'}
        with patch.object(recolher,'fetch',side_effect=fetch),patch.object(recolher.time,'sleep'):
            result=recolher.collect_source(source)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['title'],'Montemuro: O Vale do Bestança | Cinfães')
        self.assertEqual(result[0]['date'],day.isoformat())

    def test_programas_guardados_nao_regressam_apos_falha_de_fonte(self):
        future=(recolher.TODAY+timedelta(days=18)).isoformat()
        kept={'id':'um-dia','title':'Trilho do Monte','date':future,
              'organizer':'Clube A','url':'https://clube.pt/eventos/monte'}
        trip={'id':'viagem','title':'Expedição Outonal de 4 dias','date':future,
              'organizer':'Clube A','url':'https://clube.pt/eventos/expedicao'}
        with TemporaryDirectory() as folder:
            target=Path(folder)/'eventos.json'
            target.write_text(json.dumps({'events':[kept,trip]}),encoding='utf-8')
            with patch.object(recolher,'OUT',target),patch.object(recolher,'SOURCES',[]):
                self.assertEqual(recolher.main(),0)
            events=json.loads(target.read_text(encoding='utf-8'))['events']
        self.assertEqual([e['id'] for e in events],['um-dia'])

    def test_catalogo_publicado_sem_multidias_e_datas_explicitas_erradas(self):
        data=json.loads((ROOT/'eventos.json').read_text(encoding='utf-8'))
        events=data['events']
        self.assertTrue(events)
        self.assertEqual(len(events),len({e['id'] for e in events}))
        for e in events:
            with self.subTest(id=e['id']):
                self.assertFalse(MULTIDAY.search(e.get('title') or ''))
                self.assertFalse(GENERIC_TITLE.match(e.get('title') or ''))
                self.assertFalse(title_date_conflicts(e))


if __name__=='__main__':
    unittest.main()
