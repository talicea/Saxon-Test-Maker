#!/usr/bin/env node
/** Read JSON array of LaTeX strings from stdin; write JSON array of HTML strings. */
const fs = require('fs');
const path = require('path');
const code = fs.readFileSync(path.join(__dirname, 'katex.min.js'), 'utf8');
const mod = { exports: {} };
const exp = mod.exports;
// Provide a minimal CommonJS-like env for the UMD bundle
const fn = new Function('module', 'exports', 'window', 'global', code + '\n;return module.exports;');
const katexMod = fn(mod, exp, global, global);
const katex = (katexMod && katexMod.renderToString) ? katexMod
            : (katexMod && katexMod.katex) ? katexMod.katex
            : global.katex;
if (!katex || !katex.renderToString) {
  console.error('KaTeX failed to load');
  process.exit(1);
}
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => input += c);
process.stdin.on('end', () => {
  let exprs;
  try { exprs = JSON.parse(input); } catch (e) {
    console.error('Invalid JSON input');
    process.exit(1);
  }
  const out = exprs.map(tex => {
    try {
      return katex.renderToString(String(tex), {
        throwOnError: false,
        displayMode: false,
        strict: 'ignore',
        trust: false,
        output: 'html',
      });
    } catch (e) {
      return '<span class="katex-error">' + String(tex)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</span>';
    }
  });
  process.stdout.write(JSON.stringify(out));
});
