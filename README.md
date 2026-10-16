# grog-architecture-skills

Эталон устройства проектов для Claude Code и всё, что к нему нужно, одним маркетплейсом плагинов.

## Установка на сервер (один раз)

```bash
git clone https://github.com/oggrebnev-maker/grog-architecture-skills
bash grog-architecture-skills/install.sh
```

Скрипт ставит плагины (`architecture`, `owner-skills`, `superpowers`, `claude-md-management`, `caveman`), навыки Firecrawl и find-skills, Firecrawl CLI, общие правила владельца в `~/.claude/CLAUDE.md` и запреты чтения секретов. Повторный запуск безопасен.

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
| `skills/` | ваши навыки (плагин `owner-skills`): `design-transfer` и следующие |

## Добавить свой навык

1. Положить папку навыка в `skills/<имя>/` — внутри `SKILL.md` с шапкой `name` и `description` (когда вызывать). Можно через сайт GitHub: Add file → Upload files, путь `skills/<имя>/`.
2. Сохранить (commit) в `main`. Номер версии не нужен: каждый коммит в `owner-skills` — обновление.
3. На серверах: `claude plugin update owner-skills@grog-architecture-skills` или `bash install.sh`, затем перезапустить Claude Code.

Если навыку нужны программы — `setup.sh` в его папке; `install.sh` его не знает, запустить `bash skills/<имя>/setup.sh` или попросить Claude дописать его в `install.sh`.

## Обновление эталона

Правка → версия +1 в `plugins/architecture/.claude-plugin/plugin.json` → строка в `CHANGELOG.md` → тесты `bash test.sh` → push. На серверах: `claude plugin update architecture@grog-architecture-skills`.
