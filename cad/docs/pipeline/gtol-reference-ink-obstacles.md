# GTol placement and center-reference ink

This is a bounded planner correction, not native acceptance evidence for the
changed drawing. It preserves center marks/centerlines and the final collision
gate. Native rerun and current PNG inspection remain required.

## Retained failure

At root `4c3c1e116980fa8ed0bbb4e384c9c2bd952d95f7`, production
`drawing:cone_pivot_screw` failed in the fresh final annotation check. Trace
`0x4339a41c960ce33fcd059a38e0c03ab2` in
`cad/out/reports/telemetry/traces.jsonl` ends at
`2026-09-07T11:22:34.345307Z`. Template HIT, ThreadTail import, GTol placement,
and packing readback completed before this rejection:

- View `end`: source `DetailItem344`, combined stroke index `7`.
- Target `DetailItem349`, kind `5`, text
  `['<GTOL-TRUN>', '0.05', 'A', 'SHOULDER OD']`.
- Target body in sheet metres:
  `[0.1039590787186291, 0.16291526514446417,
  0.1363848787186291, 0.1754815155262133]`.

That receipt omitted the source kind and stroke coordinates. It does **not**
establish that `DetailItem344` is a center mark. The fastener recipe deliberately
creates end-view center marks before its dimensions, making the missing planner
inventory a concrete lead, not a confirmed identity for that native name. The
existing September 6 screw PNG is stale and is not evidence for this failed run.

## Correction and limits

The planner previously enumerated only datum, dimension, and surface-finish
annotations (`2/4/7`), while the final reverse check already included every
measured annotation's displayed strokes and native leader segments. The planner
now also enumerates `swCenterMarkSym=13` and `swCenterLine=15` through the existing
`IView.GetAnnotationsByType` call. Those enum values and the view-local array
contract were checked against the bundled official API reference.

The existing native bounds reader encloses center-reference strokes and their
measured print widths in the annotation body. That body feeds the existing
outboard/vertical candidate policy; no reference annotation is selected, moved,
removed, or recreated. Hidden and template-owned reference ink is excluded
consistently with the final packing collision bank. Unknown visibility is not
silently treated as hidden.

Each included reference annotation costs one additional fresh full planner read,
plus two type-enumeration calls per nonempty GTol view. Nullable native positions
are supported by the bounds reader, but not by the XYZ-only handoff, so these
measurements are deliberately **not** registered in that cache. Initial/final
packing and all existing semantic, source, attachment, and collision checks stay
unchanged. This is not a zero-COM or measured speedup claim. Rectangle envelopes
can conservatively reject otherwise clear lanes; no exact ink-routing claim is
made. Deferred notes and other final-only kinds are not newly added to planning.

Reverse-collision failures now retain source kind, each hit's exact coordinates
and width, its displayed-stroke versus native-leader inventory/index, and hit
decoration bounds. These are derived only from the existing final snapshot;
the hit predicate and original fields are unchanged.

## Offline regression

In `C:/src/ha-perf-gtol-reference-ink`, fail-first receipt
`cad/out/reports/pytest-telemetry/run-f8qfi2d2` recorded four failures: both
`13/15` reference fixtures still intersected the old accepted GTol lane, and
both error-evidence fixtures lacked source kind. Four exclusion controls passed.
The corrected suite also proves that the new lane passes the unchanged final
check, reference ink is read once and never handed off/moved, empty GTol views
do not scan references, and hidden/template exclusions preserve required ink.

The broader bounds/GTol/layout/handoff suite passed **495 tests** in 6.02 s,
receipt `run-z2z5jtt7`. Focused reproduction from an initialized checkout:

```powershell
uv run python -m pytest cad/scripts/test_native_gtol_drawing.py cad/scripts/test_leader_clearance_drawing.py -q
```
