# Fresh linked-title update control

Status: native baseline reproduced the printed shift; the one pre-save redraw
and one checked pre-save rebuild did not prevent it. This diagnostic does not
change production finalization. Same-value horizontal justification followed by
its documented redraw also leaves the shift. A forced-rebuild control is next.
Both independent native controls are recorded below.

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
False/None rejection before saving. 66 focused tests pass; native result pending.
