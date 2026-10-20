#!/usr/bin/env python3
"""Страж дизайн-системы. Без ИИ, без сети, только стандартная библиотека Python.

    python3 guard.py package <папка пакета> [--sync <файл сообщений дизайнеру>]   # пакет дизайнера до любой работы
    python3 guard.py code [--write-baseline]                                   # встроенные стили в шаблонах и скриптах
    python3 guard.py system [папка пакета]                                     # дизайн-система одним JSON (для guard-page.mjs)

Дизайн-система собирается из файлов (все, какие есть):
  <пакет>/typography.json или guard.tokens — роли текста: переменные type-<роль>-<ширина> / leading-… / type-<роль>-weight,
      или tokens.json дизайн-системы (type.groups: роль → fontSize/lineHeight/fontWeight; на всех ширинах);
  guard.roles — роли по ширинам поверх: {"h1": {"390": [30, 36, 700], "360": [30, 36, 700]}};
  <пакет>/source/variables.json, guard.variables — палитра Pencil, значения по темам ({"value": …, "theme": {"mode": "dark"}}).
Пакет проверяется по исходнику Pencil (transport/snapshot.html), если он есть, иначе по HTML-экспорту каждого кадра
(<страница>-<ширина>[-<тема>].html в любой подпапке; цвет кадра темы сверяется с палитрой этой темы):
  T1 текст не привязан к роли системы (размер, межстрочный, толщина вписаны числом)            — нарушение
  T2 привязан к роли другой ширины (в кадре 390 стоит $type-h2-1440)                             — серьёзное
  T3 размер / межстрочный / толщина не совпадают ни с одной ролью на этой ширине                 — серьёзное
  T4 шрифт не из системы                                                                         — серьёзное
  C1 цвет вписан числом, но такой цвет в палитре есть                                            — нарушение
  C2 цвета нет в палитре                                                                         — серьёзное
  K1 компонент изменён на месте (у экземпляра свои заливка, рамка, отступы, размеры шрифта)      — серьёзное
  K2 элемент вида «кнопка / поле / флажок / карточка…» нарисован не из компонента                — нарушение
  K3 элементы одного вида на одной ширине выглядят по-разному                                    — серьёзное
  G1 рамка с дробной высотой (87.5)                                                              — нарушение
  S0 нет дизайн-системы, проверять не по чему                                                   — серьёзное
По экспорту проверяются T3, T4, C2; привязку к переменным и компоненты (T1, T2, C1, K1–K3, G1) — только по исходнику.
Серьёзное — работу не начинать, пакет на доработку. Только нарушения — работу начать, пакет на доработку параллельно.
Код: в шаблонах нет style="" и <style>, в скриптах нет .style / cssText / setProperty — только классы из файлов стилей.
Настройки — design-transfer.json (или файл из DT_CONFIG) → "guard". Исключения — "allow" (каждое с датой «да» владельца). Код: "baseline" — известные
старые нарушения; новые не проходят, старые уходят по мере исправления.
Коды выхода: 0 — чисто, 1 — только нарушения, 2 — есть серьёзные.
"""
import json
import os
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

BASE_WIDTHS = [1920, 1440, 1024, 768, 390, 360]
WEIGHTS = {'normal': 400, 'regular': 400, 'medium': 500, 'semibold': 600, 'bold': 700}
STYLE_KEYS_ON_REF = {'fill', 'stroke', 'strokeWidth', 'padding', 'gap', 'cornerRadius', 'fontSize', 'lineHeight',
                     'fontWeight', 'fontFamily', 'letterSpacing', 'effect', 'opacity'}
KINDS = {  # вид элемента → слова в имени слоя (нижний регистр)
    'кнопка': ('кнопка', 'button'),
    'поле ввода': ('поле', 'input'),
    'флажок': ('флажок', 'чекбокс', 'checkbox'),
    'переключатель': ('переключатель', 'radio', 'toggle'),
    'выпадающий список': ('выпадающ', 'select'),
    'карточка': ('карточка', 'card'),
    'уведомление': ('уведомлени', 'notice'),
}
SEVERE = {'T2', 'T3', 'T4', 'C2', 'K1', 'K3', 'S0'}
TITLES = {
    'T1': 'текст не привязан к роли системы (числа вместо $type-…)',
    'T2': 'текст привязан к роли другой ширины',
    'T3': 'размер / межстрочный / толщина не совпадают ни с одной ролью на этой ширине',
    'T4': 'шрифт не из системы',
    'C1': 'цвет вписан числом (в палитре есть — нужна переменная)',
    'C2': 'цвета нет в палитре',
    'K1': 'компонент изменён на месте',
    'K2': 'элемент нарисован не из компонента',
    'K3': 'элементы одного вида выглядят по-разному',
    'G1': 'дробная высота рамки',
    'S0': 'нечем проверить',
}


def cfg():
    p = Path(os.environ.get('DT_CONFIG') or 'design-transfer.json')
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def guard_cfg():
    return cfg().get('guard', {})


# ---------- дизайн-система ----------

def load_system(pkg: Path):
    """Роли текста, палитра по темам и шрифты из всех файлов системы; None — ролей нет нигде."""
    g = guard_cfg()
    system = {'roles': defaultdict(dict), 'palette': defaultdict(set), 'fonts': set(), 'vars': {}}
    used = []
    typo = [pkg / 'typography.json'] if pkg else []
    typo += [Path(t) for t in ([g['tokens']] if isinstance(g.get('tokens'), str) else g.get('tokens', []))]
    for p in typo:
        if p.exists():
            add_system(system, json.loads(p.read_text(encoding='utf-8')))
            used.append(p)
    for role, ws in g.get('roles', {}).items():
        for w, (size, line, weight) in ws.items():
            system['roles'][role][w if w == '*' else int(w)] = (float(size), float(line), norm_weight(weight))
    pal = [pkg / 'source' / 'variables.json'] if pkg else []
    pal += [Path(v) for v in g.get('variables', [])]
    for p in pal:
        if p.exists():
            add_system(system, json.loads(p.read_text(encoding='utf-8')))
            used.append(p)
    for extra in g.get('palette', []):  # цвета, утверждённые владельцем вне файла системы
        c = hex_norm(extra)
        if c:
            system['palette'][c].add('*')
    for f in g.get('fonts', []):
        system['fonts'].add(f)
    if not system['roles']:
        return None, None
    system['roles'] = dict(system['roles'])
    return system, ', '.join(str(p) for p in used) or 'design-transfer.json → guard'


def themed(value):
    """Значение переменной Pencil → [(значение, тема)]; тема '*' — общая для всех."""
    if isinstance(value, list):
        return [(x.get('value'), (x.get('theme') or {}).get('mode', '*')) for x in value if isinstance(x, dict)]
    return [(value, '*')]


def add_system(system, d):
    if 'variables' in d:
        v = {k: x.get('value') if isinstance(x, dict) else x for k, x in d['variables'].items()}
        system['vars'].update(v)
        for k, val in v.items():
            m = re.fullmatch(r'type-([a-z0-9]+)-(\d+)', k)
            if m:
                role, w = m.group(1), int(m.group(2))
                lead = v.get(f'leading-{role}-{w}', 1)
                weight = norm_weight(v.get(f'type-{role}-weight', 400))
                system['roles'][role][w] = (float(val), round(float(val) * float(lead), 2), weight)
                continue
            for x, theme in themed(val):
                if not isinstance(x, str):
                    continue
                if k in ('heading', 'body') or k.startswith('font-'):
                    system['fonts'].add(x.split(',')[0].strip().strip('"\''))
                    continue
                for c in colors_in(x):
                    system['palette'][c].add(theme)
    elif isinstance(d.get('type'), dict):  # tokens.json дизайн-системы: type.groups → стили, одинаковые на всех ширинах
        for fam in (d['type'].get('families') or {}).values():
            system['fonts'].add(fam.split(',')[0].strip().strip('"\''))
        for grp in d['type'].get('groups', []):
            for st in grp.get('styles', []):
                system['roles'][st['name']]['*'] = (px(st['fontSize']), px(st['lineHeight']), norm_weight(st['fontWeight']))
        walk_colors(d.get('color'), system)
    else:  # прежний вид: roles → width → fontSize/lineHeight/fontWeight
        system['fonts'].add(d.get('fontFamily', 'Onest'))
        for role, ws in d.get('roles', {}).items():
            for w, x in ws.items():
                if isinstance(x, dict) and 'fontSize' in x:
                    system['roles'][role][int(w)] = (float(x['fontSize']), float(x['lineHeight']), norm_weight(x['fontWeight']))


def walk_colors(node, system, theme='*'):
    if isinstance(node, dict):
        for k, x in node.items():
            walk_colors(x, system, k if k in ('light', 'dark') else theme)
    elif isinstance(node, list):
        for x in node:
            walk_colors(x, system, theme)
    elif isinstance(node, str):
        for c in colors_in(node):
            system['palette'][c].add(theme)


def px(v):
    return float(str(v).rstrip('px'))


def in_palette(system, c, theme='*'):
    themes = system['palette'].get(c)
    return bool(themes) and (theme == '*' or '*' in themes or theme in themes)


def norm_weight(w):
    if isinstance(w, (int, float)):
        return int(w)
    w = str(w).strip().lower()
    return WEIGHTS.get(w, int(w) if w.isdigit() else 400)


def role_of(system, width, size, line, weight):
    """Роль системы на этой ширине с теми же размером, межстрочным (±0.5) и толщиной; None — нет такой.
    line 0 — межстрочный не задан (Pencil: «авто»), сверяются только размер и толщина."""
    for role, ws in system['roles'].items():
        r = ws.get(width, ws.get('*'))
        if r and abs(r[0] - size) < 0.01 and (not line or abs(r[1] - line) <= 0.5) and r[2] == weight:
            return role
    return None


def nearest_role(system, width, size, weight):
    best = None
    for role, ws in system['roles'].items():
        r = ws.get(width, ws.get('*'))
        if r:
            d = abs(r[0] - size) + (0 if r[2] == weight else 3)
            if best is None or d < best[0]:
                best = (d, role, r)
    return f'{best[1]} {fmt(best[2])}' if best else '—'


def fmt(r):
    return f'{r[0]:g}/{r[1]:g} {r[2]}'


def design_width(width):
    return min(BASE_WIDTHS, key=lambda w: abs(w - width))


def colors_in(value):
    """Все цвета значения (#hex, rgb/rgba, в том числе внутри градиента) — в виде #RRGGBB или #RRGGBBAA."""
    out = []
    for m in re.finditer(r'#[0-9A-Fa-f]{3,8}\b|rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)', value):
        if m.group(0).startswith('#'):
            c = hex_norm(m.group(0))
        else:
            a = m.group(4)
            a = 1 if a is None else float(a[:-1]) / 100 if a.endswith('%') else float(a)
            c = None if a == 0 else '#' + ''.join(f'{round(float(m.group(i))):02X}' for i in (1, 2, 3)) + ('' if a >= 1 else f'{round(a * 255):02X}')
        if c:
            out.append(c)
    return out


def hex_norm(c):
    c = c.strip().upper()
    if re.fullmatch(r'#[0-9A-F]{8}', c):
        return None if c.endswith('00') else c[:7] if c.endswith('FF') else c
    if re.fullmatch(r'#[0-9A-F]{6}', c):
        return c
    if re.fullmatch(r'#[0-9A-F]{3}', c):
        return '#' + ''.join(ch * 2 for ch in c[1:])
    if re.fullmatch(r'#[0-9A-F]{4}', c):
        return hex_norm('#' + ''.join(ch * 2 for ch in c[1:]))
    return None


# ---------- исходник Pencil (transport/snapshot.html) ----------

def load_source(pkg: Path):
    p = pkg / 'transport' / 'snapshot.html'
    if not p.exists():
        return None
    h = p.read_text(encoding='utf-8')
    # Chunks: <div data-pencil-name="Данные 3"> or "Данные / 60000" (index or offset) with text CHUNK:…:END.
    parts = sorted(re.findall(r'data-pencil-name="Данные\D*(\d+)"[^>]*>\s*(CHUNK:.*?)</div>', h, re.S), key=lambda x: int(x[0]))
    s = ''.join(re.sub(r'\s+', '', b).removeprefix('CHUNK:').removesuffix(':END') for _, b in parts)
    return json.loads(urllib.parse.unquote(s))


class Report:
    def __init__(self):
        self.items = defaultdict(list)  # code → [(frame, where, detail)]

    def add(self, code, frame, where, detail):
        key = (frame, where, detail)
        if key not in self.items[code]:
            self.items[code].append(key)

    def severe(self):
        return any(self.items[c] for c in SEVERE)

    def any(self):
        return any(self.items.values())


def check_source(src, system, rep: Report):
    variables = {k: v.get('value') for k, v in src.get('variables', {}).items()}
    comps = {}

    def index(n):
        if n.get('reusable'):
            comps[n['id']] = n
        for c in n.get('children') or []:
            index(c)
    for root in src['children']:
        index(root)

    def resolve(v):
        return variables.get(v[1:]) if isinstance(v, str) and v.startswith('$') else v

    def text(node, frame, width, path):
        fs, lh, fw, ff = node.get('fontSize'), node.get('lineHeight'), node.get('fontWeight'), node.get('fontFamily')
        if fs is None:
            return
        label = f'{path} «{str(node.get("content", ""))[:40]}»'
        literal = [k for k, v in (('размер', fs), ('межстрочный', lh), ('толщина', fw)) if v is not None and not str(v).startswith('$')]
        if literal:
            rep.add('T1', frame, label, 'числом: ' + ', '.join(literal))
        for v in (fs, lh):
            m = re.fullmatch(r'\$(?:type|leading)-[a-z0-9]+-(\d+)', str(v))
            if m and width and int(m.group(1)) != width:
                rep.add('T2', frame, label, f'{v} в кадре {width}')
        size = float(resolve(fs) or 0)
        lead = resolve(lh)
        line = round(size * float(lead), 2) if lead not in (None, 'normal') and float(lead) < 4 else float(lead or 0)
        weight = norm_weight(resolve(fw) if fw is not None else 400)
        if width and size and not role_of(system, width, size, line, weight):
            rep.add('T3', frame, label, f'{size:g}/{line:g} {weight} — ближайшая роль {nearest_role(system, width, size, weight)}')
        fam = resolve(ff) if ff else None
        if fam and fam not in system['fonts']:
            rep.add('T4', frame, label, str(fam))

    def color(value, frame, where):
        if isinstance(value, dict):
            value = value.get('color') if value.get('type') == 'color' else None
        if not isinstance(value, str):
            return
        if value.startswith('$'):
            return
        c = hex_norm(value)
        if c is None:
            return
        if in_palette(system, c):
            names = [k for k, x in system['vars'].items() for y, _ in themed(x) if isinstance(y, str) and c in colors_in(y)]
            rep.add('C1', frame, where, f'{value} = ${names[0]}' if names else value)
        else:
            rep.add('C2', frame, where, value)

    def walk(n, frame, width, path, inherited_kind=None):
        name = n.get('name', '')
        here = f'{path} / {name}' if path else name
        if n.get('type') == 'text':
            text(n, frame, width, here)
        for key in ('fill', 'stroke'):
            if key in n:
                color(n[key], frame, f'{here} ({key})')
        h = n.get('height')
        if isinstance(h, (int, float)) and h != int(h):
            rep.add('G1', frame, here, f'{h}')
        kind = kind_of(name) or ('кнопка' if any(c.get('name') == 'Текст кнопки' for c in n.get('children') or []) else None)
        if n.get('type') == 'ref':
            own = sorted(k for k in n if k in STYLE_KEYS_ON_REF)
            if own:
                rep.add('K1', frame, here, 'свои ' + ', '.join(own) + f' у экземпляра «{comps.get(n.get("ref"), {}).get("name", n.get("ref"))}»')
            for did, over in (n.get('descendants') or {}).items():
                style = sorted(k for k in over if k in STYLE_KEYS_ON_REF and not str(over[k]).startswith('$type-')
                               and not str(over[k]).startswith('$leading-') and k not in ('fontFamily',))
                for key in ('fill', 'stroke'):
                    if key in over:
                        color(over[key], frame, f'{here} › {did} ({key})')
                if 'fontSize' in over:
                    text({**over, 'content': over.get('content', did)}, frame, width, f'{here} › {did}')
                if [k for k in style if k not in ('fill', 'stroke', 'fontSize', 'lineHeight', 'fontWeight')]:
                    rep.add('K1', frame, f'{here} › {did}', 'свои ' + ', '.join(style))
        elif kind and n.get('type') == 'frame' and not n.get('reusable') and not inherited_kind:
            rep.add('K2', frame, here, f'{kind} не из компонента')
            looks[(kind, width)].append((signature(n, resolve), frame, here))
        for c in n.get('children') or []:
            walk(c, frame, width, here, inherited_kind or kind)

    looks = defaultdict(list)
    for root in src['children']:
        if root.get('reusable'):
            continue
        m = re.search(r'/\s*(\d{3,4})\s*$', root.get('name', ''))
        width = int(m.group(1)) if m else (root.get('width') if root.get('width') in BASE_WIDTHS else None)
        walk(root, root.get('name', root.get('id')), width, '')
    for (kind, width), items in looks.items():
        sigs = defaultdict(list)
        for sig, frame, where in items:
            sigs[sig].append(f'{frame}: {where}')
        if len(sigs) > 1:
            variants = [f'вариант {i + 1} ({len(v)} шт.: {sig}) — например {v[0]}' for i, (sig, v) in enumerate(sorted(sigs.items(), key=lambda x: -len(x[1])))]
            rep.add('K3', f'ширина {width}', kind, '; '.join(variants))


def kind_of(name):
    low = name.lower()
    for kind, words in KINDS.items():
        if any(w in low for w in words) and 'текст кнопки' not in low:
            return kind
    return None


def signature(n, resolve):
    """Вид элемента: заливка, рамка, отступы, высота, стиль первого текста."""
    def first_text(x):
        if x.get('type') == 'text':
            return x
        for c in x.get('children') or []:
            t = first_text(c)
            if t:
                return t
        return None
    t = first_text(n) or {}
    parts = [f'фон {resolve(n.get("fill")) if isinstance(n.get("fill"), str) else "—"}',
             f'рамка {resolve(n.get("stroke")) if isinstance(n.get("stroke"), str) else "—"}',
             f'отступы {n.get("padding", "—")}',
             f'текст {resolve(t.get("fontSize"))}/{resolve(t.get("fontWeight"))}' if t else 'без текста']
    return ', '.join(str(p) for p in parts)


# ---------- HTML-экспорт кадров ----------

class Export(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.texts, self.colors = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        style = dict(x.split(':', 1) for x in (a.get('style') or '').split(';') if ':' in x)
        style = {k.strip(): v.strip() for k, v in style.items()}
        self.stack.append((tag, a.get('data-pencil-name', ''), style))
        props = [(k, v) for k, v in style.items() if re.fullmatch(r'color|background(-color|-image)?|border(-[a-z]+)?-?color|border(-[a-z]+)?|outline(-color)?|fill|stroke|box-shadow', k)]
        props += [(k, a[k]) for k in ('fill', 'stroke') if a.get(k)]
        for key, value in props:
            for c in colors_in(value):
                self.colors.append((self.path(), key, c))

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        if data.strip() and self.stack:
            tag, name, style = self.stack[-1]
            if 'font-size' in style:
                self.texts.append((self.path(), data.strip()[:40], style))

    def path(self):
        return ' / '.join(n for _, n, _ in self.stack if n)[-160:]


EXPORT_NAME = re.compile(r'-(\d{3,4})(?:-(light|dark))?\.html$')


def check_export(pkg: Path, system, rep: Report, with_colors: bool):
    """Кадры <страница>-<ширина>[-<тема>].html в любой подпапке пакета (кроме исходника и прежних передач)."""
    checked = 0
    for f in sorted(pkg.rglob('*.html')):
        if 'transport' in f.relative_to(pkg).parts:
            continue
        h = f.read_text(encoding='utf-8')
        m = EXPORT_NAME.search(f.name)
        # Кадр без ширины в имени (h0TKPu.html) — ширина верхнего кадра, тема — неизвестна.
        top = re.search(r'<body[^>]*>.*?style="[^"]*?(?<![-\w])width:\s*(\d+)px', h, re.S)
        if not m and not top:
            continue
        width = design_width(int(m.group(1) if m else top.group(1)))
        theme = (m and m.group(2)) or next((t for t in ('light', 'dark') if t in f.stem.split('-')), '*')
        frame = str(f.relative_to(pkg))
        checked += 1
        p = Export()
        p.feed(h)
        for where, text, st in p.texts:
            size = px(st['font-size'])
            lh = st.get('line-height', 'normal')
            line = px(lh) if lh.endswith('px') else round(size * float(lh), 2) if lh not in ('normal', '') else 0
            weight = norm_weight(st.get('font-weight', '400'))
            if not role_of(system, width, size, line, weight):
                rep.add('T3', frame, f'{where} «{text}»', f'{size:g}/{line:g} {weight} — ближайшая роль {nearest_role(system, width, size, weight)}')
            fam = st.get('font-family', '').split(',')[0].strip().strip('"\'')
            if fam and fam not in system['fonts'] and fam not in ('system-ui', 'sans-serif', 'monospace'):
                rep.add('T4', frame, f'{where} «{text}»', fam)
        if with_colors:
            for where, key, c in p.colors:
                if not in_palette(system, c, theme):
                    rep.add('C2', frame, f'{where} ({key})', c + (f' (в теме {theme})' if theme != '*' and c in system['palette'] else ''))
    if not checked:
        rep.add('S0', pkg.name, 'HTML-экспорт', 'нет ни исходника, ни кадров экспорта с шириной')


# ---------- отчёт ----------

def allowed(code, frame, where, detail):
    for a in guard_cfg().get('allow', []):
        if a.get('code') == code and re.search(a.get('match', '^$'), f'{frame} | {where} | {detail}'):
            return True
    return False


def filtered(rep: Report):
    out = Report()
    for code, items in rep.items.items():
        for item in items:
            if not allowed(code, *item):
                out.add(code, *item)
    return out


def markdown(pkg: Path, rep: Report, tokens: Path, limit=40):
    status = 'работу не начинаю' if rep.severe() else 'работу начинаю параллельно'
    lines = [f'Проверка пакета `{pkg.name}` по дизайн-системе (`{tokens}`): {status}, пакет на доработку.', '']
    for code in ['S0', 'T3', 'T2', 'T4', 'C2', 'K1', 'K3', 'T1', 'C1', 'K2', 'G1']:
        items = rep.items.get(code)
        if not items:
            continue
        mark = 'серьёзное' if code in SEVERE else 'нарушение'
        lines.append(f'**{code} · {TITLES[code]}** ({mark}, {len(items)}):')
        groups = defaultdict(list)
        for frame, where, detail in items:
            groups[detail].append(f'{frame}: {where}')
        for detail, places in sorted(groups.items(), key=lambda x: -len(x[1]))[:limit]:
            more = f' и ещё {len(places) - 1}' if len(places) > 1 else ''
            lines.append(f'- {detail} — {places[0]}{more}')
        if len(groups) > limit:
            lines.append(f'- … ещё {len(groups) - limit} видов, полный список — guard-report.json')
        lines.append('')
    return '\n'.join(lines)


def cmd_package(argv):
    pkg = Path(argv[0])
    sync = Path(argv[argv.index('--sync') + 1]) if '--sync' in argv else None
    rep = Report()
    system, tokens = load_system(pkg)
    src = None
    if not system:
        rep.add('S0', pkg.name, 'typography.json', 'нет ролей текста: ни typography.json в пакете, ни guard.tokens / guard.roles')
    else:
        src = load_source(pkg)
        if src:
            check_source(src, system, rep)
        else:  # исходник точнее: экспорт — только когда исходника нет
            check_export(pkg, system, rep, with_colors=True)
    if system:
        print(f'система: {tokens}', file=sys.stderr)
    rep = filtered(rep)
    out = Path(cfg().get('outDir', '.design-transfer/out'))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'guard-report.json').write_text(json.dumps({c: v for c, v in rep.items.items() if v}, ensure_ascii=False, indent=1), encoding='utf-8')
    scope = '' if src or not system else ' (по экспорту: исходника transport/snapshot.html нет — привязку к переменным и компоненты не проверить)'
    if not rep.any():
        print(f'{pkg.name}: по дизайн-системе чисто{scope}')
        return 0
    md = markdown(pkg, rep, tokens) + scope.strip()
    print(md)
    for code, items in sorted(rep.items.items()):
        if items:
            print(f'{code} {"СЕРЬЁЗНОЕ" if code in SEVERE else "нарушение"}: {len(items)}', file=sys.stderr)
    if sync:
        from datetime import date
        head = cfg().get('guard', {}).get('syncHeader', '## Разработчик → Дизайнер · {date} · {package}: несоответствие дизайн-системе')
        with sync.open('a', encoding='utf-8') as f:
            f.write('\n' + head.format(date=date.today().strftime('%d.%m.%Y'), package=pkg.name) + f'\n\n{md}\n\n'
                    'Прошу исправить в макете и прислать пакет заново.\n')
    return 2 if rep.severe() else 1


# ---------- код: встроенные стили ----------

CODE_RULES = [
    (r'\.blade\.php$|\.html$', [(r'\sstyle\s*=\s*["\']', 'атрибут style'), (r'<style[\s>]', 'тег <style>'), (r':style\s*=', 'атрибут :style')]),
    (r'\.(ts|tsx|js|jsx|mjs)$', [(r"\.style\.[a-zA-Z]+\s*=", "element.style.… ="), (r'\.style\.setProperty\(', 'style.setProperty'),
                            (r'\.style\.removeProperty\(', 'style.removeProperty'), (r'cssText', 'cssText'),
                            (r"setAttribute\(\s*['\"]style['\"]", "setAttribute('style')"), (r'style=\{\{', 'style={{…}}')]),
]


def cmd_code(argv):
    g = guard_cfg()
    roots = [r for r in g.get('code', ['frontend/src', 'frontend/app', 'src', 'app', 'resources/views']) if Path(r).is_dir()]
    skip = re.compile(g.get('codeSkip', r'/(node_modules|vendor|build|Tests?|tests?)/|\.test\.|\.spec\.'))
    found = []
    for root in roots:
        for f in Path(root).rglob('*'):
            if not f.is_file() or skip.search(str(f)):
                continue
            for pat, rules in CODE_RULES:
                if re.search(pat, f.name):
                    for i, line in enumerate(f.read_text(encoding='utf-8', errors='ignore').splitlines(), 1):
                        for rx, label in rules:
                            if re.search(rx, line):
                                found.append(f'{f}:{i} {label}')
    base_file = Path(g.get('baseline', 'scripts/design-guard/baseline.json'))
    # Известные места без номеров строк, по одному на каждое вхождение: новое в том же файле не прячется за старым.
    baseline = Counter(json.loads(base_file.read_text(encoding='utf-8')).get('code', [])) if base_file.exists() else Counter()
    if '--write-baseline' in argv:
        data = json.loads(base_file.read_text(encoding='utf-8')) if base_file.exists() else {}
        data['code'] = sorted(re.sub(r':\d+ ', ' ', x) for x in found)
        base_file.parent.mkdir(parents=True, exist_ok=True)
        base_file.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f'baseline: {len(data["code"])} known places')
        return 0
    new, left = [], Counter(baseline)
    for x in found:
        k = re.sub(r':\d+ ', ' ', x)
        if left[k]:
            left[k] -= 1
        else:
            new.append(x)
    old = len(found) - len(new)
    for x in new:
        print('NEW', x)
    print(f'inline styles: {len(new)} new, {old} known (baseline {base_file})')
    return 2 if new else 0


def cmd_system(argv):
    pkg = Path(argv[0]) if argv else Path(cfg().get('package', '.'))
    system, tokens = load_system(pkg)
    if not system:
        sys.exit('нет ролей текста: guard.tokens / guard.roles или typography.json в пакете')
    print(json.dumps({'source': tokens, 'fonts': sorted(system['fonts']),
                      'roles': {r: {str(w): v for w, v in ws.items()} for r, ws in system['roles'].items()},
                      'palette': {c: sorted(t) for c, t in system['palette'].items()}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    cmds = {'package': cmd_package, 'code': cmd_code, 'system': cmd_system}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    sys.exit(cmds[sys.argv[1]](sys.argv[2:]))
