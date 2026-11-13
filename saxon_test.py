#!/usr/bin/env python3
"""
saxon_test.py - local port of the Saxon Test Generator (Tester.exe v1.44).

Reads the original problem library (Smde._bk), runs each problem's randomization
script, and writes a printable HTML test (+ answer key) for one or more forms.

  python saxon_test.py --list [--book 65] [--grep fraction]
  python saxon_test.py --book 65 --count 20 --forms A,B --title "Math 65 Test 4" -o test.html
  python saxon_test.py --ids SX650033,SX540002 --forms A,B -o test.html

Notes: $once/$each/$every semantics were inferred from the library (the help file
is compressed). Problems needing drawing/typesetting functions (line, fraction,
polynom, slate, ...) are not supported yet and are skipped. Equation objects are
rendered by a heuristic MTEF reader and are flagged (~) in the key when approximate.
"""
import re, sys, struct, math, random, html, argparse, os

u32 = lambda b, o: struct.unpack('>I', b[o:o+4])[0]
mac = lambda b: b.decode('mac_roman')

# ---------------------------------------------------------------- library parser
def load_library(path):
    d = open(path, 'rb').read()
    ents = []
    for m in re.finditer(rb'((?:SX|AM|AL|SM)[A-Z0-9]{6})    ', d[:70000]):
        t = u32(d, m.start() + 30)
        if 0x1000 < t < len(d): ents.append((m.group(1).decode(), t))
    out = []
    for pid, t in sorted(ents, key=lambda e: e[1]):
        r = parse_record(d, t)
        if r: r['id'] = pid; out.append(r)
    return out

def parse_record(d, t):
    try:
        o = t; titles = []
        while True:   # title-style fields: [u32 len][u32 inner][04 00 00 00 00 00][text]; variants have several
            L = u32(d, o)
            if d[o+8:o+14] != b'\x04\0\0\0\0\0' or L > 400: break
            titles.append(mac(d[o+14:o+4+L]).strip()); o += 4 + L
        title = next((x for x in titles if x), '')
        kl = u32(d, o); kw = mac(d[o+4:o+4+kl]); o += 4 + kl
        sl = u32(d, o+14); s0 = o + 20
        script = mac(d[s0:s0+sl-2]).split('\0')[0]; o = s0 + sl - 2
    except Exception:
        return None
    items = []
    while o + 6 <= len(d):
        L = u32(d, o)
        if L < 2 or o + 4 + L > len(d): break
        p = d[o+4:o+4+L]; o += 4 + L
        if L == 2 and p[0] == 9: break
        if p[1] == 0 and b'\0' not in p[2:]: items.append((p[0], mac(p[2:])))
        else: items.append(('blob', p))
    prompt = ''
    if '=' not in script and not re.search(r'\w\(', script):
        t3 = next((i for i, (k, v) in enumerate(items) if k == 3), None)
        if t3 is not None: prompt = script; script = items.pop(t3)[1]
    return {'title': title, 'kw': re.sub(r'[^ -~]', '', kw), 'script': script, 'prompt': prompt.strip(), 'items': items}

# ---------------------------------------------------------------- expression language
TOK = re.compile(r'\s*(?:(\d*\.\d+|\d+\.?)|"((?:[^"]|"")*)"|(\$\w+)|([A-Za-z_]\w*)|(<>|<=|>=|[-+*/^()\[\],=<>|&!]))')
class Retry(Exception): pass
class Unsupported(Exception): pass

def tokenize(s):
    # normalize whitespace / tabs; drop trailing colon-only labels if whole line is just a label
    s = s.replace('\t', ' ').strip()
    pos = 0; out = []
    while pos < len(s):
        m = TOK.match(s, pos)
        if not m or m.end() == pos:
            # skip isolated colons / punctuation that appear in labels
            if s[pos] in ':,;?!' :
                pos += 1
                continue
            raise Unsupported('syntax: ' + s[pos:pos+30].replace('\n',' '))
        pos = m.end()
        n, st, dl, idn, op = m.groups()
        if n is not None: out.append(('n', float(n) if '.' in n else int(n.rstrip('.') or 0)))
        elif st is not None: out.append(('s', st.replace('""', '"')))
        elif dl: out.append(('d', dl.lower()))
        elif idn:
            w = idn.lower(); out.append(('o', {'and': '&', 'or': '|', 'not': '!'}[w]) if w in ('and', 'or', 'not') else ('i', w))
        else: out.append(('o', op))
    return out

class P:  # recursive-descent parser -> AST tuples
    def __init__(s, toks): s.t = toks; s.i = 0
    def pk(s): return s.t[s.i] if s.i < len(s.t) else (None, None)
    def nx(s): v = s.pk(); s.i += 1; return v
    def isop(s, *ops): k, v = s.pk(); return k == 'o' and v in ops
    def parse(s):
        e = s.orx()
        if s.i != len(s.t): raise Unsupported('trailing tokens')
        return e
    def orx(s):
        e = s.andx()
        while s.isop('|'): s.nx(); e = ('b', '|', e, s.andx())
        return e
    def andx(s):
        e = s.notx()
        while s.isop('&'): s.nx(); e = ('b', '&', e, s.notx())
        return e
    def notx(s):
        if s.isop('!'): s.nx(); return ('u', '!', s.notx())
        return s.cmp()
    def cmp(s):
        e = s.add()
        while s.isop('=', '<>', '<', '>', '<=', '>='): op = s.nx()[1]; e = ('b', op, e, s.add())
        return e
    def add(s):
        e = s.mul()
        while s.isop('+', '-'): op = s.nx()[1]; e = ('b', op, e, s.mul())
        return e
    def mul(s):
        e = s.un()
        while s.isop('*', '/'): op = s.nx()[1]; e = ('b', op, e, s.un())
        return e
    def un(s):
        if s.isop('-'): s.nx(); return ('u', '-', s.un())
        if s.isop('+'): s.nx(); return s.un()
        return s.pw()
    def pw(s):
        e = s.prim()
        if s.isop('^'): s.nx(); return ('b', '^', e, s.un())
        return e
    def prim(s):
        k, v = s.nx()
        if k == 'n': return ('n', v)
        if k == 's': return ('s', v)
        if k == 'd': return ('d', v)
        if k == 'o' and v == '(': e = s.orx(); s.nx(); return e
        if k == 'i':
            if s.isop('('):
                s.nx(); args = []
                if not s.isop(')'):
                    args.append(s.orx())
                    while s.isop(','): s.nx(); args.append(s.orx())
                s.nx(); return ('c', v, args)
            if s.isop('['): s.nx(); ix = s.orx(); s.nx(); return ('x', v, ix)
            return ('v', v)
        raise Unsupported('parse error')

def parse_expr(src): return P(tokenize(src)).parse()

# ---------------------------------------------------------------- script compiler
ASSIGN = re.compile(r'^([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*=(?!=)(.*)$', re.S)
def compile_script(script):
    # strip comments (# to end of line) and blank lines; keep original for line numbers if needed
    raw = re.split(r'[\r\n]+', script)
    lines = []
    for l in raw:
        # remove # comments, but not inside quotes (simple heuristic)
        if '#' in l:
            # crude: drop from # if not after an odd number of quotes
            parts = l.split('#')
            keep = parts[0]
            for i, p in enumerate(parts[1:], 1):
                if keep.count('"') % 2 == 1:
                    keep += '#' + p
                else:
                    break
            l = keep
        l = l.strip()
        if l:
            lines.append(l)
    pos = [0]
    def block(stop):
        out = []
        while pos[0] < len(lines):
            ln = lines[pos[0]]; w = re.match(r'[A-Za-z_]+', ln); w = w.group(0).lower() if w else ''
            if w in stop and not ASSIGN.match(ln): return out
            pos[0] += 1
            if w == 'if' and not ASSIGN.match(ln):
                cond = parse_expr(ln[2:].lstrip()); a = block(('else', 'endif')); b = []
                if pos[0] < len(lines) and lines[pos[0]].lower().startswith('else'):
                    pos[0] += 1; b = block(('endif',))
                if pos[0] < len(lines): pos[0] += 1  # consume endif if present
                out.append(('if', cond, a, b))
            elif w == 'while' and not ASSIGN.match(ln):
                cond = parse_expr(ln[5:].lstrip()); body = block(('endwhile',)); 
                if pos[0] < len(lines): pos[0] += 1
                out.append(('while', cond, body))
            else:
                m = ASSIGN.match(ln)
                if m:
                    ix = parse_expr(m.group(2)[1:-1]) if m.group(2) else None
                    out.append(('set', m.group(1).lower(), ix, parse_expr(m.group(3))))
                else:
                    try: out.append(('do', parse_expr(ln)))
                    except Unsupported:
                        if re.search(r'[=(\[]', ln): raise
                        # bare label / prose line such as "Compare:" -> no-op
        return out
    return block(())

# ---------------------------------------------------------------- interpreter
ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'x x twenty thirty forty fifty sixty seventy eighty ninety'.split()
def words(n):
    n = int(n)
    if n < 0: return 'negative ' + words(-n)
    if n < 20: return ONES[n]
    if n < 100: return TENS[n//10] + ('-' + ONES[n % 10] if n % 10 else '')
    if n < 1000: return ONES[n//100] + ' hundred' + (' ' + words(n % 100) if n % 100 else '')
    return words(n//1000) + ' thousand' + (' ' + words(n % 1000) if n % 1000 else '')

def num(v):
    if isinstance(v, str):
        try:
            v = float(v) if '.' in v else int(v)
        except Exception:
            return 0
    if isinstance(v, float) and abs(v - round(v)) < 1e-9: return int(round(v))
    return v

def fmt_val(v, f=None):
    if isinstance(v, str): return v
    if f:
        try: return f % v
        except Exception: pass
    v = num(v)
    if isinstance(v, float): return ('%.6f' % v).rstrip('0').rstrip('.')
    return str(v)

class Interp:
    def __init__(s, rng, shared, pid):
        s.rng, s.shared, s.pid = rng, shared, pid
        s.v = {}; s.arr = {}; s.pools = {}; s.fmts = {}; s.choices = None; s.mcorrect = None; s.bad = []
    def get(s, n, default=0): return s.v.get(n, default)
    def run(s, stmts):
        for st in stmts:
            k = st[0]
            if k == 'set':
                val = s.ev(st[3])
                if st[2] is None: s.v[st[1]] = val
                else: s.arr.setdefault(st[1], {})[int(s.ev(st[2]))] = val
            elif k == 'do': s.ev(st[1])
            elif k == 'if':
                s.run(st[2] if s.ev(st[1]) else st[3])
            elif k == 'while':
                n = 0
                while s.ev(st[1]):
                    s.run(st[2]); n += 1
                    if n > 5000: raise Retry()
    def ev(s, n):
        k = n[0]
        if k == 'n' or k == 's': return n[1]
        if k == 'd': return math.pi if n[1] == '$pi' else math.pi/180 if n[1] == '$dtr' else n[1]
        if k == 'v': return s.get(n[1])
        if k == 'x': return s.arr.get(n[1], {}).get(int(s.ev(n[2])), 0)
        if k == 'u':
            x = s.ev(n[2]); return (0 if x else 1) if n[1] == '!' else -x
        if k == 'b':
            op = n[1]
            if op == '|': return 1 if (s.ev(n[2]) or s.ev(n[3])) else 0
            if op == '&': return 1 if (s.ev(n[2]) and s.ev(n[3])) else 0
            a, b = s.ev(n[2]), s.ev(n[3])
            if op == '+': 
                if isinstance(a, str) or isinstance(b, str):
                    return fmt_val(a) + fmt_val(b)
                return num(a) + num(b)
            if op == '-': return num(a) - num(b)
            if op == '*': return num(a) * num(b)
            if op == '/': 
                bb = num(b)
                return num(a) / bb if bb else 0
            if op == '^': 
                aa, bb = num(a), num(b)
                try:
                    return aa ** bb if not (aa < 0 and bb != int(bb)) else 0
                except Exception:
                    return 0
            if isinstance(a, str) or isinstance(b, str):
                sa, sb = fmt_val(a), fmt_val(b)
                if op == '=': return int(sa == sb)
                if op == '<>': return int(sa != sb)
                return 0
            a, b = num(a), num(b)
            if op == '=': return 1 if abs(a - b) < 1e-9 else 0
            if op == '<>': return int(not (abs(a - b) < 1e-9))
            return int({'<': a < b, '>': a > b, '<=': a <= b + 1e-9, '>=': a >= b - 1e-9}[op])
        return s.call(n[1], n[2])
    # -- function library
    def pool(s, name): return s.pools[name]
    def draw(s, name, mode=None):
        p = s.pools[name]; lo, hi, step = p['lo'], p['hi'], p['step'] or 1
        if hi < lo: lo, hi = hi, lo
        n = max(1, int(round((hi - lo) / step)) + 1)
        val = lambda i: num(round(lo + i * step, 6))
        mode = mode or p['mode']
        if mode == '$sign': return s.rng.choice([-1, 1])
        key = (s.pid, name)
        def pick(used):
            if len(used) >= n: used.clear()
            for _ in range(80):
                v = val(s.rng.randrange(n))
                if v not in used: break
            used.add(v); return v
        if mode == '$once': return pick(s.shared.setdefault(key, set()))
        if mode == '$every':
            cnt = s.shared.get(('ev',) + key, s.rng.randrange(n)); s.shared[('ev',) + key] = cnt + 1
            return val(cnt % n)
        return pick(p['used'])      # $each: no repeats within one problem
    def call(s, f, args):
        if f == 'random':
            if not args or args[0][0] != 'v':   # random(lo,hi)
                a = [s.ev(x) for x in args]; return s.rng.randint(int(a[0]), int(a[1]))
            name = args[0][1]
            if len(args) == 1: return s.draw(name)
            if len(args) == 2 and args[1][0] == 'd': 
                if name not in s.pools: s.pools[name] = dict(lo=-1, hi=1, step=1, mode=args[1][1], used=set())
                return s.draw(name, args[1][1])
            mode = args[1][1] if args[1][0] == 'd' else '$each'; lo_hint = None
            if mode not in ('$each', '$once', '$every', '$sign'):      # '$each1' = $each with lower bound 1; typos like '$pnce'
                mm = re.fullmatch(r'\$(each|once|every)(\d+)', mode)
                if mm: mode = '$' + mm.group(1); lo_hint = int(mm.group(2))
                else: mode = {'$pnce': '$once', '$never': '$each'}.get(mode, '$each')
            rest = [s.ev(x) for x in (args[2:] if args[1][0] == 'd' else args[1:])]
            if lo_hint is not None and len(rest) == 1: rest = [lo_hint, rest[0]]
            s.pools[name] = dict(lo=rest[0], hi=rest[1], step=rest[2] if len(rest) > 2 else 1, mode=mode, used=set())
            return s.draw(name)
        if f == 'select':
            i = int(s.ev(args[0])); i = max(1, min(i, len(args) - 1)); return s.ev(args[i])
        if f == 'cat':
            return ''.join(fmt_val(s.ev(x), s.fmts.get(x[1]) if x[0] == 'v' else None) for x in args)
        if f == 'literal':      # n-th letter of the alphabet, skipping the letters named in arg 1
            name = str(s.ev(args[0])).lower(); n = int(num(s.ev(args[1])))
            letters = [c for c in 'abcdefghijklmnopqrstuvwxyz' if c not in name]
            s.v[args[-1][1]] = letters[(n - 1) % len(letters)]; return 0
        if f == 'format':
            fm = s.ev(args[0])
            for a in args[1:]:
                if a[0] == 'v': s.fmts[a[1]] = fm
            return 0
        if f == 'mode':
            vals = [(s.ev(a), a[1] if a[0] == 'v' else None) for a in args[2:]]
            perm = list(range(len(vals))); s.rng.shuffle(perm)
            s.choices = [vals[i] for i in perm]; s.mcorrect = perm.index(0)
            s.v[args[0][1]] = 0   # status code: 0 = ok (scripts do reject(m<>0))
            s.arr[args[1][1]] = {j+1: s.choices[j][0] for j in range(len(perm))}
            return 0
        a = [s.ev(x) for x in args]
        if f == 'require':
            if not a[0]: raise Retry()
            return 0
        if f == 'reject':
            if a[0]: raise Retry()
            return 0
        if f == 'mod': 
            aa, bb = num(a[0]), num(a[1]) if len(a)>1 else 1
            return aa % bb if bb else 0
        if f == 'abs': return abs(num(a[0]))
        if f == 'int': return int(num(a[0]))
        if f == 'nint': return int(math.floor(num(a[0]) + 0.5))
        if f == 'sgn': 
            x = num(a[0]); return (x > 0) - (x < 0)
        if f == 'min': return min(num(x) for x in a)
        if f == 'max': return max(num(x) for x in a)
        if f == 'sqr': 
            x = num(a[0]); return math.sqrt(x) if x >= 0 else 0
        if f in ('sin', 'cos', 'tan'): return getattr(math, f)(num(a[0]))
        if f == 'atn': return math.atan(num(a[0]))
        if f == 'atn2': return math.atan2(num(a[0]), num(a[1]))
        if f == 'acos': return math.acos(num(a[0]))
        if f == 'gcf': return math.gcd(int(num(a[0])), int(num(a[1])))
        if f == 'rel_prim': return int(math.gcd(int(num(a[0])), int(num(a[1]))) == 1)
        if f == 'cat': return ''.join(fmt_val(x) for x in a)
        if f == 'comma':
            x = num(a[0]); return f'{x:,}' if isinstance(x, int) else f'{x:,.2f}'.rstrip('0').rstrip('.')
        if f == 'word': return words(a[0])
        if f == 'duplicat':
            keys = [round(float(x), 6) if isinstance(x, (int, float)) else str(x) for x in a]
            return int(len(set(keys)) < len(keys))
        if f == 'fences':
            pair = {'$paren': '()', '$bparen': '()', '$brack': '[]', '$bbrack': '[]',
                    '$brace': r'\{\}', '$bbrace': r'\{\}', '$abs': '||'}.get(a[0], '()')
            body = lx_unwrap(fmt_val(tex(a[1])))
            if pair == r'\{\}':
                return lx_wrap(r'\left\{' + body + r'\right\}')
            if pair == '||':
                return lx_wrap(r'\left|' + body + r'\right|')
            l, r = pair[0], pair[1]
            return lx_wrap(r'\left' + l + body + r'\right' + r)
        if f == 'supersub':
            base = lx_unwrap(fmt_val(tex(a[0])))
            def _sn(v):
                if isinstance(v, (int, float)):
                    n = num(v)
                    return str(n)
                s = str(fmt_val(v))
                return s
            if len(a) > 1 and a[1] != '' and not (len(a) > 2 and num(a[1]) == 0):
                base += '^{' + _sn(a[1]) + '}'
            if len(a) > 2 and a[2] != '':
                base += '_{' + _sn(a[2]) + '}'
            return lx_wrap(base)
        if f == 'upper': return str(a[0]).upper()
        if f == 'lower': return str(a[0]).lower()
        if f == 'mathsym':
            # Prefer LaTeX macros where they exist
            n = int(num(a[0]))
            latex_sym = {43: '+', 45: '-', 61: '=', 180: r'\times', 184: r'\div', 176: r'^\circ',
                         163: r'\leq', 179: r'\geq', 185: r'\neq', 177: r'\pm', 112: r'\pi',
                         60: '<', 62: '>'}
            if n in latex_sym:
                return lx_wrap(latex_sym[n])
            return MATHSYM.get(n, chr(n))
        if f == 'radical':
            body = lx_unwrap(fmt_val(tex(a[1])))
            n = int(num(a[0]))
            if n == 2:
                return lx_wrap(r'\sqrt{' + body + '}')
            return lx_wrap(r'\sqrt[' + str(n) + ']{' + body + '}')
        if f == 'fraction':
            return lx_wrap(r'\frac{' + lx_unwrap(fmt_val(tex(a[0]))) + '}{' + lx_unwrap(fmt_val(tex(a[1]))) + '}')
        if f == 'polynom':
            return lx_wrap(polynom(str(fmt_val(a[0]))))
        # known unsupported drawing / typesetting functions from the original Tester
        if f in ('slate', 'line', 'loadpict',
                 'flood', 'overbar', 'root', 'picture',
                 'graph', 'draw', 'arc', 'circle', 'rect', 'poly', 'text'):
            raise Unsupported(f)
        raise Unsupported(f)


MATHSYM = {43: '+', 45: '\u2212', 61: '=', 180: '\u00d7', 184: '\u00f7', 176: '\u00b0', 163: '\u2264', 179: '\u2265', 185: '\u2260', 177: '\u00b1', 112: '\u03c0', 60: '<', 62: '>'}
# polynom(): compact polynomial strings -> readable math.
# Library format is a sequence of signed terms. Each term is:
#   [sign] [coef] [^coef_exp]? ( factor )*
# where factor is  letter[^exp]?  or  digits^exp  (digit bases only appear with an explicit ^).
# Examples:  '+1x^+6y^+3'  '-2X^2+5'  '+14^-1+1d^+24^-2'  '+1xy^-4'
# Non-polynomial strings (words, bare letters) are returned unchanged.

def polynom(src):
    """Compact library polynomials -> readable math with real superscripts.

    Term grammar (library cat / %+.0f style):
        term   := [sign] [coef ['^' exp]] {factor}
        factor := letter ['^' exp] | digits '^' exp
    Digit bases only appear with an explicit caret (e.g. 4^-2 mid-term).
    """
    src = str(src)
    if not src or ' ' in src or not re.search(r'[\d^+\-]', src):
        return src
    s = src.replace('+-', '-').replace('-+', '-').replace('--', '+')

    def exp_mark(e):
        try:
            n = int(e)
        except (TypeError, ValueError):
            return '^{' + str(e) + '}'
        if n == 1:
            return ''
        return '^{' + str(n) + '}'

    def read_exp(pos):
        """Read ^[+-]?digits. If digits were stolen from a following base^exp
        factor (rest starts with ^), give them back one by one."""
        if pos >= len(s) or s[pos] != '^':
            return None, pos
        pos += 1
        sign = ''
        if pos < len(s) and s[pos] in '+-':
            sign = s[pos]
            pos += 1
        d0 = pos
        while pos < len(s) and s[pos].isdigit():
            pos += 1
        if pos == d0:
            return None, d0 - 1 - len(sign)
        # d^+24^-2  → after taking 24, rest is '^-2'. The leading digits of the
        # next factor were swallowed; push them back until rest no longer starts
        # with '^' (or we run out of digits).
        while pos > d0 and pos < len(s) and s[pos] == '^':
            pos -= 1
        if pos == d0:
            return None, d0 - 1 - len(sign)
        return sign + s[d0:pos], pos

    terms = []
    pos = 0
    n = len(s)
    while pos < n:
        sg = '+'
        if s[pos] in '+-':
            sg = s[pos]
            pos += 1
        if pos >= n:
            break

        co = None
        co_exp = None
        # coefficient digits
        if pos < n and (s[pos].isdigit() or s[pos] == '.'):
            d0 = pos
            if s[pos] == '.':
                pos += 1
            while pos < n and s[pos].isdigit():
                pos += 1
            if pos < n and s[pos] == '.' and '.' not in s[d0:pos]:
                pos += 1
                while pos < n and s[pos].isdigit():
                    pos += 1
            co = s[d0:pos]
            co_exp, pos = read_exp(pos)

        factors = []
        while pos < n and s[pos] not in '+-':
            if s[pos].isalpha():
                base = s[pos]
                pos += 1
                exp, pos = read_exp(pos)
                factors.append((base, exp))
            elif s[pos].isdigit():
                d0 = pos
                while pos < n and s[pos].isdigit():
                    pos += 1
                base = s[d0:pos]
                exp, pos = read_exp(pos)
                if exp is None:
                    # bare digits mid-term with no ^ — not a format we know
                    return src
                factors.append((base, exp))
            else:
                return src

        if co is None and not factors:
            return src
        if co is not None:
            try:
                if float(co) == 0 and factors:
                    continue
            except ValueError:
                pass
        if factors and co in ('1', '1.0') and co_exp is None:
            co = ''

        piece = ''
        if co is not None and co != '':
            piece += co
            if co_exp is not None:
                piece += exp_mark(co_exp)
        for i, (base, exp) in enumerate(factors):
            # Dot only before a numeric base (d²4⁻² → d²·4⁻²). Letter products stay xy.
            if base[0].isdigit() and (piece or i > 0):
                piece += r'\cdot '
            piece += base
            if exp is not None:
                piece += exp_mark(exp)
        if piece:
            terms.append((sg, piece))

    if not terms:
        return src
    out = ''
    for i, (sg, t) in enumerate(terms):
        if i == 0:
            out = ('-' if sg == '-' else '') + t
        else:
            out += (' - ' if sg == '-' else ' + ') + t
    return out


# LaTeX fragment markers ('\x10'...'\x11'): math functions wrap pure LaTeX so typeset()
# can html-escape plain text while leaving math for KaTeX.
def lx_wrap(s):
    s = lx_unwrap(s)
    if not s:
        return s
    return '\x10' + s + '\x11'

def lx_unwrap(s):
    s = str(s)
    if '\x10' not in s:
        return s
    parts = []; i = 0; n = len(s)
    while i < n:
        if s[i] == '\x10':
            j = s.find('\x11', i + 1)
            if j < 0:
                parts.append(s[i+1:]); break
            parts.append(s[i+1:j]); i = j + 1
        else:
            j = s.find('\x10', i)
            if j < 0:
                parts.append(s[i:]); break
            parts.append(s[i:j]); i = j
    return ''.join(parts)




# ---- Math HTML rendering (print-safe, no Node required) ----
_KATEX_CACHE = {}
_KATEX_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor', 'katex', 'render.cjs')

def _brace_arg(s, i):
    """If s[i] is '{', return (content, index_after_closing). Else (None, i)."""
    if i >= len(s) or s[i] != '{':
        return None, i
    depth, j = 1, i + 1
    while j < len(s) and depth:
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
        j += 1
    return s[i + 1:j - 1], j

def latex_to_html(tex):
    """Convert the small LaTeX subset we emit into print-ready HTML."""
    tex = str(tex).strip()
    # Normalize common forms
    tex = (tex.replace(r'\left', '').replace(r'\right', '')
              .replace(r'\cdot ', '\u22c5').replace(r'\cdot', '\u22c5')
              .replace(r'\times', '\u00d7').replace(r'\div', '\u00f7')
              .replace(r'\pm', '\u00b1').replace(r'\pi', '\u03c0')
              .replace(r'\leq', '\u2264').replace(r'\geq', '\u2265')
              .replace(r'\neq', '\u2260').replace(r'\circ', '\u00b0')
              .replace(r'\{', '{').replace(r'\}', '}'))
    out = []
    i, n = 0, len(tex)
    while i < n:
        if tex.startswith(r'\frac', i):
            i += 5
            num, i = _brace_arg(tex, i)
            den, i = _brace_arg(tex, i)
            if num is None or den is None:
                out.append(html.escape(r'\frac'))
                continue
            out.append('<span class="fr"><span>%s</span><span>%s</span></span>' % (
                latex_to_html(num), latex_to_html(den)))
        elif tex.startswith(r'\sqrt', i):
            i += 5
            root = None
            if i < n and tex[i] == '[':
                j = tex.find(']', i)
                if j > i:
                    root = tex[i + 1:j]
                    i = j + 1
            body, i2 = _brace_arg(tex, i)
            if body is None:
                out.append('√')
                continue
            i = i2
            inner = latex_to_html(body)
            # Radical with vinculum (overbar on the radicand)
            idx_html = ('<span class="radical-index">%s</span>' % html.escape(root)
                        if root and root != '2' else '')
            out.append(
                '<span class="radical">%s<span class="radical-sym">√</span>'
                '<span class="radical-vinculum">%s</span></span>' % (idx_html, inner)
            )
        elif tex.startswith(r'\text', i):
            i += 5
            body, i = _brace_arg(tex, i)
            out.append(html.escape(body or ''))
        elif tex[i] == '{':
            body, i = _brace_arg(tex, i)
            out.append(latex_to_html(body or ''))
        elif tex[i] == '^':
            i += 1
            if i < n and tex[i] == '{':
                body, i = _brace_arg(tex, i)
                out.append('<sup>%s</sup>' % latex_to_html(body or ''))
            elif i < n:
                out.append('<sup>%s</sup>' % html.escape(tex[i])); i += 1
        elif tex[i] == '_':
            i += 1
            if i < n and tex[i] == '{':
                body, i = _brace_arg(tex, i)
                out.append('<sub>%s</sub>' % latex_to_html(body or ''))
            elif i < n:
                out.append('<sub>%s</sub>' % html.escape(tex[i])); i += 1
        elif tex.startswith(r'\\', i):
            out.append('<br>'); i += 2
        elif tex[i] == '\\' and i + 1 < n and tex[i + 1].isalpha():
            # unknown control sequence: skip the name
            j = i + 1
            while j < n and tex[j].isalpha():
                j += 1
            i = j
        else:
            ch = tex[i]
            if ch in '<>&':
                out.append(html.escape(ch))
            else:
                out.append(ch)
            i += 1
    return ''.join(out)

def render_latex_batch(exprs):
    """Render LaTeX to HTML. Prefer pure Python (always works offline/print).
    Optional Node+KaTeX for higher fidelity when available."""
    if not exprs:
        return []
    results = [None] * len(exprs)
    missing_idx = []
    missing_tex = []
    for i, e in enumerate(exprs):
        key = e if isinstance(e, str) else str(e)
        if key in _KATEX_CACHE:
            results[i] = _KATEX_CACHE[key]
        else:
            missing_idx.append(i)
            missing_tex.append(key)
    if not missing_tex:
        return results

    # Try Node KaTeX once; if it fails, use pure Python for everything
    use_node = os.path.isfile(_KATEX_SCRIPT)
    node_ok = False
    if use_node:
        try:
            import subprocess, json
            env = os.environ.copy()
            # GUI-launched apps on macOS often lack node on PATH
            env['PATH'] = '/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:' + env.get('PATH', '')
            proc = subprocess.run(
                ['node', _KATEX_SCRIPT],
                input=json.dumps(missing_tex),
                capture_output=True, text=True, timeout=20, env=env,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                rendered = json.loads(proc.stdout)
                if len(rendered) == len(missing_tex):
                    for i, k, h in zip(missing_idx, missing_tex, rendered):
                        _KATEX_CACHE[k] = h
                        results[i] = h
                    node_ok = True
        except Exception:
            node_ok = False

    if not node_ok:
        for i, k in zip(missing_idx, missing_tex):
            h = '<span class="eq">' + latex_to_html(k) + '</span>'
            _KATEX_CACHE[k] = h
            results[i] = h
    return results

def render_latex(tex):
    return render_latex_batch([tex])[0]


def tex(x):
    """The original program typesets any compact expression with exponents automatically."""
    if isinstance(x, str) and '^' in x and ' ' not in x: return polynom(x)
    return x


def typeset(s):
    """Escape plain text; pre-render LaTeX fragments to static KaTeX HTML (print-safe)."""
    s = str(s)
    s = re.sub('\x03([^\x04]*)\x04', lambda m: '^{' + m.group(1) + '}', s)
    s = re.sub('\x05([^\x06]*)\x06', lambda m: '_{' + m.group(1) + '}', s)
    while True:
        def _frac(m):
            return '\x10' + ('\\frac{' + lx_unwrap(m.group(1)) + '}{' + lx_unwrap(m.group(2)) + '}') + '\x11'
        s2 = re.sub('\x01([^\x01\x02]*)\x1f([^\x01\x02]*)\x02', _frac, s)
        if s2 == s:
            break
        s = s2

    LX, RX = chr(0x10), chr(0x11)
    parts = []
    i, n = 0, len(s)
    while i < n:
        if s[i] == LX:
            j = s.find(RX, i + 1)
            if j < 0:
                parts.append(('plain', s[i:])); break
            latex = s[i + 1:j].strip()
            if latex.startswith('\\(') and latex.endswith('\\)'):
                latex = latex[2:-2]
            for a, b in (('\u2212', '-'), ('\u00d7', '\\times'), ('\u00f7', '\\div'),
                         ('\u22c5', '\\cdot'), ('\u2013', '-'), ('\u2014', '-'),
                         ('\u221a', '\\sqrt')):
                pass  # placeholder
            latex = latex.replace('\u2212', '-').replace('\u00d7', '\\times')
            latex = (latex
                .replace('−', '-')
                .replace('×', '\\times')
                .replace('÷', '\\div')
                .replace('⋅', '\\cdot')
                .replace('–', '-')
                .replace('—', '-')
                .replace('√', '\\sqrt'))
            parts.append(('tex', latex))
            i = j + 1
        else:
            j = s.find(LX, i)
            if j < 0:
                parts.append(('plain', s[i:])); break
            parts.append(('plain', s[i:j])); i = j

    texes = [t for kind, t in parts if kind == 'tex']
    rendered = render_latex_batch(texes) if texes else []
    ri = 0
    out = []
    for kind, val in parts:
        if kind == 'plain':
            out.append(html.escape(val))
        else:
            out.append(rendered[ri]); ri += 1
    return ''.join(out)

# ---------------------------------------------------------------- equation blobs (heuristic MTEF)
SYM = {0x2b: '+', 0x2d: '\u2212', 0xb4: '\u00d7', 0xb8: '\u00f7', 0x3d: '=', 0xb9: '\u2260', 0x3c: '<', 0x3e: '>', 0xa3: '\u2264', 0xb3: '\u2265', 0xb1: '\u00b1', 0xbb: '\u2248', 0xa5: '\u221e', 0xd6: '\u221a', 0xb0: '\u00b0', 0xd7: '\u22c5', 0xd0: '\u2220', 0x40: '\u2245', 0x5e: '\u22a5'}
def decode_blob(b, it):
    k = b.rfind(b'\x0a\x01'); e = b.find(b'\x03FFFE', k)
    reg = b[k+2:e if e > 0 else len(b)]
    m0 = re.search(rb'\x02[\x80-\x9f]', reg)      # first character record; header length varies between blobs
    reg = reg[m0.start():] if m0 else reg[6:]
    approx = any(c == 3 for c in reg)
    lines = [[]]; i = 0
    while i < len(reg):
        c = reg[i]; nxt = reg[i+1] if i + 1 < len(reg) else 0
        if c == 0xc1 and reg[i+1:i+3] == b'\x00\x01': lines.append([]); i += 3; continue
        if c == 0 and reg[i:i+2] == b'\x00\x01' and reg[i+2:i+4] == b'\x02\x86' and lines[-1]: lines.append([]); i += 2; continue
        if 0x81 <= c <= 0x9f and i + 1 < len(reg) and (32 <= nxt < 127 or (c == 0x86 and nxt >= 0x80)):
            if c == 0x83 and chr(nxt).isalnum() and not (i + 2 < len(reg) and reg[i+2] in b'\x00\x01\x02\xc1' ) : pass
            if c == 0x86: lines[-1].append(SYM.get(nxt, chr(nxt) if nxt < 128 else '?'))
            elif c == 0x83 and chr(nxt).islower(): lines[-1].append(('v', chr(nxt)))     # uppercase letters are literals (e.g. the missing addend N)
            else: lines[-1].append(chr(nxt))
            i += 2; continue
        i += 1
    return lines, approx

NUMROW = re.compile(r'^(\$?)(-?[\d,]*)(?:\.(\d*))?$')
def stack_html(rows):
    """Vertical arithmetic: operator column | integer part ($ attached, right-aligned) | decimal point | fraction digits.
    Aligning on the decimal point keeps columns straight even when the numbers have different lengths."""
    trs = []; parsed = []
    for r in rows:
        op = ''; m = re.match(r'^([+\u2212\u00d7\u00f7])\s*(\S.*)$', r)
        if m: op, r = m.group(1), m.group(2)
        parsed.append((op, r))
    rl = max([i for i, (op, r) in enumerate(parsed) if op] or [len(parsed) - 1])
    for idx, (op, r) in enumerate(parsed):
        mn = NUMROW.match(r.strip())
        if mn and (mn.group(2) or mn.group(3)):
            ip, dp, fp = html.escape(mn.group(1) + mn.group(2)), ('.' if mn.group(3) is not None else ''), (mn.group(3) or '')
        else: ip, dp, fp = typeset(r), '', ''
        trs.append('<tr%s><td class="op">%s</td><td class="i">%s</td><td class="d">%s</td><td class="f">%s</td></tr>' % (' class="rl"' if idx == rl else '', op, ip, dp, fp))
    return '<table class="stk">' + ''.join(trs) + '</table>'

def render_blob(lines, it):
    rows = []
    for ln in lines:
        for x in ln:
            if isinstance(x, tuple) and x[1] not in it.v: it.bad.append(x[1])
        txt = ''.join(fmt_val(it.get(x[1]), it.fmts.get(x[1])) if isinstance(x, tuple) else x for x in ln)
        txt = re.sub(r'\s+', ' ', txt).strip()
        if txt: rows.append(txt)
    if not rows: return ''
    if len(rows) > 1: return stack_html(rows)
    return '<span class="eq">' + typeset(rows[0]) + '</span>'

def blob_html(b, it):
    """Render an equation/figure blob. Returns (html, approximate?)."""
    # 1. some equation objects simply embed their text with `var` placeholders
    runs = [m.group(0).decode('latin1') for m in re.finditer(rb'[\x20-\x7e]{3,}', b) if b'`' in m.group(0)]
    if runs:
        t = max(runs, key=len); t = re.sub(r'^[0-9A-Fa-f]{1,3},', '', t)
        if '[]' in t:     # placeholders for symbol-font objects: take their identities from the MTEF tail
            GREEK = dict(p='\u03c0', a='\u03b1', b='\u03b2', q='\u03b8', m='\u03bc', l='\u03bb', f='\u03c6', d='\u03b4', s='\u03c3', w='\u03c9')
            greek = [GREEK.get(chr(m.group(1)[0]), '?') for m in re.finditer(rb'\x84([a-z])', b)]
            syms = [SYM.get(m.group(1)[0], '?') for m in re.finditer(rb'\x86([\x80-\xff\x20-\x7e])', b)]
            objs = greek + syms
            t = re.sub(r'\[\]', lambda m: objs.pop(0) if objs else '\u03c0', t)
        return '<span class="eq">' + typeset(sub_text(t, it)) + '</span>', False
    # 2. MTEF character stream
    lines, ap = decode_blob(b, it)
    r = render_blob(lines, it)
    if r: return r, ap or bool(re.search(r'\(\s*\)', plain(r)))
    return '<i class="fig">[figure not rendered]</i>', True

# ---------------------------------------------------------------- problem instantiation
def sub_text(s, it):
    def rep(m):
        e = m.group(1).strip().lower()
        try: n = parse_expr(e); v = it.ev(n)
        except Unsupported: raise
        except Exception: it.bad.append(e); return ''
        if n[0] == 'v' and n[1] not in it.v: it.bad.append(e)
        if n[0] == 'x' and int(it.ev(n[2])) not in it.arr.get(n[1], {}): it.bad.append(e)
        return fmt_val(tex(v), it.fmts.get(e) if n[0] == 'v' else None)
    return re.sub(r'`([^`]*)`', rep, s)

def html_text(s): return typeset(s).replace('\r', '<br>').replace('\n', '<br>')

class Problem:
    def __init__(s, rec):
        s.rec = rec; s.id = rec['id']; s.title = rec['title']; s.kw = rec['kw']
        try: s.prog = compile_script(rec['script']); s.err = None
        except Exception as e: s.prog = None; s.err = 'compile: %s' % e
    def make(s, rng, shared):
        if s.prog is None: raise Unsupported(s.err)
        for _ in range(400):
            it = Interp(rng, shared, s.id)
            try: it.run(s.prog)
            except Retry: continue
            r = s.render(it)
            if r['bad']: raise Unsupported('unresolved: ' + ','.join(sorted(set(r['bad']))[:3]))
            if not re.sub(r'<[^>]+>|\s', '', ''.join(r['q'])): raise Unsupported('empty question')
            return r
        raise Unsupported('could not satisfy require/reject')
    def render(s, it):
        q, ch, ans, approx = [], [], [], False
        if s.rec.get('prompt'): q.append(html_text(s.rec['prompt']))
        items = s.rec['items']
        kinds = [k for k, v in items]
        has6, has8 = 6 in kinds, 8 in kinds
        first6 = kinds.index(6) if has6 else None
        nblob = kinds.count('blob'); seen_blob = 0
        first8 = kinds.index(8) if has8 else None
        # a blob directly before choices that start at d1 is the correct choice (z) drawn as an equation object
        zblob = first8 - 1 if has8 and first8 > 0 and kinds[first8 - 1] == 'blob' and re.match(r'\W*d1\b', items[first8][1]) else None
        raw_ch = []                                   # (substituted text, html)
        for idx, (kind, val) in enumerate(items):
            if kind == 4: q.append(html_text(sub_text(val, it)))
            elif kind == 8: raw_ch.append((sub_text(val, it), html_text(sub_text(val, it))))
            elif kind == 6: ans.append(html_text(sub_text(val, it)))
            elif kind == 'blob' and idx == zblob:
                h, ap = blob_html(val, it); approx |= ap; raw_ch.insert(0, (re.sub(r'<[^>]+>', '', h), h))
            elif kind == 'blob':
                seen_blob += 1
                h, ap = blob_html(val, it); approx |= ap
                # a blob after the answer text, or the last of several blobs when there is no answer text/choices, is the answer
                to_ans = (has6 and idx > first6) or (not has6 and not has8 and seen_blob == nblob and (nblob >= 2 or 4 in kinds[:idx]))
                (ans if to_ans else q).append(h)
        if it.choices:
            ch = [html.escape(fmt_val(v, it.fmts.get(n))) for v, n in it.choices]
            ans = ['(%s) %s' % ('ABCD'[it.mcorrect], ch[it.mcorrect])]
        elif raw_ch:
            # the original program shuffles the choices; the correct one is the one equal to z (else the first one listed)
            zt = fmt_val(it.v['z'], it.fmts.get('z')) if 'z' in it.v else None
            order = list(range(len(raw_ch))); it.rng.shuffle(order)
            right = 0 if zblob is not None else next((i for i, (t, h) in enumerate(raw_ch) if zt is not None and t.strip(' $') == str(zt).strip(' $')), 0)
            ch = [raw_ch[i][1] for i in order]
            if not ans: ans = ['(%s) %s' % ('ABCDEFGH'[order.index(right)], raw_ch[right][1])]
        return dict(q=q, ch=ch, ans=ans, approx=approx, bad=it.bad)

def probe(p):
    try: g = p.make(random.Random(1), {}); p.why = ''; p.approx = g['approx']; return True
    except Unsupported as e: p.why = str(e); return False
    except Exception as e: p.why = 'error: %r' % e; return False

# ---------------------------------------------------------------- HTML output (one-page Saxon-style layout)
import math as _m
def plain(h): return html.unescape(re.sub(r'<[^>]+>', '', h.replace('<br>', ' ')))

def is_calc(g):
    """Short computation items (stacked arithmetic, bare expressions) go in columns; wordy ones get full width."""
    txt = ' '.join(g['q']); pl = plain(txt)
    return not g['ch'] and '?' not in pl and ('class="stk"' in txt or len(pl) <= 28)

def item_lines(g, cpl):
    txt = ' '.join(g['q']); pl = plain(txt)
    stack = max([m.count('<tr>') + 0.4 for m in re.findall(r'<table class="stk">(.*?)</table>', txt, re.S)] or [0])
    lines = max(stack, _m.ceil(len(pl) / cpl)) + txt.count('<br>')
    if 'class="fr"' in txt: lines += 1.1
    if g['ch']:
        mx = max(len(plain(c)) for c in g['ch']); lines += 1 if mx <= 14 else _m.ceil(len(g['ch']) / 2)
    return max(1, lines)

def layout(gen, keep_order):
    words = [x for x in gen if not is_calc(x[1])]; calcs = [x for x in gen if is_calc(x[1])]
    order = gen if keep_order else words + calcs
    nw = len(words) if not keep_order else 0
    return order, nw, 3

FIT_K = 1.5     # static-estimate safety factor, calibrated against headless Chromium (0 silent overflows in 60 layouts)
SHEET_PT = 8.15 * 72

def estimate(order, nw, cols, fs, gw=7, gc=9):
    lh = fs * 1.38; cpl = (540 - 30) / (fs * 0.5)
    W = order[:nw]; C = order[nw:]
    hw = sum(item_lines(g, cpl) * lh for p, g in W)
    rows = [C[i:i+cols] for i in range(0, len(C), cols)]
    hc = sum(max(item_lines(g, cpl / cols) for p, g in r) * lh * 1.12 for r in rows)
    return (hw + hc) * FIT_K + gw * len(W) + gc * len(rows) + (gw * .6 if rows else 0)

def fit(order, nw, cols):
    """Largest font size (pt) whose estimated height fits the sheet; returns (fs, word_gap, calc_gap, fits).
    The page's inline script refines this in the browser; this is the static fallback."""
    n = max(1, nw + (len(order) - nw + cols - 1) // cols)
    for fs in (13, 12.5, 12, 11.5, 11, 10.5, 10, 9.5, 9, 8.5, 8):
        need = estimate(order, nw, cols, fs)
        if need <= SHEET_PT:
            left = SHEET_PT - need
            return fs, 7 + min(34, left / n * 0.6), 9 + min(38, left / n * 0.6), True
    return 8, 4, 5, False


def katex_assets(base=''):
    """CSS for pre-rendered KaTeX HTML. Optional auto-render catches leftover delimiters."""
    if base and not base.endswith('/'):
        base = base + '/'
    local_css = base + 'katex.min.css'
    local_js = base + 'katex.min.js'
    local_auto = base + 'auto-render.min.js'
    cdn = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist'
    return (
        '<link rel="stylesheet" href="%s" onerror="this.onerror=null;this.href=\'%s/katex.min.css\'">\n'
        '<script defer src="%s" onerror="this.onerror=null;this.src=\'%s/katex.min.js\'"></script>\n'
        '<script defer src="%s" onerror="this.onerror=null;this.src=\'%s/contrib/auto-render.min.js\'"></script>\n'
        '<script>\n'
        'document.addEventListener("DOMContentLoaded",function(){\n'
        '  function go(){\n'
        '    if(typeof renderMathInElement==="undefined"){setTimeout(go,40);return;}\n'
        '    try{renderMathInElement(document.body,{delimiters:['
        '{left:"$$",right:"$$",display:true},'
        '{left:"\\\\[",right:"\\\\]",display:true},'
        '{left:"\\\\(",right:"\\\\)",display:false}'
        '],throwOnError:false,strict:"ignore"});}catch(e){}\n'
        '    window.dispatchEvent(new Event("load"));\n'
        '  }\n'
        '  go();\n'
        '});\n'
        '</script>\n'
    ) % (local_css, cdn, local_js, cdn, local_auto, cdn)


CSS = """
@page{size:letter;margin:.5in}
*{box-sizing:border-box}body{margin:0;font-family:Georgia,'Times New Roman',serif;color:#000;background:#d9d9d9}
.page{width:7.5in;height:9.95in;margin:16px auto;padding:0;background:#fff;page-break-after:always;break-after:page}
.page:last-child{page-break-after:auto;break-after:auto}
@media screen{.page{padding:.5in;width:8.5in;height:11in;box-shadow:0 1px 6px #0004}}
@media print{body{background:#fff}.page{margin:0 auto}}
.tbar{font:bold 13pt Arial,Helvetica,sans-serif;letter-spacing:6pt;padding:2pt 6pt;margin-bottom:8pt;background:linear-gradient(90deg,#fff 0,#e0e0e0 40%,#ececec 100%);-webkit-print-color-adjust:exact;print-color-adjust:exact}
.head{display:flex;align-items:flex-start;gap:16pt;margin-bottom:10pt}
.box{border:1.6px solid #000;border-radius:2px;font-size:28pt;line-height:1;padding:7pt 22pt 8pt;min-width:78pt;text-align:center}
.note{flex:1;font-style:italic;font-size:9.5pt;padding-top:8pt}
.name{font-size:12pt;padding-top:14pt;white-space:nowrap}.name span{display:inline-block;width:2.5in;border-bottom:1px solid #000;vertical-align:baseline}
.sheet{font-size:var(--fs,11pt);line-height:1.38;height:8.15in}
.q{display:flex;gap:6pt;break-inside:avoid}.n{font-weight:bold;min-width:20pt;text-align:right;flex:none}.b{flex:1;min-width:0}
.words .q{margin-bottom:var(--gw,8pt)}
.calc{display:grid;grid-template-columns:repeat(var(--cols,3),1fr);column-gap:16pt;row-gap:var(--gc,12pt);margin-top:calc(var(--gw,8pt) * .6)}
.ch{display:grid;grid-template-columns:repeat(var(--cc,2),auto);justify-content:start;column-gap:18pt;margin-top:2pt}.ch div{margin:0}
table.stk{border-collapse:collapse;display:inline-table;margin:2pt 0 2pt 4pt;font-family:"Times New Roman",Times,"Liberation Serif",serif;font-size:1.08em;line-height:1.28;font-variant-numeric:lining-nums tabular-nums}
.stk td{padding:0;white-space:nowrap}.stk td.op{padding-right:6pt;text-align:left}.stk td.i{text-align:right}.stk td.d,.stk td.f{text-align:left}
.stk tr.rl td{border-bottom:1.3px solid #000;padding-bottom:1.5pt}
sup,sub{font-size:.75em;line-height:0}
.eq{font-family:inherit}.fr{display:inline-block;vertical-align:middle;text-align:center;margin:0 2px;font-size:.92em}
.fr>span{display:block;padding:0 3px;line-height:1.15}.fr>span:first-child{border-bottom:1px solid #000}.radical{display:inline-flex;align-items:stretch;vertical-align:middle;margin:0 1px;line-height:1.15}.radical-index{font-size:.62em;line-height:1;align-self:flex-start;margin:0.05em -0.12em 0 0;padding-right:1px}.radical-sym{font-size:1.2em;line-height:1;align-self:stretch;display:flex;align-items:center;padding:0}.radical-vinculum{border-top:1.35px solid currentColor;padding:0 0.18em 0 0.04em;margin-top:0.14em;line-height:1.25;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.fig,.ap{color:#999;font-size:8.5pt}.foot{text-align:right;font:italic bold 11pt Georgia,serif;padding-top:4pt}
.key .sheet{columns:3;column-gap:22pt;font-size:10.5pt}.key .k{break-inside:avoid;margin-bottom:5pt;display:flex;gap:6pt}.key .tag{color:#888;font-size:8pt}
.warn{display:none;background:#fff3cd;border:1px solid #e0b100;padding:6px 10px;margin-bottom:8pt;font:11px Arial}@media print{.warn,.warn.on{display:none}}.warn.on{display:block}
"""

JS = '''<script>
(function(){
  function fit(sh){
    var inner=sh.firstElementChild, page=sh.closest('.page'), warn=page.querySelector('.warn');
    function set(n,v,u){sh.style.setProperty(n,v+u)}
    function get(n,d){return parseFloat(sh.style.getPropertyValue(n))||d}
    function ok(){return inner.getBoundingClientRect().height<=sh.clientHeight+0.5}
    var fs=13.5, gw=4, gc=5;
    set('--gw',gw,'pt');set('--gc',gc,'pt');set('--fs',fs,'pt');
    while(!ok()&&fs>7.5){fs-=.25;set('--fs',fs,'pt')}
    for(var i=0;i<80;i++){set('--gw',gw+1,'pt');set('--gc',gc+1.3,'pt'); if(ok()){gw+=1;gc+=1.3}else{set('--gw',gw,'pt');set('--gc',gc,'pt');break}}
    if(warn) warn.classList.toggle('on',!ok());
  }
  function all(){document.querySelectorAll('.page:not(.key) .sheet').forEach(fit)}
  window.addEventListener('load',all); window.addEventListener('beforeprint',all);
  if(document.fonts&&document.fonts.ready) document.fonts.ready.then(all);
})();
</script>'''

def build_html(problems, forms, title, seed, number='', keep_order=False, katex_base=''):
    parts = []; shared = {}; warns = []
    for form in forms:
        rng = random.Random((seed, form).__repr__()); gen = []
        for p in problems:
            for attempt in range(8):
                try: gen.append((p, p.make(rng, shared))); break
                except Unsupported: continue
            else: print('warning: skipped %s (could not generate)' % p.id, file=sys.stderr)
        order, nw, cols = layout(gen, keep_order)
        fs, gw, gc, fits = fit(order, nw, cols)
        if not fits: warns.append('Form %s: %d problems will not fit on one page - reduce the count.' % (form, len(order)))
        label = '%s%s' % (number, form) if number else form
        def qhtml(n, g):
            ch = ''
            if g['ch']:
                cc = 4 if max(len(plain(c)) for c in g['ch']) <= 14 else 2
                ch = '<div class="ch" style="--cc:%d">%s</div>' % (cc, ''.join('<div>(%s) %s</div>' % ('ABCDEFGH'[i], c) for i, c in enumerate(g['ch'])))
            return '<div class="q"><div class="n">%d.</div><div class="b">%s%s</div></div>' % (n, '<br>'.join(g['q']), ch)
        head = '<div class="tbar">T E S T</div><div class="head"><div class="box">%s</div><div class="note">%s<br>Form %s</div><div class="name">Name <span></span></div></div>' % (html.escape(label), html.escape(title), form)
        body = ''.join(qhtml(i + 1, g) for i, (p, g) in enumerate(order[:nw]))
        calc = ''.join(qhtml(nw + i + 1, g) for i, (p, g) in enumerate(order[nw:]))
        warn = '<div class="warn%s">Too many problems to fit on one page at a readable size - reduce the count (printing will spill onto a second page).</div>' % (' on' if not fits else '')
        parts.append('<div class="page">%s%s<div class="sheet" style="--fs:%.1fpt;--gw:%.1fpt;--gc:%.1fpt;--cols:%d"><div class="inner"><div class="words">%s</div>%s</div></div><div class="foot">%s</div></div>' % (
            warn, head, fs, gw, gc, cols, body, '<div class="calc">%s</div>' % calc if calc else '', html.escape(title)))
        keyh = ''.join('<div class="k"><div class="n">%d.</div><div>%s %s</div></div>' % (i + 1, ' ; '.join(g['ans']) or '<i>(see problem)</i>', '<span class="tag">~ approx</span>' if g['approx'] else '') for i, (p, g) in enumerate(order))
        parts.append('<div class="page key"><div class="tbar">ANSWER KEY</div><div class="head"><div class="box">%s</div><div class="note">%s<br>Form %s</div></div><div class="sheet">%s</div></div>' % (html.escape(label), html.escape(title), form, keyh))
    return ('<!doctype html><meta charset="utf-8"><title>%s</title>%s'
            '<style>%s</style>%s%s') % (
                html.escape(title), katex_assets(katex_base), CSS, chr(10).join(parts), JS)

# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description='Saxon test generator (local port)')
    ap.add_argument('--lib', default=None, help='path to Smde._bk')
    ap.add_argument('--list', action='store_true'); ap.add_argument('--grep'); ap.add_argument('--book', help='54, 65, 76, 87, A1 (Algebra 1), AM (Advanced Math), DE')
    ap.add_argument('--allow-approx', action='store_true', help='include problems whose equations/figures render approximately'); ap.add_argument('--ids'); ap.add_argument('--count', type=int, default=20); ap.add_argument('--forms', default='A')
    ap.add_argument('--title', default='Saxon Test'); ap.add_argument('--number', default='', help='test number shown in the header box, e.g. 22'); ap.add_argument('--keep-order', action='store_true', help='do not move short computation problems to the end'); ap.add_argument('--seed', default='1'); ap.add_argument('-o', '--out', default='saxon_test.html')
    a = ap.parse_args()
    lib = a.lib or next((p for p in ('Smde._bk', os.path.join(os.path.dirname(__file__), 'Smde._bk')) if os.path.exists(p)), None)
    if not lib: sys.exit('Smde._bk not found - pass --lib')
    probs = [Problem(r) for r in load_library(lib)]
    sel = probs
    if a.book: sel = [p for p in sel if p.id.startswith('SX' + a.book.upper())]
    if a.grep: g = a.grep.lower(); sel = [p for p in sel if g in (p.title + ' ' + p.kw).lower()]
    if a.ids: byid = {p.id: p for p in probs}; sel = [byid[i.strip()] for i in a.ids.split(',')]
    if a.list:
        for p in sel: print('%s  %-3s %-34s %-34s %s' % (p.id, ('~' if getattr(p, 'approx', False) else 'ok') if probe(p) else '--', p.title[:34], re.sub(r'[^ -~]', '', p.kw)[:34], p.why))
        print('\n%d problems, %d supported' % (len(sel), sum(probe(p) for p in sel))); return
    if not a.ids:
        sel = [p for p in sel if probe(p) and (a.allow_approx or not p.approx)]; random.Random(a.seed).shuffle(sel); sel = sel[:a.count]
    pkg = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.dirname(os.path.abspath(a.out)) or '.'
    try:
        katex_base = os.path.relpath(os.path.join(pkg, 'vendor', 'katex'), out_dir)
    except ValueError:
        katex_base = os.path.join(pkg, 'vendor', 'katex')
    # normalize to forward slashes for file URLs
    katex_base = katex_base.replace(chr(92), '/')
    out = build_html(sel, [f.strip() for f in a.forms.split(',')], a.title, a.seed, a.number, a.keep_order, katex_base)
    open(a.out, 'w', encoding='utf-8').write(out); print('wrote', a.out, '-', len(sel), 'problems,', a.forms.count(',') + 1, 'form(s)')
if __name__ == '__main__': main()
