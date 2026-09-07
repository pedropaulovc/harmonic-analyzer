# Tooth-selector observation control

Diagnostic-only, opt-in observation of the existing gear selector. Two native
observations are recorded below; full recipe acceptance remains pending.
It changes no recipe, selection predicate,
radius tolerance, tie rule, entity identity gate, source pin, or BSURF index rule.

## Retained reason for the control

Root `datum-policy-i7kxmdqn/pilot.json` at `29c6ec1e` has SHA-256
`bdfb9187087864c69698c499beaa01fc5648f1f123e1a1f715d28ea2ba7403bf`.
Its selector scanned nine silhouettes and matched zero. The preceding
`vxy0llpy` and `ous640en` receipts both scanned nine and matched one, then failed
strict BSURF `GetControlPoints(1,6)` readback. The requested BSURF boundary-domain
experiment in `i7kxmdqn` therefore never ran.

The later failure snapshots show Right at `(-0.311355991, -0.026894309)` m in
`i7kxmdqn`, versus the requested `(0.300, 0.175)` m in both earlier receipts.
Each position was unchanged across failure PDF export. These are **post-failure**
observations, not proof of the position during the selector or of its cause.
Front/Iso positions and view scales agree. All retained sheet scales are 2:1;
the factory had checked 1:1 before view creation in all three runs.

Original/copy source SHA was identical across the three receipts:
`a5a2e0882336d622a7e93fae4d326cb059e7d91758e536488fcc6bf6de4ce93f`.
A subsequent read of the current producer execution token matched it, but those
pilots did not archive that token. Recipe, selector/common helper and imported
adapter fingerprints also agree. No source/token difference establishes a cause.
The reports lack each candidate's endpoints, read errors and radius differences.

## Scope and API premises

Set `HARMONIC_TOOTH_SELECTOR_OBSERVATION=endpoints` explicitly. The default is
`off`: no alias patch, journal or extra native observation. Invalid modes and
unrelated targets fail before parent/worker native routing. The supported targets
are the two existing callers, `crank_drive_gear` and `crank_pinion`.

Within the existing owned recipe scope, the observer wraps the recipe's actual
`visible_tooth_tip_silhouette` alias. The production function still performs its
single `visible_view_entities` enumeration, early binding, endpoint reads,
filtering, telemetry and final selection. A forwarding adapter passes the actual
endpoint callbacks to the real `_attempt` and actual `ArrayData` reads to the
real `_get_attr_or_call`, once each. A swallowed endpoint exception is recorded
before the original adapter returns its original default. Nothing rereads an
endpoint or substitutes an entity wrapper. Enumeration and binding indices and
Python wrapper IDs describe call correspondence, **not native identity**.

Entry/exit observations use these bundled official contracts:

- `IView.Position`: two doubles, geometric center relative to sheet origin.
- `IView.ScaleDecimal`: view scale, getter only in this control.
- `IView.ModelToViewTransform` and `IMathTransform.ArrayData`: model-to-view
  transform, sixteen doubles; rotation 0–8, translation 9–11, scale 12, unused 13–15.
- `IDrawingDoc.GetViews`: arrays of sheet/view arrays, first element is the sheet.
  The control requires exactly one native `IsSame == 1` match for the passed view
  in the exact owned drawing, plus exact current/active drawing and referenced
  source identity. Sixteen sheets/128 entries per sheet are diagnostic bounds,
  not claimed native limits.
- `ISilhouetteEdge.GetStartPoint/GetEndPoint` and `IMathPoint.ArrayData`: returned
  math points and their three doubles. The method docs do not establish that the
  observed discrepancy is a coordinate-space problem; this control infers none.

The bundled *Get Views and Notes* and *Dimension Edge in Drawing* examples were
read for the membership/transform call shapes. No transforms are applied and no
property, selection, view, source, rebuild or save setter is added.

Raw arrays retain their original numeric values and container types. Invalid
shape/type/nonfinite values and getter errors are explicit observations, never
an alternate accepted geometry. The actual selector alone determines its result.
Its exception object and returned entity survive exit-observation failure. Entry
ownership must be proved before running it. All scoped patches restore on exit.

The additional boundary getters are proactive and may affect timing/native cache
state. Entry/exit spans and per-read durations separate their cost; this is not a
performance comparison or a claim that getters are universally inert. The pilot
retains its existing hashes, ownership, source/attachment, save/cold/print gates.
The new journal is attached to the trial before selection so failure retains it.

## Rerun

From the reviewed integrated checkout, with confirmed exclusive seat ownership
and current PID, use the existing locked parent runner. Keep the first diagnostic
independent of BSURF exploratory indexing:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<confirmed current PID>'
$env:HARMONIC_TOOTH_SELECTOR_OBSERVATION = 'endpoints'
$env:HARMONIC_BSURF_GRID_CONTROL = 'off'
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py --source-root C:/src/harmonic-analyzer/cad/out/sldprt --guard-root C:/src/harmonic-analyzer/cad/out/sldprt --factory prepared --target crank_drive_gear --candidate <reviewed-integrated-SHA>
```

No new lifecycle, retry, selector fallback or accepted snapshot from exploratory
reads is introduced. Inspect `trials[0].tooth_selector_observations` alongside the
original selector span and unchanged failure evidence.

## Native observations on 2026-09-07

Both runs used root/helper revision `d93b88503769b9be23b8a10f12d95307ae53adab`,
adapter `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`, prepared factory, the same
protected gear hash above, and existing SolidWorks PID 42080 / revision 34.3.0.
They ran serially with source/config/adapter files unchanged during execution.

| pilot directory under `cad/out/reports/` | BSURF control | native enumeration | selector including observations | pilot elapsed |
|---|---|---:|---:|---:|
| `datum-policy-w4090gdy` | off | 293.020 s | 296.700 s | 387.879 s |
| `datum-policy-5fe0i713` | boundary-domain | 9.812 s | 13.803 s | 115.879 s |

Each enumerated nine silhouettes, matched one and returned binding index 8.
All actual endpoint arrays were finite native doubles, without swallowed getter
errors. Entry and exit each proved one owning-view match and exact current,
active and referenced-source identity. Right stayed at `(0.300, 0.175)` m,
scale 1.0, with the same model-to-view transform across the selector.
The selected endpoints' Y coordinates were approximately `0.0325753615032` m,
matching the requested radius; the observer did not transform them.

During the long first scan, a read-only `uv tool run py-spy dump --pid 33356`
showed the Python main thread waiting in generated `GetVisibleEntities2`, called
from the original `visible_view_entities`. The watchdog thread remained alive.
A Win32-only inventory found the enabled drawing window and no matching modal.
The native call eventually returned without interruption. Its variable cost is
unexplained; these two instrumented runs are not an ABBA speed comparison and
do not establish whether the additional getters affect native cache state.

Neither run accepted the recipe: both stopped at strict BSURF
`GetControlPoints(1,6)` readback before tooth FCF insertion. The second retained
the [eleven index-boundary results](tooth-tip-bsurface-witness.md#native-index-boundary-result).
Both original/copy gear hashes remained exact, all four protected hashes and
factory/helper/adapter guards matched, runtime guard errors were empty, and
initial/final native inventories were empty with no cleanup error.

Receipt SHA-256 values:

- `w4090gdy/pilot.json`: `d79005d14c32f36bd9342f96ba9e6e7dc219f58c32faf41308439ea12a7b5f87`.
- `w4090gdy/ownership.json`: `ca6a86a5584c09a08be098c345911a869850180d1cd9b0cb364efb5c06bd84fd`.
- `5fe0i713/pilot.json`: `3a8a480a45d9e12435b727554c2e5b0fe0b89a37072c1a8ce7a5700b9881e3fb`.
- `5fe0i713/ownership.json`: `0e252783399310a488c970704b4703052ddec316df4e72d9d1762d926cd1c2c9`.

These successful selections do not explain the earlier zero-match run or its
post-failure displaced view. No selector radius/tie rule or production layout
was changed, and no failed identity check was bypassed.
