# Fresh linked-title update control

Status: native baseline reproduced the printed shift; the one pre-save redraw
did not prevent it. This diagnostic does not change production finalization.

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
   It adds exactly one documented `GraphicsRedraw2()` before native save. It has
   identical observations plus one post-redraw title snapshot.

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

Only after main-agent source review and an exclusive native seat grant:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<granted-existing-PID>'
uv run --no-project --python C:/src/harmonic-analyzer/.venv/Scripts/python.exe python cad/scripts/diagnostics/probe_fresh_title_update.py --source C:/src/ha-perf-channel/cad/out/sldprt/rocker-arm.SLDPRT --guard-source C:/src/harmonic-analyzer/cad/out/sldprt/rocker-arm.SLDPRT
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
