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
- Assemble a jig and fit a running gap to a measured number
- Mill a 2D profile to a line
- Hold twenty identical parts identically

## Prerequisites

- m06
- m08 — the jig's holes, so it can be assembled and cut rocker arms

## References

- `references/machining-for-hobbyists-getting-started/09_chapter-7-milling-machines.pdf`
- [`ch-rocker-arm-tl-oblique-base-bar`](../../cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml) and
  [`ch-rocker-arm-tl-oblique-riser`](../../cad/config/parts/ch-rocker-arm-tl-oblique-riser.yaml) registry rows
- `cad/scripts/ch_rocker_arm_tl_oblique_jig_assembly_spec.py` and the
  `ch-rocker-arm-tl-oblique-jig` assembly drawing (fit-up, travel, BOM)
- [Oblique jig plain-pivot tooling](../../cad/docs/subsystem-identities.md#oblique-jig-plain-pivot-tooling)
  (shimming the carrier's running gap)
- `cad/docs/machining-dfm.md` (`ch-rocker-arm`, `ch-connecting-rod` rows)
- `cad/scripts/build_ch_rocker_arm.py`

## Practice

- Slots: width, and why a slot is never the cutter diameter
- Speed, depth and chip clearing in an aluminium slot
- Thin stock: holding 6 mm acetal flat, and tape or double-sided workholding
- Fit-up: shims, feeler gauges, and measuring a running gap
- Profile milling: cutter comp by hand, leaving a finishing pass
- Arcs on a manual machine: rotary table, template, file-to-line, or a jig
  that generates them
- Simple fixtures, stops, and soft jaws
- Twenty identical profiles without CNC

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

**Finish the oblique jig, then cut rocker arms on it:**

1. The two hold-down slots through each **`ch-rocker-arm-tl-oblique-base-bar`**.
2. **`ch-rocker-arm-tl-oblique-riser`** (TL-24): 1/4 in acetal faced to 6.0 and
   milled to a 40 × 340 blank. At assembly, spot its holes from the carrier,
   drill #4 clearance and countersink 82°; drill the HUB, CL and CR clearance
   holes.
3. **Assemble `ch-rocker-arm-tl-oblique-jig`** (TL-00) on the table to its
   drawing. Fit each measured carrier running gap to 0.05–0.25 mm with the
   purchased shims.
4. Use the jig to cut **`ch-rocker-arm`** ×20: 2.5 mm steel, with an R800
   concave top edge that is the **outline** of the plate, not a pocket.

Then **`ch-connecting-rod`** ×20: a flat 2D profile, with the rough finish the
book shows.

## Competency check

Twenty rocker arms whose pivot-to-pin distance varies by less than 0.05 mm across the set.

## Notes

The R800 arc is what the amplitude bar rides on. Its consistency across twenty
parts is a functional requirement, not cosmetic. That is why the jig is worth
building before the first arm.

The 2026-10-30 session is logged here, but what it actually did was face to
length, which is M06 work. It stays where it was logged.

## Sessions

Log entries for this module, newest last. Create them with
`entries/TEMPLATE.md`; **every observation in them comes from you.**

| date | entry | outcome | hours |
|---|---|---|---|
| 2026-10-30 | [pendant and roughing the base bar to length](../entries/2026-10-30-pendant-and-roughing-base-bar-to-length.md) | scrapped | 5 |
