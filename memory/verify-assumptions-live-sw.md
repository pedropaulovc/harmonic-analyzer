---
name: verify-assumptions-live-sw
description: Don't trust old code comments — verify load-bearing CAD/mate assumptions empirically in live SolidWorks before designing a fix
metadata:
  type: feedback
---

When a fix hinges on claims in code comments (e.g. "eye_axes off until the
summation reorg", "angle mates are unreliable for mirrored parts", "this part has
no named axes"), treat those comments as **likely stale** and **retest the
assumption in live SolidWorks first** — open the actual part/assembly, list its
real features/refs, read the live `Transform2`/mirror state, try the candidate
mate and observe — before committing to a design or escalating scope.

**Why:** Pedro corrected a plan that escalated "mate tilted springs at angle" into
a large deferred reorg based purely on reading comments (`_spring.py` eye_axes
"off by default", `spin_driver` angle-mate warning). The comments may no longer
reflect the built parts or the current API behaviour, so the inferred blocker /
scope may be wrong.

**How to apply:** Before sizing or rejecting a CAD fix, write a small probe that
introspects the live model (features, named axes, component transforms, mirror
flags) and, where cheap, actually attempts the candidate mate. Let empirical
results — not the prose in the file — set the design and the scope. Relates to
[[no-untested-failure-assumptions]] and [[verify-sw-api-with-research]].
