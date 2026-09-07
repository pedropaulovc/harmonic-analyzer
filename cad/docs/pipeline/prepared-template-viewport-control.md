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
documents. The initial control commit provided offline tests only; its later
native result is retained below.

## Zoom-only native result and controlled-translation follow-up

At root `ddf232ba`, the zoom-only control completed as **failed**, receipt
`cad/out/reports/prepared-viewport/prepared-viewport-3375jkd8/measurements.json`,
SHA-256 `f40200f604630f70030d0c7cc0699b68ea26a81a87408d06a0985291eb6dd67a`.
All three per-arm export-default/viewport checks, A/B and A/A text/style/native
stroke semantics, PDF glyphs, supported paths and complete object inventories
passed. All uncropped 5100×3301 RGB rasters have identical pixel SHA-256
`58270d9f1ad721417deef0f717dd2b16b247198092c4416e19ec2be62a4c922f`.
Input hashes stayed exact, ownership returned empty→empty and cleanup succeeded.

Strict A/A raw defaults and viewport equality failed. Although `Scale2` returned
to the initial value, screen-space translation changed by +113.881013359 px in
X and −7.570898485 px in Y. Thus this was **not the same viewport**; it does not
prove instability at a fixed viewport or a printed-ink mutation.

The initial transform gives 333.709601874 µm/pixel, matching the original failed
preparation's two extent-delta clusters. Zoomed pitch is 166.854800937 µm/pixel.
Every visible-note X extent in every arm maps to an integer pixel endpoint
within 4.55e−13 px. A/A pixel endpoint changes of 113 or 114 px, against the
113.881013359 px viewport translation, explain the measured −294.002617140 µm
and +39.706984733 µm sheet-coordinate changes. Native glyph anchors/positions
remain exact. These are measured viewport-dependent extent observations, not
permission to drop the raw defaults gate.

The independent next variant adds `--translation original` to the command above.
The default `--translation native` retains the zoom-only mechanism. Both now
record the original `Translation3.ArrayData` and `Orientation3.ArrayData` before
any Scale2 setter. The new variant creates a **fresh** native MathVector from
the original three translation components after each absolute Scale2 assignment,
assigns it through `Translation3`, and requires exact translation readback and
unchanged orientation. It does not derive native translation from PDF/screen
coordinates, write orientation, or touch sheet/annotation positions. All strict
A/A, export, semantic and image checks are unchanged. The new variant has only
offline mock verification until its own reviewed native receipt exists.

Bundled contracts additionally inspected:
[Translation3](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelView~Translation3.html),
[Orientation3](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelView~Orientation3.html),
[CreateVector](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMathUtility~CreateVector.html),
and [MathVector.ArrayData](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMathVector~ArrayData.html).
The official “Get Angle of Hole Not Normal to a Face” example creates a vector
from three doubles. This is a call-shape reference, not proof that restoring
viewport translation will make this native template's A/A defaults exact.
