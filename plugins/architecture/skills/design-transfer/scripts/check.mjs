// Section check: our page vs the designer export, every section x every width. Free, no AI.
//   node check.mjs [section keys...] [--widths=1440,390]
// Needs: design-transfer.json, `dt.py prepare-ref`, the site running at cfg.preview.
// Per section/width: size of our block vs the export node, pixel diff %, export texts missing on our page.
// Pictures: <outDir>/<key>-<width>-{cur,ref,diff}.png. Summary: <outDir>/report.json. Exit 1 on failure.
import { writeFileSync } from 'node:fs';
import { config, sectionOf, browser, open, refUrl, widths, diffPng } from './lib.mjs';

const cfg = config();
const args = process.argv.slice(2);
const only = args.filter(a => !a.startsWith('--'));
const ws = (args.find(a => a.startsWith('--widths='))?.slice(9).split(',').map(Number)) ?? widths(cfg);
const sections = cfg.sections.filter(s => !only.length || only.includes(s.key)).map(sectionOf);
if (!sections.length) { console.error('no sections: list them in design-transfer.json "sections"'); process.exit(2); }

const b = await browser();
const report = [];
let failed = false;
const textsOf = el => [...el.querySelectorAll('*')].concat(el)
  .flatMap(n => [...n.childNodes].filter(c => c.nodeType === 3).map(c => c.textContent.replace(/\s+/g, ' ').trim()))
  .filter(Boolean);
for (const s of sections) {
  for (const w of ws) {
    const row = { section: s.key, width: w };
    const shots = {};
    for (const [tag, url, sel, css] of [['cur', cfg.preview + s.url, s.selector, cfg.injectCss ?? ''], ['ref', refUrl(cfg, s.page, w), `[${cfg.nameAttr}="${s.node}"]`, '']]) {
      const p = await open(b, url, w, css);
      const el = p.locator(sel).first();
      if (!(await el.count())) { row.error = `${tag}: ${sel} not found`; await p.close(); break; }
      const box = await el.boundingBox();
      shots[tag] = { file: `${cfg.outDir}/${s.key}-${w}-${tag}.png`, w: Math.round(box.width), h: Math.round(box.height) };
      await el.screenshot({ path: shots[tag].file });
      shots[tag].texts = await el.evaluate((e, f) => new Function('return ' + f)()(e), textsOf.toString());
      // Visible text plus what form controls and images show without being text nodes.
      shots[tag].innerText = (await el.evaluate(e => [e.innerText, ...[...e.querySelectorAll('input, textarea, img, [aria-label]')]
        .map(n => [n.placeholder, n.value, n.alt, n.getAttribute('aria-label')].filter(Boolean).join(' '))].join(' '))).replace(/\s+/g, ' ');
      await p.close();
    }
    if (!row.error) {
      const d = await diffPng(b, shots.ref.file, shots.cur.file, `${cfg.outDir}/${s.key}-${w}-diff.png`);
      Object.assign(row, { ref: `${shots.ref.w}x${shots.ref.h}`, cur: `${shots.cur.w}x${shots.cur.h}`, diffPct: d.pct, bands: d.bands,
        missingTexts: shots.ref.texts.filter(t => !shots.cur.innerText.includes(t)) });
      const sizeBad = Math.abs(shots.ref.w - shots.cur.w) > cfg.thresholds.sizePx || Math.abs(shots.ref.h - shots.cur.h) > cfg.thresholds.sizePx;
      row.ok = !sizeBad && d.pct <= cfg.thresholds.diffPct && !row.missingTexts.length;
    }
    if (!row.ok) failed = true;
    report.push(row);
    console.log(`${row.ok ? 'OK  ' : 'FAIL'} ${s.key} ${w}: ` + (row.error ?? `ref ${row.ref} cur ${row.cur} diff ${row.diffPct}%`
      + (row.bands.length ? ` bands(y,%) ${JSON.stringify(row.bands)}` : '') + (row.missingTexts.length ? ` missing texts: ${JSON.stringify(row.missingTexts)}` : '')));
  }
}
await b.close();
writeFileSync(`${cfg.outDir}/report.json`, JSON.stringify(report, null, 2) + '\n');
console.log(`${report.filter(r => r.ok).length}/${report.length} ok; pictures and report.json in ${cfg.outDir}`);
process.exit(failed ? 1 : 0);
