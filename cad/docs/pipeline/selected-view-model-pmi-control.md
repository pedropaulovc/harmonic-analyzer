# Selected-view native PMI control

Implemented and native-tested; **selected-view GTol import works for this source,
but complete drawing acceptance fails**. The earlier all-view control imported real plain model datums/FCFs quickly,
with correct face attachments, but duplicated them across views and left
overlapping native positions. This is one selection-scope delta, not a rollout or
a claim that native import can already replace every drawing recipe.

`diagnostics/probe_selected_view_model_pmi.py` composes the safe owned
`probe_native_model_pmi.py` witnesses. Its all-view implementation and existing
tests remain unchanged. The unsafe historical plain-annotation scratch probe is
not used.

The new control opens only a unique exact transgear-stub bytecopy. It uses the
same configured drawing template as the old control, with the exact native path
and file hash pinned; no missing-template fallback is allowed. SolidWorks creates
the three orthographic views and chooses their scale/positions. The unique native
`*Front` orientation identifies the target; view order or sheet coordinates do
not identify it.

Before **each** import, it activates then explicitly selects the actual view name
using `SelectByID2(name, "DRAWINGVIEW", 0, 0, 0, False, 0, null, 0)`. It requires
exactly one selected object, type 12, and `IsSame(GetSelectedObject6(1,-1), view)`.
The zeros are the documented named-view selection shape, not feature picks.
It then calls precisely:

```python
InsertModelAnnotations3(0, 32, False, True, False, True)  # GTols
InsertModelAnnotations3(0, 2, False, True, False, True)   # datum, after reselection
```

The bundled method specifies that `AllViews=False` targets the selected view.
`DuplicateDims=True` concerns dimensions; it does not guarantee datum/FCF
deduplication. The control checks that separately: exactly one of each authored
semantic item, with its actual selected-view owner, source face identity and
geometry, label/XML, visibility, and non-dangling state. Returned annotation
handles must match the newly enumerated drawing instances one-to-one; other
view/template annotations must stay unchanged.

The native save/cold-reopen/PDF/PNG path retains all source and layout checks.
Source PMI and observed feature-dimension values/tolerances/BASIC/presentation
must remain unchanged, with same-session native identities checked; the copy may
not be saved. This observed dimension inventory is not a full BREP immutability
claim. Originals, template, helper files, actual imported adapter and copy bytes
receive final guards on failure too. Shared ownership closes only exact owned
documents and preserves the existing session. Primary, cleanup and final-guard
errors are retained together.

Missing coverage can still produce diagnostic images, but machine status remains
failed. Cold layout changes remain failures. No manual annotation positioning,
arrangement, reconstruction, second candidate, automatic retry or source-PMI edit
is included. `visual_review` stays pending even if all machine witnesses pass;
native position/visibility alone does not prove readable, non-overlapping ink.

After source review and a separate native-seat grant, set `HARMONIC_SW_AUTOSTART=0`,
`HARMONIC_REMOTE_CACHE_MODE=off`, and `HARMONIC_DIAGNOSTIC_SW_PID` to the approved
current PID. Run in the frozen checkout's venv:

```powershell
uv run python cad/scripts/diagnostics/probe_selected_view_model_pmi.py C:/src/harmonic-analyzer/cad/out/sldprt/transgear-stub.SLDPRT --expected-pid <approved-PID>
```

The parent pins source SHA before acquiring the existing machine-global seat;
the attach-only worker rejects a changed source or native PID. Receipts and
initial/cold diagnostic exports live under a unique `selected-view-pmi-*` report
directory. Untested until that invocation: selected-view coverage, native layout,
and persistence for this source/template/selection shape. Other views, source
annotation views and placement policies remain separate experiments.

API references read: `IDrawingDoc.InsertModelAnnotations3`,
`IModelDocExtension.SelectByID2`, `ISelectionMgr.GetSelectedObject6`,
`GetSelectedObjectType3`, `GetSelectedObjectCount2`, `IView.GetName2`,
`GetOrientationName`, `ReferencedConfiguration`, and `Create3rdAngleViews2`;
the bundled Get Annotations Arrays and named drawing-view selection examples.

## First native attempt: diagnostic creation-scope defect

At root `e6484849`, adapter `e77bfda4`, PID 31860, the first native attempt
stopped before either import. `Create3rdAngleViews2` renamed the unsaved drawing
after its source, outside the probe's creation scope. The exact ownership guard
rejected the unrecorded title and refused cleanup; this is not an import failure.
The probe now includes native view creation in that scope. The scope still
requires the same native document handle, kind and declared output path.
Lifecycle tests reproduce the title change on success and on native rejection.

Receipt: `cad/out/reports/selected-view-pmi-rf8wvvaq/observations.json`, SHA-256
`ddd94abf10cd05bc5437598bcec9e97991f276d58e7ebfbb5c1edb956b831fe4`.
Original part, configured template and copied part hashes were unchanged.
The two diagnostic documents were subsequently closed without saving after
checking the exact recorded empty baseline, full current inventory, three view
references to that exact copied part, native identity and hashes. No global close
or recovery restart was used. The recovery command and output are retained in
`cad/out/logs/selected-view-pmi-rf8wvvaq-recovery.log`; final native inventory was
empty and all three hashes remained unchanged. The old all-view control is
unchanged; historical import evidence does not prove its current lifecycle.

## Scope-corrected native result

At root `a0d156b9`, adapter `e77bfda4`, PID 31860, exact selection succeeded
before each import: count 1, type 12, and native view identity 1.

| Import | Returned | Native call time |
| --- | ---: | ---: |
| GTols into Front | 2 | 0.026473200 s |
| Datum into Front | 0 | 0.004490300 s |

The two returned GTols bijectively matched the new view annotation inventory.
Both had the intended source-face identity, typed frame content, correct native
view owner and no dangling attachment. They were not duplicated into other
views. Datum A was missing, so coverage already failed. The retained initial
PNG was inspected: the two frames overlap each other on the part. Fast insertion
is not readable manufacturing output.

The initial native save/PDF export also introduced a type-13 center mark,
`Drawing View2/DetailItem1`, absent from the before-save inventory. The unchanged
full-annotation inventory gate stopped there. Cold reopen was not reached, and
the added center mark has not been exempted from preservation checks.

Receipt: `cad/out/reports/selected-view-pmi-4jskgzkm/observations.json`, SHA-256
`55db6b3f8cf4f6b8ed144cf300cc154027e312d5da9158ee2345b6c623d55b0a`.
Total diagnostic time was 29.554629 s, not a production recipe timing. Original,
copied-part, configured-template, helper and actual-adapter guards passed.
Cleanup closed only the owned drawing/copy and restored the empty baseline.

This rejects this exact Front-only, unchanged-position candidate as a complete
replacement. Datum import into another native orientation, source annotation
view choices, and native arrangement are untested deltas, not unavailable APIs.
The coordinate-removal work can independently use existing exact model entities
while preserving the shared typed PMI content.

## Explicit orthographic orientation control

`--orientation '*Right'` now changes only the selected native orientation; the
default remains `*Front`. Each invocation uses a fresh source bytecopy and makes
the same two imports exactly once. `*Top` is also selectable. The requested
orientation must match the source's `GetStandardViewRotation` and the drawing
view's `ModelToViewTransform` rotation. The named Front view must first match
the source Front matrix as a positive control of the coordinate convention.
Neither view order nor position substitutes for identity. All original coverage,
source/native identity, layout, export and cleanup checks remain unchanged.

This tests whether the missing Front datum is view-dependent, using the earlier
all-view datum import as the positive control. There is no annotation repositioning
or center-mark exemption, so existing frame overlap or export inventory changes
can still reject the candidate even if datum import succeeds.

The first Right attempt at `43247c6f` stopped before import because its selector
incorrectly expected `GetOrientationName` to name the two projected views.
Both returned an empty string, exactly as that method's bundled documentation
specifies. Receipt `selected-view-pmi-nuwwyl5k/observations.json`, SHA-256
`266ad1767fb46b532e3a52a3685cd94652586e62caf846a2abec2df8b7b9a01b`,
records the 15.013326 s attempt, unchanged source/runtime guards and clean
empty-to-empty cleanup. Rotation matching corrects the diagnostic, not the
model-PMI importer. Rotation arrays must be finite, orthonormal and uniquely
matched within 1e-9; projected views need no invented name.

### Right-view import has complete PMI coverage

At `26baadce`, adapter `e77bfda4`, PID 31860, the Front matrix positive control
passed and exactly one projected view matched the source Right rotation. Both
imports selected that exact native view (count 1, type 12, `IsSame == 1`). GTol
import returned two items in 0.024126800 s; datum import returned A in
0.013330900 s. All three had the correct source face identity, typed content,
visible/non-dangling state and exact view ownership. Returned handles matched
the new inventory without duplicates; the coverage failure list was empty.

Receipt `selected-view-pmi-vx_7_s57/observations.json`, SHA-256
`91a2e336a5a1349f00c90553784c4a3223f397b8f65cd51b3d5c83caa7d7a217`,
records the 28.820601 s diagnostic. Original/template/copied-source and runtime
fingerprints passed; owned cleanup returned the empty baseline without error.
The retained PNG was inspected: datum A is readable, but both tolerance frames
have the same native position and overlap. Native save/PDF export again added
`Drawing View2/DetailItem1` (center mark), stopping the unchanged full-inventory
gate before cold reopen. There is no complete-sheet acceptance or production
performance claim. Native insertion of all three items into one selected view
is now positively established for this source; their layout remains unfinished.

## One native spacing command on the complete Right bank

The successful Right coverage control at `26baadce` imported two exact GTols
and datum A in 37.4577 ms. It did not produce publishable layout: the two GTols
share the same source-model position and the same imported sheet anchor. The
first native save again added the independently gated type-13 center mark.
That inventory failure remains, and cold persistence was not proved.

The next diagnostic-only delta adds
`--orientation '*Right' --arrangement space-tightly-down` to this same owned
runner. The two import call shapes, including `UsePlacementInSketch=True`, stay
unchanged. After proving complete coverage and exact returned identities, it
selects those **three existing annotations** and runs `SpaceTightlyDown` (317)
exactly once. No Align Left, position setter, new annotation, spacing search,
retry, or production layout hook is added. The datum is a real selected member;
no synthetic annotation is inserted to meet the command's selection cardinality.

The bundled `swCommands_e` documents 317 for multi-selected annotations or
dimensions. `ISldWorks.IsCommandEnabled` and `RunCommand` provide separate
enablement/acceptance observations. Existing native GTol controls proved the
Select2(True,0) call shape and observed 317 disabled for two GTols; this control
tests one real mixed bank of two imported GTols and one imported datum.
`ISelectionMgr` must report types 13/13/36, and each returned IGtol/IDatumTag
must round-trip to the exact annotation with the exact Right-view owner.
`UsePlacementInSketch` is documented specifically for dimensions; no claim is
made that changing it would arrange these GTols.

The report retains native before/after anchors, frame/text/stroke measurements,
and pairwise body gaps. Native True alone is not success: at least one GTol
anchor must actually move and the three measured bodies must not overlap or
touch. Failed visual movement/clearance remains a failed result while diagnostic
export is retained. Exact manufacturing signatures, all annotation/owner/attached
native objects, source PMI/dimensions, view/sheet state and unselected ink remain
gated. The original save/export, copied-source hash, cold-reopen and scoped
cleanup checks are unchanged; the known new-center-mark failure is not waived.

This is a native mechanism control, not a performance comparison or approval
to replace the production drawing path. Printed readability and native command
effectiveness remain unproven until the coordinated frozen run.

### First three-annotation command result

At root `b63fc27e` / adapter `e77bfda4` / PID 31860, all three selections had
the expected types and exact annotation/view identities. Command 317 was
enabled and returned True in 1.0712462 s. The cylindricity anchor stayed fixed;
the runout anchor moved from Y=89.960000 to 82.997604 mm, and datum A moved
from Y=67.060000 to 72.475196 mm. The runout Z readback also became 2.5 mm;
sheet-space ink, not anchor motion alone, must establish the rendered result.

The diagnostic then rejected missing body measurements before export. Its
shared raw reader had called `bounds_from_snapshot` without the symbol lookup
already supplied by production `annotation_box`, so `<GTOL-CYL>` was explicitly
unmeasured. It now uses the same `IEnvironment` native definition reader on
the already-captured snapshot, with successful definitions cached only within
that capture. Unknown definitions still produce an explicit measurement failure;
there is no font-glyph guess or omitted-body acceptance. Two new regressions
failed before this correction; 230 focused tests passed afterward.

Receipt `selected-view-pmi-6eemzmc6/observations.json` has SHA-256
`80f15e532be61a416216b4653035ca8fd83187627cf4136afe6ca5f54c68ad8f`.
The 44.167799 s diagnostic ran alongside offline tests and is not a speed
comparison. Source/template/runtime guards and empty-to-empty cleanup passed.
No PDF, saved drawing or cold-reopen acceptance was produced by this attempt.

At this code checkpoint the seven offline gates were current, including 4,143
recipe tests (`pytest-telemetry/run-jatvb_dw`, 86.84 s); this remains distinct
from full native pipeline acceptance.

### Cold source-PMI position serialization boundary

Receipt `selected-view-pmi-dw50mqvy/observations.json`, SHA-256
`d1c551feb949197d0915d94aa4cbbe3df0c6f8812bf48816a229c6468ce1ef0f`,
reached native/PDF save with unchanged live source/drawing witnesses, then
rejected its cold source witness. The diagnostic took 70.760989 s, not a paired
performance measurement. Original/template/copied-source and runtime fingerprints
remained exact. Cold drawing/export acceptance was not reached.

The committed [full source snapshot fixture](evidence/selected-view-pmi-dw50mqvy-source-cold.json)
replays every source leaf: the only differences are three `pmi/*/position_m/0`
coordinates. Datum A changes from `5.832380380939283e-19` to
`5.8323803809392685e-19` m (-1.4444474582904269e-33 m, 15 component ULP).
Both FCFs change from `3.061616940311174e-19` to `3.06161694031216e-19` m
(9.860761315262648e-32 m, 2048 component ULP). All remaining position axes,
PMI names/signatures/visibility/owner/face witnesses, and source dimension,
tolerance and display inventories are exact. This is an observed-inventory
comparison, not a full source BREP equivalence proof.

Only the **cold source-PMI position vectors** now use the existing 16-ULP and
1e-14 m caps with ULP measured at the largest absolute component of the before
and after XYZ vectors. Both bounds must hold. The resulting per-axis budgets
are 2.7755575615628914e-17 m for the datum and 5.551115123125783e-17 m for
each FCF. Raw coordinates, deltas and budgets remain in the receipt; no value
is rounded or overwritten. Types, keys, inventory order/multiplicity, content,
identity and geometry fields remain exact; nonfinite values reject. Source
dimension/geometry/hash gates and the drawing comparator are unchanged.

After cold reopen, the fresh source snapshot and dimension handles become the
baseline for the existing post-PDF-export read. That comparison is exact
same-session again, including native handle identity. There are no additional
COM reads or new native calls. The retained three tiny deltas pass the pure
cold replay and fail the live replay; tests also reject either bound exceeded,
source/content/type mutations and post-reopened-export drift. Native acceptance
of this correction is pending a separately granted run.

```powershell
uv run python -m pytest cad/scripts/test_source_pmi_comparison_drawing.py cad/scripts/test_selected_view_model_pmi_drawing.py cad/scripts/test_reopen_annotation_comparison_drawing.py -q
```

## Standalone Space Evenly Down alternative

The symbol-measurement-corrected 317 trial retained an initial drawing, PDF and
PNG, but did not pass. Receipt `selected-view-pmi-dw50mqvy/observations.json`,
SHA-256 `d1c551feb949197d0915d94aa4cbbe3df0c6f8812bf48816a229c6468ce1ef0f`,
records exact three-item selection, command enabled/returned True in 1.0760444 s,
and FCF pair clearance **-0.0376042155 mm**. The inspected initial PNG also has
the frames over the shaft's model lines. A separate source-PMI comparison error
stopped cold acceptance. Neither the body intersection nor the source error is
waived by this next variant.

The same runner now accepts a mutually exclusive option:

```powershell
# Same frozen checkout, guarded source, verified PID and coordinated seat as above.
uv run python cad/scripts/diagnostics/probe_selected_view_model_pmi.py C:/src/harmonic-analyzer/cad/out/sldprt/transgear-stub.SLDPRT --expected-pid <approved-PID> --orientation '*Right' --arrangement space-evenly-down
```

This chooses `swCommands_SpaceEvenlyDown` (313) **instead of** 317. It starts from
fresh imports, selects the same two real GTols and datum A, tests enablement,
and makes exactly one command call. It never runs 317 first, retries, sets a
position, edits a source, or changes either import's arguments. Omitting
`--arrangement` still performs no spacing command; `space-tightly-down` retains
the original standalone 317 control.

The bundled [swCommands_e reference](https://help.solidworks.com/2026/english/api/swcommands/SolidWorks.Interop.swcommands~SolidWorks.Interop.swcommands.swCommands_e.html)
explicitly lists 313 for multiple selected annotations or dimensions. It does
not guarantee clear text, a particular pitch, or separation from model ink.
This is one testable native alternative, not a claim that it repairs the sheet.

Acceptance is unchanged: exact selected types/identities/owners, complete
manufacturing/source/attachment witnesses, unchanged unselected ink and views,
actual GTol motion, positive pairwise body gaps, and all native save/export/cold
and ownership/hash guards. Native True cannot pass a no-op, touching frames or
changed semantics. Printed readability remains a separate required inspection;
the receipt keeps `visual_review=pending`. The 313 option has offline coverage
only until a separately authorized frozen native run.

### 313 native result: machine checks passed, visual acceptance failed

At `db33e21f` / adapter `e77bfda4` / PID31860, command 313 was enabled and
returned True in 1.069610 s on the exact imported types13/13/36 bank. All machine,
manufacturing, source, attachment, save/export and cold-reopen checks passed;
the FCF pair's measured gap was **2.7344607728 mm**. The diagnostic took
83.2161434 s, not a production recipe timing or speed comparison.

Receipt `selected-view-pmi-cekzu9_u/observations.json`, SHA-256
`717f72bf504c857eaae2b59c5204632a5e6fe5a8033d7837efffeec6455476bf`,
retains `status=passed` for those machine checks and `visual_review=pending`.
Its raw receipt remains unchanged. Independent inspection of `initial.png`
rejects the layout: the two FCFs no longer overlap each other, but shaft edges
still cross their frames/text. **This is not a publishable or accepted production
drawing.** Pairwise body separation is not model-ink separation; the separate
visual gate remains necessary.

## Standalone Auto Arrange alternative on actual imported PMI

The next option is `--orientation '*Right' --arrangement auto-arrange`.
It uses `swCommands_AutoArrangeDimension` (2976) **instead of either 313 or 317**
on a fresh two-GTol/one-datum imported bank. There is exactly one native command,
with no earlier spacing command, coordinate setter, retry or fallback. The
default no-command path and both standalone spacing controls remain available.

The bundled `swCommands_e` explicitly lists 2976 as valid for multiple selected
annotations **or** dimensions. The older `probe_gtol_commands.py` enumerates
view-owned kind 5 GTol-only banks, so its result does not establish behavior for
this exact real mixed imported bank. The retained root selected-view receipts
contain commands 317 and 313 but no 2976 attempt before this option.

The documented [IsCommandEnabled](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~IsCommandEnabled.html)
receives the command ID and reports current enablement; it does not promise
that every annotation combination enables the command. The existing control
checks it once **after** exact view activation and selected types/identities.
False records that this context is disabled and stops before any command; it
does not trigger a fallback or prove that the API is unavailable generally.
[RunCommand](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~RunCommand.html)
receives `(2976, "")`; True reports execution, not useful layout. All actual
movement, pairwise body clearance, semantic/source/attachment, unselected-ink,
save/cold/export, hash and ownership checks remain unchanged. Model-ink conflicts
still require the visual inspection above. This variant adds no measurements or
acceptance exemptions and is native-untested until a coordinated frozen run.

### 2976 result: disabled for the exact mixed imported selection

Frozen root `035b5b0d` / adapter `e77bfda4` / existing PID 31860 ran the
standalone Auto Arrange variant. Receipt
`selected-view-pmi-31ypm276/observations.json` has SHA-256
`53a84978bca78554afa60b4a75f56b9912a63f0445339d61354c35b7c5e58dbd`.
The exact imported selection contained GTol/GTol/datum native selection types
13/13/36, each with `IsSame == 1` and the expected annotation owner. Native
`IsCommandEnabled(2976)` returned False; the control stopped before RunCommand,
so it proves no arrangement, saved-layout or cold-layout result.

The failed receipt is retained as a failed observation. Source/input/helper and
adapter guards stayed exact; cleanup restored the empty baseline without error.
This is a rejection of this mixed bank after ActivateView and Select2, not a
general API limitation. A different selected subset, Select3 with explicit
drawing-view selection data, and other native document contexts remain untested
by this receipt. No production behavior or acceptance gate changed in response.
