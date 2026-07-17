---
name: drawing-sheet-zone-border
description: The DRWDOT's drawn border frame is a pure (+3.217, +0.656) mm translation off its declared 12.7 mm zone margins, and its zone ticks follow SHEET quarters not zone-area quarters — three inconsistent systems in one template
metadata:
  type: project
---

Measured 2026-07-16 (PR #334) while adding the sheet-zone-border gate.

**Query zone margins, never hardcode them.** `ISheet::GetZoneMargin(code)` with
`swZoneMargin_e` = {top:0, bottom:1, right:2, left:3}. The project DRWDOT reports
a uniform **12.7 mm (0.5 in)** on all four sides. `_drawing_layout_check.py`'s
`DrawableRegion` is built from that query, so a template edit moves the gate with
it.

**The template has THREE mutually inconsistent systems** — do not assume any one
of them agrees with another:

1. **declared zone area** — 12.7 mm uniform, centred (what `GetZoneMargin` says);
2. **drawn border frame** — left 15.917 / right 9.483 / bottom 13.335 / top
   12.023 mm, i.e. off-centre;
3. **drawn zone grid ticks** — outer column dividers at 107.91 / 323.81, which are
   the SHEET's quarters, not the declared zone area's (114.30 / 317.50). Off by
   6.39 mm, so `ISheet::GetDrawingZone(x, y)` disagrees with the printed labels
   near the outer boundaries.

**The frame is the right SIZE, only in the wrong PLACE** — this is the decisive
fact. Drawn: 406.400 x 254.042 mm = 16.000 x 10.002 in. Implied by the 12.7 mm
margins: 406.4 x 254.0 = 16.000 x 10.000 in. Identical to within half a pixel, so
the frame is a pure **translation of (+3.217, +0.656) mm** — a hand-drawn frame
landing on exactly the declared size is not coincidence. 12.7 uniform IS the
design intent; the frame got dragged. The fix is a re-centring, not a redraw, and
matching the margins to the frame instead would codify the slip.

**Measuring the frame off a render:** the PNGs are 5100x3300 @300dpi = exactly
431.8 x 279.4 mm, so pixels map linearly to sheet metres. The RIGHT border renders
light-grey (value **192**), not black — a `< 128` threshold finds nothing. Use
`< 200`.

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
