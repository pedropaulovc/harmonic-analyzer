# Selected-view native PMI control

Implemented and offline-tested; **no native invocation or drawing acceptance
yet**. The earlier all-view control imported real plain model datums/FCFs quickly,
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
