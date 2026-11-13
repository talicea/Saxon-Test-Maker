# Saxon Test Maker - status (merged: layout engine + Grok's launchers/polynom)

**345 / 430 problems generate (315 clean, 30 flagged `~` for approximate equation layout).**
Browser check (headless Chromium, 60 layouts across all books, 10-30 problems): the in-page fitter
produced 0 silent overflows; 13 layouts correctly showed "too many problems". Static no-JS fallback: 1/60 overflow.

## Layout (matches the supplied sample tests)
TEST bar + boxed test number (e.g. 22A) + Name line; word problems full width; short computations in a
3-column grid; stacked fractions; vertical arithmetic as a decimal-aligned table with the rule under the
last operand row (result row below it). One page per test, one page per key, order Test A, Key A, Test B, Key B.
Type size/spacing fit to the page in the browser (inline script); `FIT_K` is the static fallback estimate.

## Fixed in this merge
- Silent clipping: content area no longer `overflow:hidden`; real-browser fitter + warning instead.
- Vertical stacks: decimal-aligned table, `$` attached, rule placement, Times-style tabular digits.
- Blob reader: header length varies -> first token was being dropped ("+ d = 442" now "178 + d = 442").
  Uppercase letters are literals (missing addend N); operator rows split correctly; 4 more Symbol codes
  (dot, angle, congruent, perpendicular); undefined variables in blobs now fail the problem instead of printing 0.
- cat() honors format("%+.0f", ...) so scripts that build signed polynomial strings work.
- polynom(): real grammar (signed exponents, multi-variable terms, numeric bases like 10^+3); words such as
  "acute angle" untouched (Grok's fix, re-implemented). Raw exponent strings auto-typeset inside
  radical/fraction/fences/supersub.
- literal(name, n, ..., out): output is the LAST argument. random(): '$each1'-style lower bounds, typo'd modes.
- Choice problems: blob before choices starting at d1 is the correct choice (also "d1 days" form); shuffled per form.
- Portal: Test # and "keep my order" fields. Launchers/README/SETUP from Grok kept.

## Remaining
- 53 `slate` geometry/graph problems (needs an SVG drawing layer) + ~14 residual parse errors + a few rare primitives.
- 30 supported problems with nested fences/templates are `~` (hidden unless "include approx equations").
- Word problems that reference a picture/figure (circle graphs, rulers, number lines) are not supported.
- Assumptions to verify vs the original: $once/$each/$every semantics; "first listed choice is correct".
- .wst test templates are not parsed.

## KaTeX rendering (2026-11-12)
Math from `fraction`, `radical`, `polynom`, `supersub`, `fences`, and `mathsym` is emitted as LaTeX and rendered with KaTeX (offline copy in `vendor/katex/`).
Vertical arithmetic stacks remain HTML tables. Generated HTML loads local KaTeX first, CDN as fallback.
Portal serves `/vendor/katex/*` so tests opened from the portal render offline.
