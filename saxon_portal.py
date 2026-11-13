#!/usr/bin/env python3
"""Local browser portal for saxon_test.py. Run it (or double-click 'Saxon Test Maker.command')."""
import os, sys, html, json, random, threading, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import saxon_test as S

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
.box{height:52vh;overflow:auto;border:1px solid #8884;border-radius:6px}table{border-collapse:collapse;width:100%;font-size:13px}
td{padding:4px 8px;border-bottom:1px solid #8882}tr.approx{opacity:.7}tr:hover{background:#8881}.tag{font-size:11px;color:#b45309}
.n{margin-left:auto;color:#777}</style>
<h1>Saxon Test Maker</h1><p class="sub">@@N@@ problems available. Pick problems (or let it choose randomly), then generate. About 15-20 problems fit on a page; the type size adjusts automatically. Print to PDF from your browser.</p>
<div class="bar"><label>Title<input id="title" value="Saxon Math" size="22"></label>
<label>Test #<input id="num" value="" size="4" placeholder="22"></label>
<label>Forms<input id="forms" value="A,B" size="8"></label><label>Seed<input id="seed" value="1" size="6"></label>
<label>Book<select id="book">@@OPTS@@</select></label><label>Filter<input id="q" placeholder="fraction, money..." size="20"></label>
<label><span>&nbsp;</span><span><input type="checkbox" id="ap"> include approx equations</span></label>
<label><span>&nbsp;</span><span><input type="checkbox" id="keep"> keep my order</span></label></div>
<div class="bar"><label>Random count<input id="cnt" type="number" value="20" min="1" style="width:70px"></label>
<button onclick="rand()">Pick random from view</button><button onclick="clr()">Clear</button>
<button class="go" onclick="go()">Generate test</button><span class="n" id="n"></span></div>
<div class="box"><table id="t">@@ROWS@@</table></div>
<script>
const $=id=>document.getElementById(id),rows=[...document.querySelectorAll('#t tr')];
function vis(r){const b=$('book').value,q=$('q').value.toLowerCase();return (!b||r.dataset.b===b)&&r.dataset.t.includes(q)&&($('ap').checked||!r.classList.contains('approx'))}
function filt(){rows.forEach(r=>{r.style.display=vis(r)?'':'none'});upd()}
function sel(){return rows.filter(r=>r.querySelector('input').checked).map(r=>r.querySelector('input').value)}
function upd(){$('n').textContent=sel().length+' selected, '+rows.filter(vis).length+' shown'}
function clr(){rows.forEach(r=>r.querySelector('input').checked=false);upd()}
function rand(){clr();const v=rows.filter(vis).sort(()=>Math.random()-.5).slice(0,+$('cnt').value);v.forEach(r=>r.querySelector('input').checked=true);
 rows.forEach(r=>r.querySelector('input').checked&&0);upd()}
function go(){const ids=sel();if(!ids.length){alert('Select some problems first (or use "Pick random from view").');return}
 window.open('/generate?'+new URLSearchParams({ids:ids.join(','),forms:$('forms').value,title:$('title').value,number:$('num').value,keep:$('keep').checked?'1':'',seed:$('seed').value}),'_blank')}
['book','q','ap'].forEach(i=>$(i).addEventListener('input',filt));document.addEventListener('change',upd);filt();
</script>'''.replace('@@N@@', str(len(GOOD))).replace('@@OPTS@@', opts).replace('@@ROWS@@', rows)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, body, ctype='text/html; charset=utf-8', code=200):
        b = body.encode('utf-8'); self.send_response(code); self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == '/': return self.send(page())
        if u.path == '/generate':
            try:
                ids = [i for i in q.get('ids', [''])[0].split(',') if i in BYID]
                if not ids: return self.send('<h3>No valid problems selected.</h3>', code=400)
                forms = [f.strip() for f in q.get('forms', ['A'])[0].split(',') if f.strip()] or ['A']
                out = S.build_html([BYID[i] for i in ids], forms, q.get('title', ['Saxon Test'])[0], q.get('seed', ['1'])[0], q.get('number', [''])[0].strip(), bool(q.get('keep', [''])[0]), katex_base='/vendor/katex')
                return self.send(out)
            except Exception as e:
                return self.send('<h3>Could not generate: %s</h3>' % html.escape(repr(e)), code=500)
        # Serve offline KaTeX assets
        if u.path.startswith('/vendor/'):
            rel = u.path[len('/vendor/'):]
            # prevent path traversal
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
    # Local: loopback + free port + open browser.
    # Render: 0.0.0.0 and $PORT.
    port_env = os.environ.get('PORT')
    if port_env:
        host, port, open_browser = '0.0.0.0', int(port_env), False
    else:
        host, port, open_browser = '127.0.0.1', 0, True

    srv = ThreadingHTTPServer((host, port), H)
    bound = srv.server_address[1]
    url = 'http://127.0.0.1:%d/' % bound
    print('Saxon Test Maker running at', url if open_browser else 'http://0.0.0.0:%d/' % bound)
    if open_browser:
        print('Leave this window open while you use it. Press Ctrl+C or close the window to quit.')
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()