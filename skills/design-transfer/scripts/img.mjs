// Image tools for states drawn only as PNG and for visual review. Free, no AI.
//   node img.mjs diff a.png b.png out.png [band=100]        pixel diff (% and bands of rows)
//   node img.mjs crop in.png x y w h out.png [scale=1]     cut a region (scale to zoom)
//   node img.mjs pair a.png b.png y h out.png              a and b side by side, rows y..y+h
//   node img.mjs row in.png y x1 x2 | col in.png x y1 y2   colour runs along a line: "x:#rrggbb ..." —
//                                                          edges, borders, paddings and colours of a PNG mock
//   node img.mjs ink in.png x1 x2 [y1 y2]                  row ranges containing dark pixels (text lines)
//   node img.mjs textwidth "<css font>" "<text>" [url]      rendered width of a text (find font-size/weight
//                                                          by matching a measured text width; url loads fonts)
import { readFileSync, writeFileSync } from 'node:fs';
import { browser, diffPng } from './lib.mjs';
const [cmd, ...a] = process.argv.slice(2);
const b = await browser();
const page = await b.newPage();
const url = f => 'data:image/png;base64,' + readFileSync(f).toString('base64');
const run = (fn, arg) => page.evaluate(fn, arg);
const canvasFn = `const load=s=>new Promise(r=>{const i=new Image();i.onload=()=>r(i);i.src=s});const cv=(w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;return c};`;
if (cmd === 'diff') console.log(JSON.stringify(await diffPng(b, a[0], a[1], a[2], +(a[3] || 100))));
else if (cmd === 'crop' || cmd === 'pair') {
  const png = await run(new Function('arg', canvasFn + `return (async()=>{const {cmd,a,imgs}=arg;
    if(cmd==='crop'){const i=await load(imgs[0]);const [x,y,w,h]=a.slice(1,5).map(Number);const sc=+(a[6]||1);const c=cv(w*sc,h*sc);c.getContext('2d').drawImage(i,x,y,w,h,0,0,w*sc,h*sc);return c.toDataURL()}
    const [i1,i2]=await Promise.all(imgs.map(load));const y=+a[2],h=+a[3];const w=Math.max(i1.width,i2.width);const c=cv(w*2+10,h);const g=c.getContext('2d');
    g.fillStyle='#f0f';g.fillRect(0,0,c.width,h);g.drawImage(i1,0,y,i1.width,h,0,0,i1.width,h);g.drawImage(i2,0,y,i2.width,h,w+10,0,i2.width,h);return c.toDataURL()})()`),
    { cmd, a, imgs: (cmd === 'crop' ? [a[0]] : [a[0], a[1]]).map(url) });
  writeFileSync(cmd === 'crop' ? a[5] : a[4], Buffer.from(png.split(',')[1], 'base64'));
} else if (cmd === 'row' || cmd === 'col' || cmd === 'ink') {
  console.log(await run(new Function('arg', canvasFn + `return (async()=>{const {cmd,a,src}=arg;const i=await load(src);const c=cv(i.width,i.height);const g=c.getContext('2d');g.drawImage(i,0,0);
    const d=g.getImageData(0,0,i.width,i.height).data;const px=(x,y)=>{const k=(y*i.width+x)*4;return '#'+[d[k],d[k+1],d[k+2]].map(v=>v.toString(16).padStart(2,'0')).join('')};
    if(cmd==='ink'){const [x1,x2]=a.slice(1,3).map(Number);const y1=+(a[3]??0),y2=+(a[4]??i.height-1);const runs=[];let s=-1;
      for(let y=y1;y<=y2;y++){let ink=false;for(let x=x1;x<=x2;x++){const k=(y*i.width+x)*4;if(d[k]<140&&d[k+1]<140&&d[k+2]<160){ink=true;break}}
        if(ink&&s<0)s=y;if(!ink&&s>=0){runs.push(s+'-'+(y-1));s=-1}}if(s>=0)runs.push(s+'-'+y2);return 'ink rows: '+runs.join(' ')}
    const [p,q1,q2]=a.slice(1,4).map(Number);let prev='',out=[];for(let t=q1;t<=q2;t++){const v=cmd==='row'?px(t,p):px(p,t);if(v!==prev){out.push(t+':'+v);prev=v}}return out.join(' ')})()`),
    { cmd, a, src: url(a[0]) }));
} else if (cmd === 'textwidth') {
  if (a[2]) await page.goto(a[2], { waitUntil: 'networkidle' });
  console.log(await page.evaluate(async ([font, text]) => { await document.fonts.ready; const e = document.createElement('span');
    e.style.cssText = `font:${font};white-space:nowrap;position:absolute`; e.textContent = text; document.body.append(e);
    await document.fonts.load(font, text); return e.getBoundingClientRect().width.toFixed(1); }, [a[0], a[1]]));
} else console.log(readFileSync(new URL(import.meta.url)).toString().split('\n').slice(1, 11).join('\n'));
await b.close();
