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
