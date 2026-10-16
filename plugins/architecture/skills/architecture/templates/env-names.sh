#!/bin/bash
# Prints only the key names from a secrets file (one per line). Values are never printed.
# Usage: bash scripts/env-names.sh <file>   — the guard-env hook allows exactly this form.
set -euo pipefail
file="${1:?usage: env-names.sh <file>}"
[ -f "$file" ] || { echo "нет файла: $file" >&2; exit 1; }
sed -nE 's/^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=.*/\2/p' "$file"
