# Build performance and drawing attachment contracts

The September 2026 telemetry audit identified two recurring costs: channel pose
correction repeatedly resolves the same components and transforms, and drawing
recipes repeatedly locate geometry through sheet coordinates or whole-view scans.

The audit read 69,252 spans and 126,342 log records from ten checkouts. In nine
successful channel builds without presentation-pose configurations, pose
correction consumed 353 to 468 seconds, or 66 to 73 percent of the build body.
Nine of eleven failed drawing attempts concerned geometry selection or attachment.
These histories span changing code and do not estimate production failure rates.

## Channel construction

Component handles and target transforms are prepared once within the stable
post-copy document phase. Cached handles must not survive document replacement or
topology changes. The conservative experiment preserved the original solver
sequence; a second experiment changes that sequence explicitly: reset only the
current four-component copy, retain its three construction drivers while posing
the remaining copies, then remove the complete driver bank in one native call.

The deletion manifest must contain exactly three unique, newly created distance
mates per copy. Resolve and type-check the entire manifest before mutation,
select only those features, delete without absorbed/child-feature flags, and
verify every target disappeared. The closing pose, mate-count, solver status,
operational-DOF, interference and saved-rebuild checks remain in place.

Validation compares the resulting component poses, mate health, operational DOF
and saved/reopened assembly with the reference construction. Aggregate telemetry
must distinguish preparation, resetting poses and authoring drivers, and record
the operation counts without emitting a span for every component.

Changing the solver sequence requires a separate live experiment. Fewer COM calls
are useful evidence; a single faster wall-clock run is insufficient because seat
load and SolidWorks state vary.

### Measured channel experiments

These are individual full, uncached builds on the same seat and built inputs on
2026-09-06 UTC, not a statistical speedup or failure-rate estimate. Task time
excludes seat waiting (zero for these attempts) and cache transfer.

| construction | task seconds | pose writes | driver-release seconds |
|---|---:|---:|---:|
| reference | 509.550 | 3,888 | included in each pose operation |
| prepared handles, original sequence | 320.197 | 3,888 | included in each pose operation |
| retained drivers, individual deletion | 334.959 | 216 | 76.516 |
| retained drivers, one batch deletion | 247.125 | 216 | 2.695 |
| repeated batch-deletion build | 264.880 | 216 | 3.032 |

The last deletion spent 1.143 seconds inside `DeleteSelection2(0)`; the remaining
1.552 seconds covers manifest resolution, selection and readback. The repeated
build spent 1.364 seconds inside the native deletion. All five builds
passed their construction gates. Reference and prepared-handle DOF manifests are
byte-identical. The individual-deletion experiment preserves all manifest keys,
component identities and state, with a maximum numeric difference of
1.055e-9 mm. The batch-deletion manifest likewise preserves identities and state,
with a maximum numeric difference of 1.050e-9 mm. The two batch-deletion DOF
manifests are byte-identical (SHA-256
`e5c09e65398839546c7147cc1b14724bc5b83fa4bdf7f8f2748fe86642338854`).
All five builds have the same rounded mass-properties/pose
fingerprint; that fingerprint is not raw CAD-byte equality or a substitute for
independent saved-model verification.

The corresponding task trace IDs, in table order, are
`0x7f0525b4ba7b594486d3f433c3fad1c3`,
`0x2e09f191b7027c43f04c5d9d4d2ab893`,
`0x1adeed12c9431a9fbbbb1dffc73ba773`,
`0xe96bc142669b5cd06495cf34a62b3d18`, and
`0x25ee7f00d62a807b1e6442cb045c66cf` in
`cad/out/reports/telemetry/traces.jsonl`. Logs and preserved native artifacts for
the experiment are under `cad/out/reports/performance-audit-20260905/`.

### Scheduler startup

A `doit list` profile found repeated parsing and walking of identical helper
source in config-dependency discovery. The bounded syntax cache keys immutable
references by source text and config-module names, not modification time or
checkout path. Accessor and family mappings are still resolved afresh; unknown
config uses retain the conservative dependency behavior.

Generating all 208 part, assembly and drawing task definitions took 15.645 seconds
before the change, then 6.848 and 6.027 seconds after it. The complete dependency,
task-edge and target snapshots were byte-identical (SHA-256
`24a2050d818acb6ee345fe3251fb839950b899bea45b5122b939a57653e1d904`).
These are local startup observations, not elapsed full-build measurements.

### Drawing dependency scope

`_drawing_project_layout.py` is imported directly by the seven semantic pilots,
not through `_drawing_common.py`. An exact closure comparison over all 92 drawing
recipes found that the other 85 drop only the five native layout, GTol, bounds,
packing and measurement-handoff helpers. The seven pilots retain every previous
dependency and add the new wrapper. No runtime behavior changed. Regression tests
pin both directions, so an edit to experimental layout code no longer invalidates
the unmigrated fleet through an unused shared-helper import.

## Drawing attachments

Model geometry owns attachment identity. Let SolidWorks choose annotation layout
where its native API supports it; fixed sheet coordinates are not a manufacturing
requirement. A drawing must not identify a bore, datum, controlled surface or
dimension endpoint by selecting the first nearby edge. Converting an already
identified entity's location into drawing coordinates is distinct from using
coordinates to discover that entity.

Entity resolution must specify the required geometric role, validate its model
context, and reject missing or ambiguous results. Resolve all requested entities
in one traversal while the view and model are stable. Discard live entity caches
after rebuilds, configuration changes or visibility changes. Persistent references
must travel with the exact model artifact to which they belong.

The opt-in `diagnostics/probe_drawing_attachments.py` changes view positions and
scales on a uniquely named drawing copy, rebuilds the drawing, and saves/reopens
that copy. It compares supported attachment geometry signatures and reports every
excluded annotation kind explicitly. It does not prove persistent-ID equality or
behavior after a source-part topology change. Changed source parts must also be
rebuilt and their drawing recipes rerun. Check annotation values and visual
placement: successful API calls alone do not make a sheet usable for machining.

The seven semantic pilots passed the copy/move/scale/save/reopen experiment with
61 supported geometry-attached annotations and 48 dimension annotations checked.
No dimension was excluded from the value comparison. Unsupported geometry
annotation kinds are separately enumerated in each report; they are not counted
as proven attachments. The reports also retain qualified dimension identities,
referenced configurations and SI values. Native reference dimensions use the
documented `GetSystemValue2` call shape established by the diagnostic's positive
control; the tested `GetSystemValue3` shapes returned no value for those dimensions.
Imported model dimensions use `GetSystemValue3`.

The native dimension arrangement API has a positive control in
`probe_drawing_dimension_selection.py`: a saved screw drawing selected all seven
dimensions by their returned `GetNameForSelection()` identifiers and completed one
`AlignDimensions` call. The tested `IAnnotation.Select3` shapes rejected those
same visible dimensions; that is evidence about those call shapes, not evidence
that native arrangement is unavailable.

`diagnostics/probe_gtol_autoarrange.py` supplies a separate control for GTols:
`AlignDimensions` returned success but moved none of eight selected frames, while
the dimension-only control moved an intentionally displaced dimension back by
28.284 mm. That negative result is limited to `AlignDimensions`.
`diagnostics/probe_gtol_commands.py` then exercised native annotation commands:
Space Tightly Down (317), followed by Align Left (307), each moved six of eight
frames. Exact drawing-context attachments, frame content and saved/reopened
positions were preserved. The resulting columns still need moving outboard of
the geometry; native spacing alone is not a complete sheet-layout solution.

Treat historical API limitations as hypotheses with a recorded reproduction,
including a working control and the variants not tried. In particular, a failure
to force an imported annotation to a prescribed position does not establish that
native model-annotation import is unsuitable when layout is free to change.

Two copy-only positive controls qualify that direction:

- `diagnostics/probe_native_model_pmi.py` created native third-angle views of a
  copied transgear stub and imported model datums/FCFs in 0.182 seconds. All eight
  instances retained their specified face geometry through save/reopen. Importing
  into all views duplicated annotations, and existing coincident model-annotation
  positions produced overlapping frames. Correct attachment and fast import do
  not yet make that layout publishable.
- `probe_drawing_annotation_layout.py` traced oversized roughness symbols to the
  template's 6.35 mm surface-finish font, versus its 3.5 mm dimension font. Native
  circular attachments also chose entity-perpendicular orientation. Applying the
  actual document dimension text format and native upright orientation produced
  horizontal, correctly sized text with unchanged attachment geometry through
  save/reopen. The implementation copies the document setting, not those measured
  font sizes.

The native pilots still require a separate visual acceptance pass after callout
spacing and view layout are complete. These experiments do not establish that the
remaining coordinate-based drawing fleet has been migrated.

### Measured native layout

The seven pilots arrange dimensions natively, use native annotation alignment for
GTol banks, then pack measured decorated view footprints and linked notes. Feature
selection stays model-based; initial sheet locations are placement seeds only.
The pen v-block orthographic views now use 3:1, with the isometric still at 2:1:
the measured 4:1 footprints could not clear both the title block and top border
while preserving the specified projection relationships. No text or dimension
content was reduced to make that fit.

Live controls distinguish native API behavior from implementation mistakes:

- A bare Python tuple assigned to `IView.Position` did not reach the requested
  position. Typed `VT_R8` arrays through `SetViewPosition` reached it exactly.
  `probe_drawing_annotation_performance.py` records both call shapes.
- The lever's all-around circle follows the native leader elbow when alignment
  switches leader sides. Its frame lines and text translate rigidly; the circle
  belongs to the full decorated envelope, not the rigid frame body. The copied
  drawing control is `diagnostics/probe_gtol_rigid_body.py`.
- The marker's view-owned centerline exposes one unsupported attachment slot
  (`type=0`, null entity), while its specific interface, owning view and measured
  strokes survive native movement and rebuild. Those witnesses are checked;
  underlying model-entity identity is explicitly not claimed for that slot.
- Native note extents can change after an exact anchor move. The pedestal's
  measured extent shifted about 0.010 mm in X; the rocker's changed by 0.143 mm in
  Y. Detailed failures are retained under `cad/out/reports/native-layout/`, with
  before, predicted and observed footprints and actual clearance deficits.

The project reserves an additional 0.5 mm during packing, including a planning
inset at the sheet borders. Final acceptance still uses the original borders and
2 mm clearance. This allowance is a chosen planning margin, not a guaranteed
bound on future native extent changes. At `958f2fb5`, pedestal and rocker both
passed the resulting live readback checks. No failed-layout retry loop or relaxed
acceptance tolerance was introduced.

These layout checks have a cost. At `5d863bb9`, the pedestal's measured-layout
phase took 30.474 seconds, versus 42.061 seconds before reducing repeated GTol
witnesses. That is layout time, not an end-to-end drawing speedup. The successful
lever, pen v-block and marker build bodies took 40.498, 36.595 and 16.274 seconds
in the same five-pilot run; pedestal and rocker failed their final fit checks and
did not publish new drawing outputs. The gear's earlier recipe-only speedup must
not be presented as including this added measurement work.

The first live transaction-local handoff at `465835d0` reused 21 measured
annotations for initial packing, freshly measured five others, and retained a
fresh complete final readback. Initial packing measurement took 4.487 seconds;
the final readback took 7.260 seconds. The build body took 44.695 seconds, versus
50.376 seconds in the preceding successful non-handoff pilot. These are successive
observations under changing seat load, not a controlled net-speedup estimate.
The handoff cannot survive the transaction or supply the final measurement.

Datum and surface-finish placement now precedes GTol columns. Candidates come
from measured view and annotation bodies; native `SetPosition2` readback decides
where a symbol actually moved. Final attachment, content and body checks still
run, followed by whole-sheet packing. The first integrated marker run at
`116f2395` passed and moved the datum/finish text out of the part silhouette.
Gear and rocker stopped before export because their datum could not return to
its insertion position after a clamped trial. Removing intermediate restores
allowed all four absolute candidates to run; neither drawing cleared the measured
view/annotation bodies. Eight copied datum controls also produced identical XY
and PNG output with returned Z versus sheet Z=0. Neither a restore nor Z=0 is a
solution to the observed clamping. Dimension-selected insertion remains under
test: the shapes tried so far inserted a visible but unattached tag. An existing
edge-attached gear datum refused `Shoulder=False` and reported `ForcedShoulder`.

Save/reopen controls exposed a separate specification bug: drawing-only BASIC
edits on four imported lever dimensions disappeared when the source refreshed.
`diagnostics/probe_source_basic_dimensions.py` authored BASIC on a unique copy of
the source part, saved/reopened it, and relinked a copied drawing. All four BASIC
boxes persisted, all eleven dimension values and supported attachment geometry
were unchanged, and both original hashes matched. Ten imported dimensions across
the lever, pedestal and pen v-block now declare BASIC in their source recipes;
drawings check it read-only. Drawing-created reference dimensions remain local.
The shared copy probe now checks tolerance type as well as value, including after
save/reopen. All three source builders completed at `8cc55ebd`. Pedestal and pen
v-block drawings also completed and their renders show the required BASIC boxes;
lever passed its read-only BASIC checks but stopped at datum placement. The
final-head copy/move/scale/save/reopen fleet check remains outstanding.

Readback of the screw's old saved
native feature found diameter zero and no stored standard or size, contradicting
the builder's comment that the standard table supplies the diameter. Empty
annotation display data therefore cannot establish that a correctly defined
thread has no drawing ink. A suppression/restoration control also created a new
thread-callout note on restoration, so its unequal A/A output is not a valid
no-ink witness. `probe_drawing_thread_view.py` retains both controls.

The corrected definition explicitly supplies ANSI Inch/Machine Threads, size
`#10-24`, and its 3.56616 mm minor diameter. Native creation and exact definition
readback after the production part's disk reopen passed at `8cc55ebd`. A copied
definition control exposed native lines, an arc and isometric polylines through
`IAnnotation.GetDisplayData`; matching PDF paths confirm projected sheet XY and
0.18 mm line width. All four native thread annotations reported empty layer and
Width=0. Bounds now use actual annotation widths 0–7 and fail on unverified
layer/custom overrides; the former document-custom unit test did not establish
those annotation behaviors. No projected face-box substitute or omitted thread
ink is accepted.

This does not change the simplified 3.797 mm male solid diameter. Its missing
4.826 mm nominal major outline is a separate modeling/fit-policy limitation; a
correct minor-diameter cosmetic thread cannot restore that outline.

The screw drawing subsequently exposed a datum-with-below-text case: its native
frame switches sides by translating the upright frame/text body by the measured
frame height, not by reflecting the entire body rectangle. The correction uses
the actual closed native frame and checks both frame and complete body against
the same translation. The fresh native rerun remains required.

At `8cc55ebd`, pedestal and pen v-block integrated layout took 66.380 and 45.206
seconds respectively. These are successful layout phases, not complete drawing
times or evidence of a speedup. The new callout stage adds measurements and the
remaining internal leader/text crossing work is not complete. The bounded native
GTol reader now shares geometry parsers with full bounds and rejects unsupported
multi-jog leaders; copied native parity/timing checks are pending.

The current bounds implementation is calibrated for SolidWorks 2026 (major
revision 34) and the tested native font profile. It uses conservative GDI text
cells, actual native frame/stroke geometry and native note extents, not nominal
symbol boxes. Unsupported measurement cases fail explicitly. This is not yet a
general annotation renderer or proof that every internal leader/text collision
is absent; rendered sheets still require inspection.

## Measurement and release checks

Separate cache transfer, COM-seat waiting, process startup, construction and
verification. Correlate child spans with their task and attempt; exclude mocked
test telemetry from build statistics. Do not add inclusive parents to children or
sum overlapping workers' waits as elapsed pipeline time.

Save and PDF export need separate spans: together they consumed 87 to 116 seconds
of the top assembly drawing's 107 to 140 second task in the inspected histories.

Compare repeated A/B blocks with the same source/configuration and record the
range plus operation counts. Before merge, run the full doit graph on the proposed
head, inspect affected renders/drawing sheets, and obtain clean review of that head.
Any new strategy's retry/manual-repair rate is measured separately from geometry
correctness. Zero failures in 59 representative independent trials gives a
one-sided 95 percent binomial upper bound below five percent; repeated correlated
attempts do not establish that bound.

`diagnostics/benchmark_drawing_recipes.py` runs pinned part-drawing recipes in ABBA
order, redirects managed outputs before recipe import, and fingerprints actual
helpers, configuration, templates and source parts. Both variants use the current
helpers and built parts: it measures recipe changes, not two complete historical
pipeline versions. Each trial checkpoints its result and writes distinct native,
PDF and PNG artifacts for inspection.

The paired recipe comparison at `cea71c16` produced these build-body times, before
the measured-layout integration:

| drawing | original recipe, seconds | semantic recipe, seconds |
|---|---:|---:|
| arbor pedestal | 16.838, 20.281 | 17.808, 23.166 |
| cone gear | 27.530, 26.300 | 8.967, 9.331 |

The gear's feature-owned lookup removed its expensive whole-model traversal.
The pedestal did not become faster in this small sample; its semantic changes
target attachment reliability. All eight trials passed and used identical
source-part hashes. Report:
`cad/out/reports/drawing-benchmarks/abba-u1vy0qah/measurements.json`.
The historical screw recipe could not load against the current helper API
because it supplies the removed `side_centerline_face_xy` field. That failed
attempt is not a performance result. Comparing that version requires isolating
its historical helper closure, not adding coordinate-picking compatibility back.

## Further aggressive changes, in priority order

1. **Separate assembly helper dependencies by actual consumer.** The historical
   assembly cache had 18 hits and 149 misses. Among 102 observed miss-key
   transitions, `_assembly.py` changed in 39; only one was an identity-only
   transition. Splitting construction, pose and verification helpers into modules
   imported directly by their consumers can stop a narrow edit invalidating every
   assembly. Keep dependency-closure tests; re-exporting all modules through the
   old umbrella would preserve the same invalidation problem. These counts do not
   predict the hit rate after a split.
2. **Author manufacturing annotations once, import into chosen native views.**
   The model-PMI positive control establishes fast, attached import, but not a
   finished layout. Next test selected-view import without the all-views
   duplication, then one representative drawing per geometry family. Preserve
   annotation coverage and values through source-part rebuild, scale changes and
   save/reopen before migrating that family's recipes. Current semantic pilots
   are not evidence that every remaining coordinate-based recipe is migrated.
3. **Restore coherent assembly-and-child cache bundles.** This could make a cache
   hit carry the exact referenced child identities instead of requiring the
   checkout to have them already. Validate the complete manifest before atomic
   publication/restore, detect conflicting active inputs, and fall back to the
   ordinary build on a mismatch. The observed identity-only misses were rare, so
   measure additional benefit after reducing broad recipe invalidation. Do not
   remove existing exact-identity tokens on a geometric-similarity assumption.
4. **Experiment with isolated SolidWorks workers.** Independent OS sessions/VMs,
   output roots and explicit process-bound connections can parallelize cold work.
   The existing shared desktop singleton and machine-global seat lock are not
   that isolation mechanism. Keep the lock for the present architecture; a worker
   experiment must positively prove document ownership, instance routing, recovery
   and cache coherence before concurrent production builds are enabled.

No measured conflict rate below five percent is claimed for these proposals.
Use bounded pilots with telemetry for retries, stale references and manual
repairs, then the independent-trial criterion above before making that claim.
