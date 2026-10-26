import json
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from consolidar_catalogo import integrate, load_registry, event_match


def event(eid='oficial', title='Caminhada pela Serra', date_='2026-11-14', url='https://clube.pt/eventos/caminhada-serra/', org='CAAL'):
    return {'id': eid, 'date': date_, 'title': title, 'organizer': org, 'url': url}


def registry(item=None):
    row = item or event(eid='manual', title='A mesma caminhada')
    return {'schema': 1, 'corrections': [], 'fallback_events': [{
        'id': row['id'], 'origin': row['url'], 'verified_at': '2026-10-19',
        'expires_on': row['date'], 'event': row}]}


class CatalogoUnico(unittest.TestCase):
    def test_registry_real_presente_e_valido(self):
        real = load_registry()
        self.assertEqual(real['schema'], 1)
        self.assertGreaterEqual(len(real['corrections']), 10)
        self.assertEqual(len(real['fallback_events']), 4)
        self.assertTrue(all('verified_at' in row for row in real['corrections']))

    def test_erro_se_registo_ausente(self):
        with self.assertRaises(FileNotFoundError):
            load_registry(ROOT / 'excepcoes_nao_existe.json')

    def test_erro_se_fonte_agregadora(self):
        bad = registry(event(url='https://trilhosecaminhadas.pt/percursos/evento_info.php?id=1'))
        with TemporaryDirectory() as folder:
            p = Path(folder) / 'registo.json'
            p.write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_registry(p)

    def test_erro_se_origem_diferente(self):
        bad = registry()
        bad['fallback_events'][0]['origin'] = 'https://outra-fonte.com/anuncio'
        with TemporaryDirectory() as folder:
            p = Path(folder) / 'registo.json'
            p.write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_registry(p)

    def test_validade_em_falta_gera_erro_claro(self):
        bad = registry()
        bad['fallback_events'][0].pop('expires_on')
        with TemporaryDirectory() as folder:
            p = Path(folder) / 'registo.json'
            p.write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'validade'):
                load_registry(p)

    def test_validade_com_data_impossivel_rejeitada(self):
        bad = registry()
        bad['fallback_events'][0]['expires_on'] = '2026-02-30'
        bad['fallback_events'][0]['event']['date'] = '2026-02-30'
        with TemporaryDirectory() as folder:
            p = Path(folder) / 'registo.json'
            p.write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Data inválida'):
                load_registry(p)

    def test_inserir_manual_quando_nao_recolhido(self):
        out, _, counters = integrate([], registry(), today=date(2026, 10, 23))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['id'], 'manual')
        self.assertEqual(out[0]['source_name'], 'excepcao_confirmada')
        self.assertEqual(out[0]['last_seen_at'], '2026-10-19')
        self.assertEqual(counters['added'], 1)

    def test_excepcao_nao_substitui_recolha_oficial(self):
        official = event()
        official['km'] = 13
        out, _, counters = integrate([official], registry(), today=date(2026, 10, 23))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['id'], 'oficial')
        self.assertEqual(out[0]['km'], 13)
        self.assertIn('manual', out[0]['alias_ids'])
        self.assertEqual(counters['already_collected'], 1)

    def test_id_antigo_mantido_em_recolhas_repetidas(self):
        out, _, _ = integrate([event()], registry(), today=date(2026, 10, 23))
        again, _, _ = integrate(out, registry(), today=date(2026, 10, 23))
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0]['alias_ids'], ['manual'])

    def test_dia_expirado_nao_inserido(self):
        out, _, counters = integrate([], registry(), today=date(2026, 11, 15))
        self.assertEqual(out, [])
        self.assertEqual(counters['expired'], 1)

    def test_diferentes_edicoes_mesma_pagina_nao_se_fundem(self):
        existing = event('oficial','Faias — manhã',url='https://organizador.pt/calendario')
        extra = event('extra','Faias — tarde',url='https://organizador.pt/calendario')
        out, _, _ = integrate([existing], registry(extra), today=date(2026, 10, 23))
        self.assertEqual(len(out), 2)

    def test_mesmo_titulo_e_data_fundem_sem_url_individual(self):
        existing = event('oficial','Faias — manhã',url='https://organizador.pt/calendario')
        extra = event('extra','Faias — manhã',url='https://organizador.pt/calendario')
        out, _, _ = integrate([existing], registry(extra), today=date(2026, 10, 23))
        self.assertEqual(len(out), 1)

    def test_diferentes_datas_nao_se_fundem(self):
        out, _, _ = integrate([event(date_='2026-11-15')], registry(), today=date(2026, 10, 23))
        self.assertEqual(len(out), 2)

    def test_registo_verificado_nao_inventa_revalidacao(self):
        r = load_registry()
        out, _, _ = integrate([], r, today=date(2026, 10, 23))
        self.assertEqual(len(out), 4)
        self.assertTrue(all(x['last_seen_at'] <= '2026-10-23' for x in out))
        self.assertTrue(all(x['source_name'] == 'excepcao_confirmada' for x in out))

    def test_multidias_nao_aceite_nas_excepcoes(self):
        r = load_registry()
        ids = {f['event']['id'] for f in r['fallback_events']}
        self.assertNotIn('haa-estrela-20261205', ids)

    def test_ids_unicos_apos_integrar_duas_vezes(self):
        r = load_registry()
        output, _, _ = integrate([], r, today=date(2026, 10, 23))
        output, _, _ = integrate(output, r, today=date(2026, 10, 23))
        self.assertEqual(len(output), len({i['id'] for i in output}))


if __name__ == '__main__':
    unittest.main()
