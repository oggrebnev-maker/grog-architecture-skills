"""Tests for guard.py: the design-system guard of a designer's package and of the site's code."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).parent / 'guard.py'

TOKENS = {'type': {'families': {'sans': 'Onest, sans-serif'}, 'groups': [{'styles': [
    {'name': 'h2', 'fontSize': '32px', 'lineHeight': '40px', 'fontWeight': 700},
    {'name': 'body', 'fontSize': '15px', 'lineHeight': '22px', 'fontWeight': 400}]}]}}
VARIABLES = {'variables': {
    'text-primary': {'type': 'color', 'value': [{'value': '#111111', 'theme': {'mode': 'light'}},
                                                {'value': '#eeeeee', 'theme': {'mode': 'dark'}}]},
    'bg-overlay': {'type': 'color', 'value': '#13141d7a'},
    'font-sans': {'type': 'string', 'value': 'Onest, sans-serif'}}}


def frame(width, texts):
    spans = ''.join(f'<span data-pencil-name="t" style="{s}">{t}</span>' for t, s in texts)
    return f'<html><body><div data-pencil-name="Экран" style="width: {width}px">{spans}</div></body></html>'


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / 'tokens.json').write_text(json.dumps(TOKENS))
        self.pkg = self.dir / 'pkg'
        (self.pkg / 'source').mkdir(parents=True)
        (self.pkg / 'source' / 'variables.json').write_text(json.dumps(VARIABLES))
        (self.pkg / 'html').mkdir()
        self.config({'guard': {'tokens': 'tokens.json', 'roles': {'h2': {'390': [26, 32, 700]}}}})

    def config(self, c):
        (self.dir / 'design-transfer.json').write_text(json.dumps({'outDir': 'out', **c}))

    def run_guard(self, *args):
        out = subprocess.run([sys.executable, '-I', str(GUARD), *args], cwd=self.dir, capture_output=True, text=True)
        return out.returncode, out.stdout + out.stderr

    def put(self, name, html):
        (self.pkg / 'html' / name).write_text(html)

    def test_clean_package(self):
        ok = 'font-family: Onest; font-size: 32px; line-height: 40px; font-weight: 700; color: #111111'
        self.put('list-1440-light.html', frame(1440, [('Пользователи', ok)]))
        self.put('list-1440-dark.html', frame(1440, [('Пользователи', ok.replace('#111111', '#eeeeee'))]))
        self.put('list-390-light.html', frame(390, [('Пользователи', ok.replace('32px', '26px').replace('40px', '32px'))]))
        code, out = self.run_guard('package', 'pkg')
        self.assertEqual(code, 0, out)

    def test_text_outside_roles_is_severe(self):
        self.put('list-1440-light.html', frame(1440, [('Почта', 'font-size: 14px; line-height: 20px; font-weight: 400')]))
        code, out = self.run_guard('package', 'pkg')
        self.assertEqual(code, 2)
        self.assertIn('T3', out)

    def test_role_of_other_width_is_severe(self):
        # 32/40 is h2 at 1440, not at 390 (26/32 there)
        self.put('list-390-light.html', frame(390, [('Заголовок', 'font-size: 32px; line-height: 40px; font-weight: 700')]))
        code, out = self.run_guard('package', 'pkg')
        self.assertEqual(code, 2)

    def test_auto_line_height_checks_size_and_weight(self):
        self.put('list-1440-light.html', frame(1440, [('Текст', 'font-size: 15px; font-weight: 400')]))
        self.assertEqual(self.run_guard('package', 'pkg')[0], 0)

    def test_colour_of_other_theme_is_severe(self):
        self.put('list-1440-dark.html', frame(1440, [('Текст', 'font-size: 15px; line-height: 22px; color: #111111')]))
        code, out = self.run_guard('package', 'pkg')
        self.assertEqual(code, 2)
        self.assertIn('в теме dark', out)

    def test_translucent_colour_and_rgba(self):
        self.put('list-1440-light.html', frame(1440, [('Текст', 'font-size: 15px; line-height: 22px; background-color: rgba(19, 20, 29, 0.48)')]))
        self.assertEqual(self.run_guard('package', 'pkg')[0], 0)

    def test_frame_without_width_in_name(self):
        self.put('h0TKPu.html', frame(1440, [('Почта', 'font-size: 14px; line-height: 20px')]))
        self.assertEqual(self.run_guard('package', 'pkg')[0], 2)

    def test_nothing_to_check_is_severe(self):
        code, out = self.run_guard('package', 'pkg')
        self.assertEqual(code, 2)
        self.assertIn('S0', out)

    def test_allow_with_owner_yes(self):
        self.put('list-1440-light.html', frame(1440, [('Почта', 'font-size: 14px; line-height: 20px; font-weight: 400')]))
        self.config({'guard': {'tokens': 'tokens.json', 'allow': [{'code': 'T3', 'match': '14/20', 'owner': '20.10.2026'}]}})
        self.assertEqual(self.run_guard('package', 'pkg')[0], 0)

    def test_sync_appends_report_to_channel(self):
        self.put('list-1440-light.html', frame(1440, [('Почта', 'font-size: 14px; line-height: 20px')]))
        (self.dir / 'HANDOFF.md').write_text('# Канал\n')
        self.run_guard('package', 'pkg', '--sync', 'HANDOFF.md')
        text = (self.dir / 'HANDOFF.md').read_text()
        self.assertIn('## Разработчик → Дизайнер · ', text)
        self.assertIn('T3', text)

    def test_code_baseline_counts_each_place(self):
        app = self.dir / 'frontend' / 'app'
        app.mkdir(parents=True)
        page = app / 'page.jsx'
        page.write_text('<div style={{ a: 1 }} />\n')
        self.assertEqual(self.run_guard('code')[0], 2)
        self.run_guard('code', '--write-baseline')
        self.assertEqual(self.run_guard('code')[0], 0)
        page.write_text('<div style={{ a: 1 }} />\n<div style={{ b: 2 }} />\n')  # a second one in the same file is new
        self.assertEqual(self.run_guard('code')[0], 2)

    def test_system_prints_palette_by_theme(self):
        code, out = self.run_guard('system', 'pkg')
        s = json.loads(out)
        self.assertEqual(s['palette']['#EEEEEE'], ['dark'])
        self.assertEqual(s['roles']['h2']['390'], [26.0, 32.0, 700])
        self.assertIn('Onest', s['fonts'])


if __name__ == '__main__':
    unittest.main()
