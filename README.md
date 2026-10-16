# grog-architecture-skills

Эталон устройства проектов для Claude Code и всё, что к нему нужно, одним маркетплейсом плагинов.

## Установка на сервер (один раз)

```bash
git clone https://github.com/oggrebnev-maker/grog-architecture-skills
bash grog-architecture-skills/install.sh
```

Скрипт ставит плагины (`architecture`, `superpowers`, `claude-md-management`, `caveman`), навыки Firecrawl и find-skills, Firecrawl CLI, общие правила владельца в `~/.claude/CLAUDE.md` и запреты чтения секретов. Повторный запуск безопасен.

## В проекте

Скажите Claude: «приведи проект в соответствие». Навык `architecture` проверит проект скриптом, перестроит по эталону и пропишет в `.claude/settings.json` проекта маркетплейсы и плагины — следующий, кто откроет проект, получит их автоматически.

## Что внутри

| Путь | Что |
|---|---|
| `plugins/architecture/skills/architecture/project_architecture.md` | эталон |
| `plugins/architecture/skills/architecture/SKILL.md` | порядок работы Claude |
| `plugins/architecture/skills/architecture/scripts/check.py` | проверка проекта |
| `plugins/architecture/skills/architecture/templates/` | `settings.json` проекта, `.gitignore`, `env-names.sh` |
| `plugins/architecture/skills/architecture/user_claude.md` | общие правила владельца |
| `plugins/architecture/agents/` | `reuse-scout`, `manual-keeper` |
| `plugins/architecture/hooks/` | `guard-env` — не даёт читать секреты |

## Обновление эталона

Правка → версия +1 в `plugins/architecture/.claude-plugin/plugin.json` → строка в `CHANGELOG.md` → тесты `bash test.sh` → push. На серверах: `claude plugin update architecture@grog-architecture-skills`.
