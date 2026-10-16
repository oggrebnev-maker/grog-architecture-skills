#!/bin/bash
# Brings a server in line with manifest.json: marketplaces, plugins, skills, programs, owner rules, secret guards.
# Safe to run again on a bare or an old server: installs what is missing, reports extras, never deletes.
# Usage: git clone https://github.com/oggrebnev-maker/grog-architecture-skills && bash grog-architecture-skills/install.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$HERE/plugins/architecture/skills/architecture"
MANIFEST="$SKILL/manifest.json"
fail=0
step() { printf '\n== %s\n' "$1"; }
warn() { printf '!! %s\n' "$1"; fail=1; }
list() { python3 -c "import json,sys; [print(x[sys.argv[2]]) for x in json.load(open(sys.argv[1]))[sys.argv[3]]]" "$MANIFEST" "$2" "$1"; }

step "Обновление репозитория"
git -C "$HERE" pull -q --ff-only 2>/dev/null && echo "актуальная версия" || echo "-- git pull не выполнен (нет сети или локальные правки) — ставлю текущую версию"

step "Программы"
for tool in git node npm npx python3 claude; do
  command -v "$tool" >/dev/null || warn "нет $tool — установить и запустить install.sh снова"
done
if ! command -v jq >/dev/null; then
  if command -v apt-get >/dev/null && sudo -n true 2>/dev/null; then sudo apt-get install -y jq >/dev/null && echo "jq установлен"
  else warn "нет jq — sudo apt-get install jq (без него хук guard-env блокирует все команды)"; fi
fi
while read -r pkg; do
  bin=$(python3 -c "import json,sys; print(next(x['bin'] for x in json.load(open(sys.argv[1]))['npm'] if x['package']==sys.argv[2]))" "$MANIFEST" "$pkg")
  if command -v "$bin" >/dev/null; then echo "есть: $pkg"
  else npm install -g "$pkg" >/dev/null 2>&1 && echo "установлен: $pkg" || warn "не установился npm-пакет $pkg"; fi
done < <(list npm package)
firecrawl --status 2>/dev/null | grep -q Authenticated || echo "-- Firecrawl: выполнить вход — firecrawl login"

step "Маркетплейсы и плагины Claude Code"
if command -v claude >/dev/null; then
  while read -r repo; do claude plugin marketplace add "$repo" >/dev/null 2>&1 || true; done < <(list marketplaces repo)
  claude plugin marketplace update >/dev/null 2>&1 || true
  installed=$(claude plugin list 2>/dev/null)
  while read -r p; do
    if grep -q "$p" <<<"$installed"; then
      claude plugin update "$p" >/dev/null 2>&1; echo "есть: $p"
    else
      claude plugin install "$p" --scope user >/dev/null 2>&1 && echo "установлен: $p" || warn "не установился плагин $p"
    fi
  done < <(list plugins id)
fi

step "Навыки (установщик skills)"
while read -r repo; do
  npx -y skills add "$repo" -g --all >/dev/null 2>&1 && echo "есть: $repo" || warn "не установились навыки $repo"
done < <(list skills repo)
while read -r dup; do
  [ -e "$HOME/.claude/skills/$dup" ] && echo "-- лишнее: навык $dup дублирует плагин; убрать: npx skills remove $dup -g"
done < <(list duplicates skill)

step "Настройка навыков"
while read -r script; do
  bash "$HERE/$script" >/dev/null 2>&1 && echo "готово: $script" || warn "не выполнился $script"
done < <(list setup script)

step "Общие правила владельца (~/.claude/CLAUDE.md)"
mkdir -p "$HOME/.claude"
if [ ! -f "$HOME/.claude/CLAUDE.md" ]; then
  cp "$SKILL/user_claude.md" "$HOME/.claude/CLAUDE.md" && echo "положены"
elif cmp -s "$SKILL/user_claude.md" "$HOME/.claude/CLAUDE.md"; then
  echo "совпадают с эталоном"
else
  cp "$SKILL/user_claude.md" "$HOME/.claude/CLAUDE.md.grog-new"
  echo "-- отличаются: новая версия в ~/.claude/CLAUDE.md.grog-new — сравнить и перенести"
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
echo "-- перезапустить Claude Code, чтобы новые плагины включились"
[ $fail -eq 0 ] && echo "Готово." || { echo "Есть шаги со знаком !! — выполнить их вручную."; exit 1; }
