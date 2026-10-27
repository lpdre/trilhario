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
from qualidade_anuncios import GENERIC_TITLE, MULTIDAY, title_date_conflicts, is_multiday_program


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
                self.assertTrue(recolher.valid_new_event({
                    'title':title,'date':(recolher.TODAY+timedelta(days=8)).isoformat()}))
        self.assertFalse(MULTIDAY.search('GR Peneda-Gerês Etapas 18 e 19'))
        self.assertFalse(MULTIDAY.search('Caminhada no Bosque das Faias — Sábado Manhã'))

    def test_programas_multidias_nao_identificados_pelo_titulo(self):
        known = (
            ('Trekking Roots', 'Rota das Faias e o Melhor do Outono de Manteigas',
             'https://trekkingroots.pt/caminhada/rota-das-faias-e-o-melhor-do-outono-de-manteigas/'),
            ('Trekking Roots', 'Bosques Mágicos do Courel',
             'https://trekkingroots.pt/caminhada/bosques-magicos-do-courel/'),
            ('Mais Trilhos', 'Parque Nacional de Monfragüe',
             'https://maistrilhos.pt/caminhadas/parque-nacional-de-monfrague'),
            ('Caminhando.pt', 'Caminhando em Aracena',
             'https://caminhando.pt/eventos/caminhando-em-aracena-gruta-das-maravilhas-e-parque-mineiro-de-rio-tinto'),
        )
        for organizer, title, url in known:
            event = {'organizer':organizer,'title':title,'url':url,
                     'date':(recolher.TODAY+timedelta(days=8)).isoformat()}
            with self.subTest(url=url):
                self.assertFalse(MULTIDAY.search(title))
                self.assertTrue(is_multiday_program(event))
                self.assertTrue(recolher.valid_new_event(event))
        regular={'title':'Rota das Faias e Covão D\'Ametade',
                 'url':'https://trekkingroots.pt/caminhada/rota-das-faias-e-covao-d-ametade-antiga-2026-06-15/'}
        self.assertFalse(is_multiday_program(regular))
        # URLs idênticos com outras origens não são bloqueados.
        self.assertFalse(is_multiday_program({'title':'Caminhada em Manteigas',
                 'url':'https://outro.pt/caminhada/bosques-magicos-do-courel'}))

    def test_seis_programas_identificados_sem_exigir_eventos_expirados(self):
        # Fixtures estáveis: nunca bloquear a recolha quando um destes eventos acabar.
        programs = (
            ('Expedição Outonal a Ordesa e Monte Perdido',
             'https://trekkingroots.pt/caminhada/expedicao-outonal-a-ordesa-e-monte-perdido'),
            ('Rota das Faias e o Melhor do Outono de Manteigas',
             'https://trekkingroots.pt/caminhada/rota-das-faias-e-o-melhor-do-outono-de-manteigas'),
            ('Bosques Mágicos do Courel',
             'https://trekkingroots.pt/caminhada/bosques-magicos-do-courel'),
            ('Parque Nacional de Monfragüe',
             'https://maistrilhos.pt/caminhadas/parque-nacional-de-monfrague'),
            ('Caminhando em Aracena',
             'https://caminhando.pt/eventos/caminhando-em-aracena-gruta-das-maravilhas-e-parque-mineiro-de-rio-tinto'),
            ('Fim de Semana Passagem de Ano - Douro Internacional',
             'https://maistrilhos.pt/caminhadas/passagem-de-ano-douro-internacional'),
        )
        start=recolher.TODAY+timedelta(days=8)
        for title, url in programs:
            with self.subTest(url=url):
                event={'title':title,'url':url,'date':start.isoformat(),
                       'endDate':(start+timedelta(days=2)).isoformat()}
                self.assertTrue(is_multiday_program(event))
                self.assertTrue(recolher.valid_new_event(event))

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

    def test_criterio_de_expiracao_no_dia_seguinte_ao_inicio(self):
        from datetime import date
        today=date(2026,10,30)
        started={'title':'Expedição de 3 dias', 'date':'2026-10-29',
                 'endDate':'2026-11-01', 'multiDay':True}
        starts_today={**started,'date':'2026-10-30','endDate':'2026-11-02'}
        with patch.object(recolher,'TODAY',today),patch.object(recolher,'LIMIT_DATE',today+timedelta(days=150)):
            self.assertFalse(recolher.valid_new_event(started))
            self.assertTrue(recolher.valid_new_event(starts_today))

    def test_retencao_nao_prolongada_por_enddate(self):
        from datetime import date
        today=date(2026,10,30)
        old={'id':'comecou-ontem','title':'Expedição de 3 dias',
             'date':'2026-10-29','endDate':'2026-11-01',
             'multiDay':True,'organizer':'Grupo A','url':'https://example.pt/a'}
        fresh={'id':'comeca-hoje','title':'Viagem pedestre de 2 dias',
               'date':'2026-10-30','endDate':'2026-10-31',
               'multiDay':True,'organizer':'Grupo A','url':'https://example.pt/b'}
        with TemporaryDirectory() as folder:
            path=Path(folder)/'eventos.json'
            path.write_text(json.dumps({'events':[old,fresh]}),encoding='utf-8')
            with patch.object(recolher,'TODAY',today),patch.object(recolher,'LIMIT_DATE',today+timedelta(days=150)),patch.object(recolher,'OUT',path),patch.object(recolher,'SOURCES',[]):
                self.assertEqual(recolher.main(),0)
            remaining=json.loads(path.read_text(encoding='utf-8'))['events']
        self.assertEqual([e['id'] for e in remaining],['comeca-hoje'])

    def test_intervalo_de_dois_dias_nao_e_conflito(self):
        from datetime import date
        from fontes_oficiais import _event_date, _event_range
        target=date(2026,11,7)
        for title in ('Caminhada de 7 a 8 de novembro de 2026',
                      'Travessia 7–8 novembro 2026',
                      'Caminhada 7-8 de novembro de 2026'):
            with self.subTest(title=title):
                self.assertEqual(_event_date(title,title,recolher.date_from,date(2026,10,27)),target)
                self.assertEqual(_event_range(title,recolher.date_from,date(2026,10,27))[1],
                                 date(2026,11,8))
                item={'title':title,'date':'2026-11-07',
                      'endDate':'2026-11-08','multiDay':True}
                self.assertFalse(recolher.header_date_conflicts(item))
                with patch.object(recolher,'TODAY',date(2026,10,27)), patch.object(recolher,'LIMIT_DATE',date(2027,3,26)):
                    self.assertTrue(recolher.valid_new_event(item))

    def test_enddate_publicada_em_jsonld_do_proprio_evento(self):
        url='https://clube.pt/caminhada/expedicao'
        html=BeautifulSoup(
            '<script type="application/ld+json">'+json.dumps({
                '@type':'Event','url':url,'startDate':'2026-11-07T09:00:00',
                'endDate':'2026-11-08T18:00:00'})+'</script>','html.parser')
        event={'title':'Rota da Serra','date':'2026-11-07','url':url}
        recolher.enrich_jsonld(html,event)
        self.assertEqual(event['endDate'],'2026-11-08')
        self.assertTrue(event['multiDay'])
        self.assertTrue(is_multiday_program(event))
        self.assertFalse(recolher.valid_new_event({**event,'endDate':'invalid'}))

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

    def test_programas_guardados_conservados_apos_falha_de_fonte(self):
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
        self.assertEqual({e['id'] for e in events},{'um-dia','viagem'})

    def test_catalogo_com_multidias_e_datas_explicitas_validas(self):
        data=json.loads((ROOT/'eventos.json').read_text(encoding='utf-8'))
        events=data['events']
        self.assertTrue(events)
        self.assertEqual(len(events),len({e['id'] for e in events}))
        for e in events:
            with self.subTest(id=e['id']):
                self.assertFalse(GENERIC_TITLE.match(e.get('title') or ''))
                if not is_multiday_program(e):
                    self.assertFalse(title_date_conflicts(e))
                if e.get('endDate'):
                    self.assertGreaterEqual(e['endDate'],e['date'])
                if e.get('multiDay'):
                    self.assertTrue(is_multiday_program(e))
        # A agenda pode legitimamente ficar sem programas multidiários
        # quando os anúncios concretos de 2026 terminarem.


if __name__=='__main__':
    unittest.main()
