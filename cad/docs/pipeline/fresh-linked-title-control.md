# Fresh linked-title update control

Status: native baseline reproduced the printed shift; the one pre-save redraw
and one checked pre-save rebuild did not prevent it. This diagnostic does not
change production finalization. Same-value horizontal justification followed by
its documented redraw also leaves the shift. The forced-rebuild control likewise
returned success without preventing it. No ineffective update was added to production.
All five native candidate controls are recorded below. Same-expression
property-link reapplication also leaves the printed shift unchanged.
A separate measured-cell left-justified layout candidate is prepared below;
it has not run natively and does not change production finalization.

The retained rocker control proved a real printed change: cold reopening moved
all ten `rocker-arm` title glyphs right by about 7.22523 mm, while the note anchor,
extent and justification stayed unchanged. See
[the retained-output evidence](datum-policy-retained-output-audit.md).
Redrawing that already-recentered retained copy would not test prevention.

The current finalizer assigns/verifies `ISheet.CustomPropertyView`, writes/verifies
`UNIT_DISPLAY`, activates the sheet, then saves SLDDRW and PDF. It has no explicit
redraw/rebuild between those late writes and the saves. Earlier drawing setup and
layout operations already rebuild; this order is not proof of a missing-rebuild
cause, and the property-view assignment may write its existing value.

## Bounded experiment

[`probe_fresh_title_update.py`](../../scripts/diagnostics/probe_fresh_title_update.py)
creates a fresh project-template drawing and one Front view of a uniquely named,
exact rocker-part bytecopy. It deliberately omits the full recipe's imported
dimensions/callouts and drawing-summary stamping. The production finalizer runs
unchanged, including its existing sheet checks and native/PDF/PNG output path.

1. Baseline: no extra redraw or rebuild. Capture title link, resolved text,
   justification, anchor, extent and raw generic display data after blank setup,
   after view insertion, around the late property updates, and immediately before
   and after native save and PDF export.
2. Close only owned documents, cold-open that saved drawing, and export a second
   PDF without redraw, setters, rebuild or native save. Record PDF character ink
   boxes, PNG pixel differences and every native annotation leaf delta.
3. Only if this fresh baseline reproduces a rigid printed displacement of at least
   one 300-DPI pixel, with changed PNG pixels, run an independent fresh candidate.
   Select exactly one candidate: `pre_save_redraw` adds one `GraphicsRedraw2()`;
   `pre_save_edit_rebuild` adds one checked `EditRebuild3()`. Both occur before
   native save, with identical observations plus one post-operation title snapshot.
   The rebuild candidate does not also redraw or force-rebuild. A return other
   than native `True` stops before SLDDRW/PDF output.
   The fifth candidate, `pre_save_relink`, performs exactly one property assignment
   of the title's already-verified `INote.PropertyLinkedText` expression and no
   redraw or rebuild; its additional preservation guards are described below.

`unchanged`, subpixel or non-rigid baseline deltas are **inconclusive** and prevent
candidate execution. The 0.001-point rigid-residual threshold only classifies the
PDF experiment; it does not round or relax a native comparator. Candidate
`printed_stable` requires exact glyph-box equality and zero changed PNG pixels
between its first and cold-opened exports. It is not whole-sheet/native-layout
acceptance. All raw native geometry changes remain reported.

## Ownership and interpretation

The true attach-only session requires the granted machine seat, expected existing
PID, `HARMONIC_SW_AUTOSTART=0`, and remote cache off before the parent runner.
Shared ownership preserves all visible baseline documents (including the clean
lever part and dirty unsaved Draw2); hidden/unexpected/replaced documents fail.
There is no `run_build`, `CloseAllDocuments`, launch, recovery or retry in this
diagnostic. Cleanup uses the shared exact owned-copy no-save path.

Original part and project-template hashes are protected. Both independent source
copies must keep their exact original disk hashes, including through native save,
PDF export, close and cold reopen. The three named rocker source parameters,
tolerances/configuration and live native identities are checked; this does not
claim full in-memory source immutability. Drawing views must reference that
trial's exact owned source and configuration. Annotation content/attachment
semantics and view layout retain the existing comparison guards. The cold PDF
export must not change live generic annotation geometry or source parameters.

The known correct reference is cold reopening. If the minimal fresh baseline
does not reproduce, no API verdict follows: a separately reviewed full-recipe
control would be needed. Native property resolution may be influenced by the
diagnostic reads themselves; baseline reproduction is therefore mandatory.

## Reviewed call shape and execution

Official bundled references read: `ISheet.CustomPropertyView`,
`IModelDoc2.GraphicsRedraw2`, `Redraw_Graphics_Example_VB`, the standard `INote`
text/link/justification/extent getters, and `IAnnotation.GetDisplayData`.
`GraphicsRedraw2()` returns void and documents immediate display update. It is
obsolete in favor of `IModelView.GraphicsRedraw`, but this experiment deliberately
uses the existing project's documented no-argument form. No success boolean is
invented. `INote.SetTextJustification` documents a redraw requirement after text
changes; it does not prove this unchanged-justification title issue has that cause.
`IModelDoc2.EditRebuild3` and `Rebuild_Example_VB` document a no-argument boolean
operation in the active document's context. The existing observer checks that
exact active owned drawing immediately before the call. Its success return is
not evidence that the title's printed position changed; the same glyph/pixel
comparison and cold-reopen witnesses determine that result.

Only after main-agent source review and an exclusive native seat grant:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<granted-existing-PID>'
uv run --no-project --python C:/src/harmonic-analyzer/.venv/Scripts/python.exe python cad/scripts/diagnostics/probe_fresh_title_update.py --candidate pre_save_edit_rebuild --source C:/src/ha-perf-channel/cad/out/sldprt/rocker-arm.SLDPRT --guard-source C:/src/harmonic-analyzer/cad/out/sldprt/rocker-arm.SLDPRT
```

Run from the isolated frozen `ha-perf-title-update` checkout. Its source copies,
SLDDRW/PDF/PNG outputs, raw snapshots, timings, imported-adapter fingerprints and
ownership receipts live in a unique `cad/out/reports/fresh-title-*` directory.
The actual imported editable adapter is fingerprinted; an empty local submodule
directory is never reported as runtime provenance. Stop on the first failed gate.

The earlier PID 37136 is no longer a valid assumed target: the user closed
SolidWorks during a separate root pilot while this control was being prepared.
The reviewed invocation below used newly confirmed PID 31860 with an empty
document inventory. Future invocations still require a new explicit grant and
confirmed existing PID; this diagnostic must not launch/recover SolidWorks itself.

Offline verification: 42 focused tests and 160 adjacent tests passed; Ruff is
clean. Tests cover candidate gating, exact one-redraw ordering, wrapper restoration,
source-copy save rejection, wrong view references, title link/style/identity
mutations, and survival of the clean part plus dirty unsaved baseline drawing
after normal execution and baseline/candidate failures. The test is automatically
enrolled by the existing `test_*_drawing.py` recipe-gate discovery.

## Native result: redraw does not prevent this reproduced shift

One approved invocation at frozen `8d3b6c6d9a12dfc91684c31447e452a0751a7804`
finished with exit 0 and diagnostic outcome `candidate_not_stable` on
2026-09-06, 17:33:57–17:36:19 PDT. The candidate ran only because the fresh
baseline satisfied the printed-displacement and changed-pixel gate. There was
no retry or additional native operation after the invocation.
That historical revision selected redraw internally; the current CLI requires
an explicit candidate. Its original raw receipt and conclusions remain unchanged.

- Trace: `0xdd6bf5200f4839777a72b1424c036716`; task 142.160844 s.
- Report: `C:/src/ha-perf-title-update/cad/out/reports/fresh-title-_bp8u5uy/title-update.json`.
- Report SHA-256: `01f9deb35b48ce90c12402e249ebe4842e119c2cb5f42d75912c873a1f5e556e`.
- Baseline trial: 72.182456 s; candidate: 68.235653 s, including diagnostic
  measurements and cold exports. This is not a performance comparison.
- The candidate's single `GraphicsRedraw2()` took 0.003567 s.

Both trials produced exactly the same printed result: cold reopening moved all
ten title characters right by 20.48095703125 pt (7.22522650825 mm), with
0.00006103515625 pt maximum rigid-translation residual. Each first/cold PNG pair
differs in 11,232 pixels, all inside `[4183,2749,4694,2813]` on the 5100×3300
image. The baseline and candidate **first PNGs are byte-identical**, as are their
**cold PNGs**:

| render | SHA-256, same for baseline and redraw candidate |
|---|---|
| first PDF rendered PNG | `e5373867e6a2bb0f31ba0a08bc3387a2005241fc121a49a90ecb8b1e60d5557c` |
| cold-reopened PDF rendered PNG | `dfe17a7faaf8ff2c809aad9793ae2a018a66ce5ead32dff7299fa0f7de4d3f72` |

The stage observations narrow the problem:

| boundary | property source | resolved title | generic text X, metres |
|---|---|---|---:|
| blank setup | `Default` | empty | no text primitive |
| immediately after Front view | `Default` | `rocker-arm` | 0.35389179984999647 |
| explicit property link / UNIT_DISPLAY | `Drawing View1` | unchanged | unchanged |
| candidate pre-save redraw | `Drawing View1` | unchanged | unchanged |
| native save and first PDF export | `Drawing View1` | unchanged | unchanged |
| cold reopen | `Drawing View1` | unchanged | 0.3611170096970891 |
| subsequent PDF-only export | `Drawing View1` | unchanged | unchanged |

Thus the title is already resolved, with the eventually displaced origin, before
the finalizer changes `CustomPropertyView`. This rules out the need for full
recipe annotation/layout work to reproduce; it does not identify which native
update mechanism is missing. The title's anchor, native extent, horizontal
justification 2, vertical justification 0, lock state and linked text remain
unchanged after initial resolution. The only three cold-reopen snapshot changes
are the same title X origin represented in generic data, measured text runs and
native text runs. All other leaves across 47 annotation rows are identical;
the subsequent no-setter PDF export produces zero live snapshot differences.

Both original rocker paths and the template retain exact hashes. Both owned
source copies retain original SHA-256
`3bfb6da45b91e5a73b24c74baf81141899149e3c327aa943930baed3fba4d4a0`.
The three named source parameters/tolerances/configuration and their same-session
native identities pass. The one drawing view references the exact owned source
and `Default` configuration. This minimal view has no authored drawing dimensions
or checked model-geometry attachments; its two native kind-13 center-mark
exclusions are retained explicitly. Do not describe this as full manufacturing
sheet validation.

Ownership started and ended with `[]`, reports `preserved`, and has no native or
cleanup error. All owned documents were closed without a source save; the seat
was explicitly released. The two distinct PNGs were visually inspected: title
movement agrees with the glyph/pixel measurements, and the simple Front view
and other printed content do not change.

Conclusion is limited to this call shape: **one pre-native-save GraphicsRedraw2
does not prevent linked-title recentering on cold reopen**. Late `EditRebuild3`,
late `ForceRebuild3`, same-value native justification reapplication, and the modern
model-view redraw method remain untested here. No production fallback or comparator
relaxation follows from this result.

## Native result: checked EditRebuild3 also leaves the shift

One separately approved invocation at frozen
`09dcae4cd220f945f930fa40c15ccb097c205473`, with explicit candidate
`pre_save_edit_rebuild`, finished with exit 0 and `candidate_not_stable` on
2026-09-06, 17:48:44–17:50:56 PDT. The fresh baseline reproduced first; there was
no automatic retry. The existing PID was 31860, with an empty initial inventory.

- Trace: `0x5a76b8cba34db633e04e04d28fe860d8`; task 131.745262 s.
- Report: `C:/src/ha-perf-title-update/cad/out/reports/fresh-title-8zhi6y5h/title-update.json`.
- Report SHA-256: `2fc6f75d39f802c8bd4f38a53e9a163cca2b3e36e6863986b8c40a431c9b6954`.
- Baseline trial: 65.162347 s; candidate: 64.947117 s, including diagnostic
  measurements and cold exports, not a performance comparison.
- The candidate made exactly one `EditRebuild3()`, returned native `True`, and
  took 0.044046 s. It made no redraw call.

Both trials again shifted all ten title glyphs right by 7.22522650825 mm on cold
reopen, with 11,232 changed PNG pixels in the same title-only bounding rectangle.
The first and cold PNGs have respectively the same `e5373867…` and `dfe17a7f…`
hashes recorded above: baseline, redraw and rebuild all produced identical
printed states. The rebuild candidate's two distinct PNGs were visually inspected.

The post-rebuild title origin remains `0.35389179984999647` m, unchanged through
native save and first PDF export. Cold reopen changes it to
`0.3611170096970891` m. Each trial's complete cold-leaf audit again reports only
the three title-X representations listed above, maximum delta
`0.0072252098470926285` m; the subsequent PDF-only export changes zero leaves.
Anchor, extent, justification, lock/link/text and all other annotation leaves
remain unchanged. The documented successful rebuild return therefore does not
prove title-display data was refreshed.

Both original parts, the template and both owned source-copy disk hashes remain
exact. Named source dimensions, tolerances/configuration, view references and
annotation semantic/layout witnesses pass with the same limited minimal-view
scope described above. Ownership reports `[]` to `[]`, `preserved`, and no probe
or cleanup error. All owned documents were closed, and the COM seat was explicitly
released. Source remained frozen throughout the invocation; 55 focused offline
tests and Ruff had passed before it.

This is a negative result for **one pre-native-save checked EditRebuild3 in this
fresh minimal drawing**, not a general rebuild or linked-title API verdict.
Same-value justification reapplication, force rebuild and model-view redraw
remain untested here. No production or comparator change is made by this evidence.

## Next control: preserve alignment and refresh native note text

`--candidate pre_save_rejustify` uses the exact observed title handle, reads its
current horizontal justification, and reapplies that value through the void
`INote.SetTextJustification` setter. Its official documentation requires the
following `GraphicsRedraw2`; this candidate includes exactly one. Both operations
have separate snapshots inside the existing pre-native-save boundary. Link,
anchor, vertical alignment, lock and text remain governed by the original exact
checks. No positions or property expressions are assigned. The same positive
baseline gate, cold exports, full raw deltas and ownership protection remain.
Offline: 63 focused tests pass, including void return, changed alignment/link,
setter failure and restoration of diagnostic wrappers.

The native control at root `5bef3987` finished with exit 0 and
`candidate_not_stable`; session 4767 released the seat. Report:
`cad/out/reports/fresh-title-9vn4gojb/title-update.json`, SHA-256
`17653a6eed210105ce9e1a27a8bb856b1bea47c24fea49c1c31e9f2e6aab0e30`.
Both baseline and candidate retain the same 7.22522650825 mm printed shift and
11,232 changed pixels. Trial totals were 63.859078 and 63.149497 seconds, including
the full diagnostic observations; these are not speed comparisons. Candidate
counts are one justification setter, one redraw, zero rebuilds, one native save
and one PDF save. The rejustify span includes observation/checkpoint work and
must not be described as setter-only time.

The raw pre-setter, post-setter and post-redraw observations confirm exact
anchor/extent, horizontal/vertical alignment, lock and unresolved-link equality.
Originals, template and both copied parts retain their exact hashes. Ownership
starts/ends empty and reports preserved, with no probe or cleanup error. This
same-value setter result does not establish whether a different-value setter,
text-format update or forced rebuild refreshes the cached text origin.

`--candidate pre_save_force_rebuild` adds one documented
`IModelDoc2.ForceRebuild3(False)` before the native save, requires native `True`,
and makes no redraw or note setter call. Existing baseline and output comparisons
are unchanged. The ordinary/forced rebuild tests cover exact argument shapes and
False/None rejection before saving. 66 focused tests pass.

At frozen root `cd0ab7c6`, session 9540 finished with exit 0 and
`candidate_not_stable`. Report:
`cad/out/reports/fresh-title-rrt7c__6/title-update.json`. The baseline and candidate
trial totals were 60.691189 and 60.603678 seconds. Each still shifts the title
7.22522650825 mm on cold reopen, changing 11,232 pixels. The candidate recorded
one successful forced rebuild, no ordinary rebuild/redraw/note setter, and one
native/PDF save. Originals, template and copied-source hashes are unchanged;
ownership ends empty with preservation passed and no probe/cleanup error.

The remaining strict-position acceptance question is separate from native API
effectiveness. Both inspected title placements fit visibly within the title cell.
The user permits layout changes, but that alone has not been treated as permission
to relax the existing cold-position comparator. Any explicit allowance for linked
title reflow must validate both title-cell placements and preserve the stronger
manufacturing-annotation/source-identity checks; it must not become a general
annotation-displacement tolerance. That choice has been raised with the user.

## Fifth candidate: reapply the exact property link

`--candidate pre_save_relink` reads the title note's native unresolved expression,
requires the exact already-witnessed `$PRPSHEET:"SW-Title(Title)"`, and assigns
that same string once through `INote.PropertyLinkedText` immediately before
native save. It never substitutes the resolved `rocker-arm` literal, calls
`SetText`, changes justification/position, or adds redraw/rebuild. The property
documentation states get/set semantics and imposes no redraw requirement.
The bundle search found no setter-specific `PropertyLinkedText` example; the
related `Change_Note_Text_Example_VB` demonstrates `SetText`, not this property.
That documentation motivated the hypothesis; the negative native control below
tests this exact assignment rather than inferring effectiveness from the API.

Before save, readback must preserve the exact unresolved link, resolved title,
horizontal/vertical justification, lock, annotation anchor, property-view/source
context, native text content and all sixteen `ITextFormat` properties plus height
mode and document-format inheritance. Those full font checks also run against
the cold-reopened title. Glyph positions and note extent remain raw treatment
observations; changing either does not itself pass the candidate. The existing
exact first/cold PDF glyph and PNG comparisons determine printed stability,
and all original ownership, source-value, disk-hash and annotation-semantic gates
remain active. Getter/observation overhead is included in the relink span; it
is not a setter-only timing or a proof that the assignment alone caused change.

The fresh baseline must still reproduce the material rigid printed displacement
with changed pixels before the candidate can start. Counters require one link
assignment, zero extra redraw/rebuild/justification calls and one native/PDF save;
attempted counts and partial evidence survive a failed setter/readback. Tests
first failed on the missing variant and on an otherwise undetected native Bold
change, then cover exact assignment/readback, anchor/link/font failures, no
candidate on non-reproduction, and restoration of wrapped finalizer functions.

Prepared in isolated `ha-perf-title-link-refresh` from root `1acb6dfe`, with its
own locked uv environment and unchanged adapter `e77bfda4`. The implementation
commit `1b0ab300` passed 215 scoped offline tests, not the full pipeline; the
reviewed native invocation below used its integrated root revision.

### Native result: exact link reapplication also leaves the shift

At frozen root `0ee5978b885c46c494f5f5da4f264d78619ec1c5`, the approved
baseline plus `pre_save_relink` pair on PID 31860 finished with exit 0 and
`candidate_not_stable` (session 12571). Exit 0 means the diagnostic completed,
not that title stability passed. The fresh baseline reproduced before the
candidate ran; no retry or further title variant followed.

- Report: `C:/src/harmonic-analyzer/cad/out/reports/fresh-title-hgj78f5g/title-update.json`.
- Report SHA-256: `98762abb263b761d8c5426f0c8c08d0bf9a671391f413cae388b8504740fcdb4`.
- Baseline trial: 65.112050 s; candidate: 63.760221 s. These include native
  observations and cold exports and are not a performance comparison.
- Candidate counts: one same-expression link assignment, zero extra redraw,
  ordinary/forced rebuild or justification calls, and one native/PDF save.

Both trials moved all ten PDF title glyphs right by 7.22522650825 mm on cold
reopen. Each first/cold 5100×3300 PNG pair changed 11,232 pixels, confined to
`[4183,2749,4694,2813]`. The exact link, resolved text, anchor, alignment, lock,
all sixteen native font properties, height mode and format inheritance passed
the candidate's pre/post-assignment and cold-readback guards. Each full cold
snapshot changed only the same three title-X representations recorded above;
the subsequent no-setter PDF export changed zero native snapshot leaves.

Both protected original rocker paths retain SHA-256 `3bfb6da4…3fba4d4a0`,
and the project template retains `cbad80d2…980b55cc`; the full before/after hashes
are in the receipt. Both independently owned source copies retain the exact
original part hash. Existing named source-value/tolerance, view-reference and
annotation-semantic guards passed within this minimal drawing's stated scope.
The companion `ownership.json` records `[]` initially and finally, `preserved`,
and no probe or cleanup error. All owned documents closed and the native seat
was released.

Conclusion: **one pre-native-save assignment of the already-correct
PropertyLinkedText expression does not prevent this reproduced cold title
reflow**. This is not a verdict on untested linked-note update mechanisms, a
full manufacturing-sheet acceptance, or a speedup claim. No production setter,
fallback or comparator relaxation follows; further title variants are paused.

## Next layout control: left-justified title in its measured cell

`--candidate pre_save_left_title_cell` is a diagnostic layout change, not another
same-value refresh setter. The existing tests deliberately reject changed
justification, including the same-value REJUSTIFY control. That contract conflict
was raised before editing: those tests and the global cold comparator stay
unchanged. Only this new mode allows one checked center (`2`) to left (`1`)
transition before saving, then seals the new alignment and anchor. Links, resolved
title, vertical justification, lock, all sixteen font properties, height mode,
format inheritance, source values/tolerances and document ownership remain exact.

The diagnostic-only [`_linked_title_cell.py`](../../scripts/diagnostics/_linked_title_cell.py)
reads `ISheet.GetTemplateSketch`, inventories its segments and transforms native
line endpoints into sheet coordinates with the inverse `ModelToSketchTransform`.
It finds the nearest horizontal/vertical rules crossing the exact linked TITLE
note's anchor, then requires all four sides to close. Split collinear rules may
join within an explicit 1 nm topology bound; raw coordinates remain unrounded.
This bound is not used for title placement, fit or cold comparisons. Missing,
ambiguous, nonplanar or open boundaries fail without choosing a larger rectangle.
Curves, sketch text and construction entities are inventoried as non-boundaries,
not declared absent or preserved in shape by this line-only reader.

The requested sheet anchor is `(cell_left + native_font_height / 2, original_y, 0)`.
The half-font-height inset is an explicit layout choice, not a compensation for
the measured 7.225 mm shift; no old title-cell coordinates are supplied. The mode
requires an unlocked centered note and makes exactly these calls:

1. `INote.SetTextJustification(1)` (documented void).
2. `IAnnotation.SetPosition2(x, y, 0)`, requiring native `True` and exact position
   readback; a clamped position fails.
3. `IModelDoc2.GraphicsRedraw2()`, as required by the justification documentation.

No link, text, font, lock, source property, vertical alignment or template file is
written. Native note extent must fit the measured cell after placement and cold
reopen; every first/cold PDF title glyph box must also fit, with no acceptance
tolerance. The cold cell is measured again. Candidate success additionally
requires zero changed native annotation leaves, exact first/cold PDF glyph boxes
and zero changed PNG pixels. Original positive-baseline reproduction, native
identity and source-hash gates remain mandatory. Measured rules and attempted
calls are retained if discovery or placement fails.

Official bundle pages read: `ISheet.GetTemplateSketch`; `ISketch.GetSketchSegments`
and `ModelToSketchTransform`; `ISketchSegment.GetType`, `GetID` and
`ConstructionGeometry`; `ISketchLine.GetStartPoint2/GetEndPoint2`;
`ISketchPoint.X/Y/Z`; `IMathTransform.Inverse/ArrayData`;
`ISldWorks.GetMathUtility`; `IMathUtility.CreatePoint`;
`IMathPoint.MultiplyTransform/ArrayData`; `INote.SetTextJustification`,
`GetTextJustification`, `LockPosition`; `IAnnotation.SetPosition2`; and
`IModelDoc2.GraphicsRedraw2`, plus `swTextJustification_e` and `swSketchSegments_e`.
The official template-segment and sketch-to-model transform examples support
those read patterns. The segment example edits the template; this diagnostic
instead uses the documented direct `GetTemplateSketch` accessor and never selects
or enters template-edit mode. That combined native call shape still needs its
first live proof. The title may expose a different anchor or reference convention;
the exact readbacks must establish that, not a pre-emptive fallback.

After main-agent review, integration and an explicit exclusive seat grant, from
the frozen integrated root with its unchanged locked uv environment:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<granted-existing-PID>'
uv run --no-sync python cad/scripts/diagnostics/probe_fresh_title_update.py --candidate pre_save_left_title_cell --source C:/src/ha-perf-channel/cad/out/sldprt/rocker-arm.SLDPRT --guard-source C:/src/harmonic-analyzer/cad/out/sldprt/rocker-arm.SLDPRT
```

This prepares one baseline/candidate pair, not a production fix or full-recipe
acceptance. New tests first failed on the missing cell helper/variant; they cover
cell translation, segmented/open borders, native coordinate conversion, null and
malformed data, strict fit, checked setters, exact font/link/clamp rejection,
baseline gating and the stronger native-cold success condition. Native result,
visual title-cell clearance and whole manufacturing-sheet acceptance are pending.
