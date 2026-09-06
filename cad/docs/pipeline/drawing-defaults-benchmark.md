# Drawing defaults: experiment scope

These are experiments, not established end-to-end speedups. The source drawing
template, original source CAD, and manufacturing requirements remain unchanged
during controls; owned source copies can become recipe outputs as documented below.

## Current result: blank-sheet setup

The native setup-only ABBA at frozen `ba2efb5d` passed all four arms with the
existing defaults witnesses and protected-document cleanup. Current setup took
5.782 and 5.258 seconds; prepared-template setup took 1.301 and 1.335 seconds.
The means are 5.520 versus 1.318 seconds: an observed 4.202-second reduction
(76.1%) in **blank-sheet setup**, not the complete drawing build. One-time
template preparation, including save/inheritance checks and cleanup, took
36.409 seconds. The prepared template must be reused for matching specifications
to amortize that work; preparing it for every drawing would lose time.

The comparison preserves units, precision, leader styles, scale and sheet notes;
it skips repeat setters, note normalization and the two startup rebuilds. It does
not enable draft-quality views or disable automatic updates. Default witnesses
and cleanup were timed separately, and no trial drawing or source part was saved.
Both original open documents, including the dirty unsaved drawing, were preserved.

This is one exploratory ABBA block. COM-free tests ran on the same host during
measurement, so it is not an unloaded-host latency estimate, confidence interval
or evidence of a less-than-five-percent conflict rate. Receipt:
`C:/src/ha-perf-sheet-template/cad/out/reports/template-defaults/template-setup-abba-o46g8sv9/measurements.json`.
The full-recipe comparison remains unaccepted; the saved linked-title displacement
and dimensional-line/frame collision are tracked in
[`datum-policy-retained-output-audit.md`](datum-policy-retained-output-audit.md).

## Opportunity and experiment design

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
Both independent-family mechanisms are proven on this copied rocker. A later
fresh rocker recipe retained both family lengths, but failed cold-reopen layout
equivalence and has a confirmed dimensional-line/frame collision. The combined
recipe is therefore not accepted, and the fresh lever drawing remains untested;
see the retained-output audit linked above.

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
the save and ordinary cleanup. Scoped no-save recovery subsequently restored
the two original open documents, preserving all source hashes. This is not a template-candidate
failure: no candidate ran. The failed baseline reached that guard in 97.693
seconds, with 4.627 seconds in setup. Neither is a completed drawing timing or
evidence of a template speedup. Evidence is in the isolated template worktree's
`template-abba-bn33bcg_/measurements.json` and `ownership.json`.

The owned-copy first-transition control at `99eadbe7` found the part stayed clean
through template setup, three view insertions, dimension import and curation.
The `set_dimension_callouts` group then changed the source BoreDia display text
from empty to `THRU` and marked the copy dirty. All 20 observed source dimension
identities, values and tolerances were unchanged; source and copy disk hashes
matched, and cleanup preserved the original open documents. This identifies
the operation group, not an inner setter-versus-rebuild boundary or the effects
of later recipe operations. The report is
`C:/src/ha-perf-datum-functional/cad/out/reports/source-dirty-9cbdz77u/source-dirty.json`.
Subsequent drawing controls must use owned part copies; the generic protection
for borrowed originals remains unchanged. No completed full-recipe template
timing comparison is available yet; the independent blank-sheet result above
does not replace it.

At `ab264db8`, preparation passed again in 36.329 seconds. The first baseline
then completed save/export but failed the copied-part disk witness: during
finalization, that part changed from dirty to clean in memory and its file hash
changed. The original part, original template and prepared template were
unchanged. Scoped cleanup restored the exact original two-document baseline.
The 104.641-second recipe interval (5.569 seconds in setup) is a failed benchmark
trial, not an accepted comparison; no candidate or cold-reopen validation ran.
The retained native drawing, PDF, PNG and changed source copy are under
`C:/src/ha-perf-sheet-template/cad/out/reports/template-defaults/template-abba-ykoh1l_z/`.
Root inspected the baseline PNG; that eye pass does not replace the unperformed
cold-reopen checks.

Immutable original inputs remain required. Assuming that an owned source copy
also stayed byte-identical through the unchanged recipe was an additional
benchmark assumption, now disproven. The next diagnostic design gives each arm
an exact fresh starting copy and retains the resulting part as that arm's output.
It must compare source dimension identities, values, tolerances and BASIC state,
record presentation changes, and reopen both source and drawing cold. No changed
copy is reset or overwritten to hide the side effect. Pre-authoring presentation
in the part is a separate production change, not an equivalent baseline.

## Quality and update settings: separate controls

The existing HLR and HLV helpers call
`IView.SetDisplayMode4(False, mode, False, False, True)`: both geometry and
cosmetic threads are explicitly precision quality. A draft template default
would be overwritten. Sheet size/scale, view quality, and application defaults
must therefore be evaluated as separate factors.

The first proposed quality control changes only `Faceted` to true at the existing
view-local calls, leaving cosmetic threads at precision quality and retaining
all explicit rebuilds. It must check `GetFacettedHlrDisplay`, `GetCThreadQuality`,
display mode and parent-setting inheritance. For a final-precision experiment,
restore precision before measured layout and final validation, refresh the
display geometry, and include that conversion in total time. Permanent draft
output would need its own rendering and persistence acceptance.

This view-local control cannot speed up initial view creation: those views
already exist when the helpers run. The creation-time hidden/wireframe quality
setting, `swEdgeQualityWireframeHiddenViews`, is application-global, not a sheet
property; any later experiment must capture and restore it explicitly.

`IView.DisableAutoUpdate` is another per-view setting. Like the drawing-wide
`AutomaticViewUpdate` property, its name does not establish an annotation
batching benefit. First prove deferred work with a controlled source change on
an owned source/drawing pair, then measure the cost of re-enabling and updating.
`UpdateViewDisplayGeometry` updates accessible display data; do not assume it
replaces the model rebuild. These quality/update controls have not run natively.

## Trial isolation

All native trials require the machine-global seat, an explicitly identified
running SolidWorks session, owned outputs, and diagnostic-only attachment.
They must not use the production build wrapper's document clearing or automatic
restart behavior. Timing observations from one ABBA block are not a fleet failure
rate estimate and cannot establish the requested less-than-five-percent risk.
