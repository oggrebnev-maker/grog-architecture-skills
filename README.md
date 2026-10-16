# grog-architecture-skills

Эталон устройства проектов для Claude Code и всё, что к нему нужно, одним маркетплейсом плагинов.

## Для Claude: «загрузи и примени»

Владелец дал ссылку на этот репозиторий и сказал «загрузи и примени». Порядок:

1. Клон: нет папки `~/grog-architecture-skills` — `git clone https://github.com/oggrebnev-maker/grog-architecture-skills ~/grog-architecture-skills`; есть — `git -C ~/grog-architecture-skills pull --ff-only`.
2. `bash ~/grog-architecture-skills/install.sh` — приводит сервер в соответствие списку `plugins/architecture/skills/architecture/manifest.json`: ставит недостающее, обновляет установленное, ничего не удаляет, сообщает лишнее. Строки `!!` — выполнить вручную или сказать владельцу, что нужно от него (например `firecrawl login`, `sudo apt-get install jq`).
3. `~/.claude/CLAUDE.md.grog-new` появился — сравнить с `~/.claude/CLAUDE.md`; правила владельца из эталона заменяют старые, личное из старого файла перенести в новый.
4. Попросить владельца перезапустить Claude Code: плагины включаются после перезапуска.
5. После перезапуска, в папке проекта — навык `architecture`: «приведи проект в соответствие».

## Установка на сервер вручную

```bash
git clone https://github.com/oggrebnev-maker/grog-architecture-skills ~/grog-architecture-skills
bash ~/grog-architecture-skills/install.sh
```

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
