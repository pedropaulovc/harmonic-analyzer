---
module: M10
title: "Gear cutting — making the cutter, then the gear"
status: not started      # not started | in progress | competent | applied
hours_estimated: 60
hours_actual: 0
---

# M10 — Gear cutting — making the cutter, then the gear

## Objectives

- Generate a form cutter by the Eureka method
- Harden and temper it
- Cut an involute gear and inspect it
- Work down in size to the fragile end of the cone set

## Prerequisites

- m09
- m05

## References

- `references/gears-and-gear-cutting/gears-and-gear-cutting.pdf` **ch. 12 (Eureka method)**
- `cad/docs/machining-dfm.md` (gear routing; cutter plan with the stock cutter number and indexing for each gear)
- `cad/docs/gear-standard.md` (why the replica uses 20° inch-standard teeth)
- `cad/scripts/build_dt_cone_gear.py`, `cad/scripts/build_dt_cylinder_gear.py`

## Practice

- Choosing the stock cutter number for each gear from its tooth count, and why T006 falls outside every range
- Making the button tool for the T006 cutter
- Generating the form; relieving; hardening and tempering
- Testing a cutter on scrap before trusting it
- Blank prep: the bore is the datum
- Mandrels, depth of cut, full tooth depth
- Inspection: over-pins, runout on a mandrel, meshing a pair
- The helical 64T crank gear: why it needs a spiral-capable universal head geared to the table (`cad/docs/machining-dfm.md`, cutter plan)

## Now make — the real part this unlocks

**`dt-cone-gear` T120** first (largest, most forgiving), then the `dt-cylinder-gear` ×20, then down the cone set toward T006.

## Competency check

A cut gear that meshes with its mate through a full rotation with no tight spot, and measures within tolerance over pins.

## Notes

**The long pole of the entire project.** 60 h is a guess and probably low. The T006 gear (~4.16 mm OD, Ø1.5875 mm bore, **0.354 mm root-to-bore web** at the largest allowed bore) is the single hardest part in the machine — treat reaching it as a separate milestone, and cut a first article long before committing the set.

## Sessions

Log entries for this module, newest last. Create them with
`entries/TEMPLATE.md`; **an agent may create the file, only you may fill it in.**

| date | entry | outcome | hours |
|---|---|---|---|
| | | | |
