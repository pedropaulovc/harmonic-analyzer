---
name: balloon-anchor-vs-circle-frame
description: SetPosition moves a balloon's annotation ANCHOR, but the ink and the layout audit are the CIRCLE — separation enforced in the wrong frame under-delivers by up to a full balloon diameter
metadata:
  type: project
---

`IAnnotation::SetPosition` moves a BOM balloon's **annotation anchor**.
`INote::GetBalloonInfo` returns the **circle** (centre + radius). SolidWorks
derives the anchor→centre offset from the balloon's TEXT and LEADER SIDE, so it
differs per balloon on the same ring — a 2-character item and a 1-character one
carry different offsets.

`_drawing_common._spread_balloons` computed a separation with `_min_angular_gap`
and then aimed the **anchor** at the ring point, while both the drawn ink and
`_note_element` (the layout audit) measure the **circle**. The real gap is
therefore short by the DIFFERENTIAL offset, bounded only by a full balloon
diameter — a silent, geometry-dependent shortfall, not a constant one.

Repro (2026-07-28, drive-train sheet 4 concealed-bottom ring): two balloons
ALONE on a ring with the whole circle free — '25' (cone-gear-shaft) and '6'
(cone-tip-bushing). Circles landed **6.99 mm** apart where the formula demanded
**15.2 mm**; the layout audit failed with a 7.7 × 3.0 mm overlap on 9.7 mm
boxes. Offline model of the same pair: 5.42 mm against a 9.7 mm box.

**Fix:** the placement loop already calls `GetBalloonInfo` for the radius, so
one extra `GetPosition` per balloon gives the offset; placement pre-subtracts
it. Cost is one COM read per balloon — no rebuild, no second pass. The offset
is recorded on the `drawing.balloon_ring` span event, so a ring that WOULD have
under-separated is visible in `traces.jsonl`.

**The generalisable rule: placement must be enforced in the frame the GRADER
measures.** `_min_angular_gap`'s docstring already said this in words — it
separates against the audit's circumscribed SQUARE rather than the circle,
because "placement must satisfy the model that grades it" — and the code then
broke the same rule one level down, on the frame rather than the shape. When a
checker and a placer read different APIs for the same object, verify they agree
on the ORIGIN, not just the size.

**Refuted en route, so nobody re-walks it:** the hypothesis that
`_min_angular_gap`'s use of `min(Rx, Ry)` is only conservative for infinitesimal
gaps (the ellipse "doubling back" at its pointy end). Probed as a pure function
to 5:1 eccentricity — separation holds at every ratio. The frame mismatch, not
the ellipse, was the defect. See [[load-bearing-claims-need-a-repro]] and
[[negative-result-needs-a-positive-control]].

Related: [[drawing-recipe-com-pitfalls]], [[drawing-text-leader-style]].
