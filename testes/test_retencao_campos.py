"""Preservação de aliases e dificuldade pelo coletor seguido do normalizador."""
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
import recolher
import normalizar_eventos as normalizar


class RetencaoCampos(unittest.TestCase):
    def setUp(self):
        self.event = {'id': 'publicado', 'title': 'Caminhada pela Serra',
                      'date': (date.today() + timedelta(days=10)).isoformat(),
                      'organizer': 'Clube X', 'url': 'https://clube.pt/eventos/serra',
                      'start': 'Posto de Turismo de Óbidos', 'town': 'Óbidos'}

    def pipeline(self, previous, fresh):
        with TemporaryDirectory() as folder, ExitStack() as stack:
            path = Path(folder) / 'eventos.json'
            path.write_text(json.dumps({'events': previous}), encoding='utf-8')
            stack.enter_context(patch.object(recolher, 'OUT', path))
            stack.enter_context(patch.object(recolher, 'SOURCES', [{'organizer': 'Clube X'}]))
            stack.enter_context(patch.object(recolher, 'collect_source', return_value=copy.deepcopy(fresh)))
            self.assertEqual(recolher.main(), 0)
            collected = json.loads(path.read_text(encoding='utf-8'))['events']
            stack.enter_context(patch.object(normalizar, 'CATALOG', path))
            stack.enter_context(patch.object(normalizar, 'git_previous', return_value=copy.deepcopy(previous)))
            stack.enter_context(patch('consolidar_catalogo.load_registry', return_value={
                'schema': 1, 'corrections': [], 'fallback_events': []}))
            stack.enter_context(patch.object(normalizar, 'enrich_official', return_value={}))
            stack.enter_context(patch.object(normalizar, 'PHOTO_VISITS_PER_RUN', 0))
            stack.enter_context(patch.object(normalizar, 'report'))
            self.assertEqual(normalizar.main(), 0)
            return collected, json.loads(path.read_text(encoding='utf-8'))['events']

    def test_mesma_edicao_preserva_aliases_e_dificuldade(self):
        old = {**self.event, 'alias_ids': ['anterior', 'historico', 'publicado'], 'difficulty': 3}
        new = {**self.event, 'alias_ids': ['novo-alias', 'historico'], 'difficulty': None}
        for stage in self.pipeline([old], [new]):
            self.assertEqual(stage[0]['id'], 'publicado')
            self.assertEqual(stage[0].get('alias_ids'), ['anterior', 'historico', 'novo-alias'])
            self.assertEqual(stage[0].get('difficulty'), 3)

    def test_dificuldade_atual_prevalece(self):
        old = {**self.event, 'difficulty': 3}
        for stage in self.pipeline([old], [{**self.event, 'difficulty': 2}]):
            self.assertEqual(stage[0]['difficulty'], 2)

    def test_outra_edicao_ou_fonte_nao_herda_dificuldade(self):
        for change in ({'date': (date.today() + timedelta(days=11)).isoformat()},
                       {'url': 'https://clube.pt/eventos/outro'}, {'organizer': 'Outro Clube'}):
            with self.subTest(change=change):
                for stage in self.pipeline([{**self.event, 'difficulty': 3}],
                                           [{**self.event, **change, 'difficulty': None}]):
                    self.assertIsNone(stage[0].get('difficulty'))

    def test_dificuldade_antiga_invalida_nao_e_recuperada(self):
        for value in (0, 6, True, 'difícil'):
            with self.subTest(value=value):
                for stage in self.pipeline([{**self.event, 'difficulty': value}], [self.event]):
                    self.assertIsNone(stage[0].get('difficulty'))

    def test_aliases_em_colisao_nao_sao_atribuidos_a_outro_evento(self):
        old = {**self.event, 'alias_ids': ['historico', 'outro', 'partilhado']}
        other = {**self.event, 'id': 'outro', 'title': 'Outro percurso',
                 'url': 'https://clube.pt/eventos/outro', 'alias_ids': ['partilhado']}
        for stage in self.pipeline([old, other], [self.event, other]):
            events = {e['id']: e for e in stage}
            self.assertEqual(events['publicado'].get('alias_ids'), ['historico'])
            self.assertFalse(events['outro'].get('alias_ids'))


if __name__ == '__main__':
    unittest.main()
