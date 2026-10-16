#!/bin/bash
# PreToolUse(Bash): keeps secret files (.env, .env.*, .envrc) out of shell commands.
# Allowed: .env.example, and env-names.sh <file> on its own (prints key names only).
# A safety net, not a sandbox: it reads the command text, it cannot see what a program opens.
if ! command -v jq >/dev/null 2>&1; then
  echo "guard-env: jq не установлен — команда заблокирована. Установить jq (раздел «Инструменты» эталона)." >&2
  exit 2
fi
cmd=$(jq -r '.tool_input.command // empty')
deny() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
if printf '%s' "$cmd" | grep -qE '^[[:space:]]*((ba)?sh[[:space:]]+)?[A-Za-z0-9_./-]*env-names\.sh[[:space:]]+[A-Za-z0-9_./-]+[[:space:]]*$'; then
  exit 0
fi
rest=$(printf '%s' "$cmd" | sed -E 's/\.env\.example//g')
if printf '%s' "$rest" | grep -qE '(^|[^A-Za-z0-9_])\.env(rc)?([^A-Za-z0-9_]|$)'; then
  deny "Доступ к файлам секретов (.env, .env.*, .envrc) запрещён. Имена ключей: bash <путь>/env-names.sh <файл>; значения не читать."
fi
exit 0
