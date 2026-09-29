---
module: M11
title: "Soldering, finishing and assembly craft"
status: not started      # not started | in progress | competent | applied
hours_estimated: 16
hours_actual: 0
---

# M11 — Soldering, finishing and assembly craft

## Objectives

- Fit gear D-bores to their shaft flats and assemble a solid, touching gear stack
- Make a silver-soldered joint you can rely on
- Finish a part to the standard the book will photograph
- Assemble precision parts without damaging them

## Prerequisites

- m03
- m10 — the "now make" is the cone gear stack on its D-flat shaft, so the
  gears have to exist first. (The silver-solder *practice* can be done any
  time after m03.)

## References

- `references/machining-for-hobbyists-getting-started/`
- `cad/docs/machining-dfm.md` (D-flat gear seats, no keys or adhesive)
- `cad/scripts/gear_seat_fit.py`, `cad/scripts/cone_gear_stack.py` and
  `cad/scripts/cone_stack_end_play.py` (the fit, stack and end-play numbers)
- `cad/config/parts/*.yaml` (appearance per part)

## Practice

- Gauging a shaft flat across flats and a D-bore across its flat
- Judging a slip fit by feel, and deburring a D-bore entry without rounding its flat
- Setting end play with a feeler
- Silver solder: cleanliness, flux, and heating a joint evenly
- Draw filing, stoning, polishing brass, blacking steel
- Matching the original: matte-black rods, bright amplitude bars, black-stained crank handle

## Now make — the real part this unlocks

The **cone gear stack on its D-flat shaft**: the 64T and twenty cone gears slid on flat to flat, touching, with the tip block set off a feeler. Silver-solder the `crank-pin-ring` ends. Then finish the `crank-handle` and a `connecting-rod`.

## Competency check

A twenty-gear stack that measures 137.774 ±0.20 mm (`cad/scripts/cone_gear_stack.py`) and turns free with no tight spot; a silver-soldered test joint pulled to destruction that fails in the parent metal, not the joint; and a polished brass surface with no visible scratch pattern.

## Notes

There is not a single keyway in this machine. The cone gears and the 64T locate on D-flats (user ruling 2026-09-28): the flat clocks each gear, the touching stack spaces them, and nothing is soldered or glued.

## Sessions

Log entries for this module, newest last. Create them with
`entries/TEMPLATE.md`; **an agent may create the file, only you may fill it in.**

| date | entry | outcome | hours |
|---|---|---|---|
| | | | |
