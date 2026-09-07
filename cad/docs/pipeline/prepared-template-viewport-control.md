# Retained prepared-template viewport control

## Production measurement-frame correction

The production preparer now captures the first owned blank's native viewport
before reading defaults. It restores that exact scale and translation on the
verification drawing, requires unchanged orientation and complete viewport
readback, then performs the original exact raw-default comparison. It sets no
note position, font, sheet property or annotation geometry. The cache receipt
retains both viewport observations; a hit also requires the successful exact
restoration witness. The helper's source enters the preparation input key.

This follows the successful same-document controlled-pan experiment below,
not a rounding allowance. The actual two-document production path passed the
native run recorded below. Fail-first fixtures reproduced the differing measurement frame
and missing restoration; 143 preparation/control tests and 217 factory tests
pass. Three diagnostic integration expectations now account for the one new
production restoration; normal mode still adds no diagnostic override, and all
raw-extent drift rejection assertions remain in place.

### Production MISS/HIT at `d6ad5aad`

The actual `drawing:fulcrum_shaft` task prepared and validated the template in
28.735 s; its drawing build took 42.171 s. A separately invoked
`drawing:pivot_shaft` used the same cache key in 0.002477 s and built in 13.391 s.
Both tasks exited zero on the existing PID 31860 with adapter `e77bfda4` and
remote cache/autostart disabled. The `-s` task selection used the existing part
artifacts without rebuilding their producers; this is not a full pipeline gate.

Receipt: `cad/out/prepared-drawing-templates/ad3b6bf9cd3fffd8f2d69c251e1dba186dc9b304f5a0584debc4f7ad7ed978d8/receipt.json`,
SHA-256 `866a379644da0f9a92123fba25cb00765f47accb982b1969379a4e375cc90391`.
Viewport restoration, all 43 note records, both surface-finish records, styles,
sheet properties and units are exact. Only 18 leaves in the previously excluded
empty linked-field extent observations differ. Preparation inputs stayed exact
and owned preparation documents were cleaned up without error.

Both generated full-sheet PNGs were visually inspected: dimensions, symbols
and title-block text are readable. Original source hashes remain exactly
`73eeb75dcb1f24ca70b5f5ad2212d7b829a94af3a518b7c3830ff6c58e47d740`
(fulcrum) and
`e5bcdb79849aac9ce6068188ccf0c6e2fd1222e82f1d8b4d75e0fd2723f01dc5`
(pivot). The open pivot file required read-only shared access for SHA-256;
size/mtime stayed stable during that read. This run did not cold-reopen the
drawings or compare printed normal/MISS/HIT pairs. Those boundaries remain
separate from production cache acceptance.

## Diagnostic provenance

The controls below neither change the production comparator nor publish the
failed template. Their run-local artifacts are not production cache entries.

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

## Controlled-translation positive result and two-document test

The independently executed `--translation original` control at root `fabbea31`
passed, receipt `prepared-viewport-0htc7jjy/measurements.json`, SHA-256
`f853ba23b5cc867d92f2955fc5f8639e4aca8ed164736b067404f07b7169824d`.
The original/first/restored viewports and the complete A/A defaults (including
raw blank-linked extent observations) are exactly equal. Every export, semantic,
glyph/pixel and supported-path/object-inventory gate passed. All three full-page
raster hashes equal the zoom-only run's `58270d9f…c922f`. Inputs remained exact;
ownership returned empty→empty with no cleanup error. A/B extents still changed
on the half-size pixel grid. This proves the same-document native call shape,
not preparation equivalence between two newly created documents.

The shared capture/vector/restore operations now live in the drawing-only
`_drawing_template_viewport.py`, with no diagnostic imports. Restore refuses a
different orientation or visible pixel box, and requires exact full viewport
readback. It never writes orientation or resizes the document window.

The next independently gated cache experiment is:

```powershell
uv run python cad/scripts/diagnostics/probe_prepared_template_cache.py `
  --expected-pid $env:HARMONIC_DIAGNOSTIC_SW_PID `
  --scale 1 1 --decimals 2 --printed-format compare --viewport captured
```

Use the same explicit environment/seat conditions as above. This probe uses only
its run-local cache. Normal setup captures its viewport. Both preparation CREATE
scopes and subsequent prepared MISS/HIT trials restore it after creation, before
their strict snapshots. All existing normal/MISS/HIT raw defaults, printed output,
source/hash/cache and ownership gates remain in force. The default `--viewport
normal` adds no diagnostic viewport-restoration calls; the production preparer
still restores its verification frame. The captured-mode mock demonstrates
new-document pan changing extents, and still rejects independent `1e-12` raw
extent drift, orientation changes and wrong translation readback. Its native
two-document outcome is not claimed by the same-document positive control.
