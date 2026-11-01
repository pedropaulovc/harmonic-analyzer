---
module: M01
title: "Measurement and layout"
status: not started      # not started | in progress | competent | applied
hours_estimated: 12
hours_actual: 0
---

# M01 — Measurement and layout

## Objectives

- Measure to 0.01 mm and know your own repeatability
- Read a drawing from this project and know what each callout demands
- Lay out work accurately enough to drill to position

## Prerequisites

- m00

## References

- `references/machining-for-hobbyists-getting-started/04_chapter-2-measuring-tools.pdf`
- `references/machinerys-handbook/` (limits and fits)
- `cad/docs/tolerance-policy.md`, `cad/docs/tolerance-gdt-assessment.md`
- `references/magxact-mx100m-mill-dro-manual/`, `references/el400-operation-manual/`

## Practice

- Calipers vs micrometer: measure one gauge block twenty times with each; compute your own spread. **This number is your real tolerance floor.**
- Bore measurement: telescoping gauge, small-hole gauge, bore gauge
- Indicating: runout, flatness, tram — what a DTI actually tells you
- Layout: bluing, scribing, edge finding, using the DRO as the datum
- Read the drawing sheets in `cad/out/pdf/` and translate three callouts into shop checks

## Controlled mistakes

Make each on scrap first, under the
[rules](README.md#the-twist-break-it-on-purpose-first), then do it right and
compare.

- **Squeeze the calipers.** Measure the same gauge block twenty times with a
  heavy grip and twenty with a light one. The difference between the two
  spreads is an error you would otherwise carry into every part unknowingly.
- **Measure it warm.** Measure an aluminium offcut straight after a cut, then
  again when it is cold.
- **An indicator on a loose mount.** Indicate a fixed jaw with the indicator
  on a magnetic base stuck to the spindle, then held in an R8 collet, as on
  2026-10-29. Record the repeatability of each.
- **Scribe wet layout fluid.** Scribe one line in Dykem before it dries and
  another after, side by side. 2026-10-29 did the first by accident.
- **Cut without an allowance sheet.** Take a scrap end to a target by counting
  increments, without first measuring and writing target − actual. Then do the
  same from a measured allowance split into roughing passes and a finish pass,
  cutting to an absolute DRO coordinate. 2026-10-30 lost a part the first way.

## Now make — the real part this unlocks

**The allowance sheet for the oblique-jig stock.** Measure every piece of
stock bought for the `ch-rocker-arm-tl-oblique-jig` parts: base bars, blocks,
carrier, end brackets, feed lever and riser. For each one, write the target
from its drawing, the measured size and the allowance per face, split into
rough and finish passes. M06 cuts to these sheets, and every later part gets
one before its first cut.

## Competency check

Your measurement spread on a known gauge block is < 0.01 mm, and you can state the shop check for a runout callout, a position callout and a profile callout without looking them up.

## Notes

This is the module beginners skip and then spend a year confused. Every tolerance in the book is meaningless if you cannot verify it.

## Sessions

Log entries for this module, newest last. Create them with
`entries/TEMPLATE.md`; **every observation in them comes from you.**

| date | entry | outcome | hours |
|---|---|---|---|
| 2026-10-29 | [vise install and first cuts](../entries/2026-10-29-vise-install-and-first-cuts.md) (layout with Dykem and scriber) | partial | 0.5 of 6.5, counted under M06 |
