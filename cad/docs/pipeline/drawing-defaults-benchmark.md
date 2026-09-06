# Drawing defaults: experiment scope

These are experiments, not established speedups. The source drawing template,
source CAD, and manufacturing requirements remain unchanged during controls.

The ten-checkout telemetry audit in
`cad/out/reports/performance-audit-20260905/summary.json` contains 593
`drawing.new_from_template` spans: 2,116.929 seconds total, or 3.570 seconds per
call. Its `drawing.normalize_edge_break` child accounts for 1,053.965 seconds,
or 1.777 seconds per call. These historical timings bound the setup opportunity;
they do not explain the much larger native annotation-layout cost.

| Experiment | Change under test | Required comparison |
|---|---|---|
| Prepared template | Store the existing metric edge-break note, units, precision and dimension leader styles in a derived DRWDOT; omit repeat setters and blank-sheet rebuilds | Same recipe, source part and final precision quality; setup and full-recipe ABBA timings; native/PDF/PNG and saved-reopen witnesses |
| Annotation defaults | Give geometric tolerances and surface finishes their own document-level bent-leader lengths while retaining the datum policy | Actual leader geometry, attachment identity and manufacturing semantics; verify unrelated annotations do not change |
| View quality | Evaluate draft geometry/cosmetic-thread quality separately from template preparation | Verify actual quality readback, model attachments, curves and thread linework; account for any final precision conversion before comparing total time |
| Native view placement | Let SolidWorks choose initial standard-view locations/scale, then validate the resulting print | Preserve required views, model orientation, dimension values, projection convention, legibility and final clearance; no coordinate-based entity picking |

One-time template preparation is reported separately and included in cold totals.
A prepared template must be keyed by its original template bytes, preparation
recipe, units/precision and scale. It is not a replacement for validating a new
template or for final native drawing checks.

Sheet size and scale are currently constrained by `assert_asme_b_sheet` and each
recipe's sheet/view scales. A size experiment must explicitly parameterize those
contracts; disabling the final assertion would not test a coherent new layout.

`IDrawingDoc.AutomaticViewUpdate` concerns changes to the underlying model. It
is not documented as an annotation-layout batching switch. Likewise,
`ISketchManager.AddToDB` is a sketch-entity optimization, not a general promise
to accelerate dimensions, datums or geometric tolerances. Neither mechanism is
credited with a speedup without a matched native control.

The local SolidWorks API bundle provides the relevant references:
`IDrawingDoc/Create3rdAngleViews2`, `ISheet/SetScale`, `IView/SetDisplayMode4`,
and Document Properties > Annotations > Geometric Tolerances / Surface Finishes.
The latter expose separate type-level leader-length settings, which avoid
assuming that one shared annotation length is appropriate for every symbol.

## Native leader update control

`diagnostics/probe_gtol_leader_override.py` changes one existing tolerance
annotation on a uniquely copied rocker drawing. The shared datum leader setting
stays at 73.30296548 mm; the requested individual tolerance leader is 6.35 mm.

The immediate-read variant at `9eef747b` accepted the setter, but its first
`GetLeaderPointsAtIndex` still returned the old geometry. Later display-data
measurement and the saved/reopened drawing already showed the correct short
leader. Its strict pre-export assertion failed; this is an update-order result,
not evidence that the setter is unavailable.

At `108fe65a`, one checked `EditRebuild3` before measurement made the exact 6.35 mm
leader visible both before export and after reopening. The annotation body,
frame join, model endpoint, view contexts and source hashes were unchanged.
All 60 annotation semantic records, eight supported geometry attachments and
four dimensions/tolerance types passed; no dimension was excluded. The control
preserved the two existing visible documents, including an unsaved drawing, and
closed only its own copy.

The report is
`C:/src/ha-perf-channel/cad/out/reports/gtol-leader-override-fd4f_eux/gtol-leader-override.json`.
This establishes one annotation override and its update boundary, not a
type-level default, a completed lever drawing, or an end-to-end speedup.

## Trial isolation

All native trials require the machine-global seat, an explicitly identified
running SolidWorks session, owned outputs, and diagnostic-only attachment.
They must not use the production build wrapper's document clearing or automatic
restart behavior. Timing observations from one ABBA block are not a fleet failure
rate estimate and cannot establish the requested less-than-five-percent risk.
