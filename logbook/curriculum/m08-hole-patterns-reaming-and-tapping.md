---
module: M08
title: "Hole patterns, reaming and tapping"
status: not started      # not started | in progress | competent | applied
hours_estimated: 16
hours_actual: 0
---

# M08 — Hole patterns, reaming and tapping

## Objectives

- Drill a pattern to position
- Tap a hole without breaking the tap
- Ream in the mill
- Counterbore to a depth

## Prerequisites

- m06 — the jig parts squared, so there are faces to locate holes from

## References

- `references/machinerys-handbook/` (tap drill sizes, thread data)
- `references/el400-operation-manual/` (linear and bolt-circle hole patterns)
- The oblique-jig registry rows and drawings in M06's references
- `cad/docs/machining-dfm.md` (`fr-rocker-arm-support`, `sm-summing-lever`)
- `cad/scripts/build_fr_rocker_arm_support.py` (foot thickness, four-hole pattern and 1/2-13 UNC-2B thread)
- `cad/scripts/_holes.py` (`TAP_DRILL_MM["1/2-13"]`)

## Practice

- Position tolerance and what it means when you drill
- Cutting to absolute coordinates and the DRO's hole-pattern functions,
  instead of counting increments
- Spot drill, drill, ream — and when to skip a step
- Tapping by hand, under the spindle, and with a tapping head
- Counterbores: depth from the right Z zero
- Blind holes: tap drill depth, bottoming taps, chip packing
- Breakout on a thin floor

## Controlled mistakes

Make each on scrap first, under the
[rules](README.md#the-twist-break-it-on-purpose-first), then do it right and
compare.

- **No spot drill.** Drill a row of scrap holes straight and a row after
  spotting, then measure position error on both.
- **Count increments.** Drill a five-hole row by counting handwheel turns, and
  another with the EL400 linear pattern or absolute coordinates. Measure both.
  2026-10-30 lost track of increments in a cut.
- **The tap drill one size small.** Hand-tap a scrap hole drilled one size
  under and feel the torque climb. Back out before it binds, then tap a hole at
  the right size.
- **Not breaking the chip.** Hand-tap a blind scrap hole without backing off
  and feel the load build. Stop well before it binds.
- **Counterbore from the wrong zero.** Set Z off the wrong surface for one
  scrap counterbore and measure the floor height you got.
- **Wrong reaming allowance.** Ream one scrap hole with too little stock and
  one with too much, and compare them with one at the handbook allowance on a
  gauge pin.

## Now make — the real part this unlocks

**The oblique jig's holes**, in the parts squared in M06:

- **`ch-rocker-arm-tl-oblique-end-bracket`** ×2: four #8-32 and two #6-32
  tapped through.
- **`ch-rocker-arm-tl-oblique-base-bar`** ×2: the seven #8-32 rail holes
  tapped through, and the eight #8 bracket holes drilled through and
  counterbored from the underside.
- **`ch-rocker-arm-tl-oblique-feed-lever`**: two 5/16 clearance holes through.
- **`ch-rocker-arm-tl-oblique-pivot-block`** and
  **`ch-rocker-arm-tl-oblique-feed-block`**: the Ø10 H7 pivot seat 6.85 deep
  with M8×1.25 tapped through below it, and the four carriage counterbores
  with floors 15.600 above the bottom. Drill the feed block's four nut taps to
  print, not by transfer.
- **`ch-rocker-arm-tl-oblique-carrier`**: the four reamed pivot-pin holes, each
  with its underside edge chamfered 0.3 min × 45°; the HUB and CL spots; the
  CR, riser and feed-lever taps.

Then, in the analyzer: **`fr-rocker-arm-support`** foot holes: 4× 1/2-13 UNC-2B
through the 6.35 mm foot, tap drill Ø10.716 mm (Ø10.72 displayed; 27/64 in),
from `cad/scripts/build_fr_rocker_arm_support.py` and `cad/scripts/_holes.py`.
Then the 20× Ø2.0 spring holes in the summing lever at 7.0565 mm pitch.

## Competency check

A four-hole pattern within 0.1 mm true position, and a 1/2-13 UNC-2B thread cut clean without a broken tap (the support thread specified in `cad/scripts/build_fr_rocker_arm_support.py`).

## Notes

The support feet are one tapped joint among several; the knife-mount hanger-stud seat is another (`cad/docs/machining-dfm.md`). There are no keyways: gears seat on D-flats, are pinned, or run free on an arbor.

The carrier's 5/16-18 feed-lever taps engage only 1.20D in the 12 mm plate,
under the usual 1.5D. That shortfall is accepted on the drawing because the
lever takes only hand load (carrier registry row, RV-01).

## Sessions

Log entries for this module, newest last. Create them with
`entries/TEMPLATE.md`; **every observation in them comes from you.**

| date | entry | outcome | hours |
|---|---|---|---|
| | | | |
