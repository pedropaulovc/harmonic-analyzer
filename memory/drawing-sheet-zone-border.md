---
name: drawing-sheet-zone-border
description: The DRWDOT's drawn border frame is a pure (+3.217, +0.656) mm translation off its declared 12.7 mm zone margins — ONE defect, not three; the zone grid is CORRECT (region=Sheet, EvenlySized 2x4) and must not be "fixed"
metadata:
  type: project
---

Measured 2026-07-16 (PR #334) while adding the sheet-zone-border gate.

**Query zone margins, never hardcode them.** `ISheet::GetZoneMargin(code)` with
`swZoneMargin_e` = {top:0, bottom:1, right:2, left:3}. The project DRWDOT reports
a uniform **12.7 mm (0.5 in)** on all four sides. `_drawing_layout_check.py`'s
`DrawableRegion` is built from that query, so a template edit moves the gate with
it.

**The zone-SIZE queries need an EARLY-BOUND `ISheet`; late-bound they all fail —
each differently, none saying "use early binding".** `GetZoneMargin` works
late-bound (simple int in, double out), which makes the object look fine and sends
you hunting the wrong thing. Anything returning a VARIANT or carrying OUT params
does not:

| call | late-bound (`CDispatch`) | early-bound |
|---|---|---|
| `GetZoneMargin(3)` | `0.0127` ✓ | `0.0127` ✓ |
| `GetProperties2()` | `TypeError: 'tuple' object is not callable` | `(2.0, 12.0, 1.0, 1.0, 0.0, 0.4318, 0.2794, 1.0)` |
| `GetZoneSizeRegion()` | `TypeError: 'int' object is not callable` | `1` |
| `GetZoneSizeDistribution()` | `com_error: Parameter not optional` | `(1, 2, 4)` |
| `GetZoneSizeDistribution(0,0)` | `com_error: Type mismatch` | `(1, 2, 4)` |

The "'tuple'/'int' object is not callable" pair is the giveaway: late binding
resolved the NAME to the property VALUE, so calling it calls the result. Fix:
`_early_bound(sheet, "ISheet")`. The two OUT params come back in the return tuple
`(retval, rows, columns)` — passing placeholders is unnecessary and harmless. And
`adapter._attempt()` swallows all of this into a bare `None`, which cannot
distinguish "missing" from "raised" — call raw when probing.

**Exactly ONE thing is wrong: the frame's POSITION.** An earlier version of this
note claimed "three mutually inconsistent systems", the third being that the zone
grid ticks divide the SHEET rather than the declared 12.7-inset zone area, so
`GetDrawingZone` would disagree with the printed labels. **That is FALSE** — it was
inferred from the frame's margins without ever asking the sheet, and acting on it
would have dragged correct geometry to wrong coordinates. Probed live 2026-07-16:

- `GetZoneSizeRegion()` → **1 = `swRegionTypeSheet`** — the zone divisions are
  computed over the WHOLE SHEET, deliberately, not over the margin-inset area;
- `GetZoneSizeDistribution()` → **(1, 2, 4)** = `swZoneSizeDistribution_EvenlySized`,
  rows=2, columns=4.

So the ticks BELONG on the sheet's quarters (107.95 / 215.90 / 323.85) and the
column centres on its eighths (53.97 / 161.92 / 269.88 / 377.82) — which is exactly
where the printed labels are. `GetDrawingZone` AGREES with them: it flips B4→B3 at
107.95, B3→B2 at 215.90, B2→B1 at 323.85. The margins-region alternative would put
centres at 63.50 / 165.10 / 266.70 / 368.30, matching nothing on the sheet. **Do not
touch the zone grid**; it is correct, it is independent of both the frame position
and the margins, and re-centring the frame will not move it.

The one real defect:

1. **declared zone margins** — 12.7 mm uniform (`GetZoneMargin`), so the frame
   SHOULD sit 12.7 from each sheet edge;
2. **drawn border frame** — left 15.917 / right 9.483 / bottom 13.335 / top
   12.023 mm: off-centre, and the only thing needing an edit.

**CONSEQUENCE: the border gate is BLIND on the LEFT and BOTTOM until the frame is
re-centred.** The gate bounds on the DECLARED margins (12.7), but ink is judged by
a reader against the DRAWN rule. Where the rule sits further in than the margin,
ink can pass the gate and still print on/through the rule. Quantified by draw-C
across five sheets (2026-07-16), independently reproducing the insets above:

| rule | drawn at | gate bound | gate is |
|---|---|---|---|
| left | **0.0159** | 0.0127 | **BLIND by 3.2 mm** |
| bottom | **0.0133** | 0.0127 | **BLIND by 0.6 mm** |
| right | 0.4223 | 0.4191 | conservative — safe |
| top | 0.2673 | 0.2667 | conservative — safe |

So "the audit passed" is not evidence for the left 3.2 mm strip. **Nine draw
scripts already carry a hand-written workaround comment** for exactly this (e.g.
"x=0.020: … the drawn frame rule is at x=0.0159 — 0.014 printed the first glyph
through it (the audit's bound is the 12.7 mm zone margin, so it cannot see
this)"). Nine manual compensations for one missing check is the tell that this
should be gated, not commented.

Re-centring the frame closes it at the source (declared == drawn, all four sides).
The tempting shortcut — bounding the gate on the *measured* 0.0159 — **codifies the
slip** (see below) and goes stale the moment the frame moves. If it must be gated
before the template edit, QUERY the drawn frame's position rather than hardcoding
it, so the bound tracks the frame instead of freezing today's error.

**The frame is the right SIZE, only in the wrong PLACE** — this is the decisive
fact. Drawn: 406.400 x 254.042 mm = 16.000 x 10.002 in. Implied by the 12.7 mm
margins: 406.4 x 254.0 = 16.000 x 10.000 in. Identical to within half a pixel, so
the frame is a pure **translation of (+3.217, +0.656) mm** — a hand-drawn frame
landing on exactly the declared size is not coincidence. 12.7 uniform IS the
design intent; the frame got dragged. The fix is a re-centring, not a redraw, and
matching the margins to the frame instead would codify the slip.

**Measuring ANY render: a sheet has TWO ink populations, and `< 128` sees only
one. DEFAULT YOUR THRESHOLD TO `< 200`.** The PNGs are 5100x3300 @300dpi =
exactly 431.8 x 279.4 mm, so pixels map linearly to sheet metres. Histogram of a
real sheet (platen-guide, 2026-07-16):

- level **0** (~217k px) — BLACK: geometry, dimensions, GD&T frames, notes;
- level **192** (~91k px) — GRAY: **reference dimensions, native hole callouts,
  AND ALL FOUR DRAWN FRAME RULES**.

`< 128` discards the entire gray population, and it fails in the WORST direction:
it reports **"BLANK (no ink)"** for a region holding a full-height frame rule, and
"clear" for one holding a 39 mm gray callout. Demonstrated: the right frame-rule
region reads `x 0.4221..0.4225` at threshold 200 and **"BLANK"** at 128. So a
clearance measured against a margin or a gray annotation at `< 128` **is not
evidence** — it is a false pass.

This note has said "use < 200" since it was written, and the session's own crop
helper still shipped `< 128` to four review agents; eye-1 nearly lost a real
crank-arm strikethrough to it and eye-4 independently re-derived the frame rules
because of it. Recording a threshold is not the same as defaulting to it — so:
**any render-measuring tool defaults to 200**, and drops to 128 only to
deliberately separate black geometry from a gray reference dim, never to answer
"does X clear Y".

**The pixel-scan failure mode is measuring your own WINDOW and narrating it as the
drawing.** Three separate times in one session (draw-C) a scan reported back its
own scan-window start column, or found "content" in every column that was really
the bottom frame rule caught by an over-wide row band. **The tell: independent
sheets agreeing to four decimal places.** Real content never agrees that
precisely — five sheets all reporting 0.0165 means the number is the template, the
frame, or the window, not the geometry. Sanity-check any cross-sheet constant
against that before believing it (it is the same shape as the first GD&T probe
"finding" every datum triangle inside its own box: a measurement true by
construction, see [[drawing-text-leader-style]]).

Measured frame rules (gray, invisible below 200): **left x=0.0159, right
x=0.4221..0.4225, top y=0.2672..0.2675**. Note the right RULE (0.4221) and the
12.7 mm zone MARGIN (0.4191) are different, and the margin is the tighter bound —
an annotation can clear the rule and still bust the margin.

**Editing the template is GUI-only, and expensive.** `ISketchPoint::SetCoords`
"adheres to any constraints that are active in the sketch" — it can return true
and silently land elsewhere on a hand-drawn format full of h/v relations;
`IModelDocExtension::MoveOrCopy` is the right primitive but buys no precision over
typed GUI coordinates; `ISheet::SaveFormat` writes an EXTERNAL `.slddrt`, which
this project deliberately avoids (the format is embedded in the DRWDOT). Whether a
`.DRWDOT` survives a COM open/save round-trip is undocumented and untested. The
DRWDOT is in `DrawingSpec.assets` unconditionally, feeding both `file_dep` and
`_cache_key`, so ANY template touch rebuilds **23/23** drawings and busts the
shared Azure cache key for every seat in the fleet — batch template edits into one.

**If the frame moves, re-measure the title-block keep-out.** The block is nested in
the frame's bottom-right corner (its bottom rule sits exactly on the frame's bottom
line) and translates with it, so `_TITLE_BLOCK_LEFT_M` (0.264) /
`_TITLE_BLOCK_TOP_M` (0.064) in `_drawing_common.py` go stale. The right/bottom
sides stay safe (the keep-out runs to the sheet edge) but a stale LEFT edge leaves
the block's leftmost 3.2 mm unguarded. The keep-out is deliberately exempt from the
border audit — it legitimately reaches the sheet corner. See
[[drawing-text-leader-style]].
