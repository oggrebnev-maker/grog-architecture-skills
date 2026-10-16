#!/bin/bash
# One line for the owner: download or update the toolkit, set up the server, then the project in the current folder.
# Usage (terminal, or in Claude Code chat with "!" in front):
#   bash <(curl -fsSL https://raw.githubusercontent.com/oggrebnev-maker/grog-architecture-skills/main/bootstrap.sh)
set -uo pipefail
DIR="${GROG_DIR:-$HOME/grog-architecture-skills}"
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull -q --ff-only || echo "-- не обновился $DIR, беру текущую версию"
else git clone -q https://github.com/oggrebnev-maker/grog-architecture-skills "$DIR" || { echo "!! не скачался репозиторий"; exit 1; }; fi
bash "$DIR/install.sh"; status=$?
if git -C "$PWD" rev-parse --show-toplevel >/dev/null 2>&1; then
  printf '\n== Проект %s\n' "$(git -C "$PWD" rev-parse --show-toplevel)"
  bash "$DIR/project.sh" "$(git -C "$PWD" rev-parse --show-toplevel)"
fi
exit $status
