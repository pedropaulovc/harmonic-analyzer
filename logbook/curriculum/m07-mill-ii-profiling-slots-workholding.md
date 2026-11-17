---
module: M07
title: "Mill II — profiling, slots, workholding"
status: not started      # not started | in progress | competent | applied
hours_estimated: 28
hours_actual: 5
---

# M07 — Mill II — profiling, slots, workholding

## Objectives

- Cut a slot to width
- Hold thin and flexible stock flat without crushing it
- Prove a profile program in air, then run it on stock
- Mill a 2D profile from a program to its drawing limits
- Hold twenty identical parts identically

## Prerequisites

- m06
- m08 — drilling and reaming, which the rocker strap's hub and rod-pin holes need

## References

- `references/machining-for-hobbyists-getting-started/09_chapter-7-milling-machines.pdf`
- [`ch-rocker-strap`](../../cad/config/parts/ch-rocker-strap.yaml) registry row
- `cad/process/ch_rocker_strap/`: the strap's process plan and CAM recipe; its
  NC programs are posted to `cad/out/nc/ch_rocker_strap/` and ship with each
  release under `nc/ch_rocker_strap/`
- `cad/docs/machining-dfm.md` (`ch-rocker-arm`, `ch-connecting-rod` rows)
- `cad/scripts/build_ch_rocker_strap.py`, `cad/scripts/build_ch_rocker_arm.py`

## Practice

- Slots: width, and why a slot is never the cutter diameter
- Speed, depth and chip clearing in an aluminium slot
- Thin stock: holding the 1/8 in strap flat, and tape or double-sided workholding
- Proving a program: tool lengths on the tool setter, work zero from the touch
  probe, a run in air above the stock, then the first part checked before the
  rest
- Profile milling from a program: cutter compensation in the CAM, leaving a
  finishing pass
- Arcs: the controller interpolates them, so the R800/R816 edges need no jig
- Simple fixtures, stops, and soft jaws
- Twenty identical profiles: one program, one stop, one work zero

## Controlled mistakes

Make each on scrap first, under the
[rules](README.md#the-twist-break-it-on-purpose-first), then do it right and
compare.

- **A slot in one pass.** Mill a scrap slot full-width in a single pass and
  measure it: width, and both walls. Then rough it undersize and finish each
  wall separately.
- **Hunt for the chatter band.** Take the same light cut in scrap at several
  spindle speeds and note where it chatters. On 2026-10-30 a full-width cut
  that chattered at 1500 rpm was acceptable at 1000–1200 rpm; find out whether
  that holds with a stiff setup.
- **Recut the chips.** Mill a scrap slot without clearing chips, then one with
  air or fluid, and compare the floor and walls.
- **No finishing allowance.** Profile one scrap edge straight to the line and
  another with a finishing pass left, then compare.
- **No stop.** Mill five scrap profiles locating each by eye, then five against
  a stop, and measure the spread of each set.
- **Clamp thin stock hard.** Clamp a scrap acetal strip tightly across its
  thin section and measure how much it bows. Then hold it right.

## Now make — the real part this unlocks

**`ch-rocker-strap`** (MHA-CH-13) ×20 from its CNC programs, the first part
trialled end to end on the CNC mill: 1018 flat with an R800 concave top edge
that is the **outline** of the strap, not a pocket. Each strap takes a hub
turned on the lathe to make a **`ch-rocker-arm`**.

Then **`ch-connecting-rod`** ×20: a flat 2D profile, with the rough finish the
book shows.

## Competency check

Twenty rocker arms whose pivot-to-pin distance varies by less than 0.05 mm across the set.

## Notes

The R800 arc is what the amplitude bar rides on. Its consistency across twenty
parts is a functional requirement, not cosmetic. That is why all twenty come
from one program and one work zero.

The 2026-10-30 session is logged here, but what it actually did was face to
length, which is M06 work. It stays where it was logged.

## Sessions

Log entries for this module, newest last. Create them with
`entries/TEMPLATE.md`; **every observation in them comes from you.**

| date | entry | outcome | hours |
|---|---|---|---|
| 2026-10-30 | [pendant and roughing the base bar to length](../entries/2026-10-30-pendant-and-roughing-base-bar-to-length.md) | scrapped | 5 |
