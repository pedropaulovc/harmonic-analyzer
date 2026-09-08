# Shared title fields: pinned visual batch 3

Head: `64c3dab4875354a7d44d709539e001db920a0377`.
Checkout: `C:/src/ha-assembly-closeout-independent`.

Codex viewed all 11 pinned complete sheets and all 11 readable title-field
crops. **DWG and REV values are separate and readable on 11/11. No part title
or material value overflows its cell. The crank-handle finish spills into the
material row, and harmonic-base's hole table obscures the title-block header
and part of its general tolerances.** These findings remain deferred.

The filename list was pinned once from completed root `*_drawing.png` files,
excluding all 27 names in batches 1 and 2, with a cap of 20. There were 11
remainder files at pin time and all were included. Later outputs were not
added or inspected. Exact source-byte copies, full PNG SHA-256 values,
timestamps, dimensions, crop coordinates, and crop SHA-256 values are in
[title-fields-batch3-manifest.json](title-fields-batch3-manifest.json).
The inspected full sheets and crops are under
[title-fields-batch3-images](title-fields-batch3-images).

All full sheets are 5100 by 3300 pixels. Every unscaled title crop uses the
pixel rectangle `[3060, 2508, 5100, 3300]`, yielding 2040 by 792 pixels. The
full-sheet copies retain the exact original bytes; the crops are inspection
derivatives from those copies.

| Sheet stem | DWG no. | REV | Part title / material | Finish | Other title-block observation |
| --- | --- | --- | --- | --- | --- |
| channel-lever | MHA-009 | v32 | Both contained | Two lines, contained | None |
| crank-arm | MHA-020 | v32 | Both contained | Contained | None |
| crank-handle | MHA-022 | v32 | Both contained | **Third line in material row** | None |
| crankshaft | MHA-026 | v32 | Both contained | Contained | None |
| cylinder-gear-shaft | MHA-028 | v32 | Both contained | Contained | None |
| hanger-screw | MHA-034 | v32 | Both contained | Contained | None |
| harmonic-base | MHA-035 | v32 | Both contained | Two lines, contained | **Hole table over header/tolerances** |
| knife-mount | MHA-037 | v32 | Both contained | Contained | None |
| lag-screw | MHA-039 | v32 | Both contained | Contained | None |
| platen-guide | MHA-111 | v32 | Both contained | Contained | None |
| swing-stop-screw | MHA-095 | v32 | Both contained | Contained | None |

## Observations for existing deferred work

1. **Crank-handle finish overflow:** The
   [crank-handle title crop](title-fields-batch3-images/crank-handle_drawing_title.png)
   shows the third finish line, `cure 7 d`, extending below the finish cell
   into the material row. The material string remains readable below it.
   Retain with [#709](https://github.com/pedropaulovc/harmonic-analyzer/issues/709).
   This is observed wrapping with unknown cause: no old-sheet comparison was
   performed for this drawing, so this receipt does not attribute it to the
   template replacement.
2. **Harmonic-base table overlap:** The
   [complete harmonic-base sheet](title-fields-batch3-images/harmonic-base_drawing.png)
   shows the lower rows of the right-hand hole table superimposed on the
   front view and continuing into the title-block area. Row F4 covers parts
   of the project header and general tolerance panel, also visible in
   [the title crop](title-fields-batch3-images/harmonic-base_drawing_title.png).
   The part title, finish, material, DWG, and REV cells remain readable below
   that collision. The lower-left general notes also cross the drawing border,
   overlap the Maker watermark, and continue beyond the bottom image edge.
   Retain with deferred drawing layout
   [#712](https://github.com/pedropaulovc/harmonic-analyzer/issues/712).
   Cause and introduction point are unverified.
3. **Channel-lever notes cross the border:** On the
   [complete channel-lever sheet](title-fields-batch3-images/channel-lever_drawing.png),
   note 8's final `SET THE STATION PITCH (NO SPACERS).` line appears below
   the lower drawing border, although it remains visible in the PNG. The
   two-line finish remains inside its own title-block cell. Retain this
   whole-sheet layout observation with
   [#712](https://github.com/pedropaulovc/harmonic-analyzer/issues/712).
   Cause and introduction point are unverified.

## Boundaries

This remains a partial visual receipt. It does not certify complete drawing
acceptance, native reopening, leader attachment persistence, dimensions, or
the running full build. Separate known failures, including the rack cold
leader failure, are not waived by these hot drawing PNGs.

No COM was launched and no production drawings, tracked source, tests, or
telemetry were changed. No issue or PR was mutated by this reviewer. Only
the pinned inspection copies, crops, manifest, and report were written.
