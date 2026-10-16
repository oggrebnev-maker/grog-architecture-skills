// Shared helpers of the browser checks: config, browser, image comparison in a canvas (no extra deps).
import { chromium } from 'playwright';
import { readFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

export function config() {
  if (!existsSync('design-transfer.json')) throw new Error('design-transfer.json not found: run from the project root (dt.py init)');
  const c = JSON.parse(readFileSync('design-transfer.json', 'utf8'));
  c.nameAttr ??= 'data-pencil-name'; c.refDir ??= '.design-transfer/ref'; c.outDir ??= '.design-transfer/out';
  c.thresholds = { sizePx: 1, diffPct: 3, ...(c.thresholds ?? {}) };
  c.sections ??= [];
  mkdirSync(c.outDir, { recursive: true });
  return c;
}

/** Section entry -> page, our selector and the export node, taken from the first rule of its map. */
export function sectionOf(entry) {
  const spec = JSON.parse(readFileSync(entry.map, 'utf8'));
  const [selector, path] = spec.rules[0];
  const node = typeof path === 'string' ? path : path['*'] ?? Object.values(path)[0];
  return { key: entry.key, page: entry.page ?? spec.page, url: entry.url ?? '/', selector: entry.selector ?? selector, node: entry.node ?? node };
}

export async function browser() {
  try { return await chromium.launch({ channel: 'chromium' }); }
  catch { return chromium.launch(); }
}

/** Opens a page ready for a stable screenshot: fonts loaded, lazy images decoded, injected CSS applied. */
export async function open(b, url, width, css = '', height = 1000) {
  const p = await b.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  await p.goto(url, { waitUntil: 'networkidle' });
  if (css) await p.addStyleTag({ content: css });
  await p.evaluate(async () => {
    await document.fonts.ready;
    for (const i of document.images) { i.loading = 'eager'; await i.decode().catch(() => {}); }
  });
  return p;
}

export const refUrl = (cfg, page, width) => 'file://' + resolve(cfg.refDir, `${page}-${width}.html`);
export const widths = cfg => Object.keys(cfg.widths).map(Number).sort((a, b) => b - a);

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
