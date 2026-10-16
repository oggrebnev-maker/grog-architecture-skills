"""Tests for templates/env-names.sh: names out, values never."""
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / 'templates' / 'env-names.sh'


class EnvNamesTest(unittest.TestCase):
    def test_prints_names_only(self):
        with tempfile.NamedTemporaryFile('w', suffix='.secrets', delete=False) as f:
            f.write('# comment\nAPI_KEY=supersecret\nexport DB_URL="postgres://u:p@h/db"\n\n  SPACED = x\nnot a line\n')
        out = subprocess.run(['bash', str(SCRIPT), f.name], capture_output=True, text=True)
        Path(f.name).unlink()
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.split(), ['API_KEY', 'DB_URL', 'SPACED'])
        self.assertNotIn('supersecret', out.stdout + out.stderr)
        self.assertNotIn('postgres', out.stdout + out.stderr)

    def test_missing_file_fails(self):
        out = subprocess.run(['bash', str(SCRIPT), '/nonexistent/file'], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)


if __name__ == '__main__':
    unittest.main()
