# Fresh linked-title update control

Status: offline-tested diagnostic, not yet run in SolidWorks. It does not change
production finalization or establish a redraw fix.

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
This diagnostic has made no native calls. Use only a new explicitly confirmed
existing PID; it must not launch/recover SolidWorks itself.

Offline verification: 42 focused tests and 160 adjacent tests passed; Ruff is
clean. Tests cover candidate gating, exact one-redraw ordering, wrapper restoration,
source-copy save rejection, wrong view references, title link/style/identity
mutations, and survival of the clean part plus dirty unsaved baseline drawing
after normal execution and baseline/candidate failures. The test is automatically
enrolled by the existing `test_*_drawing.py` recipe-gate discovery. Native outcome
remains untested pending source review and a new seat grant.
