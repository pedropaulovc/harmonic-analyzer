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

The subsequent `--length-scope gtol_default --update-boundary edit_rebuild`
control at `4a28d4e0` used only the two GTol-family document settings. It also
passed: the actual 6.35 mm leader, unchanged 73.30296548 mm global datum setting,
annotation semantics and source hashes persisted through reopening. Its
`BentLeaderLength` getter remained -1, as expected for a document-driven length.
The settings/readback phase took 0.094 seconds and the rebuild 0.164 seconds;
the full evidence run took 100.864 seconds, including repeated inventories and
three exports. Those are diagnostic costs, not a full-recipe speed comparison.
Report: `gtol-leader-override-y228ca9f/gtol-leader-override.json` in the same
worktree's reports directory. The output pixels match the individual-override
control. Surface-finish defaults are not covered by this result.

The live toggle setter returned true while its explicit getter read false,
contrary to the bundled method page's resulting-state return description. The
control records both and checks the getter; it does not infer the setting from
the setter's Boolean alone.

The independent surface-finish control at `55f14f9d` also passed. Only the
view-owned Ra 1.6 leader changed: its anchor-to-elbow length became 6.35 mm,
while its measured 1.75 mm symbol-side extension remained unchanged. Symbol
body, model endpoint, attachments, dimension values/tolerances, and the other
59 annotation records were preserved through save/reopen. The global datum
and GTol-family settings, including the sheet-format symbols, were unchanged.
Settings/readback took 0.102 seconds and one checked rebuild 0.162 seconds;
the complete diagnostic took 96.394 seconds. Report:
`gtol-leader-override-f4ty_f46/gtol-leader-override.json`. Root visual inspection
found the shortened leader readable; the after/reopened PNGs are identical.

The preceding SF attempt stopped before mutation because its diagnostic assumed
a non-JIS symbol. The recipe actually pins native type 1. The corrected control
preserves that exact existing type and omits only a getter documented as
inapplicable to it; no production symbol-style change is part of this experiment.
Both independent-family mechanisms are now proven on this copied rocker, but
their combined production policy and the fresh lever drawing remain untested.

## Prepared-template progress

The first preparation stopped before saving because its MMGS-preset assertion
did not match the existing helper's actual Custom/mm state. A two-blank-drawing
control traced the exact cause: selecting MMGS returns preset 5, then explicitly
setting linear units to millimetres changes the preset to Custom 4. The unchanged
helper produces the same final values. The benchmark now preserves those exact
values, with the complete repro in `diagnostics/probe_drawing_unit_defaults.py`.

The next preparation passed its default-setting witness but produced no DRWDOT
despite `IModelDocExtension.SaveAs3` returning `(True, 0, 0)`. The owned-output
guard rejected it before any recipe trial. This is a failed save call shape,
not proof that template saving is unavailable. The subsequent four-cell control
at `282bb9e7` saved and reopened both SLDDRW and DRWDOT with the existing
`IModelDoc2.SaveAs3(path, 0, 0)` call. The tested advanced/silent call produced
neither format despite its success tuple; other option combinations remain
untested. Preparation now uses the proven existing call and retains fresh-file,
exact-path and full inherited-default checks. See
`diagnostics/template_defaults.md` for provenance.

At `bc63e4d7`, preparation and native inheritance passed in 34.062 seconds,
including save, additional comparison witnesses and cleanup. Ten empty linked
notes had different cached extents but independently exposed zero native text,
geometry and leaders; their link expressions, anchors and font definitions
matched exactly. All other captured defaults matched. Raw extents remain in the
report rather than being treated as displayed content.

The first unchanged arbor baseline then stopped before save/export: its source
part changed from clean to dirty in memory during drawing construction. The
source file hash stayed unchanged. The source-preservation guard refused both
the save and ordinary cleanup; scoped diagnostic recovery and a first-transition
repro are required before another trial. This is not a template-candidate
failure: no candidate ran. The failed baseline reached that guard in 97.693
seconds, with 4.627 seconds in setup. Neither is a completed drawing timing or
evidence of a template speedup. Evidence is in the isolated template worktree's
`template-abba-bn33bcg_/measurements.json` and `ownership.json`.

## Trial isolation

All native trials require the machine-global seat, an explicitly identified
running SolidWorks session, owned outputs, and diagnostic-only attachment.
They must not use the production build wrapper's document clearing or automatic
restart behavior. Timing observations from one ABBA block are not a fleet failure
rate estimate and cannot establish the requested less-than-five-percent risk.
