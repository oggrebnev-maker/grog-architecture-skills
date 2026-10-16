---
name: architecture
description: Use when the owner asks to set up, check, audit or bring a project into line with his infrastructure standard ("приведи проект в соответствие", "проверь структуру", "архитектура проекта", "эталон", "инфраструктура"), when starting a new project, or when CLAUDE.md, AGENTS.md, context/, .claude/ rules, agents, hooks, settings or project plugins are being created or reorganized.
---

# Architecture — эталон устройства проекта

Эталон — `project_architecture.md` в папке этого навыка. Скрипт `scripts/check.py` проверяет механическое; суждение (содержание `context/`, формулировки правил) — твоё. Шаблоны — `templates/`.

## Порядок

1. **Проверка до.** `python3 -B <папка навыка>/scripts/check.py <проект>` — сохранить вывод (первая строка — версия эталона).
2. **Прочитать** `project_architecture.md`: новый проект — раздел 3А, существующий — 3Б.
3. **Перестройка** шагами, коммит на шаг, тесты проекта после шага. Необходимое делать сразу; план заранее — только для необратимого, удаления, чужой незавершённой работы или бизнес-решения владельца (раздел 2).
4. **Проверка после.** Снова `check.py`: FAIL 0; WARN — исправить или объяснить. Затем пункты раздела 18, которые скрипт не видит.
5. **Отчёт владельцу**: что смотреть, вывод `check.py` до/после, что не сделано и почему, «Ждёт решения» списком; вопрос — один.

## Настройки Claude меняет владелец

Claude Code блокирует попытки Claude менять свои настройки: `~/.claude/*`, `.claude/settings*.json` проекта, установку плагинов. Снимают блок: исключение для скриптов этого репозитория, которое `install.sh` записывает в `~/.claude/settings.json`, или сообщение владельца, где названы конкретные изменения (фраза — README репозитория, раздел «Установка»). Скрипты запускать: `bash ~/grog-architecture-skills/bootstrap.sh` из папки проекта. Защита всё равно отказала — не обходить, а дать строку владельцу, начинающуюся с `!` (её запускает он сам):
- сервер и проект целиком: `! bash <(curl -fsSL https://raw.githubusercontent.com/oggrebnev-maker/grog-architecture-skills/main/bootstrap.sh)`;
- только настройки проекта: `! bash ~/grog-architecture-skills/project.sh .`.
Затем — попросить перезапустить Claude Code.

## Перед записью в CLAUDE.md или AGENTS.md

`ls -la CLAUDE.md AGENTS.md`. Символьная ссылка — сначала `rm`, потом писать обычный файл: запись через ссылку затирает файл, на который она указывает.

## Уровень пользователя

`check.py` без `--no-user` проверяет `~/.claude/CLAUDE.md`, плагин `architecture`, `jq`, Firecrawl. Не хватает — строка владельцу `! bash <(curl -fsSL https://raw.githubusercontent.com/oggrebnev-maker/grog-architecture-skills/main/bootstrap.sh)` (раздел 17). `~/.claude` действует во всех проектах: менять — с разрешения владельца.

## Соблазны

| Соблазн | Вместо этого |
|---|---|
| Удалить старый отчёт или правило | `git mv` в `docs/archive/<тема>/` |
| Заполнить `context/product.md` догадками | факты из документов и кода; нет — `уточнить:` и вопрос владельцу |
| «Готово» по ощущению | вывод `check.py` с FAIL 0 в отчёте |
| Повторить общие правила владельца в проекте | раздел 5 `CLAUDE.md` — только отличия проекта |
| Править эталон под проект | отличие — в `docs/DECISIONS.md` проекта; полезное всем — в `grog-architecture-skills` (версия, CHANGELOG) |
