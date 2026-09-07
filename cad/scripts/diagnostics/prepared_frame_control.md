# Prepared-template document-frame control

This is a diagnostic-only candidate. Production still refuses a different
visible pixel box without any frame setters; its existing deliberate test is
unchanged. No native result or production fix is claimed by the offline tests.

## Trigger and measured boundary

The actual `drawing:cone_tip_adjuster` task at root `2d5d4d4d` failed before its
recipe, during prepared-template verification. The source part had built; the
subsequent cone-pivot-screw task had not run. Retained source receipt:

`cad/out/prepared-drawing-templates/pending-09f01092e507-2yl_jg8x/receipt.json`

SHA-256 `66814a0291ddb4ab5a33acf43807a2cdc16398cb287747d4499dfa40f2136a1c`.
The preparation took 23.1159306 seconds before failure, with empty baseline,
preserved ownership and no cleanup error. The original project DRWDOT digest is
`2b1bbe3dfff265e8bb35ea79f0f9690f808049f5cef764cab8959c1eaee5e849`;
the exact specification is scale 4:1, two decimal places, SW revision 34.3.0.

| Raw viewport observation | First blank | Verification blank |
| --- | --- | --- |
| Visible rectangle, screen pixels | 2216, 141, 3824, 995 | 2216, 141, 3823, 994 |
| Width × height | 1608 × 854 | 1607 × 853 |
| Transform scale | 2996.6174014344465 | 2993.108481760635 |
| Translation3 X, metres | 0.041203122560499586 | 0.04124646346228999 |

Orientation was identical. The transform-scale ratio differs from 853/854 by
only −1.1102230246251565e−16; X translation changed by 43.34090179040212 µm.
This is evidence of a changed measurement frame, not an observed defaults/ink
change: the second defaults snapshot was never reached. The old receipt did not
capture native `Frame*` properties, so it does not identify whether the document
frame itself or another visible-client-area factor changed. No DPI/window-manager
cause is established.

The strict production viewport gate came from the earlier native controls in
[prepared-template-viewport-control.md](../../docs/pipeline/prepared-template-viewport-control.md):
note extents were observed on the pixel grid, and exact scale-plus-pan restoration
made repeated raw defaults equal. Those controls did not prove that every new
document keeps the same visible pixel rectangle. The new failure falsifies that
creation assumption, not the need to compare raw extents in a controlled frame.

## Explicit mechanism and limits

`probe_prepared_template_cache.py --frame-policy measured_restore` scopes an
interceptor around the existing owned normal/MISS/HIT control. It requires the
failure receipt path/hash, the same original template bytes and exact specification,
`--viewport captured`, and `--printed-format compare`. Input hashes are checked
again at phase boundaries and in the final guard. The invalid unpublished DRWDOT
is neither consumed nor reset. The cache remains unique to this diagnostic run.

The selected context requires an **empty initial native document inventory**;
it never closes a user document to make the session eligible. Baseline frame
inventories are therefore empty, and final inventory must again be empty. Every
frame write additionally requires exactly one open, owned active drawing and the
same ownership record, model and model-view handles. This first control does not
claim that frame changes are harmless to another SDI/MDI document window.

The interceptor captures `IModelView.FrameLeft`, `FrameWidth`, `FrameTop`,
`FrameHeight`, and `FrameState` alongside the existing raw viewport. If the
measured frame or visible box differs, it applies those five **captured values**
once, in that order, checking exact ownership before and after each setter. It
does not add or subtract a pixel, write orientation, resize the application
window, change preferences, or retry. Minimized, malformed or unsupported frame
state is rejected. After frame readback, the unchanged production restore still
requires the exact visible rectangle, orientation, scale, native translation and
full transform. The full raw-default and PDF-glyph/PNG gates are unchanged.

All patched bindings are restored on success/failure. Receipts retain the measured
target/before/after frames and each requested setter; a remaining frame or pixel
difference fails, as does independent raw-note drift. Final inventory errors do
not replace an earlier validation error. `mechanism_outcome` distinguishes actual
restoration of observed pixel drift from a run that happened to need no frame
changes; the latter is not a positive control of the failing mechanism.

The SolidWorks skill's bundled official references were read in full before
implementation: `types/IModelView/{GetVisibleBox,FrameLeft,FrameWidth,FrameTop,
FrameHeight,FrameState,Transform,Scale2,Translation3}.md`,
`enums/swWindowState_e.md`, and
`examples/Position_a_Document_Window_Example_VB.md`. The example writes the five
document-frame properties; it does not establish that those writes recover this
seat's one-pixel difference. `GetVisibleBox` excludes the FeatureManager-obscured
area, while the frame properties describe the document window in client-area
pixels. Exact visible-box readback is therefore still necessary.

## Proposed single native invocation — not yet run

Only after main-agent source review, explicit seat grant and current inventory
verification, with the existing licensed process and unchanged adapter:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '31860'
uv run --no-sync python cad/scripts/diagnostics/probe_prepared_template_cache.py `
  --expected-pid 31860 --scale 4 1 --decimals 2 `
  --viewport captured --printed-format compare --frame-policy measured_restore `
  --failure-receipt C:/src/harmonic-analyzer/cad/out/prepared-drawing-templates/pending-09f01092e507-2yl_jg8x/receipt.json `
  --failure-receipt-sha256 66814a0291ddb4ab5a33acf43807a2cdc16398cb287747d4499dfa40f2136a1c
```

The unchanged parent runner takes the machine-global COM lock and attaches only.
It is not permission to launch/recover SolidWorks, alter borrowed documents, or
continue after a failed contract. This is a correctness positive control, not an
unloaded-host timing benchmark, first-fleet speedup or populated-drawing proof.

Offline verification: 227 tests passed in 12.75 seconds, retained pytest receipt
`run-ds1u8b18`. This includes the new frame-control tests plus unchanged
`test_prepared_viewport_drawing.py`, `test_prepared_template_cache_probe_drawing.py`,
`test_prepared_template_drawing.py`, and `test_owned_native_documents_drawing.py`.
The original zero-setter rejection assertion is unchanged. Mock success is not
native frame-restoration evidence.
