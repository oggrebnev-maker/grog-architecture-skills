# grog-architecture-skills

Эталон устройства проектов для Claude Code и всё, что к нему нужно, одним маркетплейсом плагинов.

## Установка

**Обычным сообщением Claude** (в папке проекта):

> Загрузи и примени https://github.com/oggrebnev-maker/grog-architecture-skills — разрешаю запустить его bootstrap.sh: он ставит плагины из manifest.json и меняет настройки Claude (~/.claude/settings.json, ~/.claude/CLAUDE.md, .claude/settings.json проекта).

**Командой** (терминал, или в чате Claude Code с `!` в начале строки):

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/oggrebnev-maker/grog-architecture-skills/main/bootstrap.sh)
```

Строка скачивает или обновляет репозиторий в `~/grog-architecture-skills`, ставит всё по `manifest.json` (`install.sh`), приводит настройки текущего проекта (`project.sh`) и записывает в `~/.claude/settings.json` исключение автоматического режима для скриптов этого репозитория — после первой установки обновлять можно короткой фразой «обнови и примени grog-architecture-skills». Ничего не удаляет; лишнее называет. Затем — перезапустить Claude Code.

Отдельно: только сервер — `bash ~/grog-architecture-skills/install.sh`; только проект — `bash ~/grog-architecture-skills/project.sh <папка проекта>`.

## Для Claude: как выполнить «загрузи и примени»

1. Есть `~/grog-architecture-skills` — `bash ~/grog-architecture-skills/bootstrap.sh`; нет — `bash <(curl -fsSL https://raw.githubusercontent.com/oggrebnev-maker/grog-architecture-skills/main/bootstrap.sh)`. Запускать из папки проекта.
2. Защита автоматического режима не дала запустить (настройки Claude меняет только владелец) — не обходить: дать владельцу строку `! bash <(curl -fsSL https://raw.githubusercontent.com/oggrebnev-maker/grog-architecture-skills/main/bootstrap.sh)` и фразу из раздела «Установка» на будущее.
3. По выводу: строки `!!` — что сделать вручную (`sudo apt-get install jq`, `firecrawl login`); `~/.claude/CLAUDE.md.grog-new` — сравнить с `~/.claude/CLAUDE.md`, правила эталона перенести.
4. Попросить владельца перезапустить Claude Code; после — навык `architecture`: «приведи проект в соответствие».

Что ставится и зачем — `plugins/architecture/skills/architecture/manifest.json`: плагины (эталон, навыки владельца, superpowers, caveman, skill-creator, pr-review-toolkit, typescript-lsp, security-guidance, playwright, hookify, claude-md-management), навыки (Firecrawl, find-skills, research-first), программы (Firecrawl CLI, TypeScript language server), общие правила владельца, запреты чтения секретов. Добавить сторонний инструмент — строка в `manifest.json`, затем `bash install.sh`.

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
