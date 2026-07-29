---
name: balloon-anchor-vs-circle-frame
description: OPEN — drive-train sheet 4's concealed-bottom balloon ring is never spread (SetPosition returns True, no effect); three mechanisms refuted with measurements
metadata:
  type: project
---

**The defect (mechanism still OPEN):** on drive-train sheet 4 the
concealed-BOTTOM ring is not spread on the saved sheet — `SetPosition` returns
True and the balloons stay at their default creation placement. Cause not yet
identified; three candidate mechanisms have been refuted (below). This BLOCKS
`drawing:drive_train_assembly`.

Repro (2026-07-28, drive-train sheet 4): on the saved sheet both bottom balloons sat
`(0.0176, 0.0114)` m from their own attachments — **the same delta to 0.1 mm**,
i.e. the creation offset, not a ring position. Their circles therefore kept the
attachments' 6.86 mm spacing (measured 6.99 mm) instead of the ring's 15.2 mm,
and the layout audit failed with a 7.7 × 3.0 mm overlap between items 25 and 6.

Subtracting the recorded anchor offsets, both ANCHORS sit a constant
`(13.50, 13.44)` mm from their attachment — a 45° default placement. The
identical-delta signature is the diagnostic: **balloons at a constant offset
from their own attachments were never re-ringed.**

Contrast the grouped rings on the same drawing, which ARE spread (two of their
attachments are 0.9 mm apart and the audit passes them) — so whatever loses the
concealed ring's placement does not affect `_add_component_balloons`. That
difference is the live lead.

**Three theories measured and REFUTED for this same overlap.** Each was specific,
plausible, and wrong; none is worth re-walking:

1. *Anchor-vs-circle frame.* `SetPosition` moves the annotation ANCHOR while the
   ink and the audit (`_note_element`) measure the CIRCLE (`GetBalloonInfo`), so
   a differing per-balloon offset would eat the gap. The offset is REAL — every
   drive-train balloon carries ~`(+4.2, -2.0)` mm — but it is UNIFORM, so the
   differential is `(0.05, 0.14)` mm, two orders of magnitude too small. The
   corrected build produced byte-identical boxes: a confident no-op. The offsets
   are still recorded on the `drawing.balloon_ring` span event, which is what
   refuted it.
2. *Spread-before-the-second-view.* That placing `concealed_front` re-solved
   the sheet and undid the bottom ring, since `_add_component_balloons` gets its
   views already placed. Moving BOTH concealed spreads after both views exist
   changed nothing — byte-identical boxes for the third time.
3. *Ellipse eccentricity.* That `_min_angular_gap`'s use of `min(Rx, Ry)` is
   conservative only for infinitesimal gaps, since an eccentric ellipse doubles
   back at its pointy end. Probed as a pure function to 5:1 — separation holds
   at every ratio.

**Three code changes, byte-identical output every time.** That repetition was
itself the signal, and it was under-weighted twice: when a change provably
cannot move the artefact, stop proposing mechanisms for the artefact and go
measure whether the code path runs at all. The next step is telemetry on the
ring geometry (centre, radii, gap, and each computed target) plus a read-back of
the balloon positions immediately after `SetPosition`, to separate "never
applied" from "applied then reverted" — a distinction none of the evidence so
far can make.

**Lesson.** An overlap on a ring has three candidate causes and they are
cheaply distinguishable from the recorded data before touching COM: crowding
(count vs ring circumference), a frame/units mismatch (compare the offsets), or
the spread not having taken effect at all (compare each balloon's final position
to its own ATTACHMENT — a constant delta across balloons means un-spread). Check
the third first; it is the only one that needs no geometry reasoning.

See [[load-bearing-claims-need-a-repro]] and
[[negative-result-needs-a-positive-control]]. Related:
[[drawing-recipe-com-pitfalls]], [[drawing-text-leader-style]].
