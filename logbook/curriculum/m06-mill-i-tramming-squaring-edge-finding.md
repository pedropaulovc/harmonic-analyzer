---
module: M06
title: "Mill I — tramming, squaring, edge finding"
status: in progress      # not started | in progress | competent | applied
hours_estimated: 24
hours_actual: 21.75
---

# M06 — Mill I — tramming, squaring, edge finding

## Objectives

- Hold work stiffly enough that the cut, not the setup, decides the finish
- Face a sawn bar to length and thickness by cutting to a written allowance
- Square a block on all six faces
- Find an edge with the touch probe and set the work zero from it
- Set tool lengths on the tool setter and prove a program in air before it cuts
- Tell climb from conventional milling before the cut starts
- Tram the head and know when it has drifted

## Prerequisites

- m01 — the allowance sheet for the first mill parts' stock

## References

- `references/machining-for-hobbyists-getting-started/09_chapter-7-milling-machines.pdf`
- `references/magxact-mx100m-mill-dro-manual/`
- [`sm-knife-mount`](../../cad/config/parts/sm-knife-mount.yaml) registry row
- [`cad/process/README.md`](../../cad/process/README.md) (process plans, and
  the NC programs posted for CNC parts)

## Practice

- Workholding first: parallels, how high the work sits above the jaws,
  overhang, and when the table beats the vise
- Facing to length: measure, write target − actual, split the passes, cut to
  an absolute work coordinate
- Squaring a block: the order of faces
- Edge finding: the touch probe, a mechanical finder as the cross-check, and
  the tip-diameter arithmetic
- Jogging, tool lengths from the tool setter, and running a program in air
  above the stock before it cuts
- Climb vs conventional: which side of the cutter the work is on, worked out
  with the spindle direction before the cut starts
- Axes: every axis describes the cutter moving relative to the work
- Tramming: the sweep method, and how often to re-check
- The escape: feed hold or e-stop, wait for motion to end, retract Z

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

**`sm-knife-mount`** ×2, a rectangular block 34 × 43.77 × 14. It is the
simplest prismatic part in the machine, and there are two of them.

## Competency check

A block square within 0.02 mm across 40 mm, verified on a surface plate.

## Notes

Watch the 4 mm floor under the knife-mount's Ø25.4 bore when you get to boring
it — breakout there scraps the part.

The oblique trammel jig this module used to open on was deleted (2026-11-17);
the sessions below made its parts and stay as they were logged.

## Sessions

Log entries for this module, newest last. Create them with
`entries/TEMPLATE.md`; **every observation in them comes from you.**

| date | entry | outcome | hours |
|---|---|---|---|
| 2026-10-29 | [vise install and first cuts](../entries/2026-10-29-vise-install-and-first-cuts.md) | partial | 6.5 |
| 2026-11-04 | [oblique-jig end brackets](../entries/2026-11-04-oblique-end-brackets-scrapped.md) | scrapped | 5.25 |
| 2026-11-05 | [base bar on the table](../entries/2026-11-05-base-bar-on-the-table.md) | partial | 4 |
| 2026-11-06 | [base bar, both edges, controller reset](../entries/2026-11-06-base-bar-both-edges-and-a-controller-reset.md) | partial | 6 |
