---
module: M08
title: "Hole patterns, reaming and tapping"
status: not started      # not started | in progress | competent | applied
hours_estimated: 12
hours_actual: 0
---

# M08 — Hole patterns, reaming and tapping

## Objectives

- Drill a pattern to position
- Tap a hole without breaking the tap
- Ream in the mill

## Prerequisites

- m06

## References

- `references/machinerys-handbook/` (tap drill sizes, thread data)
- `cad/docs/machining-dfm.md` (`rocker-arm-support`, `summing-lever`)
- `cad/scripts/build_rocker_arm_support.py` (foot thickness, four-hole pattern and 1/2-13 UNC-2B thread)
- `cad/scripts/_holes.py` (`TAP_DRILL_MM["1/2-13"]`)

## Practice

- Position tolerance and what it means when you drill
- Spot drill, drill, ream — and when to skip a step
- Tapping by hand, under the spindle, and with a tapping head
- Blind holes: tap drill depth, bottoming taps, chip packing
- Breakout on a thin floor

## Now make — the real part this unlocks

**`rocker-arm-support`** foot holes: 4× 1/2-13 UNC-2B through the 6.35 mm foot, tap drill Ø10.716 mm (Ø10.72 displayed; 27/64 in), from `cad/scripts/build_rocker_arm_support.py` and `cad/scripts/_holes.py`. Then the 20× Ø2.0 spring holes in the summing lever at 7.0565 mm pitch.

## Competency check

A four-hole pattern within 0.1 mm true position, and a 1/2-13 UNC-2B thread cut clean without a broken tap (the support thread specified in `cad/scripts/build_rocker_arm_support.py`).

## Notes

The support feet are one tapped joint among several; the knife-mount hanger-stud seat is another (`cad/docs/machining-dfm.md`). There are no keyways: gears are soldered or run free on an arbor.

## Sessions

Log entries for this module, newest last. Create them with
`entries/TEMPLATE.md`; **an agent may create the file, only you may fill it in.**

| date | entry | outcome | hours |
|---|---|---|---|
| | | | |
