"""Tests for user_settings.py: owner-level Claude Code settings written by install.sh."""
import json
import tempfile
import unittest
from pathlib import Path

import user_settings as us


class UserSettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'settings.json'

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        return json.loads(self.path.read_text())

    def test_bare_settings_get_denies_and_automode_allow(self):
        us.apply(self.path, home='/home/u', toolkit='/home/u/grog-architecture-skills')
        d = self.load()
        self.assertIn('Read(//home/u/**/.env)', d['permissions']['deny'])
        self.assertIn('Edit(//home/u/**/.envrc)', d['permissions']['deny'])
        allow = d['autoMode']['allow']
        self.assertEqual(allow[0], '$defaults')
        self.assertTrue(any('grog-architecture-skills' in a and 'bootstrap.sh' in a for a in allow))

    def test_existing_settings_kept_and_not_duplicated(self):
        self.path.write_text(json.dumps({'permissions': {'deny': ['Read(./x)'], 'allow': ['Bash(ls)']},
                                         'autoMode': {'allow': ['$defaults', 'Mine'], 'environment': ['E']},
                                         'hooks': {'Stop': []}, 'enabledPlugins': {'a@b': True}}))
        us.apply(self.path, home='/home/u', toolkit='/home/u/grog-architecture-skills')
        first = self.path.read_text()
        us.apply(self.path, home='/home/u', toolkit='/home/u/grog-architecture-skills')
        self.assertEqual(first, self.path.read_text())
        d = self.load()
        self.assertIn('Read(./x)', d['permissions']['deny'])
        self.assertEqual(d['permissions']['allow'], ['Bash(ls)'])
        self.assertIn('Mine', d['autoMode']['allow'])
        self.assertEqual(d['autoMode']['environment'], ['E'])
        self.assertEqual(d['enabledPlugins'], {'a@b': True})

    def test_allow_list_without_defaults_is_not_changed_in_meaning(self):
        self.path.write_text(json.dumps({'autoMode': {'allow': ['Only mine']}}))
        us.apply(self.path, home='/home/u', toolkit='/t')
        allow = self.load()['autoMode']['allow']
        self.assertNotIn('$defaults', allow)
        self.assertIn('Only mine', allow)
        self.assertEqual(len(allow), 2)


if __name__ == '__main__':
    unittest.main()
