---
name: balloon-anchor-vs-circle-frame
description: A deterministic "edge nearest the component centroid" anchor rule CLUSTERS anchors of physically adjacent components — it regressed drive-train sheet 4 into a balloon overlap; plus three refuted theories for that overlap
metadata:
  type: project
---

**What happened (2026-07-28).** Replacing the arrival-order anchor edge
(`edges[0]`) with a deterministic "edge whose midpoint is nearest the mean of
midpoints" pulled every anchor toward its component's CENTROID. For two
components in the same physical stack — `cone-gear-shaft` and
`cone-tip-bushing`, both in the cone journal stack — that puts their anchors on
top of each other. Recorded attachments for drive-train sheet 4's two-balloon
ring:

| code | item A | item B | separation |
|---|---|---|---|
| main | `0.087730, 0.123821` | `0.102846, 0.187109` | **65.1 mm** |
| centroid rule | `0.102557, 0.185808` | `0.100503, 0.179268` | **6.86 mm** |

One anchor moved ~57 mm onto its neighbour, and the layout audit failed with a
7.7 × 3.0 mm overlap on 9.7 mm boxes. **This was a regression, not a latent
main-branch defect** — main's anchors were 65 mm apart, so nothing ever needed
separating and the drawing was solidly green.

**The general trap.** A deterministic anchor rule is not automatically a SAFE
one. Any global geometric rule (most-negative corner, nearest-centroid, …)
applies the same bias to every component, so components that are physically
adjacent get anchors that are adjacent too. Arrival order was nondeterministic
but spatially arbitrary, which is what kept anchors apart by luck. **Determinism
and spread are separate properties; a fix for one can destroy the other.**
Before shipping an anchor rule, diff the resulting attachment points against
main and look for pairs that moved TOGETHER — the `drawing.balloon_ring` span
event records them per ring.

**Corollary:** any anchor rule that clusters makes the drawing depend on
`_spread_balloons` actually separating the balloons. On this ring it did not —
anchors 6.86 mm apart produced circles 6.99 mm apart, where the gap formula
demands 15.2 mm. Whether the spread works on that view AT ALL is untested;
main never exercised it, because its anchors were already far apart.

**Three theories measured and REFUTED for that non-separation.** Each was
specific, plausible, and wrong:

1. *Anchor-vs-circle frame.* `SetPosition` moves the annotation ANCHOR while the
   ink and the audit (`_note_element`) measure the CIRCLE (`GetBalloonInfo`).
   The offset is REAL — every drive-train balloon carries ~`(+4.2, -2.0)` mm —
   but UNIFORM, so the differential is `(0.05, 0.14)` mm, ~100x too small.
2. *Spread ran before the second view was placed*, so the sheet re-solve undid
   it. Moving both concealed spreads after both views changed nothing.
3. *Ellipse eccentricity* makes `min(Rx, Ry)` non-conservative. Probed as a pure
   function to 5:1 — separation holds at every ratio.

Three code changes, byte-identical boxes every time. **That repetition was the
signal and it was under-weighted twice**: when a change provably cannot move the
artefact, stop proposing mechanisms and go measure whether the code path runs.
The cheap discriminator, before any COM run: compare each balloon's final
position to its OWN attachment — a constant delta across balloons means the ring
was never applied.

See [[load-bearing-claims-need-a-repro]] and
[[negative-result-needs-a-positive-control]]. Related:
[[drawing-recipe-com-pitfalls]], [[drawing-text-leader-style]].
