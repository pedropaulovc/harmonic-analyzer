---
module: M06
title: "Mill I — tramming, squaring, edge finding"
status: in progress      # not started | in progress | competent | applied
hours_estimated: 24
hours_actual: 6.5
---

# M06 — Mill I — tramming, squaring, edge finding

## Objectives

- Hold work stiffly enough that the cut, not the setup, decides the finish
- Face a sawn bar to length and thickness by cutting to a written allowance
- Square a block on all six faces
- Find an edge and trust the DRO after it
- Tell climb from conventional milling before the cut starts
- Tram the head and know when it has drifted

## Prerequisites

- m01 — the allowance sheet for the oblique-jig stock

## References

- `references/machining-for-hobbyists-getting-started/09_chapter-7-milling-machines.pdf`
- `references/magxact-mx100m-mill-dro-manual/`, `references/el400-operation-manual/`
- The jig parts' registry rows:
  [`end-bracket`](../../cad/config/parts/ch-rocker-arm-tl-oblique-end-bracket.yaml),
  [`feed-lever`](../../cad/config/parts/ch-rocker-arm-tl-oblique-feed-lever.yaml),
  [`base-bar`](../../cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml),
  [`pivot-block`](../../cad/config/parts/ch-rocker-arm-tl-oblique-pivot-block.yaml),
  [`feed-block`](../../cad/config/parts/ch-rocker-arm-tl-oblique-feed-block.yaml),
  [`carrier`](../../cad/config/parts/ch-rocker-arm-tl-oblique-carrier.yaml)
- `cad/process/ch_rocker_arm_tl_oblique_base_bar/plan.toml`, a held preview
  route for the base bar's setups; not approval to machine

## Practice

- Workholding first: parallels, how high the work sits above the jaws,
  overhang, and when the table beats the vise
- Facing to length: measure, write target − actual, split the passes, cut to
  an absolute DRO coordinate
- Squaring a block: the order of faces
- Edge finding: mechanical, electronic, and the tool-diameter arithmetic
- Climb vs conventional: which side of the cutter the work is on, worked out
  with the spindle direction before the cut starts
- Axes: every axis describes the cutter moving relative to the work
- Tramming: the sweep method, and how often to re-check
- The escape: stop, wait for motion to end, retract Z

## Controlled mistakes

Make each on scrap first, under the
[rules](README.md#the-twist-break-it-on-purpose-first), then do it right and
compare. The 2026-10-30 entry made several of these by accident. Here they
are made deliberately, with a light cut.

- **Work high above the jaws.** With a light cut, mill the edge of a scrap
  plate standing well proud of the jaws, as on 2026-10-30. Then take the same
  cut with the plate low in the jaws or flat on the table. Listen, and compare
  the finish.
- **Climb when you think it is conventional.** Take one light finishing pass
  on the scrap each way. Before each pass, say which one it is. Compare sound,
  finish and any pull on the table.
- **Skip the parallels, or don't tap the work down.** Face a scrap block both
  ways and measure the error each produces in squareness and thickness.
- **Square faces in the wrong order.** Square one scrap block in the wrong face
  order and one in the right order, then check both on the surface plate.
- **Forget the cutter radius.** Edge-find without the radius offset, mill a
  step to a coordinate and measure how far off it lands. Then do it right.
- **Zero off the wrong corner, or with the wrong sign.** Cut one scrap feature
  from a datum set the wrong way and measure the miss.
- **An untrammed head.** Face a wide scrap face in overlapping passes before
  tramming and look at the steps between passes. Tram, then face it again.

## Now make — the real part this unlocks

**The oblique jig's bars, blocks and carrier**, in this order, so each part
needs one new skill:

1. **`ch-rocker-arm-tl-oblique-end-bracket`** ×2 (TL-28) and
   **`ch-rocker-arm-tl-oblique-feed-lever`** (TL-26): 1/2 × 1 in bar, saw and
   face to length. These are the smallest first cuts.
2. **`ch-rocker-arm-tl-oblique-base-bar`** ×2 (TL-20): 440 long with both large
   faces faced to 12.0. The owned 6 in bar is milled to width; the target width
   is open in [#2083](https://github.com/pedropaulovc/harmonic-analyzer/issues/2083).
   This is the long-part workholding lesson.
3. **`ch-rocker-arm-tl-oblique-pivot-block`** (TL-22) and
   **`ch-rocker-arm-tl-oblique-feed-block`** (TL-32): 40 wide by 24.3 high from
   1 × 3-1/2 in bar, squared on all six faces.
4. **`ch-rocker-arm-tl-oblique-carrier`** (TL-21): ripped from the 6 in bar,
   faced to 12.0 and milled to 520 × 130.

Their holes come in M08 and the base bars' slots in M07.

Then, in the analyzer: **`sm-knife-mount`** ×2, a rectangular block
34 × 43.77 × 14. It is the simplest prismatic part in the machine, and there
are two of them.

## Competency check

A block square within 0.02 mm across 40 mm, verified on a surface plate. The
pivot block and the feed block are each 40 wide, so either can be the block
checked.

## Notes

Watch the 4 mm floor under the knife-mount's Ø25.4 bore when you get to boring
it — breakout there scraps the part.

Standing a base bar on its end is out: 443 mm is more than the 17 in maximum
from spindle to table (`cad/process/shop/inventory.toml`).

## Sessions

Log entries for this module, newest last. Create them with
`entries/TEMPLATE.md`; **every observation in them comes from you.**

| date | entry | outcome | hours |
|---|---|---|---|
| 2026-10-29 | [vise install and first cuts](../entries/2026-10-29-vise-install-and-first-cuts.md) | partial | 6.5 |
