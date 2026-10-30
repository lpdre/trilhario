"""O relatório do normalizador deve refletir os estados da monitorização."""
import copy
import json
import sys
import unittest
from contextlib import ExitStack
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import normalizar_eventos as normalizar
from monitorizacao_fontes import SOURCE_STATES, empty_metrics, enrich_catalog


class ResumoFontes(unittest.TestCase):
    def catalog(self):
        return {'events': [{'id': 'evento-publicado', 'title': 'Caminhada pela Serra',
                            'date': (date.today() + timedelta(days=10)).isoformat(),
                            'organizer': 'Clube X', 'url': 'https://clube.pt/eventos/serra',
                            'start': 'Posto de Turismo de Óbidos', 'town': 'Óbidos'}]}

    def summary(self, data):
        with TemporaryDirectory() as folder, ExitStack() as stack:
            catalog = Path(folder) / 'eventos.json'
            catalog.write_text(json.dumps(data), encoding='utf-8')
            stack.enter_context(patch.object(normalizar, 'CATALOG', catalog))
            stack.enter_context(patch.object(normalizar, 'git_previous', return_value=[]))
            stack.enter_context(patch('consolidar_catalogo.load_registry', return_value={
                'schema': 1, 'corrections': [], 'fallback_events': []}))
            stack.enter_context(patch.object(normalizar, 'enrich_official', return_value={}))
            stack.enter_context(patch.object(normalizar, 'PHOTO_VISITS_PER_RUN', 0))
            report = stack.enter_context(patch.object(normalizar, 'report'))
            self.assertEqual(normalizar.main(), 0)
            self.assertEqual(json.loads(catalog.read_text(encoding='utf-8')), data)
        return next(line for line in report.call_args.args[0] if line.startswith('Fontes:'))

    def test_estados_produzidos_pela_monitorizacao_nao_desaparecem(self):
        scenarios = [dict(seen=[{'id': 'evento-publicado'}]),
                     dict(seen=[{'id': 'evento-publicado'}], http_errors=[503]),
                     dict(usable_pages=1), dict(http_errors=[403]),
                     dict(network_errors=1), dict(unusable_pages=1),
                     dict(exceptions=1), dict(usable_pages=1, network_errors=1), {}]
        observations = {f'Fonte {i}': {**empty_metrics(), **values}
                        for i, values in enumerate(scenarios)}
        observations['Outra fonte HTTP'] = {**empty_metrics(), 'http_errors': [500]}
        data = self.catalog()
        enrich_catalog(data, observations, date.today().isoformat() + 'T12:00:00+00:00')
        self.assertEqual({x['state'] for x in data['sources_health'].values()}, set(SOURCE_STATES))
        line = self.summary(copy.deepcopy(data))
        counts = {part.split(' ', 1)[1]: int(part.split(' ', 1)[0])
                  for part in line.removeprefix('Fontes: ').split('; ')}
        self.assertEqual(counts, {state: 2 if state == 'erro_http' else 1 for state in SOURCE_STATES})

    def test_estados_legados_e_novos_continuam_visiveis(self):
        data = self.catalog()
        data['sources_health'] = {state: {'state': state} for state in
                                 ('erro', 'sem_eventos_ou_indisponivel', 'estado_futuro')}
        line = self.summary(data)
        for state in data['sources_health']:
            self.assertIn('1 ' + state, line)

    def test_sem_diagnostico_nao_anuncia_sucesso(self):
        self.assertEqual(self.summary(self.catalog()), 'Fontes: sem diagnóstico disponível')


if __name__ == '__main__':
    unittest.main()
