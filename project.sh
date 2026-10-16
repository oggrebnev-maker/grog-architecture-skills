#!/bin/bash
# Brings a project's Claude Code settings in line with the standard. Run by the owner (Claude may not edit its own settings).
# Merges, never removes: .claude/settings.json (marketplaces, plugins, read denies) for the project and every add-ons/** extension,
# missing lines of .gitignore, scripts/env-names.sh. Usage: bash project.sh [project_dir]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$HERE/plugins/architecture/skills/architecture/templates"
ROOT="$(cd "${1:-$PWD}" && pwd)"
python3 - "$ROOT" "$T" <<'PY'
import json, sys, shutil, filecmp
from pathlib import Path
root, tpl_dir = Path(sys.argv[1]), Path(sys.argv[2])
tpl = json.loads((tpl_dir / 'project-settings.json').read_text(encoding='utf-8'))

def units(base: Path):
    yield base
    addons = base / 'add-ons'
    if addons.is_dir():
        for d in sorted(addons.iterdir()):
            if d.is_dir() and (d / 'CLAUDE.md').is_file():
                yield from units(d)

for unit in units(root):
    path = unit / '.claude' / 'settings.json'
    data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() and path.read_text().strip() else {}
    before = json.dumps(data, sort_keys=True)
    deny = data.setdefault('permissions', {}).setdefault('deny', [])
    deny += [r for r in tpl['permissions']['deny'] if r not in deny]
    markets = data.setdefault('extraKnownMarketplaces', {})
    for name, spec in tpl['extraKnownMarketplaces'].items():
        markets.setdefault(name, spec)
    plugins = data.setdefault('enabledPlugins', {})
    for pid, on in tpl['enabledPlugins'].items():
        plugins.setdefault(pid, on)
    if json.dumps(data, sort_keys=True) != before:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'настройки: {path.relative_to(root.parent)}')
    else:
        print(f'настройки в порядке: {path.relative_to(root.parent)}')

ignore = root / '.gitignore'
current = ignore.read_text(encoding='utf-8') if ignore.is_file() else ''
have = {l.strip() for l in current.splitlines()}
missing = [l for l in (tpl_dir / 'gitignore.txt').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#') and l.strip() not in have]
if missing:
    sep = '' if not current or current.endswith('\n') else '\n'
    ignore.write_text(current + sep + '# эталон architecture\n' + '\n'.join(missing) + '\n', encoding='utf-8')
    print('.gitignore: добавлено ' + ', '.join(missing))
else:
    print('.gitignore в порядке')

target = root / 'scripts' / 'env-names.sh'
source = tpl_dir / 'env-names.sh'
if not target.is_file() or not filecmp.cmp(source, target, shallow=False):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(0o755)
    print('scripts/env-names.sh: положен')
else:
    print('scripts/env-names.sh в порядке')
PY
echo "Готово. Перезапустить Claude Code, затем в чате: «приведи проект в соответствие»."
