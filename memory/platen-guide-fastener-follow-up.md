---
name: platen-guide-fastener-follow-up
description: platen-guide's 6 BA -> #4-40 UNC fastener conversion is OWNED by PR #247 (fleet-wide Hole Wizard), NOT the drawing stack; after #247 merges, rebuild the platen-guide drawing so its 6 BA callouts become #4-40 UNC
metadata:
  type: project
---

The platen-guide manufacturing drawing (PR #225, base of the drawing stack
#225 → #243 → #246) still carries **6 BA** thread callouts/notes. Per the
2026-07-11 US-customary direction ([[period-accurate-fasteners-on-hold]] /
merged #248), those must become **#4-40 UNC**, but that conversion is **owned
by PR #247** (the fleet-wide Hole Wizard → US-customary UNC effort), NOT by the
drawing stack.

**Why not done on the drawing stack:** #247's `0be089b` rewrites
`build_platen_guide.py` to native Hole Wizard `#4-40` bottoming taps (tap drill
Ø2.261, lock holes → `#4` clearance) via its new `_holes.py` helper — the same
file #225 heavily edited for drawing marks. A cherry-pick conflicts hard and
would drag in `3680fa1` (`_holes.py`) + `0be089b` (7 platen/pen parts) +
`3fa32cd` (all screws) from an unmerged draft, and re-conflict when #247 merges.
A note-only change (drawing says #4-40, part stays plain Ø3.0) would create the
exact part↔callout mismatch the no-context machinist reviews flag.

**How to apply (do NOT lose this):** once #247 merges to `main`, rebase the
drawing stack onto it. build_platen_guide.py then carries the #4-40 geometry, so
**regenerate the platen-guide drawing** (`doit drawing:platen_guide`) and
confirm the 6 BA notes are gone (→ #4-40 UNC) in the eye-pass. Also revisit the
BA toolbox standard reference in `provision_solidworks_seat.py` if #247 hasn't
already. crank-arm (#243) and rocker-arm-support (#246) already spec 9/16-12 UNC
— nothing period-British survives on those two prints. Tracked on #225.
