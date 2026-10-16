"""Tests for guard-env.sh: the PreToolUse hook that keeps secret files out of Bash commands."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).parent / 'guard-env.sh'


def decide(command: str, path_env: str | None = None) -> str:
    env = dict(os.environ)
    if path_env is not None:
        env['PATH'] = path_env
    out = subprocess.run(['bash', str(HOOK)], input=json.dumps({'tool_input': {'command': command}}),
                         capture_output=True, text=True, env=env)
    if out.returncode == 2:
        return 'deny'
    if out.stdout.strip():
        return json.loads(out.stdout)['hookSpecificOutput']['permissionDecision']
    return 'allow'


class GuardEnvTest(unittest.TestCase):
    def test_blocks_env_file(self):
        self.assertEqual(decide('cat ops/' + '.env'), 'deny')

    def test_blocks_env_variants(self):
        for name in ['.env.local', '.env.production', '.envrc']:
            self.assertEqual(decide(f'cat {name}'), 'deny', name)

    def test_allows_example(self):
        self.assertEqual(decide('cat .env.example'), 'allow')

    def test_allows_env_names_script(self):
        self.assertEqual(decide('bash scripts/env-names.sh ops/' + '.env'), 'allow')

    def test_env_names_cannot_smuggle_other_commands(self):
        self.assertEqual(decide('bash scripts/env-names.sh ops/' + '.env; cat ops/' + '.env'), 'deny')

    def test_allows_ordinary_command(self):
        self.assertEqual(decide('ls -la'), 'allow')

    def test_denies_when_jq_missing(self):
        with tempfile.TemporaryDirectory() as d:
            for tool in ['bash', 'sed', 'grep', 'cat', 'printf']:
                real = subprocess.run(['bash', '-c', f'command -v {tool}'], capture_output=True, text=True).stdout.strip()
                if real:
                    os.symlink(real, Path(d) / tool)
            self.assertEqual(decide('ls', path_env=d), 'deny')


if __name__ == '__main__':
    unittest.main()
