---
name: balloon-anchor-vs-circle-frame
description: A balloon ring spread before every view on the sheet is placed gets undone by the sheet re-solve — plus two refuted theories for the same overlap (anchor/circle frame, ellipse eccentricity)
metadata:
  type: project
---

**The defect:** `_spread_balloons` places balloons on a ring around a view. If
it runs while another view is still to be PLACED on that sheet, placing that
view re-solves the sheet and the balloons snap back to their creation offset
from their own attachments — the ring is silently undone, `SetPosition` having
returned True.

Repro (2026-07-28, drive-train sheet 4): the concealed-BOTTOM ring was spread
before `concealed_front` was placed. On the saved sheet both its balloons sat
`(0.0176, 0.0114)` m from their own attachments — **the same delta to 0.1 mm**,
i.e. the creation offset, not a ring position. Their circles therefore kept the
attachments' 6.86 mm spacing (measured 6.99 mm) instead of the ring's 15.2 mm,
and the layout audit failed with a 7.7 × 3.0 mm overlap between items 25 and 6.

The identical-delta signature is the diagnostic: **balloons at a constant offset
from their own attachments were never re-ringed.** Contrast the grouped rings on
the same drawing, which are fine — `_add_component_balloons` receives its views
already placed. The invariant is therefore about ORDER, not about the spread:
*no ring may be spread while a view is still to be placed on that sheet.*

**Two theories measured and REFUTED for this same overlap.** Both were specific,
plausible, and wrong; neither is worth re-walking:

1. *Anchor-vs-circle frame.* `SetPosition` moves the annotation ANCHOR while the
   ink and the audit (`_note_element`) measure the CIRCLE (`GetBalloonInfo`), so
   a differing per-balloon offset would eat the gap. The offset is REAL — every
   drive-train balloon carries ~`(+4.2, -2.0)` mm — but it is UNIFORM, so the
   differential is `(0.05, 0.14)` mm, two orders of magnitude too small. The
   corrected build produced byte-identical boxes: a confident no-op. The offsets
   are still recorded on the `drawing.balloon_ring` span event, which is what
   refuted it.
2. *Ellipse eccentricity.* That `_min_angular_gap`'s use of `min(Rx, Ry)` is
   conservative only for infinitesimal gaps, since an eccentric ellipse doubles
   back at its pointy end. Probed as a pure function to 5:1 — separation holds
   at every ratio.

**Lesson.** An overlap on a ring has three candidate causes and they are
cheaply distinguishable from the recorded data before touching COM: crowding
(count vs ring circumference), a frame/units mismatch (compare the offsets), or
the spread not having taken effect at all (compare each balloon's final position
to its own ATTACHMENT — a constant delta across balloons means un-spread). Check
the third first; it is the only one that needs no geometry reasoning.

See [[load-bearing-claims-need-a-repro]] and
[[negative-result-needs-a-positive-control]]. Related:
[[drawing-recipe-com-pitfalls]], [[drawing-text-leader-style]].
