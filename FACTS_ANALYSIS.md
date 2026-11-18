# Facts Practice – sample analysis

Measured from the supplied FPT_*.pdf samples (letter, 1 page each = test page only).

## Grid geometry (all four)
- Page: Letter 612×792 pt.
- Outer grid box ≈ 6.8 in wide × 8.15–8.3 in tall, thin inner rules, slightly heavier outer border.
- Cell size changes with (rows, cols): 10×10, 8×8, 9×10 all fit the same physical box.
- Font: Times-style tabular lining digits; same nominal size across presets (slightly larger on sparser grids).

## Header (common)
- Gray gradient bar, letter-spaced capitals “FACTS PRACTICE TEST”.
- Left: large serif letter in a bordered box.
- Beside it: bold serif title (1 line for A/H/I, 2 lines for C; top-aligned to the box when 2 lines).
- Right: header lines chosen from {Name, Time, Date}.
  - A: Name + Date
  - H: Name + Time
  - I: Name + Time
  - C: Name + Time + Date (Date sits on the instruction row, right-aligned)
- Instruction word left above the grid (“Add.” / “Multiply.” / “Divide.”).

## Cell styles
- A, H, C (and B/G): vertical “stack” – top operand right-aligned, operator + bottom operand, rule under the pair spanning operator+digit.
- I: long-division “bracket” form – divisor)dividend with a true overbar (vinculum) over the dividend, centred on one line.

## Fact sets (confirmed)

### A – 100 Addition Facts (10×10)
- Every ordered pair (a,b) with a,b ∈ {0…9}, operator “+”. Exactly 100 cells, each fact once.
- First two rows (transcribed from high-res render):
  - R0: 4+4, 7+5, 0+1, 8+7, 3+4, 3+2, 8+3, 2+1, 5+6, 2+9
  - R1: 0+9, 8+9, 7+6, 1+3, 6+8, 7+3, 1+6, 4+7, 0+3, 6+4
  - R2: 9+3, 2+6, 3+0, 6+1, 3+6, 4+0, 5+7, 1+1, 5+4, 2+8
- Full transcription of remaining rows is in facts_samples.csv (OCR-assisted + visual verification of uniqueness). No duplicate pairs observed in sampled rows; the set is the complete addition table in a fixed but non-obvious order (different forms = different shuffles of the same 100).

### H – 100 Multiplication Facts (10×10)
- Every ordered pair (a,b) with a,b ∈ {0…9}, operator “×”. Exactly 100 cells, each fact once.
- First row: 9×1, 2×2, 5×1, 4×3, 0×0, 9×9, 3×5, 8×5, 2×6, 4×7.
- Same completeness / uniqueness properties as A.

### C – Multiplication Facts: 0’s, 1’s, 2’s, 5’s (8×8 = 64)
- Hypothesis confirmed: every ordered pair (a,b) ∈ {0…9}² such that **at least one** of a,b is in the focus set {0,1,2,5}.
- Count: 100 − 6×6 = 64. Every problem visible in the sample satisfies the rule; the complementary 36 pairs (both factors in {3,4,6,7,8,9}) are absent.
- Title is two lines; Date appears on the instruction row.

### I – 90 Division Facts (9×10)
- Hypothesis confirmed: divisor d ∈ {1…9}, quotient q ∈ {0…9}, dividend = d×q (includes 0-dividend cases such as 7)0). Never a zero divisor.
- Count: 9×10 = 90. Displayed as d)dividend with overbar.
- First row: 2)18, 6)6, 3)15, 3)27, 2)14, 5)25, 6)48, 7)21, 2)10, 6)42.

## Ordering observations
- Full-set sheets are a permutation of the complete table; different form letters are different seeds / orders of the same facts.
- No strong row/column bias toward small or large operands was measured in the sampled rows; doubles and zero facts appear scattered.
- Adjacent identical problems do not occur in the samples (as expected for a full-set without replacement).

## Footer
- Left: copyright line on the originals (“© Saxon Publishers, Inc., and Stephen Hake”). Generator default is empty (configurable).
- Right: italic bold “Saxon Math 5/4” (configurable).

## Generator rules derived from the above
- Full-set mode: emit every fact of the table exactly once, shuffled by seed.
- Focus-set mode: emit every qualifying ordered pair exactly once; grid shape is the factorisation of the count when it is rectangular (64→8×8), otherwise user-supplied.
- Practice mode: user ranges/tags, fill to exact grid size with counts differing by at most 1, then repair horizontal (and optionally vertical) adjacent duplicates.
- Cell renderer: “stack” for + − ×, “bracket” for ÷.
- Key page: same grid, bold answer (stack → sum/product/difference; bracket → quotient). Optional small problem above the answer (off by default).

## Updates from user confirmation (2026-11-18)
- **B**: Not required to be the exact inverse of the addition table. Generator draws 100 facts (without replacement when possible) from a broader stock of positive subtraction facts: minuend 0–20, subtrahend 0–12, result ≥ 0 (stock size 195). Each sheet is a fresh random selection controlled by the seed.
- **G**: Default remains 64 facts on factors 2–9 (8×8). Focus-set mode remains available for any digit set. A 100-random multiplication sheet is available via preset H (or by setting rows=10, cols=10, mode=full, op=mul).
- **Division**: Kept portrait like the other sheets; long-division bracket form is retained. Landscape was considered but not required.
- **Keys**: Generated for every sheet in the same grid layout, answers in bold (quotients for division).
- Footer left remains empty by default; right side configurable (default “Saxon Math 5/4”).
