#!/usr/bin/env bash
# One-time setup of the browser checks: Playwright + Chromium inside the skill folder (free, offline after).
set -euo pipefail
cd "$(dirname "$0")"
npm install --no-audit --no-fund
npx playwright install chromium
echo "design-transfer: ready"
