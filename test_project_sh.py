"""Tests for project.sh: brings a project's Claude settings, .gitignore and env-names.sh in line with the standard."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = json.loads((HERE / 'plugins/architecture/skills/architecture/templates/project-settings.json').read_text())


def run(project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(['bash', str(HERE / 'project.sh'), str(project)], capture_output=True, text=True)


class ProjectShTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.p)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bare_project_gets_settings_gitignore_and_script(self):
        out = run(self.p)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        s = json.loads((self.p / '.claude/settings.json').read_text())
        self.assertEqual(s['enabledPlugins'], TEMPLATE['enabledPlugins'])
        self.assertEqual(s['extraKnownMarketplaces'], TEMPLATE['extraKnownMarketplaces'])
        self.assertIn('Read(./node_modules/**)', s['permissions']['deny'])
        self.assertIn('CLAUDE.local.md', (self.p / '.gitignore').read_text())
        self.assertTrue((self.p / 'scripts/env-names.sh').is_file())

    def test_existing_settings_are_kept_and_merged(self):
        (self.p / '.claude').mkdir()
        (self.p / '.claude/settings.json').write_text(json.dumps({
            'permissions': {'deny': ['Read(./secret/**)'], 'allow': ['Bash(npm test)']},
            'enabledPlugins': {'my-plugin@my-market': True, 'caveman@caveman': False},
            'hooks': {'Stop': []}}))
        (self.p / '.gitignore').write_text('build/\n')
        self.assertEqual(run(self.p).returncode, 0)
        s = json.loads((self.p / '.claude/settings.json').read_text())
        self.assertIn('Read(./secret/**)', s['permissions']['deny'])
        self.assertEqual(s['permissions']['allow'], ['Bash(npm test)'])
        self.assertTrue(s['enabledPlugins']['my-plugin@my-market'])
        self.assertFalse(s['enabledPlugins']['caveman@caveman'], 'owner choice to disable must survive')
        self.assertTrue(s['enabledPlugins']['architecture@grog-architecture-skills'])
        self.assertIn('hooks', s)
        text = (self.p / '.gitignore').read_text()
        self.assertTrue(text.startswith('build/\n'))
        self.assertIn('.envrc', text)

    def test_second_run_changes_nothing(self):
        run(self.p)
        before = {f: (self.p / f).read_text() for f in ['.claude/settings.json', '.gitignore', 'scripts/env-names.sh']}
        run(self.p)
        after = {f: (self.p / f).read_text() for f in before}
        self.assertEqual(before, after)

    def test_extensions_get_their_own_settings(self):
        ext = self.p / 'add-ons' / 'demo'
        ext.mkdir(parents=True)
        (ext / 'CLAUDE.md').write_text('# demo\n')
        self.assertEqual(run(self.p).returncode, 0)
        self.assertTrue((ext / '.claude/settings.json').is_file())


if __name__ == '__main__':
    unittest.main()
