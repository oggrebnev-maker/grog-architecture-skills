// Playwright for the browser checks: the project's own copy if it has one, else the one setup.sh put in
// ~/.local/share/design-transfer (DESIGN_TRANSFER_HOME) — ESM resolves packages from this folder, not from the project.
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join } from 'node:path';

const from = dir => { try { return createRequire(join(dir, 'package.json'))('playwright'); } catch { return null; } };
const pw = from(process.cwd()) ?? from(process.env.DESIGN_TRANSFER_HOME ?? join(homedir(), '.local/share/design-transfer'));
if (!pw) { console.error('playwright not found: run setup.sh of the design-transfer skill'); process.exit(2); }
export const { chromium } = pw;
