# Tooth-selector observation control

Diagnostic-only, opt-in observation of the existing gear selector. Native execution
of this instrumentation is pending. It changes no recipe, selection predicate,
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
