#!/usr/bin/env python3
"""
saxon_facts.py - Facts Practice Test generator for Saxon Test Maker.

Produces printable HTML sheets matching the style of the sample FPT_A/C/H/I PDFs:
  - Gray gradient "FACTS PRACTICE TEST" bar
  - Letter box + title + Name/Time/Date header lines
  - Instruction word above a fixed-size grid of vertical (stack) or long-division (bracket) problems
  - Matching answer key page

Modes:
  full   - every fact in the table exactly once (A/H/I style)
  focus  - ordered pairs where at least one factor is in a focus set (C style)
  practice - user ranges/tags, balanced fill, no adjacent duplicates

CLI examples:
  python3 saxon_facts.py full --op add --sheets 2 --seed 5 -o facts.html
  python3 saxon_facts.py focus --op mul --focus 0,1,2,5 --sheets 1 -o facts.html
  python3 saxon_facts.py practice --op mul --a-min 0 --a-max 9 --b-min 0 --b-max 5 --rows 8 --cols 8 -o facts.html
"""
from __future__ import annotations
import argparse, html, random, sys, os, csv, math
from typing import List, Tuple, Dict, Optional, Set, Iterable

# ---------------------------------------------------------------------------
# Fact bank
# ---------------------------------------------------------------------------

OPS = {
    'add': {'sym': '+', 'word': 'Add.', 'title': 'Addition', 'stack': True},
    'sub': {'sym': '-', 'word': 'Subtract.', 'title': 'Subtraction', 'stack': True},
    'mul': {'sym': 'x', 'word': 'Multiply.', 'title': 'Multiplication', 'stack': True},
    'div': {'sym': ')', 'word': 'Divide.', 'title': 'Division', 'stack': False},
}

def make_fact(op: str, a: int, b: int) -> dict:
    """Create a fact dict. For div: a=divisor, b=quotient, answer=b, dividend=a*b."""
    if op == 'add':
        ans = a + b
    elif op == 'sub':
        ans = a - b
        if ans < 0:
            raise ValueError('negative subtraction')
    elif op == 'mul':
        ans = a * b
    elif op == 'div':
        # a = divisor, b = quotient; answer is quotient; display divisor)dividend
        if a == 0:
            raise ValueError('zero divisor')
        ans = b
        # store dividend as a*b for rendering
    else:
        raise ValueError(op)
    tags = set()
    if a == b:
        tags.add('double')
    if a == 0 or b == 0:
        tags.add('zero')
    if a == 1 or b == 1:
        tags.add('one')
    if op == 'div' and a * b == 0:
        tags.add('zero_dividend')
    return {
        'op': op, 'a': a, 'b': b, 'answer': ans,
        'tags': tags,
        'key': (op, a, b),
    }

def full_table(op: str) -> List[dict]:
    """Stock of facts for each operation.

    add / mul / div: classic complete tables (exactly the sets used by samples A/H/I).
    sub: broader positive stock (minuend 0-20, subtrahend 0-12, non-negative result)
         so each B sheet can be a random draw rather than a fixed inverse table.
    """
    facts = []
    if op == 'add':
        for a in range(10):
            for b in range(10):
                facts.append(make_fact('add', a, b))
    elif op == 'mul':
        for a in range(10):
            for b in range(10):
                facts.append(make_fact('mul', a, b))
    elif op == 'sub':
        # Stock of common positive subtraction facts (not forced to be addition inverses).
        # minuend 0-20, subtrahend 0-12, result >= 0.
        for m in range(0, 21):
            for s in range(0, 13):
                if m - s >= 0:
                    facts.append(make_fact('sub', m, s))
    elif op == 'div':
        for d in range(1, 10):          # divisor 1-9
            for q in range(10):         # quotient 0-9
                facts.append(make_fact('div', d, q))
    else:
        raise ValueError(op)
    return facts

def focus_table(op: str, focus: Set[int]) -> List[dict]:
    """Ordered pairs where at least one operand is in focus (for mul/add)."""
    if op not in ('mul', 'add'):
        raise ValueError('focus only for add/mul')
    facts = []
    for a in range(10):
        for b in range(10):
            if a in focus or b in focus:
                facts.append(make_fact(op, a, b))
    return facts

def practice_fill(op: str, a_range: Tuple[int,int], b_range: Tuple[int,int],
                  n: int, rng: random.Random, tags: Optional[Set[str]] = None) -> List[dict]:
    """Fill n facts with balanced counts, respecting ranges/tags."""
    pool = []
    amin, amax = a_range
    bmin, bmax = b_range
    if op == 'div':
        amin = max(amin, 1)
    for a in range(amin, amax + 1):
        for b in range(bmin, bmax + 1):
            try:
                f = make_fact(op, a, b)
                if tags is None or (f['tags'] & tags):
                    pool.append(f)
            except ValueError:
                continue
    if not pool:
        raise ValueError('empty practice pool')
    # balanced repetition: each appears floor(n/len) or ceil
    base = n // len(pool)
    extra = n % len(pool)
    counts = {f['key']: base for f in pool}
    extras = rng.sample(pool, extra)
    for f in extras:
        counts[f['key']] += 1
    out = []
    for f in pool:
        out.extend([f] * counts[f['key']])
    rng.shuffle(out)
    # repair adjacent identicals (horizontal then vertical later by grid)
    return out

# ---------------------------------------------------------------------------
# Sheet assembly
# ---------------------------------------------------------------------------

PRESETS = {
    'A': {
        'letter': 'A', 'op': 'add', 'mode': 'full',
        'title': '100 Addition Facts', 'instruction': 'Add.',
        'headers': ['Name', 'Date'], 'rows': 10, 'cols': 10,
        'footer_right': 'Saxon Math 5/4',
    },
    'B': {
        # Random draw of 100 facts from the subtraction stock (minuend 0-20,
        # subtrahend 0-12, non-negative). Not forced to be addition inverses.
        'letter': 'B', 'op': 'sub', 'mode': 'full',
        'title': '100 Subtraction Facts', 'instruction': 'Subtract.',
        'headers': ['Name', 'Date'], 'rows': 10, 'cols': 10,
        'footer_right': 'Saxon Math 5/4',
    },
    'C': {
        'letter': 'C', 'op': 'mul', 'mode': 'focus', 'focus': {0,1,2,5},
        'title': "Multiplication Facts:\n0's, 1's, 2's, 5's", 'instruction': 'Multiply.',
        'headers': ['Name', 'Date'], 'rows': 8, 'cols': 8,
        'footer_right': 'Saxon Math 5/4',
    },
    'G': {
        # Default: 64 facts, factors 2-9 on 8x8. Portal also offers a 100-random
        # multiplication variant (same as H but letter G / title adjustable).
        'letter': 'G', 'op': 'mul', 'mode': 'full',
        'title': '64 Multiplication Facts', 'instruction': 'Multiply.',
        'headers': ['Name', 'Date'], 'rows': 8, 'cols': 8,
        'a_range': (2,9), 'b_range': (2,9),
        'footer_right': 'Saxon Math 5/4',
    },
    'H': {
        'letter': 'H', 'op': 'mul', 'mode': 'full',
        'title': '100 Multiplication Facts', 'instruction': 'Multiply.',
        'headers': ['Name', 'Date'], 'rows': 10, 'cols': 10,
        'footer_right': 'Saxon Math 5/4',
    },
    'I': {
        'letter': 'I', 'op': 'div', 'mode': 'full',
        'title': '90 Division Facts', 'instruction': 'Divide.',
        'headers': ['Name', 'Date'], 'rows': 9, 'cols': 10,
        'footer_right': 'Saxon Math 5/4',
    },
}

def _sample_to_n(pool: List[dict], n: int, rng: random.Random) -> List[dict]:
    """Return exactly n facts from pool.

    - If len(pool) == n: shuffle and return (classic full-table behaviour).
    - If len(pool) > n: sample without replacement.
    - If len(pool) < n: balanced repetition (counts differ by at most 1), then shuffle.
    Adjacent-identical repair is applied afterwards by the caller when needed.
    """
    if not pool:
        raise ValueError('empty fact pool')
    if len(pool) == n:
        out = list(pool)
        rng.shuffle(out)
        return out
    if len(pool) > n:
        return rng.sample(pool, n)
    # balanced repetition
    base = n // len(pool)
    extra = n % len(pool)
    counts = {f['key']: base for f in pool}
    for f in rng.sample(pool, extra):
        counts[f['key']] += 1
    out = []
    for f in pool:
        out.extend([f] * counts[f['key']])
    rng.shuffle(out)
    return out

def _repair_adjacent(facts: List[dict]) -> List[dict]:
    """Greedy swap to reduce identical neighbours (horizontal order)."""
    facts = list(facts)
    for i in range(1, len(facts)):
        if facts[i]['key'] == facts[i-1]['key']:
            for j in range(i+1, len(facts)):
                if facts[j]['key'] != facts[i]['key']:
                    facts[i], facts[j] = facts[j], facts[i]
                    break
    return facts

def select_facts(cfg: dict, seed: str) -> List[dict]:
    rng = random.Random(seed)
    op = cfg['op']
    mode = cfg.get('mode', 'full')
    rows = cfg.get('rows', 10)
    cols = cfg.get('cols', 10)
    n = rows * cols

    if mode == 'full':
        if 'a_range' in cfg:  # restricted range (e.g. G factors 2-9)
            amin, amax = cfg['a_range']
            bmin, bmax = cfg.get('b_range', (amin, amax))
            pool = []
            for a in range(amin, amax+1):
                for b in range(bmin, bmax+1):
                    try:
                        pool.append(make_fact(op, a, b))
                    except ValueError:
                        continue
        else:
            pool = full_table(op)
        facts = _sample_to_n(pool, n, rng)
        return _repair_adjacent(facts)
    elif mode == 'focus':
        focus = set(cfg.get('focus', {0,1,2,5}))
        pool = focus_table(op, focus)
        facts = _sample_to_n(pool, n, rng)
        return _repair_adjacent(facts)
    elif mode == 'practice':
        ar = cfg.get('a_range', (0,9))
        br = cfg.get('b_range', (0,9))
        tags = cfg.get('tags')
        facts = practice_fill(op, ar, br, n, rng, tags)
        return _repair_adjacent(facts)
    else:
        raise ValueError(mode)

def _stack_html(a: int, op_sym: str, b: int, answer: Optional[int] = None, show_problem: bool = False) -> str:
    """Vertical arithmetic cell. Problem near the top; blank space below the rule for the answer."""
    if answer is not None:
        if show_problem:
            return ('<div class="cell stack key">'
                    '<div class="prob"><div class="top">%d</div>'
                    '<div class="bot"><span class="op">%s</span>%d</div><div class="rule"></div></div>'
                    '<div class="ans">%d</div></div>') % (a, html.escape(op_sym), b, answer)
        return '<div class="cell stack key"><div class="ans">%d</div></div>' % answer
    return ('<div class="cell stack">'
            '<div class="prob">'
            '<div class="top">%d</div>'
            '<div class="bot"><span class="op">%s</span>%d</div>'
            '<div class="rule"></div>'
            '</div></div>') % (a, html.escape(op_sym), b)

def _div_html(dividend: int, divisor: int, quotient: Optional[int] = None, show_problem: bool = False) -> str:
    """Horizontal division: 8 ÷ 2 = ______ with space for the answer."""
    if quotient is not None:
        if show_problem:
            return ('<div class="cell horiz key">'
                    '<div class="prob">%d ÷ %d =</div>'
                    '<div class="ans">%d</div></div>') % (dividend, divisor, quotient)
        return '<div class="cell horiz key"><div class="ans">%d</div></div>' % quotient
    return ('<div class="cell horiz">'
            '<span class="expr">%d ÷ %d =</span>'
            '<span class="blank"></span></div>') % (dividend, divisor)

def cell_html(fact: dict, is_key: bool = False, show_problem: bool = False) -> str:
    op = fact['op']
    if op == 'div':
        # fact['a'] = divisor, fact['b'] = quotient; dividend = a * b
        dividend = fact['a'] * fact['b']
        if is_key:
            return _div_html(dividend, fact['a'], fact['answer'], show_problem)
        return _div_html(dividend, fact['a'])
    else:
        sym = OPS[op]['sym']
        if is_key:
            return _stack_html(fact['a'], sym, fact['b'], fact['answer'], show_problem)
        return _stack_html(fact['a'], sym, fact['b'])

# ---------------------------------------------------------------------------
# HTML builder (matches sample layout)
# ---------------------------------------------------------------------------

FACTS_CSS = """
@page{size:letter;margin:.45in}
@page landscape{size:letter landscape;margin:.4in}
*{box-sizing:border-box}
body{margin:0;font-family:Georgia,"Times New Roman",Times,serif;color:#000;background:#d9d9d9}
.page{width:7.6in;height:10.1in;margin:12px auto;padding:0;background:#fff;page-break-after:always;break-after:page;position:relative}
.page.landscape{width:10.1in;height:7.6in}
.page:last-child{page-break-after:auto;break-after:auto}
@media screen{.page{padding:.4in;width:8.5in;height:11in;box-shadow:0 1px 6px #0004}
  .page.landscape{width:11in;height:8.5in;padding:.35in}}
@media print{body{background:#fff}.page{margin:0 auto}
  .page.landscape{page:landscape}}
.tbar{font:bold 11pt Arial,Helvetica,sans-serif;letter-spacing:5.5pt;padding:1.5pt 4pt;margin:0 0 5pt 0;
  background:linear-gradient(90deg,#f5f5f5 0%,#d8d8d8 45%,#ececec 100%);
  -webkit-print-color-adjust:exact;print-color-adjust:exact;text-align:center}
.head{display:flex;align-items:flex-start;gap:12pt;margin-bottom:3pt}
.letterbox{border:1.8px solid #000;border-radius:1px;font-family:Georgia,"Times New Roman",serif;
  font-size:30pt;line-height:1;padding:3pt 16pt 5pt;min-width:58pt;text-align:center;font-weight:normal}
.titleblock{flex:1;font-family:Georgia,"Times New Roman",serif;font-weight:bold;font-size:15pt;line-height:1.15;
  padding-top:2pt;white-space:pre-line}
.headers{font-size:11pt;text-align:right;padding-top:2pt;line-height:1.5;min-width:2.3in}
.headers .hline{white-space:nowrap}
.headers .hline span{display:inline-block;width:1.6in;border-bottom:1px solid #000;vertical-align:baseline;margin-left:4pt}
.instr-row{display:flex;justify-content:space-between;align-items:baseline;margin:1pt 0 2pt 0;font-size:11pt}
.instr{font-style:normal}
.instr-date{font-size:11pt}
.instr-date span{display:inline-block;width:1.4in;border-bottom:1px solid #000;margin-left:4pt}
.grid{width:6.9in;height:8.25in;border:1.5px solid #000;margin:0 auto;display:grid;
  grid-template-columns:repeat(var(--cols,10),1fr);grid-template-rows:repeat(var(--rows,10),1fr);
  font-family:"Times New Roman",Times,"Liberation Serif",serif;font-variant-numeric:lining-nums tabular-nums}
.page.landscape .grid{width:9.3in;height:5.9in}
.grid > .cell{border:0.55px solid #555;display:flex;position:relative;overflow:hidden;
  font-size:var(--cfs,12.5pt)}
/* stack cell: problem pinned near top, blank area below rule for writing */
.cell.stack{flex-direction:column;align-items:stretch;justify-content:flex-start;padding:3pt 4pt 2pt;line-height:1.05}
.cell.stack .prob{display:flex;flex-direction:column;align-items:flex-end;width:100%}
.cell.stack .top{padding-right:2pt;font-size:1em}
.cell.stack .bot{display:flex;justify-content:flex-end;align-items:baseline;gap:1pt;padding-right:2pt;width:100%}
.cell.stack .op{font-size:0.95em;margin-right:1pt}
.cell.stack .rule{width:78%;height:0;border-bottom:1.35px solid #000;margin:1.5pt 2pt 0 0}
/* horizontal division: 8 ÷ 2 = ______ */
.cell.horiz{flex-direction:row;align-items:center;justify-content:center;gap:3pt;padding:2pt 4pt;
  font-size:var(--cfs,13pt)}
.cell.horiz .expr{white-space:nowrap}
.cell.horiz .blank{display:inline-block;width:1.1em;min-width:14pt;border-bottom:1.2px solid #000;
  height:1.05em;vertical-align:baseline}
/* key */
.cell.key{align-items:center;justify-content:center}
.cell.key .ans{font-weight:bold;font-size:1.2em}
.cell.stack.key .prob{opacity:0.55;font-size:0.7em;margin-bottom:1pt}
.cell.horiz.key .prob{opacity:0.55;font-size:0.7em;margin-right:4pt}
.foot{position:absolute;bottom:6pt;left:0;right:0;display:flex;justify-content:space-between;
  font-size:8pt;padding:0 4pt}
.foot .fl{color:#444}
.foot .fr{font-style:italic;font-weight:bold}
.key .tbar{letter-spacing:4pt}
"""

def build_facts_html(sheets: List[dict], show_problem_on_key: bool = False) -> str:
    """sheets: list of {letter, title, instruction, headers, rows, cols, facts, footer_left, footer_right, form_label}"""
    parts = []
    for sh in sheets:
        letter = html.escape(sh.get('letter', 'A'))
        title = html.escape(sh.get('title', ''))
        instr = html.escape(sh.get('instruction', ''))
        headers = sh.get('headers', ['Name', 'Date'])
        rows = sh['rows']
        cols = sh['cols']
        facts = sh['facts']
        fl = html.escape(sh.get('footer_left', ''))
        fr = html.escape(sh.get('footer_right', 'Saxon Math 5/4'))
        form = html.escape(str(sh.get('form_label', '')))

        # header lines: first two on right of title, third (if Date) on instruction row
        hlines = []
        extra_date = None
        for i, h in enumerate(headers):
            if i < 2:
                hlines.append('<div class="hline">%s<span></span></div>' % html.escape(h))
            else:
                extra_date = h
        head_right = ''.join(hlines)

        # title may be 1 or 2 lines
        title_html = title.replace('\\n', '\n')

        # instruction row
        if extra_date:
            instr_row = ('<div class="instr-row"><span class="instr">%s</span>'
                         '<span class="instr-date">%s<span></span></span></div>') % (instr, html.escape(extra_date))
        else:
            instr_row = '<div class="instr-row"><span class="instr">%s</span></div>' % instr

        # font size heuristic from grid density
        dens = rows * cols
        if dens >= 100:
            cfs = 12.5
        elif dens >= 80:
            cfs = 13.5
        elif dens >= 64:
            cfs = 14.5
        else:
            cfs = 15.5

        # landscape for division sheets (horizontal problems need width)
        is_div = any(f.get('op') == 'div' for f in facts) or sh.get('op') == 'div'
        page_cls = 'page landscape' if is_div else 'page'

        # TEST page
        cells = ''.join(cell_html(f) for f in facts)
        head = ('<div class="tbar">F A C T S &nbsp; P R A C T I C E &nbsp; T E S T</div>'
                '<div class="head">'
                '<div class="letterbox">%s</div>'
                '<div class="titleblock">%s</div>'
                '<div class="headers">%s</div></div>%s') % (letter, title_html, head_right, instr_row)
        grid = ('<div class="grid" style="--rows:%d;--cols:%d;--cfs:%.1fpt">%s</div>') % (rows, cols, cfs, cells)
        foot = '<div class="foot"><span class="fl">%s</span><span class="fr">%s</span></div>' % (fl, fr)
        parts.append('<div class="%s">%s%s%s</div>' % (page_cls, head, grid, foot))

        # KEY page
        key_cells = ''.join(cell_html(f, is_key=True, show_problem=show_problem_on_key) for f in facts)
        key_head = ('<div class="tbar">A N S W E R &nbsp; K E Y</div>'
                    '<div class="head">'
                    '<div class="letterbox">%s</div>'
                    '<div class="titleblock">%s</div>'
                    '<div class="headers">%s</div></div>'
                    '<div class="instr-row"><span class="instr">%s</span></div>') % (
                        letter, title_html, head_right, instr)
        key_grid = ('<div class="grid" style="--rows:%d;--cols:%d;--cfs:%.1fpt">%s</div>') % (rows, cols, cfs, key_cells)
        parts.append('<div class="%s key">%s%s%s</div>' % (page_cls, key_head, key_grid, foot))

    return ('<!doctype html><meta charset="utf-8"><title>Facts Practice Test</title>'
            '<style>%s</style>\n%s') % (FACTS_CSS, '\n'.join(parts))

# ---------------------------------------------------------------------------
# High-level generate
# ---------------------------------------------------------------------------

def generate(preset: Optional[str] = None, op: Optional[str] = None, mode: Optional[str] = None,
             focus: Optional[str] = None, letter: Optional[str] = None, title: Optional[str] = None,
             instruction: Optional[str] = None, headers: Optional[str] = None,
             rows: Optional[int] = None, cols: Optional[int] = None,
             sheets: int = 1, seed: str = '1', footer_left: str = '',
             footer_right: str = 'Saxon Math 5/4',
             a_range: Optional[str] = None, b_range: Optional[str] = None,
             show_problem_on_key: bool = False) -> str:
    """Build HTML for one or more forms. Each form is Test+Key (2 pages)."""
    if sheets > 20:
        raise ValueError('sheet limit is 20')
    cfg = {}
    if preset and preset.upper() in PRESETS:
        cfg = dict(PRESETS[preset.upper()])
    # Only override preset values when the caller actually supplied them
    if op:
        cfg['op'] = op
    cfg.setdefault('op', 'add')
    if mode:
        cfg['mode'] = mode
    cfg.setdefault('mode', 'full')
    if focus:
        cfg['focus'] = {int(x) for x in focus.split(',') if x.strip().isdigit()}
        cfg['mode'] = 'focus'
    if letter:
        cfg['letter'] = letter
    cfg.setdefault('letter', 'A')
    if title is not None:
        cfg['title'] = title
    elif cfg.get('mode') == 'focus' and 'title' not in cfg:
        foc = sorted(cfg.get('focus', set()))
        cfg['title'] = 'Multiplication Facts:\n' + ', '.join("%d's" % d for d in foc)
    if instruction is not None:
        cfg['instruction'] = instruction
    else:
        cfg.setdefault('instruction', OPS[cfg['op']]['word'])
    if headers:
        cfg['headers'] = [h.strip() for h in headers.split(',') if h.strip()]
    if rows:
        cfg['rows'] = rows
    if cols:
        cfg['cols'] = cols
    if a_range:
        parts = [int(x) for x in a_range.split(',')]
        cfg['a_range'] = (parts[0], parts[1] if len(parts) > 1 else parts[0])
    if b_range:
        parts = [int(x) for x in b_range.split(',')]
        cfg['b_range'] = (parts[0], parts[1] if len(parts) > 1 else parts[0])
    cfg.setdefault('rows', 10)
    cfg.setdefault('cols', 10)
    cfg['footer_left'] = footer_left
    cfg['footer_right'] = footer_right

    out_sheets = []
    forms = [chr(ord('A') + i) for i in range(sheets)]
    for i, form in enumerate(forms):
        # different seed per form so different order
        form_seed = '%s-%s' % (seed, form)
        facts = select_facts(cfg, form_seed)
        # pad or trim to exact grid
        n = cfg['rows'] * cfg['cols']
        if len(facts) < n:
            facts = facts + facts[:n - len(facts)]
        facts = facts[:n]
        sh = dict(cfg)
        sh['facts'] = facts
        sh['form_label'] = form
        # if multi-sheet and letter not forced, use form letter
        if sheets > 1 and not letter:
            sh['letter'] = form
        out_sheets.append(sh)
    return build_facts_html(out_sheets, show_problem_on_key)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description='Saxon Facts Practice Test generator')
    ap.add_argument('mode', nargs='?', default=None, choices=['full', 'focus', 'practice', 'preset'])
    ap.add_argument('--preset', '-p', help='A, B, C, G, H, I')
    ap.add_argument('--op', default=None, choices=list(OPS))
    ap.add_argument('--focus', help='comma digits e.g. 0,1,2,5')
    ap.add_argument('--letter', default=None)
    ap.add_argument('--title', default=None)
    ap.add_argument('--instruction', default=None)
    ap.add_argument('--headers', default=None, help='comma list: Name,Time,Date')
    ap.add_argument('--rows', type=int)
    ap.add_argument('--cols', type=int)
    ap.add_argument('--sheets', type=int, default=1)
    ap.add_argument('--seed', default='1')
    ap.add_argument('--footer-left', default='')
    ap.add_argument('--footer-right', default='Saxon Math 5/4')
    ap.add_argument('--a-range', help='min,max')
    ap.add_argument('--b-range', help='min,max')
    ap.add_argument('--show-problem', action='store_true')
    ap.add_argument('-o', '--out', default='facts.html')
    a = ap.parse_args()
    try:
        html_out = generate(
            preset=a.preset, op=a.op, mode=a.mode,
            focus=a.focus, letter=a.letter,
            title=a.title, instruction=a.instruction, headers=a.headers,
            rows=a.rows, cols=a.cols, sheets=min(a.sheets, 20), seed=a.seed,
            footer_left=a.footer_left, footer_right=a.footer_right,
            a_range=a.a_range, b_range=a.b_range, show_problem_on_key=a.show_problem)
    except Exception as e:
        sys.exit('error: %s' % e)
    open(a.out, 'w', encoding='utf-8').write(html_out)
    print('wrote', a.out)

if __name__ == '__main__':
    main()
