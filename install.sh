#!/bin/bash
# One-time setup of the owner's Claude Code toolkit on a server. Safe to run again.
# Usage: git clone https://github.com/oggrebnev-maker/grog-architecture-skills && bash grog-architecture-skills/install.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$HERE/plugins/architecture/skills/architecture"
fail=0
step() { printf '\n== %s\n' "$1"; }
warn() { printf '!! %s\n' "$1"; fail=1; }

step "Программы"
for tool in git node npx python3 claude; do
  command -v "$tool" >/dev/null || warn "нет $tool — установить и запустить install.sh снова"
done
if ! command -v jq >/dev/null; then
  if command -v apt-get >/dev/null && sudo -n true 2>/dev/null; then sudo apt-get install -y jq >/dev/null && echo "jq установлен"
  else warn "нет jq — установить (sudo apt-get install jq): без него хук guard-env блокирует все команды"; fi
fi
if ! command -v firecrawl >/dev/null; then
  npm install -g firecrawl-cli >/dev/null 2>&1 && echo "firecrawl-cli установлен" || warn "firecrawl-cli не установился: npm install -g firecrawl-cli"
fi
firecrawl --status 2>/dev/null | grep -q Authenticated || echo "-- Firecrawl: выполнить вход — firecrawl login"

step "Маркетплейсы и плагины Claude Code"
if command -v claude >/dev/null; then
  for m in oggrebnev-maker/grog-architecture-skills obra/superpowers-marketplace anthropics/claude-plugins-official JuliusBrussee/caveman; do
    claude plugin marketplace add "$m" >/dev/null 2>&1 || true
  done
  claude plugin marketplace update >/dev/null 2>&1 || true
  for p in architecture@grog-architecture-skills superpowers@superpowers-marketplace claude-md-management@claude-plugins-official caveman@caveman; do
    if claude plugin list 2>/dev/null | grep -q "${p%@*}@${p#*@}"; then echo "есть: $p"
    else claude plugin install "$p" --scope user >/dev/null 2>&1 && echo "установлен: $p" || warn "не установился плагин $p"; fi
  done
fi

step "Навыки (установщик skills)"
npx -y skills add firecrawl/skills -g --all >/dev/null 2>&1 && echo "навыки firecrawl" || warn "не установились навыки firecrawl/skills"
npx -y skills add vercel-labs/skills -g --all >/dev/null 2>&1 && echo "навык find-skills" || warn "не установился vercel-labs/skills"

step "Общие правила владельца (~/.claude/CLAUDE.md)"
mkdir -p "$HOME/.claude"
if [ ! -f "$HOME/.claude/CLAUDE.md" ]; then
  cp "$SKILL/user_claude.md" "$HOME/.claude/CLAUDE.md" && echo "положены"
elif cmp -s "$SKILL/user_claude.md" "$HOME/.claude/CLAUDE.md"; then
  echo "совпадают с эталоном"
else
  cp "$SKILL/user_claude.md" "$HOME/.claude/CLAUDE.md.grog-new"
  echo "-- отличаются: новая версия в ~/.claude/CLAUDE.md.grog-new — сравнить и перенести (diff ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.grog-new)"
fi

step "Запреты чтения секретов (~/.claude/settings.json)"
python3 - "$HOME/.claude/settings.json" <<'PY'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]); home = str(pathlib.Path.home())
data = json.loads(p.read_text()) if p.exists() and p.read_text().strip() else {}
deny = data.setdefault('permissions', {}).setdefault('deny', [])
names = ['.env', '.env.local', '.env.development', '.env.production', '.env.test', '.envrc']
added = 0
for verb in ('Read', 'Edit'):
    for n in names:
        rule = f'{verb}(/{home}/**/{n})'
        if rule not in deny:
            deny.append(rule); added += 1
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print(f'добавлено правил: {added}')
PY

step "Проверка"
python3 -B "$SKILL/scripts/check.py" "$PWD" 2>/dev/null | grep -E '^(FAIL|WARN) .*\[~\]|^Итого|^Эталон' || true
[ $fail -eq 0 ] && echo "Готово." || { echo "Есть шаги выше со знаком !! — выполнить их вручную."; exit 1; }
