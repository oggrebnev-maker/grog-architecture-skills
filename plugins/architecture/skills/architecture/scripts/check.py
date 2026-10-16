#!/usr/bin/env python3
"""Mechanical check of a project against the owner's infrastructure standard (project_architecture.md).

Usage: python3 -B check.py [project_dir] [--no-user]
Prints one line per check: LEVEL code [where]: message. Exit 1 if any FAIL.
Judgement items (content of context/, wording beyond simple patterns) stay with the agent.
"""
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
SECTIONS = ['Проект', 'Агенты', 'Инструменты', 'Данные', 'Стиль', 'Порядок работы', 'Грабли', 'Решения']
CONTEXT_FILES = ['product.md', 'architecture.md', 'conventions.md', 'glossary.md']
WORK_FILES = {'DECISIONS': ('DECISIONS', 'OWNER_DECISIONS'), 'CHANGE_REQUESTS': ('CHANGE_REQUESTS',), 'REUSE_DECISIONS': ('REUSE_DECISIONS',)}
MUST_IGNORE = ['.env', '.env.local', '.envrc', 'CLAUDE.local.md', '.claude/settings.local.json']
REQUIRED_PLUGIN = 'architecture@grog-architecture-skills'
BUILTIN_MARKETS = {'claude-plugins-official'}
VAGUE = re.compile(r'старайс|по возможности|желательно|если получится|\bхорошо\b|\bпонятно\b|\bкачественно\b|\btry to\b|\bif possible\b', re.I)
CAPS = re.compile(r'\b(ВАЖНО|НИКОГДА|ВСЕГДА|ОБЯЗАТЕЛЬНО|MUST|NEVER|ALWAYS|CRITICAL|IMPORTANT)\b')
CODE_BLOCK = re.compile(r'```.*?```', re.S)
PATH_TOKEN = re.compile(r'`([^`\s]+)`')
CREATED = re.compile(r'создаётся|создается|появится|будет создан', re.I)
SKIP_DIRS = {'node_modules', '.git', 'dist', '.next', 'vendor', 'archive'}
MAX_LINES, MAX_BYTES, MAX_LOG_LINES = 150, 20000, 300


@dataclass
class Result:
    level: str  # OK | WARN | FAIL
    code: str
    where: str
    message: str


def version() -> str:
    manifest = HERE.parent.parent.parent / '.claude-plugin' / 'plugin.json'
    try:
        return json.loads(manifest.read_text(encoding='utf-8')).get('version', '?')
    except (OSError, json.JSONDecodeError):
        return '?'


def _read(p: Path) -> str:
    return p.read_text(encoding='utf-8') if p.is_file() else ''


def _git_top(root: Path):
    out = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    return Path(out.stdout.strip()) if out.returncode == 0 else None


def _named_elsewhere(root: Path, text: str, names) -> bool:
    for token in PATH_TOKEN.findall(text):
        if token.endswith('.md') and Path(token).stem in names:
            if (root / token).is_file() or any((p / token).is_file() for p in root.parents):
                return True
    return False


def _looks_like_path(token: str) -> bool:
    if any(c in token for c in '<>*{}…$|#') or '://' in token or token.startswith(('~', '-', '/', '@', '.claude/rules/*')):
        return False
    return '/' in token and re.search(r'\.(md|json|ts|mjs|js|py|sh|sql|yaml|yml)$', token) is not None


def check_paths(root: Path, files) -> list:
    """Paths in backticks must exist relative to the unit, the file's folder, or any parent (shared repo docs)."""
    broken = []
    for f in files:
        text = CODE_BLOCK.sub('', _read(f))
        text = '\n'.join(line for line in text.splitlines() if not CREATED.search(line))
        for token in PATH_TOKEN.findall(text):
            if not _looks_like_path(token):
                continue
            bases = [root, f.parent] + list(root.parents)
            if not any((b / token).exists() for b in bases):
                broken.append(f'{f.relative_to(root)}: {token}')
    return broken


def check_unit(root: Path, where: str, is_extension: bool) -> list:
    out = []

    def add(level, code, message):
        out.append(Result(level, code, where, message))

    claude = root / 'CLAUDE.md'
    text = _read(claude)
    if not claude.exists():
        add('FAIL', 'claude-md', 'нет CLAUDE.md')
    elif claude.is_symlink():
        add('FAIL', 'claude-md', 'CLAUDE.md — символьная ссылка; должен быть обычным файлом с правилами')
    else:
        add('OK', 'claude-md', 'CLAUDE.md — обычный файл')

    if text:
        heads = re.findall(r'^##\s+(\d+)\.\s+(.+)$', text, re.M)
        numbered = [(int(n), t.strip()) for n, t in heads]
        expected_ok = len(numbered) >= 8 and all(numbered[i][0] == i + 1 and numbered[i][1].lower().startswith(SECTIONS[i].lower()) for i in range(8))
        add('OK' if expected_ok else 'FAIL', 'claude-md-sections',
            'восемь разделов по порядку' if expected_ok else 'нужны разделы «## 1. Проект» … «## 8. Решения» по порядку: ' + ', '.join(SECTIONS))
        lines, size = text.count('\n'), len(text.encode('utf-8'))
        heavy = lines > MAX_LINES or size > MAX_BYTES
        add('WARN' if heavy else 'OK', 'claude-md-size', f'CLAUDE.md — {lines} строк, {size} байт (ориентир до {MAX_LINES} строк и {MAX_BYTES} байт)')
        if re.search(r'^\s*@\.?/?\.claude/rules/', text, re.M):
            add('FAIL', 'rules-import', 'CLAUDE.md импортирует .claude/rules через @ — убрать, правила грузятся сами')
        else:
            add('OK', 'rules-import', 'нет @-импортов правил')

    agents = root / 'AGENTS.md'
    body = _read(agents)
    if not agents.exists():
        add('FAIL', 'agents-md', 'нет AGENTS.md (короткая ссылка на CLAUDE.md)')
    elif agents.is_symlink():
        add('FAIL', 'agents-md', 'AGENTS.md — символьная ссылка: запись в него затрёт CLAUDE.md; сделать обычным файлом')
    elif 'CLAUDE.md' not in body or body.count('\n') > 8:
        add('FAIL', 'agents-md', 'AGENTS.md должен быть короткой ссылкой на CLAUDE.md')
    else:
        add('OK', 'agents-md', 'AGENTS.md — ссылка на CLAUDE.md')

    missing = [f for f in CONTEXT_FILES if not _read(root / 'context' / f).strip()]
    add('FAIL' if missing else 'OK', 'context', ('нет или пусто в context/: ' + ', '.join(missing)) if missing else 'context/ заполнен')

    top = _git_top(root)
    add('OK' if top else 'FAIL', 'git', 'в git' if top else 'нет git — git init')

    progress = root / 'PROGRESS.md'
    has_progress = progress.is_file() or _named_elsewhere(root, text, {'PROGRESS'})
    add('OK' if has_progress else 'FAIL', 'progress', 'PROGRESS.md ' + ('есть' if has_progress else 'нет'))
    long_logs = [str(p.relative_to(root)) for p in [progress, root / 'docs' / 'HANDOFF.md'] if _read(p).count('\n') > MAX_LOG_LINES]
    add('WARN' if long_logs else 'OK', 'progress-size',
        (f'длиннее {MAX_LOG_LINES} строк — старое в docs/archive/: ' + ', '.join(long_logs)) if long_logs else 'журналы короткие')

    gaps = [f'docs/{key}.md' for key, names in WORK_FILES.items()
            if not any((root / 'docs' / f'{n}.md').is_file() for n in names) and not _named_elsewhere(root, text, set(names))]
    add('FAIL' if gaps else 'OK', 'work-files', ('нет рабочих файлов: ' + ', '.join(gaps)) if gaps else 'рабочие файлы на месте')

    rules = root / '.claude' / 'rules'
    if not is_extension:
        add('OK' if rules.is_dir() and any(rules.glob('*.md')) else 'FAIL', 'rules', '.claude/rules/ ' + ('есть' if rules.is_dir() else 'нет'))

    settings_path = root / '.claude' / 'settings.json'
    try:
        settings = json.loads(_read(settings_path)) if settings_path.is_file() else None
    except json.JSONDecodeError:
        settings = None
    if settings is None:
        add('FAIL', 'settings', 'нет .claude/settings.json или он не читается')
        settings = {}
    else:
        deny = ' '.join(str(d) for d in settings.get('permissions', {}).get('deny', []))
        need = [d for d in ['node_modules', 'docs/archive'] if (root / d).exists() and d not in deny]
        add('WARN' if need else 'OK', 'settings', ('нет запрета Read(...) для: ' + ', '.join(need)) if need else 'запреты чтения есть')

    plugins = settings.get('enabledPlugins', {}) or {}
    markets = settings.get('extraKnownMarketplaces', {}) or {}
    problems = []
    if not is_extension and not plugins.get(REQUIRED_PLUGIN):
        problems.append(f'не включён {REQUIRED_PLUGIN}')
    for pid, on in plugins.items():
        market = pid.split('@', 1)[1] if '@' in pid else ''
        if on and market and market not in markets and market not in BUILTIN_MARKETS:
            problems.append(f'маркетплейс {market} для {pid} не объявлен в extraKnownMarketplaces')
    add('FAIL' if problems else 'OK', 'plugins', '; '.join(problems) if problems else 'плагины и маркетплейсы объявлены')
    undocumented = [pid for pid, on in plugins.items() if on and pid.split('@')[0] not in text]
    add('FAIL' if undocumented else 'OK', 'tools-table',
        ('плагины не описаны в разделе 3 CLAUDE.md: ' + ', '.join(undocumented)) if undocumented else 'все плагины проекта описаны в CLAUDE.md')

    add('FAIL' if (root / '.claudeignore').exists() else 'OK', 'claudeignore',
        '.claudeignore не работает в Claude Code — заменить запретами Read(...)' if (root / '.claudeignore').exists() else 'нет .claudeignore')

    if top:
        res = subprocess.run(['git', '-C', str(root), 'check-ignore', '--no-index', *MUST_IGNORE], capture_output=True, text=True)
        ignored = set(res.stdout.split())
        notignored = [f for f in MUST_IGNORE if f not in ignored]
        add('FAIL' if notignored else 'OK', 'local-files', ('не в .gitignore: ' + ', '.join(notignored)) if notignored else 'секреты и личные файлы не попадут в git')

    rule_files = [claude] + sorted(rules.glob('**/*.md')) + sorted((root / '.claude' / 'agents').glob('*.md')) + sorted((root / '.claude' / 'skills').glob('*/SKILL.md'))
    rule_files = [f for f in rule_files if f.is_file()]
    vague, loud = [], []
    for f in rule_files:
        raw = CODE_BLOCK.sub('', _read(f))
        rel = str(f.relative_to(root))
        vague += [f'{rel}:{n}' for n, line in enumerate(raw.splitlines(), 1) if VAGUE.search(line)]
        if len(CAPS.findall(raw)) > 1:
            loud.append(rel)
    if vague or loud:
        parts = (['непроверяемые пожелания: ' + ', '.join(vague)] if vague else []) + (['капс больше одного раза: ' + ', '.join(loud)] if loud else [])
        add('WARN', 'wording', '; '.join(parts))
    else:
        add('OK', 'wording', 'нет непроверяемых пожеланий и лишнего капса')

    broken = check_paths(root, rule_files + [root / 'context' / f for f in CONTEXT_FILES if (root / 'context' / f).is_file()])
    add('FAIL' if broken else 'OK', 'paths', ('ссылки на несуществующие файлы: ' + '; '.join(broken)) if broken else 'ссылки на файлы целы')
    return out


def find_extensions(root: Path, base: Path = None):
    base = base or root
    folder = base / 'add-ons'
    if folder.is_dir():
        for d in sorted(folder.iterdir()):
            if d.is_dir() and d.name not in SKIP_DIRS:
                yield d
                yield from find_extensions(root, d)


def check_user(home: Path) -> list:
    out = []
    claude = _read(home / '.claude' / 'CLAUDE.md')
    out.append(Result('OK' if '# Общие правила владельца' in claude else 'FAIL', 'user-claude-md', '~',
                      '~/.claude/CLAUDE.md ' + ('содержит общие правила' if '# Общие правила владельца' in claude else 'без общих правил — положить user_claude.md')))
    try:
        settings = json.loads(_read(home / '.claude' / 'settings.json') or '{}')
    except json.JSONDecodeError:
        settings = {}
    on = (settings.get('enabledPlugins') or {}).get(REQUIRED_PLUGIN)
    out.append(Result('OK' if on else 'FAIL', 'user-plugin', '~', f'{REQUIRED_PLUGIN} ' + ('включён' if on else 'не установлен — bash install.sh из grog-architecture-skills')))
    out.append(Result('OK' if shutil.which('jq') else 'FAIL', 'jq', '~', 'jq ' + ('есть' if shutil.which('jq') else 'нет — без него хук guard-env блокирует все команды')))
    try:
        status = subprocess.run(['firecrawl', '--status'], capture_output=True, text=True, timeout=30).stdout
        ok = 'Authenticated' in status
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    out.append(Result('OK' if ok else 'WARN', 'tool-firecrawl', '~', 'firecrawl ' + ('вошёл' if ok else 'не установлен или не выполнен вход — firecrawl login')))
    return out


def run(root: Path, user_home=None) -> list:
    root = Path(root).resolve()
    results = check_unit(root, '.', is_extension=False)
    for ext in find_extensions(root):
        results += check_unit(ext, str(ext.relative_to(root)), is_extension=True)
    if user_home is not None:
        results += check_user(Path(user_home))
    return results


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    root = Path(args[0]) if args else Path.cwd()
    results = run(root, user_home=None if '--no-user' in argv else Path.home())
    order = {'FAIL': 0, 'WARN': 1, 'OK': 2}
    print(f'Эталон architecture {version()}')
    for r in sorted(results, key=lambda r: order[r.level]):
        print(f'{r.level:4} {r.code} [{r.where}]: {r.message}')
    fails = sum(r.level == 'FAIL' for r in results)
    warns = sum(r.level == 'WARN' for r in results)
    print(f'Итого: FAIL {fails}, WARN {warns}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
