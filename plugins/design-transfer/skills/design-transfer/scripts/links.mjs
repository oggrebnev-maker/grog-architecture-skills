// Live controls check: after a transfer every link and button of the page works or leads to a reserved address.
//   node links.mjs [url paths...]
// Fails on: <a> without href or with href="#"/"javascript:"; disabled or aria-disabled controls outside
// cfg.links.allowDisabled selectors; forms without action or with a disabled submit; addresses missing from
// the link registry (cfg.links.registry: JSON {"key": {"url": "/path or /path/{slug}", "title", "status"}}).
import { readFileSync, existsSync } from 'node:fs';
import { config, browser } from './lib.mjs';
const cfg = config();
const L = cfg.links ?? {};
const paths = process.argv.slice(2).filter(a => !a.startsWith('--'));
const urls = (paths.length ? paths : [...new Set(cfg.sections.map(s => s.url ?? '/'))]);
let registry = null;
if (L.registry) {
  if (!existsSync(L.registry)) { console.error(`link registry not found: ${L.registry}`); process.exit(2); }
  const reg = JSON.parse(readFileSync(L.registry, 'utf8'));
  registry = Object.values(reg).map(e => new RegExp('^' + (typeof e === 'string' ? e : e.url)
    .replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\\?\{[^}]+\\?\}/g, '[^/?#]+') + '$'));
}
const ignore = (L.ignore ?? []).map(p => new RegExp(p)); // e.g. "^/assets/", "^mailto:"
const b = await browser();
let bad = 0;
for (const path of urls) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto(cfg.preview + path, { waitUntil: 'networkidle' });
  const found = await p.evaluate(allow => {
    const name = e => `${e.tagName.toLowerCase()}${e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).join('.') : ''} «${(e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 40)}»`;
    const allowed = e => allow.some(s => e.closest(s));
    const out = { dead: [], disabled: [], forms: [], hrefs: [] };
    for (const a of document.querySelectorAll('a')) {
      const h = a.getAttribute('href');
      if (!h || h === '#' || h.startsWith('javascript:')) out.dead.push(name(a)); else out.hrefs.push(h);
    }
    for (const e of document.querySelectorAll('button:disabled, input:disabled, [aria-disabled="true"]'))
      if (!allowed(e) && !e.closest('[hidden]')) out.disabled.push(name(e));
    for (const f of document.querySelectorAll('form')) {
      if (!f.getAttribute('action')) out.forms.push(`${name(f)}: no action`);
      const s = f.querySelector('[type=submit], button:not([type])');
      if (!s) out.forms.push(`${name(f)}: no submit`); else if (s.disabled) out.forms.push(`${name(f)}: submit disabled`);
      if (f.getAttribute('action')) out.hrefs.push(f.getAttribute('action'));
    }
    return out;
  }, L.allowDisabled ?? []);
  const unregistered = registry ? [...new Set(found.hrefs)].map(h => h.replace(/^https?:\/\/[^/]+/, ''))
    .filter(h => !ignore.some(r => r.test(h)))
    .filter(h => { const bare = h.replace(/[?#].*$/, '') || '/'; return !registry.some(r => r.test(h) || r.test(bare)); }) : [];
  for (const [label, list] of [['dead link', found.dead], ['disabled control', found.disabled], ['form', found.forms], ['not in registry', unregistered]])
    for (const item of list) { bad++; console.log(`FAIL ${path}: ${label}: ${item}`); }
  console.log(`${path}: ${found.hrefs.length} addresses checked`);
  await p.close();
}
await b.close();
console.log(bad ? `${bad} problems` : 'all links and controls are live');
process.exit(bad ? 1 : 0);
