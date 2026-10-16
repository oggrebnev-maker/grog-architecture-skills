"""Tests for check.py: each test builds a throwaway project and asserts the verdicts."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check  # noqa: E402

SECTIONS = ['Проект', 'Агенты', 'Инструменты', 'Данные', 'Стиль работы', 'Порядок работы', 'Грабли', 'Решения']
PLUGINS = {'architecture@grog-architecture-skills': True, 'superpowers@superpowers-marketplace': True}
MARKETS = {'grog-architecture-skills': {'source': {'source': 'github', 'repo': 'oggrebnev-maker/grog-architecture-skills'}},
           'superpowers-marketplace': {'source': {'source': 'github', 'repo': 'obra/superpowers-marketplace'}}}


def write_unit(root: Path, with_git: bool = True) -> None:
    if with_git:
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
    body = '# P\n\n' + ''.join(f'## {i}. {s}\n- x\n\n' for i, s in enumerate(SECTIONS, 1))
    body = body.replace('## 3. Инструменты\n- x\n', '## 3. Инструменты\n| `architecture` | эталон |\n| `superpowers` | процесс |\n')
    (root / 'CLAUDE.md').write_text(body)
    (root / 'AGENTS.md').write_text('Главный файл инструкций — `CLAUDE.md` в этой папке.\n')
    (root / 'PROGRESS.md').write_text('# Прогресс\n')
    (root / 'context').mkdir(exist_ok=True)
    for f in ['product', 'architecture', 'conventions', 'glossary']:
        (root / 'context' / f'{f}.md').write_text('# x\n- y\n')
    (root / 'docs').mkdir(exist_ok=True)
    for f in ['DECISIONS', 'CHANGE_REQUESTS', 'REUSE_DECISIONS']:
        (root / 'docs' / f'{f}.md').write_text('# x\n')
    (root / '.claude' / 'rules').mkdir(parents=True, exist_ok=True)
    (root / '.claude' / 'rules' / 'git.md').write_text('# Git\n- Коммит — только свои пути.\n')
    (root / '.claude' / 'settings.json').write_text(json.dumps({
        'permissions': {'deny': ['Read(./node_modules/**)', 'Read(./docs/archive/**)']},
        'extraKnownMarketplaces': MARKETS, 'enabledPlugins': PLUGINS}))
    (root / '.gitignore').write_text('.env\n.env.*\n!.env.example\n.envrc\nCLAUDE.local.md\n.claude/settings.local.json\nnode_modules/\n__pycache__/\n')


def verdicts(root: Path, where: str = '.') -> dict:
    return {r.code: r.level for r in check.run(root, user_home=None) if r.where == where}


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'proj'
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def append(self, rel: str, text: str) -> None:
        with open(self.root / rel, 'a') as f:
            f.write(text)

    def test_compliant_project_has_no_failures(self):
        write_unit(self.root)
        bad = [r for r in check.run(self.root, user_home=None) if r.level != 'OK']
        self.assertEqual(bad, [])

    def test_missing_git_fails(self):
        write_unit(self.root, with_git=False)
        self.assertEqual(verdicts(self.root)['git'], 'FAIL')

    def test_subfolder_of_repo_is_in_git(self):
        write_unit(self.root)
        sub = self.root / 'add-ons' / 'x'
        sub.mkdir(parents=True)
        write_unit(sub, with_git=False)
        self.assertEqual(verdicts(sub)['git'], 'OK')

    def test_agents_md_symlink_fails(self):
        write_unit(self.root)
        (self.root / 'AGENTS.md').unlink()
        os.symlink('CLAUDE.md', self.root / 'AGENTS.md')
        self.assertEqual(verdicts(self.root)['agents-md'], 'FAIL')

    def test_claude_md_symlink_fails(self):
        write_unit(self.root)
        text = (self.root / 'CLAUDE.md').read_text()
        (self.root / 'CLAUDE.md').unlink()
        (self.root / 'AGENTS.md').write_text(text)
        os.symlink('AGENTS.md', self.root / 'CLAUDE.md')
        self.assertEqual(verdicts(self.root)['claude-md'], 'FAIL')

    def test_missing_sections_fail(self):
        write_unit(self.root)
        (self.root / 'CLAUDE.md').write_text('# P\n## 1. Проект\n')
        self.assertEqual(verdicts(self.root)['claude-md-sections'], 'FAIL')

    def test_sections_out_of_order_fail(self):
        write_unit(self.root)
        text = (self.root / 'CLAUDE.md').read_text().replace('## 1. Проект', '## 9. Проект')
        (self.root / 'CLAUDE.md').write_text(text)
        self.assertEqual(verdicts(self.root)['claude-md-sections'], 'FAIL')

    def test_long_claude_md_warns(self):
        write_unit(self.root)
        self.append('CLAUDE.md', '- строка\n' * 200)
        self.assertEqual(verdicts(self.root)['claude-md-size'], 'WARN')

    def test_heavy_claude_md_warns(self):
        write_unit(self.root)
        self.append('CLAUDE.md', ('ж' * 400 + '\n') * 30)
        self.assertEqual(verdicts(self.root)['claude-md-size'], 'WARN')

    def test_rules_import_fails(self):
        write_unit(self.root)
        self.append('CLAUDE.md', '@.claude/rules/git.md\n')
        self.assertEqual(verdicts(self.root)['rules-import'], 'FAIL')

    def test_missing_context_fails(self):
        write_unit(self.root)
        (self.root / 'context' / 'glossary.md').unlink()
        self.assertEqual(verdicts(self.root)['context'], 'FAIL')

    def test_decisions_elsewhere_named_in_claude_md_passes(self):
        write_unit(self.root)
        (self.root / 'docs' / 'DECISIONS.md').unlink()
        (self.root / 'docs' / 'OWNER_DECISIONS.md').write_text('# x\n')
        self.append('CLAUDE.md', 'Решения — `docs/OWNER_DECISIONS.md`.\n')
        self.assertEqual(verdicts(self.root)['work-files'], 'OK')

    def test_other_decisions_files_do_not_count(self):
        write_unit(self.root)
        (self.root / 'docs' / 'DECISIONS.md').unlink()
        (self.root / 'docs' / 'DEPENDENCY_DECISIONS.md').write_text('# x\n')
        self.append('CLAUDE.md', 'Готовое — `docs/REUSE_DECISIONS.md`, зависимости — `docs/DEPENDENCY_DECISIONS.md`.\n')
        self.assertEqual(verdicts(self.root)['work-files'], 'FAIL')

    def test_progress_elsewhere_named_in_claude_md_passes(self):
        write_unit(self.root)
        (self.root / 'PROGRESS.md').unlink()
        (self.root / 'docs' / 'PROGRESS.md').write_text('# x\n')
        self.append('CLAUDE.md', 'Прогресс — `docs/PROGRESS.md`.\n')
        self.assertEqual(verdicts(self.root)['progress'], 'OK')

    def test_long_progress_warns(self):
        write_unit(self.root)
        self.append('PROGRESS.md', '- запись\n' * 400)
        self.assertEqual(verdicts(self.root)['progress-size'], 'WARN')

    def test_missing_work_file_fails(self):
        write_unit(self.root)
        (self.root / 'docs' / 'CHANGE_REQUESTS.md').unlink()
        self.assertEqual(verdicts(self.root)['work-files'], 'FAIL')

    def test_broken_path_reference_fails(self):
        write_unit(self.root)
        self.append('.claude/rules/git.md', '- Отчёт — `docs/manual/FEATURES.md`.\n')
        self.assertEqual(verdicts(self.root)['paths'], 'FAIL')

    def test_placeholders_and_globs_are_not_paths(self):
        write_unit(self.root)
        self.append('CLAUDE.md', 'Шаблон `docs/<имя>.md`, все `src/**/*.ts`, сайт `https://x.ru/a.md`, команда `npm run build`.\n')
        self.assertEqual(verdicts(self.root)['paths'], 'OK')

    def test_output_files_marked_as_created_are_not_broken(self):
        write_unit(self.root)
        self.append('.claude/rules/git.md', '- Справочник `docs/manual/MANUAL.md` создаётся по команде; шаблон `docs/P##_NAME.md`.\n')
        self.assertEqual(verdicts(self.root)['paths'], 'OK')

    def test_claudeignore_fails(self):
        write_unit(self.root)
        (self.root / '.claudeignore').write_text('dist\n')
        self.assertEqual(verdicts(self.root)['claudeignore'], 'FAIL')

    def test_missing_specific_read_deny_warns(self):
        write_unit(self.root)
        (self.root / 'docs' / 'archive').mkdir()
        (self.root / 'node_modules').mkdir()
        data = json.loads((self.root / '.claude' / 'settings.json').read_text())
        data['permissions']['deny'] = ['Read(./dist/**)']
        (self.root / '.claude' / 'settings.json').write_text(json.dumps(data))
        self.assertEqual(verdicts(self.root)['settings'], 'WARN')

    def test_local_files_must_be_gitignored_before_they_exist(self):
        write_unit(self.root)
        (self.root / '.gitignore').write_text('node_modules/\n')
        self.assertEqual(verdicts(self.root)['local-files'], 'FAIL')

    def test_plugin_not_described_in_claude_md_fails(self):
        write_unit(self.root)
        data = json.loads((self.root / '.claude' / 'settings.json').read_text())
        data['enabledPlugins']['caveman@caveman'] = True
        data['extraKnownMarketplaces']['caveman'] = {'source': {'source': 'github', 'repo': 'JuliusBrussee/caveman'}}
        (self.root / '.claude' / 'settings.json').write_text(json.dumps(data))
        self.assertEqual(verdicts(self.root)['tools-table'], 'FAIL')

    def test_plugin_marketplace_must_be_declared(self):
        write_unit(self.root)
        data = json.loads((self.root / '.claude' / 'settings.json').read_text())
        del data['extraKnownMarketplaces']['superpowers-marketplace']
        (self.root / '.claude' / 'settings.json').write_text(json.dumps(data))
        self.assertEqual(verdicts(self.root)['plugins'], 'FAIL')

    def test_architecture_plugin_required(self):
        write_unit(self.root)
        data = json.loads((self.root / '.claude' / 'settings.json').read_text())
        del data['enabledPlugins']['architecture@grog-architecture-skills']
        (self.root / '.claude' / 'settings.json').write_text(json.dumps(data))
        self.assertEqual(verdicts(self.root)['plugins'], 'FAIL')

    def test_vague_wording_warns_in_agents_too(self):
        write_unit(self.root)
        (self.root / '.claude' / 'agents').mkdir()
        (self.root / '.claude' / 'agents' / 'a.md').write_text('---\nname: a\n---\nПо возможности пиши хорошо.\n')
        self.assertEqual(verdicts(self.root)['wording'], 'WARN')

    def test_caps_inside_code_blocks_ignored(self):
        write_unit(self.root)
        self.append('CLAUDE.md', '```\nMUST NEVER ALWAYS\n```\n')
        self.assertEqual(verdicts(self.root)['wording'], 'OK')

    def test_nested_extensions_are_checked(self):
        write_unit(self.root)
        ext = self.root / 'add-ons' / 'demo' / 'add-ons' / 'inner'
        ext.mkdir(parents=True)
        (ext / 'CLAUDE.md').write_text('# inner\n')
        codes = verdicts(self.root, 'add-ons/demo/add-ons/inner')
        self.assertEqual(codes['agents-md'], 'FAIL')
        self.assertEqual(codes['context'], 'FAIL')

    def test_user_level_checks(self):
        write_unit(self.root)
        home = Path(self.tmp.name) / 'home'
        (home / '.claude').mkdir(parents=True)
        res = {r.code: r.level for r in check.run(self.root, user_home=home)}
        self.assertEqual(res['user-claude-md'], 'FAIL')
        self.assertEqual(res['user-plugin'], 'FAIL')
        (home / '.claude' / 'CLAUDE.md').write_text('# Общие правила владельца\n')
        (home / '.claude' / 'settings.json').write_text(json.dumps({'enabledPlugins': {'architecture@grog-architecture-skills': True}}))
        res = {r.code: r.level for r in check.run(self.root, user_home=home)}
        self.assertEqual(res['user-claude-md'], 'OK')
        self.assertEqual(res['user-plugin'], 'OK')

    def test_cli_exit_code_and_version(self):
        write_unit(self.root)
        ok = subprocess.run([sys.executable, '-B', str(Path(check.__file__)), str(self.root), '--no-user'], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertIn('Эталон', ok.stdout)
        (self.root / 'AGENTS.md').unlink()
        bad = subprocess.run([sys.executable, '-B', str(Path(check.__file__)), str(self.root), '--no-user'], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn('FAIL', bad.stdout)


if __name__ == '__main__':
    unittest.main()
