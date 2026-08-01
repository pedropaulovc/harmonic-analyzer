---
name: world-anchor-before-sign-algebra
description: PR #458 rocker-stop inversion retrospective — check references/ before asserting machine behaviour; probe world coordinates before sign-convention reasoning; name WHICH feature a photo measurement refers to; derive test directions from the physical spec, not from the code under test
metadata:
  type: feedback
---

**What happened (2026-08-01, PR #458):** the rocker-stop window shipped
direction-INVERTED for weeks — it allowed only the mirror image of the
physical stroke — and when the user hit it ("can't move rocker arm lower
than neutral") I defended the inversion with an invented mechanism model
("the ring rests on the cam base circle, it can only lift") before being
sent to the sources. Three compounding failures: (1) I asserted machine
behaviour without opening `references/` (book chapter PDFs, engineerguy
transcripts, end-view photos — all in-repo; the eccenric-STRAP positive
drive was even stated in [[ch14-rom-rederive]]); (2) I did sign-convention
algebra (plane-angle sense × arm_tilt sign × stroke sign × view handedness)
on a GUESSED pivot coordinate and flip-flopped three times, when a 5-minute
probe printing world Y of pivot/rod-pin/tail before and after a stroke
settled it instantly; (3) my own new gates inherited the inversion because
I derived their stroke directions from the existing window instead of from
the physical spec — tests ratified the folklore they should have falsified.

**Why:** an untested load-bearing SIGN lived only in a comment ("covers the
physical -7.43..0 stroke"); comments assert, gates prove. And "tips in a
flat level row" in the ch14 memory never said WHICH end the tips were — an
ambiguous photo measurement resolved the wrong way survives every review.

**How to apply:**
- Before asserting how the MACHINE behaves, open `references/` (book
  chapters by part, `engineerguy-youtube/*.vtt`, keyframes) — the user
  knows this machine; contradicting them from memory is always wrong.
- Any question of the form "which direction/side/sign" gets a
  world-coordinate probe FIRST (print the actual points, move, print
  again), never stacked-convention reasoning.
- A photo-derived quantity must name the feature it measured
  ("rod-side arm ends", not "tips") in the memory/comment that records it.
- Write kinematic gates from the PHYSICAL spec direction; if the only
  source of a test's direction is the code under test, the test proves
  nothing. Pin direction world-anchored (which end rises/falls), not in
  mate-dimension units.

Related: [[ch14-rom-rederive]], [[channel-bar-station-driven]],
[[no-untested-failure-assumptions]], [[load-bearing-claims-need-a-repro]],
[[verify-assumptions-live-sw]].
