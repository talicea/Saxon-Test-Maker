#!/usr/bin/env python3
"""Local browser portal for saxon_test.py and saxon_facts.py. Run it (or double-click 'Saxon Test Maker.command')."""
import os, sys, html, json, random, threading, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import saxon_test as S
import saxon_facts as F

LIB = os.path.join(HERE, 'Smde._bk')
PROBS = [S.Problem(r) for r in S.load_library(LIB)]
GOOD = [p for p in PROBS if S.probe(p)]
BYID = {p.id: p for p in GOOD}
BOOKS = [('', 'All books'), ('54', 'Math 54'), ('65', 'Math 65'), ('76', 'Math 76'), ('87', 'Math 87'), ('A1', 'Algebra 1'), ('AM', 'Advanced Math'), ('DE', 'Sample/Demo')]

def book_of(pid): return pid[2:4] if pid.startswith('SX') else 'ZZ'

def page():
    rows = ''.join('<tr data-b="%s" data-t="%s" class="%s"><td><input type="checkbox" value="%s"></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        book_of(p.id), html.escape((p.id + ' ' + p.title + ' ' + p.kw).lower()), 'approx' if p.approx else '', p.id, p.id,
        html.escape(p.title), html.escape(p.kw[:60]) + (' <span class="tag">~ approx equations</span>' if p.approx else '')) for p in GOOD)
    opts = ''.join('<option value="%s">%s</option>' % b for b in BOOKS)
    return '''<!doctype html><meta charset="utf-8"><title>Saxon Test Maker</title>
<style>:root{color-scheme:light dark;font-family:-apple-system,system-ui,sans-serif}body{max-width:980px;margin:24px auto;padding:0 16px}
h1{margin:0 0 4px}.sub{color:#777;margin:0 0 16px}.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:end;margin:12px 0}
label{display:flex;flex-direction:column;font-size:12px;color:#777;gap:3px}input,select,button{font:inherit;padding:6px 8px}
button{cursor:pointer}button.go{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:9px 18px;font-weight:600}
.box{height:42vh;overflow:auto;border:1px solid #8884;border-radius:6px}table{border-collapse:collapse;width:100%;font-size:13px}
td{padding:4px 8px;border-bottom:1px solid #8882}tr.approx{opacity:.7}tr:hover{background:#8881}.tag{font-size:11px;color:#b45309}
.n{margin-left:auto;color:#777}
.tabs{display:flex;gap:0;margin:16px 0 0;border-bottom:1px solid #8884}
.tabs button{background:transparent;border:0;border-bottom:2px solid transparent;padding:8px 16px;font-weight:600;color:#777}
.tabs button.on{border-bottom-color:#2563eb;color:inherit}
.panel{display:none}.panel.on{display:block}
.facts-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin:12px 0}
</style>
<h1>Saxon Test Maker</h1>
<div class="tabs">
  <button type="button" class="on" data-tab="tests">Lesson Tests</button>
  <button type="button" data-tab="facts">Facts Practice</button>
</div>

<div id="panel-tests" class="panel on">
<p class="sub">@@N@@ problems available. Pick problems (or let it choose randomly), then generate. About 15-20 problems fit on a page; the type size adjusts automatically. Print to PDF from your browser.</p>
<div class="bar"><label>Title<input id="title" value="Saxon Math" size="22"></label>
<label>Test #<input id="num" value="" size="4" placeholder="22"></label>
<label>Forms<input id="forms" value="A,B" size="8"></label><label>Seed<input id="seed" value="1" size="6"></label>
<label>Book<select id="book">''' + opts + '''</select></label>
<label>Count<input id="count" type="number" value="20" min="1" max="40" style="width:4em"></label>
<label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" id="keep"> Keep my order</label>
<label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" id="approx"> Include ~approx</label>
<span class="n"><span id="sel">0</span> selected</span>
<button class="go" id="go">Generate test</button></div>
<div class="bar"><input id="filter" placeholder="Filter title / keyword / id" style="flex:1;min-width:200px">
<button type="button" id="rand">Pick random from view</button>
<button type="button" id="clear">Clear</button></div>
<div class="box"><table><thead><tr><th></th><th>Id</th><th>Title</th><th>Keywords</th></tr></thead><tbody id="tb">''' + rows + '''</tbody></table></div>
</div>

<div id="panel-facts" class="panel">
<p class="sub">Generate Facts Practice sheets matching the classic Saxon layout (letter box, Name/Time/Date, fixed grid of vertical or long-division problems). Each sheet produces Test + Answer Key pages.</p>
<div class="bar">
<label>Preset<select id="fpreset"><option value="">Custom</option>
<option value="A">A – 100 Addition</option>
<option value="B">B – 100 Subtraction (random from stock)</option>
<option value="C">C – Mul focus 0,1,2,5 (64)</option>
<option value="G">G – 64 Multiplication (factors 2–9)</option>
<option value="H">H – 100 Multiplication</option>
<option value="I">I – 90 Division</option>
</select></label>
<label>Operation<select id="fop"><option value="add">Addition</option><option value="sub">Subtraction</option>
<option value="mul">Multiplication</option><option value="div">Division</option></select></label>
<label>Mode<select id="fmode"><option value="full">Full set (each fact once)</option>
<option value="focus">Focus set</option><option value="practice">Practice (balanced)</option></select></label>
<label>Focus digits<input id="ffocus" value="" size="10" placeholder="0,1,2,5"></label>
</div>
<div class="bar">
<label>Letter<input id="fletter" value="A" size="3"></label>
<label>Title<input id="ftitle" value="" size="28" placeholder="auto from preset/mode"></label>
<label>Instruction<input id="finstr" value="" size="10" placeholder="Add. / Multiply."></label>
<label>Headers<input id="fheaders" value="Name,Date" size="16" placeholder="Name,Time,Date"></label>
</div>
<div class="bar">
<label>Rows<input id="frows" type="number" value="10" min="1" max="15" style="width:4em"></label>
<label>Cols<input id="fcols" type="number" value="10" min="1" max="12" style="width:4em"></label>
<label>Sheets/forms<input id="fsheets" type="number" value="1" min="1" max="20" style="width:4em"></label>
<label>Seed<input id="fseed" value="1" size="6"></label>
<label>Footer right<input id="ffoot" value="Saxon Math 5/4" size="16"></label>
<label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" id="fshowprob"> Show problem on key</label>
<button class="go" id="fgo">Generate facts</button>
</div>
<p class="sub" style="margin-top:8px">Full-set uses the complete 0–9 table (or 1–9 divisor × 0–9 quotient for division). Focus-set keeps every ordered pair that has at least one factor in the focus digits. Practice fills the grid with balanced repetition from the ranges and avoids adjacent identical problems.</p>
</div>

<script>
const $ = id => document.getElementById(id);
// tabs
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tabs button').forEach(x => x.classList.toggle('on', x===b));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('on', p.id === 'panel-' + b.dataset.tab));
});
// lesson tests
const tb = $('tb'), sel = $('sel');
function visible(){return [...tb.querySelectorAll('tr')].filter(r => r.style.display !== 'none');}
function update(){sel.textContent = tb.querySelectorAll('input:checked').length;}
tb.addEventListener('change', update);
$('filter').oninput = () => {
  const q = $('filter').value.toLowerCase().split(/\\s+/).filter(Boolean);
  tb.querySelectorAll('tr').forEach(r => {
    const t = r.dataset.t || '';
    r.style.display = q.every(w => t.includes(w)) ? '' : 'none';
  });
};
$('book').onchange = () => {
  const b = $('book').value;
  tb.querySelectorAll('tr').forEach(r => r.style.display = (!b || r.dataset.b === b) ? '' : 'none');
};
$('clear').onclick = () => {tb.querySelectorAll('input').forEach(c => c.checked = false); update();};
$('rand').onclick = () => {
  const n = Math.max(1, parseInt($('count').value)||20);
  const vis = visible().filter(r => !r.classList.contains('approx') || $('approx').checked);
  $('clear').click();
  vis.sort(() => Math.random()-0.5).slice(0,n).forEach(r => r.querySelector('input').checked = true);
  update();
};
$('go').onclick = () => {
  const ids = [...tb.querySelectorAll('input:checked')].map(c => c.value);
  if(!ids.length){alert('Select at least one problem'); return;}
  const q = new URLSearchParams({
    ids: ids.join(','), forms: $('forms').value, title: $('title').value,
    number: $('num').value, seed: $('seed').value,
    keep: $('keep').checked ? '1' : '', approx: $('approx').checked ? '1' : ''
  });
  window.open('/generate?' + q.toString(), '_blank');
};
// facts
const PRESETS = {
  A:{op:'add',mode:'full',letter:'A',title:'100 Addition Facts',instr:'Add.',headers:'Name,Date',rows:10,cols:10},
  B:{op:'sub',mode:'full',letter:'B',title:'100 Subtraction Facts',instr:'Subtract.',headers:'Name,Date',rows:10,cols:10},
  C:{op:'mul',mode:'focus',letter:'C',title:"Multiplication Facts:\\n0's, 1's, 2's, 5's",instr:'Multiply.',headers:'Name,Date',rows:8,cols:8,focus:'0,1,2,5'},
  G:{op:'mul',mode:'full',letter:'G',title:'64 Multiplication Facts',instr:'Multiply.',headers:'Name,Date',rows:8,cols:8},
  H:{op:'mul',mode:'full',letter:'H',title:'100 Multiplication Facts',instr:'Multiply.',headers:'Name,Date',rows:10,cols:10},
  I:{op:'div',mode:'full',letter:'I',title:'90 Division Facts',instr:'Divide.',headers:'Name,Date',rows:9,cols:10},
};
$('fpreset').onchange = () => {
  const p = PRESETS[$('fpreset').value];
  if(!p) return;
  $('fop').value = p.op; $('fmode').value = p.mode; $('fletter').value = p.letter;
  $('ftitle').value = p.title; $('finstr').value = p.instr; $('fheaders').value = p.headers;
  $('frows').value = p.rows; $('fcols').value = p.cols;
  if(p.focus) $('ffocus').value = p.focus;
};
$('fgo').onclick = () => {
  const sheets = Math.min(20, Math.max(1, parseInt($('fsheets').value)||1));
  const q = new URLSearchParams({
    preset: $('fpreset').value, op: $('fop').value, mode: $('fmode').value,
    focus: $('ffocus').value, letter: $('fletter').value, title: $('ftitle').value,
    instruction: $('finstr').value, headers: $('fheaders').value,
    rows: $('frows').value, cols: $('fcols').value, sheets: String(sheets),
    seed: $('fseed').value, footer_right: $('ffoot').value,
    show_problem: $('fshowprob').checked ? '1' : ''
  });
  window.open('/facts?' + q.toString(), '_blank');
};
document.querySelector('.sub').textContent = document.querySelector('.sub').textContent.replace('@@N@@', ''' + str(len(GOOD)) + ''');
</script>'''

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, body, code=200, ctype='text/html; charset=utf-8'):
        if isinstance(body, str): body = body.encode('utf-8')
        self.send_response(code); self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == '/': return self.send(page())
        if u.path == '/generate':
            try:
                ids = [i for i in q.get('ids', [''])[0].split(',') if i in BYID]
                if not ids: return self.send('<h3>No valid problems selected.</h3>', code=400)
                forms = [f.strip() for f in q.get('forms', ['A'])[0].split(',') if f.strip()] or ['A']
                out = S.build_html([BYID[i] for i in ids], forms, q.get('title', ['Saxon Test'])[0],
                                   q.get('seed', ['1'])[0], q.get('number', [''])[0].strip(),
                                   bool(q.get('keep', [''])[0]), katex_base='/vendor/katex')
                return self.send(out)
            except Exception as e:
                return self.send('<h3>Could not generate: %s</h3>' % html.escape(repr(e)), code=500)
        if u.path == '/facts':
            try:
                sheets = min(20, max(1, int(q.get('sheets', ['1'])[0] or 1)))
                def g(k, d=''): return q.get(k, [d])[0]
                preset = g('preset') or None
                # When a preset is chosen, let the preset supply op/mode/letter/etc.
                # Only pass explicit overrides the user may have changed.
                kwargs = dict(
                    preset=preset,
                    focus=g('focus') or None,
                    title=g('title') or None,
                    instruction=g('instruction') or None,
                    headers=g('headers') or None,
                    rows=int(g('rows') or 0) or None,
                    cols=int(g('cols') or 0) or None,
                    sheets=sheets,
                    seed=g('seed', '1'),
                    footer_right=g('footer_right', 'Saxon Math 5/4'),
                    show_problem_on_key=bool(g('show_problem')),
                )
                if not preset:
                    kwargs.update(op=g('op') or 'add', mode=g('mode') or 'full',
                                  letter=g('letter') or 'A')
                else:
                    # still allow letter override from the form
                    if g('letter'):
                        kwargs['letter'] = g('letter')
                    if g('op'):
                        kwargs['op'] = g('op')
                    if g('mode'):
                        kwargs['mode'] = g('mode')
                out = F.generate(**kwargs)
                return self.send(out)
            except Exception as e:
                return self.send('<h3>Could not generate facts: %s</h3>' % html.escape(repr(e)), code=500)
        # Serve offline KaTeX assets
        if u.path.startswith('/vendor/'):
            rel = u.path[len('/vendor/'):]
            rel = rel.replace('..', '').lstrip('/')
            fpath = os.path.join(HERE, 'vendor', rel)
            if os.path.isfile(fpath):
                ext = os.path.splitext(fpath)[1].lower()
                ctype = {'.css': 'text/css; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
                         '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf'}.get(ext, 'application/octet-stream')
                with open(fpath, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.end_headers()
                self.wfile.write(data)
                return
        self.send('Not found', code=404)

def main():
    # Hosted (e.g. Render) sets PORT: listen on all interfaces at that port and don't open a browser.
    # Local use (no PORT): random free port on localhost and open the browser, as before.
    port_env = os.environ.get('PORT')
    host = '0.0.0.0' if port_env else '127.0.0.1'
    srv = ThreadingHTTPServer((host, int(port_env) if port_env else 0), H)
    port = srv.server_address[1]
    if port_env:
        print('Saxon Test Maker listening on %s:%d' % (host, port), flush=True)
    else:
        url = 'http://127.0.0.1:%d/' % port
        print('Saxon Test Maker running at', url, '\nLeave this window open while you use it. Press Ctrl+C or close the window to quit.')
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
if __name__ == '__main__': main()
