// Boxes of elements on a page: y, height, and the layout values that move them (align-items, min-height, padding).
// Usage: node box.mjs <url|file> <width> <selector> [selector ...]
// For the designer's export use attribute selectors by layer name: '[data-pencil-name="Главный разворот"]'.
import { chromium } from './pw.mjs';
const [url, width, ...selectors] = process.argv.slice(2);
if (!url || !width || !selectors.length) { console.error('node box.mjs <url> <width> <selector...>'); process.exit(1); }
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: +width, height: 1000 } });
await page.goto(url.includes('://') ? url : 'file://' + new URL(url, 'file://' + process.cwd() + '/').pathname, { waitUntil: 'networkidle' });
for (const s of selectors) {
  const boxes = await page.evaluate(s => [...document.querySelectorAll(s)].slice(0, 3).map(e => {
    const r = e.getBoundingClientRect(), c = getComputedStyle(e), round = v => Math.round(v * 10) / 10;
    return { x: round(r.x), y: round(r.y + scrollY), w: round(r.width), h: round(r.height), align: c.alignItems, minH: c.minHeight, pad: c.padding };
  }), s);
  console.log(s, JSON.stringify(boxes));
}
await browser.close();
