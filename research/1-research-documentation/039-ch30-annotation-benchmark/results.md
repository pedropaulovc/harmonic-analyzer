# ch30 annotation benchmark — results

## Convention-normalized (headline)

Analyzer-corner names may apply ONE consistent left↔right relabel per image —
SPEC's "machine-relative" left/right was ambiguous and models split between the
machine's-own-left and viewer-facing-front conventions. This table scores dot
PLACEMENT; the flips used are listed below the strict table.

| model | marked/visible | missed | false-visible | occl-agree | mean px | median px | ≤10px | ≤25px | ≤50px |
|-------|---------------|--------|---------------|-----------|---------|-----------|-------|-------|-------|
| fable | 52/76 | 24 | 22 | 38 | 190.5 | 22.8 | 20 | 27 | 29 |
| sonnet | 48/76 | 28 | 21 | 38 | 142.2 | 30.4 | 8 | 21 | 28 |
| opus | 50/76 | 26 | 24 | 30 | 212.2 | 81.3 | 9 | 20 | 24 |
| codex | 53/76 | 23 | 44 | 13 | 282.3 | 137.4 | 6 | 11 | 12 |
| haiku | 67/76 | 9 | 40 | 15 | 519.2 | 306.0 | 1 | 2 | 2 |

## Strict labels

Literal feature-name matching (a mirrored corner name scores as its ~800px
distance to the opposite corner).

| model | marked/visible | missed | false-visible | occl-agree | mean px | median px | ≤10px | ≤25px | ≤50px |
|-------|---------------|--------|---------------|-----------|---------|-----------|-------|-------|-------|
| codex | 53/76 | 23 | 44 | 13 | 401.8 | 166.3 | 6 | 11 | 11 |
| fable | 48/76 | 28 | 26 | 34 | 336.5 | 170.2 | 16 | 20 | 20 |
| sonnet | 44/76 | 32 | 25 | 34 | 427.8 | 266.9 | 6 | 13 | 17 |
| opus | 48/76 | 28 | 26 | 28 | 477.9 | 348.1 | 6 | 9 | 12 |
| haiku | 67/76 | 9 | 40 | 15 | 707.4 | 613.6 | 1 | 2 | 2 |

### Left↔right flips applied in the normalized table

- `fable` corner names mirrored on: page003_img01, page005_img01
- `opus` corner names mirrored on: page003_img01, page005_img01, page006_img01
- `sonnet` corner names mirrored on: page003_img01, page005_img01, page006_img01
- `haiku` corner names mirrored on: page004_img01, page005_img01, page006_img01, page007_img01
- `codex` corner names mirrored on: page005_img01, page007_img01

> **pinion_center caveat:** every model marked SPEC v2's operational definition
> (the small chain sprocket beside the large brass drive gear at platen level),
> but the human ground truth places the pinion at a different part (the book's
> ch25 pinion gear at the base), so all models carry a ~300–500px error on this
> feature in most views. It reflects a SPEC/GT identity mismatch, not placement skill.

Per-feature detail in `results.json`.
