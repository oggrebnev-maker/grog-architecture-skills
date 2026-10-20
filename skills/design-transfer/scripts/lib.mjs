// Shared helpers of the browser checks: config, browser, image comparison in a canvas (no extra deps).
import { chromium } from './pw.mjs';
import { readFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export function config() {
  // DT_CONFIG: another settings file, for a second package in the same project.
  const file = process.env.DT_CONFIG || 'design-transfer.json';
  if (!existsSync(file)) throw new Error(`${file} not found: run from the project root (dt.py init)`);
  const c = JSON.parse(readFileSync(file, 'utf8'));
  c.nameAttr ??= 'data-pencil-name'; c.refDir ??= '.design-transfer/ref'; c.outDir ??= '.design-transfer/out';
  c.thresholds = { sizePx: 1, diffPct: 3, ...(c.thresholds ?? {}) };
  c.sections ??= [];
  mockFile = c.mock ?? null;
  if (process.env.DT_PREVIEW) c.preview = process.env.DT_PREVIEW;  // a second preview (parallel worktree) on its own port
  mkdirSync(c.outDir, { recursive: true });
  return c;
}

/** Section entry -> page, our selector and the export node, taken from the first rule of its map. */
export function sectionOf(entry) {
  const spec = JSON.parse(readFileSync(entry.map, 'utf8'));
  const [selector, path] = spec.rules[0];
  return { key: entry.key, page: entry.page ?? spec.page, url: entry.url ?? '/', selector: entry.selector ?? selector, node: entry.node ?? path, init: entry.init, wait: entry.wait, refCss: entry.refCss };
}

/** A section field may differ per width: "value" or {"*": "value", "768": "other"} (a block placed elsewhere at 768). */
export function atWidth(v, w) {
  return typeof v === 'string' ? v : v?.[String(w)] !== undefined ? v[String(w)] : v?.['*'] ?? Object.values(v ?? {})[0];
}

/** Marks the export node at path "A / B / C" with data-dt-target and returns that selector. Node names may
 * themselves contain " / ", so each step takes the longest run of segments that names a descendant. */
export async function markNode(page, cfg, path) {
  const found = await page.evaluate(([attr, parts]) => {
    let scope = [document.documentElement], i = 0;
    while (i < parts.length) {
      let next = null, step = 0;
      for (let k = parts.length; k > i && !next; k--) {
        const name = parts.slice(i, k).join(' / ');
        for (const root of scope) {
          next = [...root.querySelectorAll(`[${attr}]`)].find(n => n.getAttribute(attr) === name);
          if (next) { step = k - i; break; }
        }
      }
      if (!next) return false;
      scope = [next]; i += step;
    }
    scope[0].setAttribute('data-dt-target', '');
    return true;
  }, [cfg.nameAttr, path.split(' / ').map(n => n.replace(/#\d+$/, ''))]);
  return found ? '[data-dt-target]' : `node "${path}"`;
}

export async function browser() {
  try { return await chromium.launch({ channel: 'chromium' }); }
  catch { return chromium.launch(); }
}

/** Opens a page ready for a stable screenshot: fonts loaded, lazy images decoded, injected CSS applied. */
// "mock": a module whose default export (page) => Promise stubs the site's server answers (page.route),
// for pages that show nothing without data. Applied to our pages only, not to the export.
let mockFile = null, mockFn = null;
export async function open(b, url, width, css = '', height = 1000, init = '') {
  const p = await b.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  if (mockFile && !url.startsWith('file:')) {
    mockFn ??= (await import(pathToFileURL(resolve(mockFile)).href)).default;
    await mockFn(p);
  }
  if (init) await p.addInitScript(init); // e.g. a signed-in preview or an accepted cookie banner: runs before the page's own scripts
  await p.goto(url, { waitUntil: 'networkidle' });
  if (css) await p.addStyleTag({ content: css });
  await p.evaluate(async () => {
    await document.fonts.ready;
    for (const i of document.images) { i.loading = 'eager'; await i.decode().catch(() => {}); }
  });
  return p;
}

export const refUrl = (cfg, page, width) => 'file://' + resolve(cfg.refDir, `${page}-${width}.html`);
/** Design widths of a page: "pageMedia" (glob keys, e.g. "settings-*") or the site-wide "widths". */
export const pageMedia = (cfg, page) => {
  const glob = p => new RegExp('^' + p.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.') + '$');
  const hit = page && Object.entries(cfg.pageMedia ?? {}).find(([p]) => glob(p).test(page));
  return hit ? hit[1] : cfg.widths;
};
export const widths = (cfg, page) => Object.keys(pageMedia(cfg, page)).map(Number).sort((a, b) => b - a);

/** Pixel diff of two PNG files in a canvas page. Returns {sizes, pct, bands:[[y,%]]} and writes out.png. */
export async function diffPng(b, a, c, out, band = 100) {
  const p = await b.newPage();
  const res = await p.evaluate(async ({ imgs, band }) => {
    const load = s => new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = s; });
    const [i1, i2] = await Promise.all(imgs.map(load));
    const w = Math.max(i1.width, i2.width), h = Math.max(i1.height, i2.height);
    const data = i => { const cv = document.createElement('canvas'); cv.width = w; cv.height = h; const g = cv.getContext('2d'); g.fillStyle = '#f0f'; g.fillRect(0, 0, w, h); g.drawImage(i, 0, 0); return g.getImageData(0, 0, w, h).data; };
    const A = data(i1), B = data(i2); const o = document.createElement('canvas'); o.width = w; o.height = h; const og = o.getContext('2d'); const od = og.createImageData(w, h);
    let bad = 0; const bands = [];
    for (let y = 0; y < h; y++) { if (y % band === 0) bands.push(0);
      for (let x = 0; x < w; x++) { const k = (y * w + x) * 4;
        const m = Math.abs(A[k] - B[k]) + Math.abs(A[k + 1] - B[k + 1]) + Math.abs(A[k + 2] - B[k + 2]) > 48;
        if (m) { bad++; bands[bands.length - 1]++; }
        od.data[k] = m ? 255 : A[k] * .3 + 170; od.data[k + 1] = m ? 0 : A[k + 1] * .3 + 170; od.data[k + 2] = m ? 0 : A[k + 2] * .3 + 170; od.data[k + 3] = 255; } }
    og.putImageData(od, 0, 0);
    return { png: o.toDataURL(), sizes: [i1.width, i1.height, i2.width, i2.height], pct: +(100 * bad / (w * h)).toFixed(2),
      bands: bands.map((n, i) => [i * band, +(100 * n / (w * Math.min(band, h - i * band))).toFixed(1)]).filter(x => x[1] > 0.5) };
  }, { imgs: [a, c].map(f => 'data:image/png;base64,' + readFileSync(f).toString('base64')), band });
  const { writeFileSync } = await import('node:fs');
  writeFileSync(out, Buffer.from(res.png.split(',')[1], 'base64')); delete res.png;
  await p.close();
  return res;
}
