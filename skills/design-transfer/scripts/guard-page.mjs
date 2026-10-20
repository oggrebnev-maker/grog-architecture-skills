// Страж дизайн-системы на готовых страницах: каждый видимый текст на каждой ширине макета — роль системы
// (размер, межстрочный ±0.5, толщина), шрифт системы, цвета текста, фона и рамок — из палитры. Без ИИ.
//   node guard-page.mjs [/путь ...] [--widths=1440,390] [--write-baseline]
// Пути — design-transfer.json → guard.pages (по умолчанию адреса всех секций). Исключения — guard.allow,
// известные старые нарушения — guard.baseline (ключ "page"). Новое нарушение — код выхода 2.
// Система — та же, что у `guard.py package` (`guard.py system`). Темы — guard.themes: [{"name": "dark", "init": "<JS до
// скриптов страницы>"}]; цвет сверяется с палитрой своей темы. Ответы сервера — "mock" из настроек, как у check.mjs.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { config, browser, open } from './lib.mjs';

const cfg = config();
const g = cfg.guard ?? {};
const args = process.argv.slice(2);
const onlyWidths = args.find(a => a.startsWith('--widths='))?.slice(9).split(',').map(Number);
const writeBaseline = args.includes('--write-baseline');
const paths = args.filter(a => a.startsWith('/'));
const pages = paths.length ? paths : g.pages ?? [...new Set(cfg.sections.map(s => s.url).filter(Boolean))];
const WIDTHS = onlyWidths ?? [1920, 1440, 1024, 768, 390, 360];
const skip = g.pageSkip ?? ['.pc-root'];

// Design system: roles {role: {width|"*": [size, line, weight]}}, palette {"#RRGGBB[AA]": [themes]}, fonts.
const sys = JSON.parse(execFileSync('python3', [join(dirname(fileURLToPath(import.meta.url)), 'guard.py'), 'system'], { encoding: 'utf8' }));
const roles = sys.roles;
const fonts = new Set(sys.fonts);
const inPalette = (c, theme) => { const t = sys.palette[c]; return !!t && (theme === '*' || t.includes('*') || t.includes(theme)); };
const at = (r, w) => r[w] ?? r['*'];
const roleOf = (w, size, line, wt) => Object.entries(roles).find(([, r]) => at(r, w) && at(r, w)[0] === size && Math.abs(at(r, w)[1] - line) <= 0.5 && at(r, w)[2] === wt)?.[0];
const nearest = (w, size, wt) => Object.entries(roles).filter(([, r]) => at(r, w)).map(([n, r]) => [Math.abs(at(r, w)[0] - size) + (at(r, w)[2] === wt ? 0 : 3), n, at(r, w)]).sort((a, b) => a[0] - b[0])[0];
const themes = g.themes ?? [{ name: '*', init: '' }];

const allow = (g.allow ?? []).map(a => ({ code: a.code, rx: new RegExp(a.match) }));
const allowed = (code, text) => allow.some(a => a.code === code && a.rx.test(text));
const baseFile = g.baseline ?? 'scripts/design-guard/baseline.json';
const baseData = existsSync(baseFile) ? JSON.parse(readFileSync(baseFile, 'utf8')) : {};
const known = new Set(baseData.page ?? []);

const b = await browser();
const found = [];
for (const path of pages) {
  for (const theme of themes) {
  for (const w of WIDTHS) {
    const p = await open(b, cfg.preview + path, w, '', 900, theme.init ?? '');
    const items = await p.evaluate((skip) => {
      // #RRGGBB, or #RRGGBBAA when translucent — the palette's form.
      const hex = c => {
        const m = c.match(/rgba?\(([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+))?\)/);
        if (!m || (m[4] !== undefined && Number(m[4]) === 0)) return null;
        const h = x => Math.round(Number(x)).toString(16).padStart(2, '0').toUpperCase();
        return '#' + h(m[1]) + h(m[2]) + h(m[3]) + (m[4] !== undefined && Number(m[4]) < 1 ? h(Number(m[4]) * 255) : '');
      };
      const desc = el => {
        const own = el.closest('[class]');
        const cls = own ? '.' + [...own.classList][0] : el.tagName.toLowerCase();
        return `${cls}${own === el ? '' : ' ' + el.tagName.toLowerCase()}`;
      };
      const out = [];
      for (const el of document.querySelectorAll('body *')) {
        if (skip.some(s => el.closest(s)) || !el.getClientRects().length) continue;
        const cs = getComputedStyle(el);
        if (cs.visibility === 'hidden' || cs.display === 'none') continue;
        const text = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
        const d = desc(el);
        if (text && !['SCRIPT', 'STYLE'].includes(el.tagName)) {
          out.push({ kind: 'text', d, text: text.slice(0, 40), size: parseFloat(cs.fontSize), line: cs.lineHeight === 'normal' ? -1 : parseFloat(cs.lineHeight), weight: Number(cs.fontWeight), family: cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(), color: hex(cs.color) });
        }
        const bg = hex(cs.backgroundColor);
        if (bg) out.push({ kind: 'bg', d, color: bg });
        for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
          if (parseFloat(cs[`border${side}Width`]) > 0 && cs[`border${side}Style`] !== 'none') {
            const c = hex(cs[`border${side}Color`]);
            if (c) out.push({ kind: 'border', d, color: c });
          }
        }
        if (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 && el !== document.activeElement) {
          const c = hex(cs.outlineColor);
          if (c) out.push({ kind: 'outline', d, color: c });
        }
      }
      return out;
    }, skip);
    await p.close();
    const add = (code, d, detail) => {
      const key = `${path} @${w}${theme.name === '*' ? '' : ' ' + theme.name} ${d} ${code} ${detail}`;
      if (!allowed(code, key)) found.push(key);
    };
    for (const it of items) {
      if (it.kind === 'text') {
        if (it.line < 0) add('T3', it.d, `${it.size}/normal ${it.weight} «${it.text}»`);
        else if (!roleOf(w, it.size, it.line, it.weight)) {
          const n = nearest(w, it.size, it.weight);
          add('T3', it.d, `${it.size}/${it.line} ${it.weight} (ближайшая ${n?.[1]} ${n?.[2]?.join('/')})`);
        }
        if (!fonts.has(it.family)) add('T4', it.d, it.family);
        if (it.color && !inPalette(it.color, theme.name)) add('C2', it.d, `текст ${it.color}`);
      } else if (!inPalette(it.color, theme.name)) add('C2', it.d, `${it.kind === 'bg' ? 'фон' : it.kind === 'border' ? 'рамка' : 'обводка'} ${it.color}`);
    }
  }
  }
}
await b.close();

const unique = [...new Set(found)];
if (writeBaseline) {
  baseData.page = unique.sort();
  mkdirSync(dirname(baseFile), { recursive: true });
  writeFileSync(baseFile, JSON.stringify(baseData, null, 1) + '\n');
  console.log(`baseline: ${unique.length} known places on ${pages.length} pages`);
  process.exit(0);
}
const fresh = unique.filter(x => !known.has(x));
mkdirSync(cfg.outDir, { recursive: true });
writeFileSync(`${cfg.outDir}/guard-page.json`, JSON.stringify({ new: fresh, known: unique.length - fresh.length }, null, 1));
for (const x of fresh.slice(0, 200)) console.log('NEW', x);
if (fresh.length > 200) console.log(`… ещё ${fresh.length - 200}, полный список — ${cfg.outDir}/guard-page.json`);
console.log(`design system on pages: ${fresh.length} new, ${unique.length - fresh.length} known (baseline ${baseFile}); ${pages.length} pages × ${WIDTHS.length} widths × ${themes.length} themes`);
process.exit(fresh.length ? 2 : 0);
