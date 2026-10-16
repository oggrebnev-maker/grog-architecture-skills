// Horizontal overflow check: no page may scroll sideways at any width, design widths and everything between.
//   node overflow.mjs [url paths...] [--from=320 --to=2560 --step=10]
// Reports the widths with overflow and the elements that stick out past the viewport. Exit 1 on overflow.
import { config, browser } from './lib.mjs';
const cfg = config();
const args = process.argv.slice(2);
const opt = k => Number(args.find(a => a.startsWith(`--${k}=`))?.split('=')[1]);
const paths = args.filter(a => !a.startsWith('--'));
const urls = (paths.length ? paths : [...new Set(cfg.sections.map(s => s.url ?? '/'))]).map(p => cfg.preview + p);
const from = opt('from') || 320, to = opt('to') || 2560, step = opt('step') || 10;
const b = await browser();
let bad = 0;
for (const url of urls) {
  const p = await b.newPage({ viewport: { width: to, height: 900 } });
  await p.goto(url, { waitUntil: 'networkidle' });
  for (let w = from; w <= to; w += step) {
    await p.setViewportSize({ width: w, height: 900 });
    const r = await p.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      if (document.documentElement.scrollWidth <= vw) return null;
      const out = [...document.body.querySelectorAll('*')].filter(e => { const b = e.getBoundingClientRect(); return b.width && b.right > vw + 0.5; })
        .filter(e => !e.parentElement || e.parentElement.getBoundingClientRect().right <= vw + 0.5)
        .slice(0, 5).map(e => `${e.tagName.toLowerCase()}.${[...e.classList].join('.')} right=${Math.round(e.getBoundingClientRect().right)}`);
      return { scroll: document.documentElement.scrollWidth, vw, out };
    });
    if (r) { bad++; console.log(`OVERFLOW ${url} @${w}: scrollWidth ${r.scroll} > ${r.vw}; ${r.out.join('; ')}`); }
  }
  await p.close();
}
await b.close();
console.log(bad ? `${bad} widths with horizontal overflow` : `no horizontal overflow ${from}..${to} step ${step}`);
process.exit(bad ? 1 : 0);
