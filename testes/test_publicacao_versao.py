"""Executar o passo real de publicação contra um remoto Git local."""
import os
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash') or ('C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else None)


@unittest.skipUnless(BASH and Path(BASH).is_file() and shutil.which('git'), 'Git e Bash necessários')
class PublicacaoVersao(unittest.TestCase):
    def git(self, *args, cwd=None):
        return subprocess.check_output(['git', *args], cwd=cwd or self.repo,
                                       stderr=subprocess.PIPE, text=True).strip()

    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.repo = self.root / 'produtor'
        self.repo.mkdir()
        self.remote = self.root / 'remote.git'
        self.git('init', '--bare', str(self.remote))
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Teste')
        self.git('config', 'user.email', 'teste@example.org')
        (self.repo / 'eventos.json').write_text('original', encoding='utf-8')
        (self.repo / 'rotas_precalculadas.json').write_text('{}', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-m', 'Base validada')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('push', '-u', 'origin', 'main')
        workflow = (ROOT / '.github/workflows/actualizar.yml').read_text(encoding='utf-8')
        step = workflow.split('      - name: Publicar catálogo e cache de viagens\n', 1)[1]
        script = textwrap.dedent(step.split('        run: |\n', 1)[1].split('      - name:', 1)[0])
        self.script = self.root / 'publicar.sh'
        self.script.write_text(script, encoding='utf-8', newline='\n')
        self.output = self.root / 'output.txt'
        self.output.touch()

    def publish(self):
        env = {**os.environ, 'GITHUB_SHA': self.base, 'GITHUB_REF_NAME': 'main',
               'GITHUB_OUTPUT': str(self.output)}
        return subprocess.run([BASH, '-e', str(self.script)], cwd=self.repo, env=env,
                              capture_output=True, text=True)

    def test_publica_apenas_sobre_a_base_validada(self):
        (self.repo / 'eventos.json').write_text('recolhido', encoding='utf-8')
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        tip = self.git('--git-dir', str(self.remote), 'rev-parse', 'refs/heads/main')
        self.assertEqual(self.git('rev-parse', tip + '^'), self.base)
        self.assertEqual(self.git('show', tip + ':eventos.json'), 'recolhido')
        self.assertIn('changed=true', self.output.read_text())

    def test_avanco_remoto_nao_faz_rebase_nem_publica(self):
        editor = self.root / 'editor'
        self.git('clone', '--branch', 'main', str(self.remote), str(editor))
        self.git('config', 'user.name', 'Editor', cwd=editor)
        self.git('config', 'user.email', 'editor@example.org', cwd=editor)
        (editor / 'recolher.py').write_text('# outra versão', encoding='utf-8')
        self.git('add', '.', cwd=editor)
        self.git('commit', '-m', 'Novo coletor', cwd=editor)
        newer = self.git('rev-parse', 'HEAD', cwd=editor)
        self.git('push', 'origin', 'main', cwd=editor)
        (self.repo / 'eventos.json').write_text('recolhido com código antigo', encoding='utf-8')
        result = self.publish()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git('--git-dir', str(self.remote), 'rev-parse', 'refs/heads/main'), newer)
        self.assertEqual(self.git('--git-dir', str(self.remote), 'show', 'main:eventos.json'), 'original')
        self.assertNotIn('changed=true', self.output.read_text())
        self.assertEqual(self.git('rev-parse', 'HEAD^'), self.base)

    def test_sem_alteracoes_nao_cria_commit(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)
        self.assertNotIn('changed=true', self.output.read_text())


if __name__ == '__main__':
    unittest.main()
