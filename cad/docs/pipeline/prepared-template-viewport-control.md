# Retained prepared-template viewport control

This is a diagnostic, not a prepared-cache acceptance change. It neither changes
the production comparator nor publishes the failed template.

The production first-miss receipt at `f7a9fa55` is
`cad/out/prepared-drawing-templates/pending-82fdda7f6c7b-2d8h09eb/receipt.json`,
SHA-256 `10be83e46f7d934e7455db598f8ef399a946c728ad7966f2ed9e2141b0992ee5`.
Its exact saved DRWDOT has SHA-256
`c2a012dc3e37b51e0ce9edea4dffd928753039a81aea9dc197e101d76adc0fde`.
The positive `datum-policy-7wjzdu9q` preparation receipt has SHA-256
`07dd7350ca0dcae68988cf387800b1cc3c884a036684e56ecec5f1e73f9f254f`.
Their initial defaults match exactly; the only differing runtime source is a
docstring-only `_drawing_prepared_template.py` edit.

Field-aligned failed before/after evidence:

- All 43 note text/link/anchor keys match uniquely. Whole-JSON sorting swaps
  only the A/C list indices; these are not renamed annotations.
- The 33 visible notes retain captured text, font/style, anchors, native strokes
  and text cells. Raw `GetExtent` and derived body/envelope rectangles differ.
  The 66 X-bound changes cluster at −44.207720 µm (50) and +289.501882 µm (16).
  Their 333.709602 µm separation suggests, but does not prove, pixel quantization.
- One SF has eight native line coordinates differing by one ULP; the other SF,
  sheet properties, units, visibility and document dimension styles are exact.
- These receipts do not prove printed ink moved or establish a viewport cause.
  Deliberate tests rejecting `1e-12` extent drift remain unchanged.

## One-variable native experiment

`diagnostics/probe_prepared_viewport.py` creates one owned, unsaved blank from the
pinned DRWDOT, then sets `ActiveView.Scale2` to `s`, `2*s`, and `s`. Every arm
uses the same `GraphicsRedraw2`, strict native snapshot, PDF-only export/PNG render
and post-export snapshot. Targets are absolute from the original scale. No
content, document defaults or application preferences are written; there are no
native saves or source-part opens.

The receipt records viewport transform, scale, visible pixel box, document
visibility, exact native annotation/view identity checks and all raw defaults.
The A/B strict-default result is an observation. A/A equality and each arm's
pre/post-export defaults remain strict gates. Experiment-only field alignment
also checks all captured semantics except the explicitly reported raw extent
and its two derived rectangles; this cannot turn a failed A/A result green.

PDF glyph/pixel and raw-vector comparisons have separate verdicts. The reused
vector reader supports flat, identity-transform paths and records endpoints,
matrix, native PDF bounds and stroke style. Complete object kind/matrix/bounds
inventory is compared exactly. Image appearance relies on the independent exact
full-sheet pixel/glyph verdict, not raw image or whole-vector equivalence.
Unsupported nested/other objects fail this verdict while retaining available
PDF/glyph evidence. This is not a general PDF paint-equivalence proof. Existing rendering uses the production
300-DPI preview PNG helper (including its optional one-bottom-row crop). A
separate uncropped PDFium raster size/mode/pixel hash must also match, so that
crop cannot hide image changes at the page boundary. Failure receipts and scoped cleanup are retained.

The API contracts are [Scale2](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelView~Scale2.html),
[Transform](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelView~Transform.html),
[GetVisibleBox](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelView~GetVisibleBox.html),
[GetExtent](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.INote~GetExtent.html),
and [GraphicsRedraw2](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GraphicsRedraw2.html).
`GetExtent` is documented in sheet coordinates and is invalid for invisible
documents; the documentation does not promise viewport independence or permit
rounding. `Transform` maps model points to screen pixels and is read-only.

## Run after review and an explicit native-seat grant

Use a frozen checkout and its configured venv/adapter. Set the approved running
PID; do not copy an old PID without the parent's readiness/ownership check.

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<approved running PID>'
uv run python cad/scripts/diagnostics/probe_prepared_viewport.py `
  --expected-pid $env:HARMONIC_DIAGNOSTIC_SW_PID `
  --receipt C:/src/harmonic-analyzer/cad/out/prepared-drawing-templates/pending-82fdda7f6c7b-2d8h09eb/receipt.json `
  --receipt-sha256 10be83e46f7d934e7455db598f8ef399a946c728ad7966f2ed9e2141b0992ee5 `
  --template C:/src/harmonic-analyzer/cad/out/prepared-drawing-templates/pending-82fdda7f6c7b-2d8h09eb/prepared.DRWDOT `
  --template-sha256 c2a012dc3e37b51e0ce9edea4dffd928753039a81aea9dc197e101d76adc0fde
```

The parent runner acquires the existing machine-global seat. The worker only
attaches to the approved running instance and preserves unrelated visible
documents. This commit provides offline tests; it contains no native outcome.
