# Negative-offset reference planes MIRROR sketch X (+ related COM seat facts)

Live-proven on the top-frame rederive (PR #459), R2026x seat.

## The mirror

`CreatePlaneParameters(mode="offset", offset=<negative>)` (adapter negates via
FlipDir) creates a plane whose SKETCH X AXIS IS MIRRORED relative to the base
plane: sketch x = −(model axis) — while the plane NORMAL is NOT flipped
(boss extrudes still go +normal; blind face-cut default still runs against
the base normal, so cut `reverse_direction` flags are chosen exactly as for a
positive offset). Positive-offset planes inherit the base axes unmirrored
(Right base: sketch (x,y) → (Z,Y), rocker-arm-support precedent).

- Detection was a VOLUME SIGNATURE: the hub-gusset union volume came out
  680.4 mm³; grid-integrating the four candidate hypotheses (base / flipped
  extrude / z-mirror / both) matched z-mirror to 0.1 mm³. When a feature can
  land in several discrete wrong poses, precompute each pose's analytic
  volume — the volume_check failure then NAMES the pose.
- SILENT case: symmetric sketches (e.g. panel rectangles whose spans mirror
  onto each other) pass volume checks with WRONG geometry. Any asymmetric
  sketch on a negative-offset plane must author mirrored coordinates
  (see `_panel_cut` in build_top_frame.py).

## Blind wizard holes read Ø0.0

A BLIND `wizard_holes` feature's definition reads 0.0 for BOTH HoleDiameter
and ThruHoleDiameter on this seat — `expect_dia_mm` is a THROUGH-hole-only
tripwire. Never pass it for blind specs, and never consume the readback
(`result.hole_dia_mm`) in a blind hole's volume math — use the pinned
`blind_cut_dia_mm`/`TAP_DRILL_MM` values (the dia HoleWizard5 was handed).

## Thread engagement models UNDER the tap drill

Fastener parts model their thread-engagement length at just UNDER the mating
tap drill (e.g. #10-24 shank 3.45 vs 3.797 drill; 1/2-13 stud neck 10.6 vs
10.716), else the assembly interference gate fires with exactly the annulus
volume π/4·(major²−drill²)·engagement — which is also the fingerprint to
recognize this mistake (437.85 mm³ for 1/2-13 ×12).

## Tangent-contact merges are impossible

A revolved sphere merging into an equal-diameter coaxial socket touches the
wall only along the equator circle — a zero-thickness tangent boolean
SolidWorks rejects (FeatureRevolve2 returns None). Ship the ball as a second
solid body (`merge_result=False`, pinion-handle press-fit precedent); mass
properties sum all bodies so volume gates are unchanged, but `_holes`' wizard
face scan reads GetBodies2()[0] — place wizard holes while the part is still
one body.
