"""Owner-level Claude Code settings written by install.sh (run by the owner, never by Claude).

Adds, never removes: read/edit denies for secret files and one auto mode exception that lets Claude run
this toolkit's own scripts when the owner asks in a plain message. Usage: python3 user_settings.py <settings.json> <toolkit dir>
"""
import json
import sys
from pathlib import Path

SECRET_NAMES = ['.env', '.env.local', '.env.development', '.env.production', '.env.test', '.envrc']


def automode_rule(toolkit: str) -> str:
    return (f'Running the owner\'s toolkit scripts bash {toolkit}/bootstrap.sh, bash {toolkit}/install.sh and '
            f'bash {toolkit}/project.sh (repository github.com/oggrebnev-maker/grog-architecture-skills) is allowed when the owner asks to '
            f'install, update or apply the toolkit: they install the plugins listed in its manifest.json and write the owner\'s '
            f'Claude Code settings, which the owner approved once by running install.sh himself')


def apply(path: Path, home: str, toolkit: str) -> None:
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() and path.read_text().strip() else {}
    deny = data.setdefault('permissions', {}).setdefault('deny', [])
    for verb in ('Read', 'Edit'):
        for name in SECRET_NAMES:
            rule = f'{verb}(/{home}/**/{name})'
            if rule not in deny:
                deny.append(rule)
    auto = data.setdefault('autoMode', {})
    allow = auto.get('allow')
    rule = automode_rule(toolkit)
    if allow is None:
        auto['allow'] = ['$defaults', rule]
    elif not any('grog-architecture-skills' in a and 'bootstrap.sh' in a for a in allow):
        allow.append(rule)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    apply(Path(sys.argv[1]), str(Path.home()), sys.argv[2])
    print('запреты чтения секретов и исключение автоматического режима — на месте')
