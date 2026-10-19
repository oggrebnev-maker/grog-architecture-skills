#!/usr/bin/env python3
"""design-transfer: Pencil HTML export -> exact per-breakpoint CSS. Python 3.8+, stdlib only.

The export is a reference of values, not production markup. Your templates keep their own semantic
markup; this tool copies the exact style values of mapped export nodes onto your selectors, one @media
block per design width, so no size, colour or font value is retyped by hand.

Commands (run from the project root; settings in design-transfer.json, see `init`):
  dt.py init <package dir> [page]            write design-transfer.json from <page>-<width>.html files
  dt.py sections [page] [width]              list the top-level sections of a page frame
  dt.py paths <section> [page] [width]       node paths of one section, with texts («…»), images, icons
  dt.py scaffold <section> <block> [page]    write <block>.map.json + <block>.skeleton.html into mapsDir
  dt.py build [map.json ...]                 generate CSS for the given maps (default: every section)
  dt.py prepare-ref                          viewable copy of the export (local fonts, assets) for diffs
  dt.py texts <section> [page] [width]       texts of a section in order — to copy verbatim

Map: {"page": "home", "rules": [["<css selector>", "<node path>", ...flags], ...]}
  Path: export names from the section down, joined by " / "; duplicate sibling names get "#n" (1-based).
  Differs per width: ["sel", {"*": "path", "768": "other path"}]; missing widths are skipped.
  Flags: "img" — node is an <img>: background-* become object-fit/object-position;
         "text" — drop fixed px width/height of a text box (equal rows come from grid/subgrid).
  Own widths: "widths": {"1920": "(min-width:1024px)", "390": "(max-width:1023px)"} — for a part drawn at fewer widths.
"""
import html.parser, json, math, os, re, shutil, sys, unicodedata, zipfile
from pathlib import Path

# DT_CONFIG: another settings file, for a second package in the same project (paths stay relative to the project root).
CONFIG = Path(os.environ.get('DT_CONFIG') or 'design-transfer.json')
VOID = {'meta', 'link', 'br', 'img', 'input', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'ellipse'}
DROP = {'box-sizing', 'font-family'}


# ---------- config ----------

def config():
    if not CONFIG.exists():
        sys.exit(f'{CONFIG} not found: run `dt.py init <package dir>` in the project root')
    c = json.loads(CONFIG.read_text(encoding='utf-8'))
    c.setdefault('nameAttr', 'data-pencil-name')
    c.setdefault('assetUrl', '')
    c.setdefault('mapsDir', 'design-transfer/maps')
    c.setdefault('cssDir', 'design-transfer/css')
    c.setdefault('refDir', '.design-transfer/ref')
    c.setdefault('outDir', '.design-transfer/out')
    c.setdefault('sections', [])
    return c


def media_queries(widths):
    """Each design width owns the range down to the midpoint with the next smaller one (rounded to 10px)."""
    ws = sorted(widths, reverse=True)
    out = {}
    for i, w in enumerate(ws):
        lo = None if i == len(ws) - 1 else int(math.ceil((w + ws[i + 1]) / 2 / 10) * 10)
        hi = None if i == 0 else out[ws[i - 1]][0] - 1
        out[w] = (lo, hi)
    def mq(lo, hi):
        parts = ([f'(min-width:{lo}px)'] if lo else []) + ([f'(max-width:{hi}px)'] if hi else [])
        return ' and '.join(parts) or 'all'
    return {str(w): mq(*out[w]) for w in ws}


def cmd_init(package, page=None):
    pkg = Path(package)
    files = sorted(pkg.glob('*-*.html'))
    pages = {}
    for f in files:
        m = re.fullmatch(r'(.+)-(\d{3,4})\.html', f.name)
        if m:
            pages.setdefault(m.group(1), []).append(int(m.group(2)))
    if not pages:
        sys.exit(f'no <page>-<width>.html files in {pkg}')
    page = page or ('home' if 'home' in pages else sorted(pages)[0])
    if CONFIG.exists():
        sys.exit(f'{CONFIG} exists; edit it by hand')
    fonts = sorted({m for f in files for m in re.findall(r'family=([A-Za-z0-9+]+)', f.read_text(encoding='utf-8'))})
    cfg = {
        'package': str(pkg),
        'pages': {p: sorted(w, reverse=True) for p, w in pages.items()},
        'widths': media_queries(pages[page]),
        'assetUrl': '/design-assets/',
        'fonts': {f.replace('+', ' '): 'path/to/local/font-file.ttf' for f in fonts},
        'preview': 'http://127.0.0.1:8080',
        'injectCss': '',
        'mapsDir': 'design-transfer/maps',
        'cssDir': 'design-transfer/css',
        'refDir': '.design-transfer/ref',
        'outDir': '.design-transfer/out',
        'thresholds': {'sizePx': 1, 'diffPct': 3},
        'sections': [],
    }
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {CONFIG}: pages {cfg["pages"]}\nmedia: {json.dumps(cfg["widths"], ensure_ascii=False)}\n'
          'Check: widths/media, assetUrl (where export images are served), fonts (local files), preview URL.')


# ---------- export parsing ----------

class Node:
    def __init__(self, name, style, tag, parent=None):
        self.name, self.tag, self.parent, self.children, self.text = name, tag, parent, [], ''
        self.icon = None
        self.style = {}
        for part in style.split(';'):
            if ':' in part:
                k, v = part.split(':', 1)
                self.style[k.strip()] = v.strip()


class Parser(html.parser.HTMLParser):
    def __init__(self, attr):
        super().__init__()
        self.attr = attr
        self.root = Node('', '', 'root')
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        # Pencil leaves some styled nodes unnamed (the label inside a button): name them by tag so a path reaches them.
        name = a.get(self.attr) or a.get('data-icon-name') or (tag if a.get('style') and self.cur.name else '')
        node = Node(name, a.get('style', ''), tag, self.cur)
        node.icon = a.get('data-icon-name')
        self.cur.children.append(node)
        self.cur = node

    def handle_endtag(self, tag):
        if tag not in VOID and self.cur.parent:
            self.cur = self.cur.parent

    def handle_data(self, data):
        self.cur.text += data


def walk(n):
    yield n
    for c in n.children:
        yield from walk(c)


def load(path, attr):
    p = Parser(attr)
    p.feed(Path(path).read_text(encoding='utf-8'))
    body = next(n for n in walk(p.root) if n.tag == 'body')
    return next(c for c in body.children if c.name)  # page frame


def export_file(cfg, page, width):
    return Path(cfg['package']) / f'{page}-{width}.html'


def default_page(cfg):
    return 'home' if 'home' in cfg.get('pages', {}) else sorted(cfg.get('pages', {'home': 0}))[0]


def default_width(cfg, page=None):
    # A middle width of the page itself: pages of one package may be drawn at different widths.
    ws = sorted(map(int, (cfg.get('pages') or {}).get(page) or cfg['widths']))
    return ws[len(ws) // 2]


def child_key(parent, child):
    same = [c for c in parent.children if c.name == child.name]
    return child.name if len(same) == 1 else f'{child.name}#{same.index(child) + 1}'


def find(frame, path):
    """Resolve a path; node names may themselves contain ' / ', so parts are joined greedily."""
    def rec(node, parts):
        if not parts:
            return node
        for n in range(1, len(parts) + 1):
            key = ' / '.join(parts[:n])
            child = next((c for c in node.children if child_key(node, c) == key), None)
            if child is not None:
                found = rec(child, parts[n:])
                if found is not None:
                    return found
        return None
    return rec(frame, [p.strip() for p in path.split(' / ')])


def section(frame, name):
    hits = [c for c in frame.children if c.name == name] or [c for c in frame.children if c.name.startswith(name)]
    if len(hits) != 1:
        sys.exit(f'section "{name}": {len(hits)} matches; use `dt.py sections`')
    return hits[0]


def text_of(n):
    return ' '.join(n.text.split())


def image_of(n):
    m = re.search(r"url\('([^']*)'\)", n.style.get('background-image', ''))
    return m.group(1) if m else None


# ---------- CSS generation ----------

def px(v):
    return float(v[:-2]) if v.endswith('px') else None


def inner_width(node):
    w = node.style.get('width', '')
    if w.endswith('px'):
        width = px(w)
    elif w == '100%' and node.parent is not None and node.parent.tag != 'body':
        width = inner_width(node.parent)
    else:
        return None
    if width is None:
        return None
    pad = node.style.get('padding', '0px').split()
    left = px(pad[3] if len(pad) == 4 else pad[1] if len(pad) > 1 else pad[0]) or 0
    right = px(pad[1] if len(pad) > 1 else pad[0]) or 0
    return width - left - right


def fills_parent(node):
    w = px(node.style.get('width', ''))
    if w is None or node.parent is None or node.parent.tag == 'body':
        return False
    parent = inner_width(node.parent)
    if node.parent.parent is not None and node.parent.parent.tag == 'body':
        parent = w if w == px(node.parent.style.get('width', '') or 'x') else parent  # page frame itself
    return parent is not None and abs(parent - w) <= 1


def fill_row_columns(node):
    """Pencil splits a row between fill_container children by their OUTER size; CSS flex with
    flex-basis 0 splits what is left after padding. Such rows become a grid with equal fr tracks;
    fixed-width children keep their px track."""
    st = node.style
    if st.get('display') != 'flex' or st.get('flex-direction') != 'row':
        return None
    kids = [c for c in node.children if c.name and c.style.get('position') != 'absolute']
    if not any(c.style.get('flex', '').startswith('1 1 0') for c in kids):
        return None
    tracks = []
    for c in kids:
        w = c.style.get('width', '')
        if c.style.get('flex', '').startswith('1 1 0') or w == '100%':
            tracks.append('minmax(0, 1fr)')
        elif w.endswith('px'):
            tracks.append(w)
        else:
            tracks.append('auto')
    return ' '.join(tracks)


def css(node, flags, asset_url):
    out = []
    for k, v in node.style.items():
        if k in DROP:
            continue
        if 'img' in flags and k.startswith('background-'):
            if k == 'background-size':
                out.append(f'object-fit: {"contain" if v == "contain" else "cover"}')
            elif k == 'background-position':
                out.append(f'object-position: {v}')
            continue
        if k == 'width' and v.endswith('px') and fills_parent(node):
            out.append('width: 100%')  # the exporter writes the parent's px width for "fill parent" nodes
            continue
        if k == 'width' and v.endswith('px') and node.style.get('flex', '').startswith('1 1 0'):
            continue  # fill_container: the exporter also writes a px width; the track decides
        if 'text' in flags and k in ('height', 'width') and v.endswith('px'):
            continue
        if k == 'box-sizing':
            continue
        v = re.sub(r"url\('([^'/]*)'\)", lambda m: f"url('{asset_url}{m.group(1)}')", v)
        out.append(f'{k}: {v}')
    if any(x.startswith('width: ') and x.endswith('px') for x in out) and node.style.get('position') != 'absolute':
        out.append('max-width: 100%')  # a design px width never pushes past its container
    if node.style.get('flex', '').startswith('1 1 0'):
        out.append('min-width: 0')  # Pencil fill_container ignores content size
    columns = fill_row_columns(node)
    if columns:
        out.append(f'display: grid; grid-template-columns: {columns}')
        if node.style.get('height', '').endswith('px'):
            out.append('grid-template-rows: minmax(0, 1fr)')
    if 'img' in flags and node.style.get('flex', '').startswith('1 1 0'):
        out.append('width: 100%')
    return '; '.join(out)


def section_entry(cfg, map_file):
    return next((s for s in cfg['sections'] if Path(s['map']) == Path(map_file)), None)


def build(cfg, map_file, out=None):
    spec = json.loads(Path(map_file).read_text(encoding='utf-8'))
    entry = section_entry(cfg, map_file)
    out = Path(out or (entry and entry.get('css')) or Path(cfg['cssDir']) / (Path(map_file).name.replace('.map.json', '.generated.css')))
    # A map may set its own "widths" {width: media}: a part drawn at fewer widths (a top bar at 1920 and 390
    # only) covers the whole range with them. Widths the page was not drawn at are skipped.
    widths = spec.get('widths') or cfg['widths']
    drawn = (cfg.get('pages') or {}).get(spec['page'])
    frames = {}
    lines = [f'/* GENERATED by design-transfer from {Path(cfg["package"]).name}/{spec["page"]}-*.html'
             f' with {Path(map_file).name}. Do not edit; put fluid/state overrides in a separate file. */']
    missing = []
    for w, mq in widths.items():
        if drawn and int(w) not in drawn:
            continue
        frames[w] = load(export_file(cfg, spec['page'], w), cfg['nameAttr'])
        lines.append(f'@media {mq}{{')
        for sel, path, *flags in spec['rules']:
            p = path if isinstance(path, str) else path.get(str(w), path.get('*'))
            if p is None:
                continue
            node = find(frames[w], p)
            if node is None:
                missing.append(f'{w}: {sel} <- {p}')
                continue
            lines.append(f'{sel}{{{css(node, flags, cfg["assetUrl"])}}}')
        lines.append('}')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{map_file} -> {out}')
    return missing


def cmd_build(*maps):
    cfg = config()
    maps = maps or [s['map'] for s in cfg['sections']]
    if not maps:
        sys.exit('no maps: pass map files or list sections in design-transfer.json')
    missing = []
    for m in maps:
        missing += build(cfg, m)
    if missing:
        print('MISSING NODES:\n  ' + '\n  '.join(missing), file=sys.stderr)
        sys.exit(1)


# ---------- inspection ----------

def cmd_sections(page=None, width=None):
    cfg = config()
    page = page or default_page(cfg)
    frame = load(export_file(cfg, page, width or default_width(cfg, page)), cfg['nameAttr'])
    print(f'page frame: {frame.name}')
    for c in frame.children:
        print(f'  {c.name}  [{c.style.get("height", "?")}]')


def cmd_paths(name, page=None, width=None):
    cfg = config()
    page = page or default_page(cfg)
    sec = section(load(export_file(cfg, page, width or default_width(cfg, page)), cfg['nameAttr']), name)

    def rec(n, path, depth):
        extra = [f'«{text_of(n)[:60]}»'] if text_of(n) else []
        if image_of(n):
            extra.append(f'[img {image_of(n)}]')
        if n.icon:
            extra.append(f'[icon {n.icon}]')
        print('  ' * depth + path + ('  ' + ' '.join(extra) if extra else ''))
        for c in n.children:
            if c.name:
                rec(c, path + ' / ' + child_key(n, c), depth + 1)
    rec(sec, sec.name, 0)


def cmd_texts(name, page=None, width=None):
    cfg = config()
    page = page or default_page(cfg)
    sec = section(load(export_file(cfg, page, width or default_width(cfg, page)), cfg['nameAttr']), name)
    for n in walk(sec):
        if text_of(n):
            print(text_of(n))


# ---------- scaffold ----------

TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
                     'u', 'f', 'h', 'c', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))


def slug(name):
    s = ''.join(TRANSLIT.get(ch, ch) for ch in name.lower())
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return re.sub(r'-?\d+$', '', s) or 'node'  # "Card 1" / "Card 2" share one class


def path_of(node, top):
    parts = []
    while node is not top:
        parts.append(child_key(node.parent, node))
        node = node.parent
    return ' / '.join([top.name] + parts[::-1])


def shape(n):
    return (n.tag, tuple(shape(c) for c in n.children if c.name))


def cmd_scaffold(name, block, page=None):
    """Map with one BEM selector per named node + plain skeleton markup with the export texts and images.
    Repeated siblings with the same structure (cards, list items) share a class; only the first is mapped."""
    cfg = config()
    page = page or default_page(cfg)
    width = default_width(cfg, page)
    sec = section(load(export_file(cfg, page, width), cfg['nameAttr']), name)
    rules, used, lines = [], {}, []

    def cls(n, depth):
        base = block if depth == 0 else f'{block}__{slug(n.name)}'
        return base

    def rec(n, path, depth, mapped):
        c = cls(n, depth)
        if mapped:
            if c in used and used[c] != path:
                c = f'{c}-{len([k for k in used if k.startswith(c)]) + 1}'
            used[c] = path
            flags = (['img'] if image_of(n) else []) + (['text'] if text_of(n) and not [k for k in n.children if k.name] else [])
            rules.append([f'.{c}', path] + flags)
        pad = '  ' * depth
        if image_of(n):
            lines.append(f'{pad}<img class="{c}" src="{cfg["assetUrl"]}{image_of(n)}" alt="">')
            return
        if n.icon:
            lines.append(f'{pad}<svg class="{c}" data-icon="{n.icon}"></svg>')
            return
        kids = [k for k in n.children if k.name]
        if not kids:
            lines.append(f'{pad}<div class="{c}">{text_of(n)}</div>')
            return
        lines.append(f'{pad}<div class="{c}">')
        seen = {}
        for k in kids:
            first = shape(k) not in seen.get(slug(k.name), set())
            seen.setdefault(slug(k.name), set()).add(shape(k))
            rec(k, path + ' / ' + child_key(n, k), depth + 1, mapped and first)
        lines.append(f'{pad}</div>')

    rec(sec, sec.name, 0, True)
    # Other widths may nest a node differently (a card row becomes a column with an extra wrapper):
    # find it there by name and write a per-width path.
    for w in cfg['widths']:
        if int(w) == width:
            continue
        frame = load(export_file(cfg, page, w), cfg['nameAttr'])
        other = section(frame, sec.name)
        for rule in rules:
            path = rule[1] if isinstance(rule[1], str) else rule[1]['*']
            if find(frame, path) is not None:
                continue
            target = re.sub(r'#\d+$', '', path.split(' / ')[-1])
            hits = [n for n in walk(other) if n.name == target]
            alt = path_of(hits[0], other) if hits else None
            rule[1] = {'*': path, **({} if isinstance(rule[1], str) else rule[1]), w: alt}
            if alt is None:  # null in the map: the node does not exist at this width — hide it there in your CSS
                print(f'absent at {w}: {rule[0]} ({path})', file=sys.stderr)
    out = Path(cfg['mapsDir'])
    out.mkdir(parents=True, exist_ok=True)
    map_file, skel = out / f'{block}.map.json', out / f'{block}.skeleton.html'
    if map_file.exists():
        sys.exit(f'{map_file} exists; delete it to scaffold again')
    body = ',\n'.join('    ' + json.dumps(r, ensure_ascii=False) for r in rules)
    map_file.write_text(f'{{\n  "page": "{page}",\n  "rules": [\n{body}\n  ]\n}}\n', encoding='utf-8')
    skel.write_text(f'<!-- skeleton of "{sec.name}" ({page}-{width}); turn into semantic markup, keep classes -->\n'
                    + '\n'.join(lines) + '\n', encoding='utf-8')
    print(f'wrote {map_file} ({len(rules)} rules) and {skel}\n'
          f'add to design-transfer.json "sections": {{"key": "{block}", "page": "{page}", "url": "/", '
          f'"selector": ".{block}", "node": "{sec.name}", "map": "{map_file}", "css": "<where the generated css goes>"}}')


# ---------- reference copy ----------

FILL_ROWS_JS = '''<script>
for (const el of document.querySelectorAll('[style]')) {
  if (el.style.display !== 'flex' || el.style.flexDirection !== 'row') continue;
  const kids = [...el.children].filter(c => c.style.position !== 'absolute');
  const fill = c => c.style.flex.startsWith('1 1 0');
  if (!kids.some(fill)) continue;
  el.style.gridTemplateColumns = kids.map(c => fill(c) || c.style.width === '100%' ? 'minmax(0, 1fr)' : c.style.width.endsWith('px') ? c.style.width : 'auto').join(' ');
  el.style.display = 'grid';
  if (el.style.height.endsWith('px')) el.style.gridTemplateRows = 'minmax(0, 1fr)';
  for (const c of kids) if (fill(c)) { c.style.minWidth = '0'; if (c.style.width.endsWith('px')) c.style.width = ''; }
}
</script></body>'''


def cmd_prepare_ref():
    """Copy of the export that renders offline and like Pencil: assets next to the HTML, local fonts,
    border-box sizing (Pencil sizes include padding and border), fill rows split by outer size."""
    cfg = config()
    pkg, out = Path(cfg['package']), Path(cfg['refDir'])
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for z in pkg.glob('*.zip'):
        zipfile.ZipFile(z).extractall(out)
    for d in ('assets', 'images', 'renders', 'fonts'):
        if (pkg / d).is_dir():
            shutil.copytree(pkg / d, out / d, dirs_exist_ok=True)
    for c in pkg.glob('*.css'):  # an export with local fonts links ./fonts.css next to the pages
        shutil.copy(c, out / c.name)
    faces = []
    for family, file in cfg.get('fonts', {}).items():
        f = Path(file)
        if not f.exists():
            sys.exit(f'font file for {family} not found: {f} (set "fonts" in design-transfer.json)')
        shutil.copy(f, out / f.name)
        faces.append(f'@font-face{{font-family:"{family}";src:url("{f.name}");font-weight:100 900}}')
    for f in pkg.glob('*.html'):
        s = f.read_text(encoding='utf-8')
        if faces:
            s = re.sub(r'<link\s+href="https://fonts.googleapis[^>]*/?>', '<style>' + ''.join(faces) + '</style>', s, flags=re.S)
            s = re.sub(r'<link rel="preconnect"[^>]*/?>', '', s)
        s = s.replace('box-sizing: content-box', 'box-sizing: border-box')
        s = s.replace('</body>', FILL_ROWS_JS)
        (out / f.name).write_text(s, encoding='utf-8')
    print(f'reference copy: {out}')


if __name__ == '__main__':
    cmds = {'init': cmd_init, 'sections': cmd_sections, 'paths': cmd_paths, 'scaffold': cmd_scaffold,
            'build': cmd_build, 'prepare-ref': cmd_prepare_ref, 'texts': cmd_texts}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]](*sys.argv[2:])
