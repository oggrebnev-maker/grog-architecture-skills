// Typography check: every text of the export vs the same text on our page, every section x width. Free, no AI.
//   node type.mjs [section keys...] [--widths=1440,390]
// For each export text node (leaf with text) finds our element whose own text is the same and compares the
// computed font-size, line-height, font-weight, letter-spacing, font-family. Texts that differ by data (dates,
// services) are skipped: only exact text matches are compared. Report: <outDir>/type-report.json. Exit 1 on mismatch.
import { writeFileSync } from 'node:fs';
import { config, sectionOf, atWidth, markNode, browser, open, refUrl, widths } from './lib.mjs';

const cfg = config();
const args = process.argv.slice(2);
const only = args.filter(a => !a.startsWith('--'));
const only_ws = args.find(a => a.startsWith('--widths='))?.slice(9).split(',').map(Number);
const sections = cfg.sections.filter(s => s.check !== false && (!only.length || only.includes(s.key))).map(sectionOf);
const PROPS = ['fontSize', 'lineHeight', 'fontWeight', 'letterSpacing', 'fontFamily'];

// Leaf elements with own text -> {text, style}; the page's font-family is reduced to its first name.
const collect = (root, props) => [...root.querySelectorAll('*')].concat(root)
  .filter(el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && el.getClientRects().length)
  .map(el => {
    const cs = getComputedStyle(el);
    const style = Object.fromEntries(props.map(p => [p, p === 'fontFamily' ? cs.fontFamily.split(',')[0].replace(/["']/g, '').trim() : cs[p]]));
    const text = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
    return { text, style };
  });

const b = await browser();
const report = [];
let bad = 0;
for (const s of sections) {
  for (const w of only_ws?.filter(x => widths(cfg, s.page).includes(x)) ?? widths(cfg, s.page)) {
    const node = atWidth(s.node, w);
    if (node === null) continue;
    const cur = await open(b, cfg.preview + s.url, w, cfg.injectCss ?? '');
    const sel = atWidth(s.selector, w);
    if (!(await cur.locator(sel).count())) { await cur.close(); continue; }
    const ours = await cur.locator(sel).first().evaluate((el, [fn, props]) => new Function('return ' + fn)()(el, props), [collect.toString(), PROPS]);
    await cur.close();
    const ref = await open(b, refUrl(cfg, s.page, w), w, '');
    const refSel = await markNode(ref, cfg, node);
    if (!(await ref.locator(refSel).count())) { await ref.close(); continue; }
    const theirs = await ref.locator(refSel).first().evaluate((el, [fn, props]) => new Function('return ' + fn)()(el, props), [collect.toString(), PROPS]);
    await ref.close();
    for (const t of theirs) {
      // Calendar day numbers carry the state of the day (today, picked), not the type scale.
      if (/^\d{1,2}$/.test(t.text)) continue;
      // The same text may repeat (title in the breadcrumb and in H1): fine if any of ours has the export style.
      const candidates = ours.filter(x => x.text === t.text);
      if (!candidates.length) continue;
      const score = o => PROPS.filter(p => o.style[p] !== t.style[p]).length;
      const o = candidates.reduce((a, c) => score(c) < score(a) ? c : a);
      const diff = PROPS.filter(p => o.style[p] !== t.style[p]);
      if (!diff.length) continue;
      bad++;
      const row = { section: s.key, width: w, text: t.text.slice(0, 60), ...Object.fromEntries(diff.map(p => [p, `${o.style[p]} ≠ ${t.style[p]}`])) };
      report.push(row);
      console.log(`DIFF ${s.key} ${w}: «${row.text}» ` + diff.map(p => `${p} ${row[p]}`).join(', '));
    }
  }
}
await b.close();
writeFileSync(`${cfg.outDir}/type-report.json`, JSON.stringify(report, null, 2) + '\n');
console.log(bad ? `${bad} text styles differ from the export (ours ≠ export)` : 'all matched texts have the export typography');
process.exit(bad ? 1 : 0);
