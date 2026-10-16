#!/usr/bin/env bash
# One-time setup of the browser checks: Playwright + Chromium in a stable folder outside the plugin
# (the plugin folder is replaced on every update). Safe to run again.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DT_HOME="${DESIGN_TRANSFER_HOME:-$HOME/.local/share/design-transfer}"
mkdir -p "$DT_HOME"
cp "$HERE/package.json" "$DT_HOME/package.json"
cd "$DT_HOME"
npm install --no-audit --no-fund
npx playwright install chromium
echo "design-transfer: ready ($DT_HOME)"
