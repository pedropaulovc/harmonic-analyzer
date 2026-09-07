# Tooth-tip BCURVE readback control

This diagnostic adds an explicit `bcurve-3005` reader to the existing owned
full-recipe pilot. The default remains `off`: the original analytic classifier,
B-surface indexing and all attachment, source, cold and export gates remain in
place. No manufacturing recipe, source pin or adapter changes here.

## Observed boundary

PR #692 at `36b902e46d260d2595779c9e057868b065f4aa56`, adapter
`25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`, reached the tooth silhouette after
reading all 125 B-surface control points with the explicit column-row reader.
Its curve returned native Boolean `False` from both `IsLine` and `IsCircle`,
and native integer `3005` from `Identity` (`BCURVE_TYPE`). The unsupported-curve
gate then failed; no inserted, built or cold attachment acceptance followed.

Retained evidence in `C:/src/ha-bsurf-native-indexing/cad/out/reports/`:

- `datum-policy-yqlnp5v5/pilot.json`, SHA-256
  `70b6b80ffa9f6f8e1aee1b668045b12a46b8c3e52b98c0e85c56fc210b4f0453`.
- Its `ownership.json`, SHA-256
  `5784b380cc6863aef4be1ace3667bb56961ccabadf9c14e0373992ee1d4f9c54`.

The recipe took 77.5929456 s; the pilot took 173.7003349 s. These are not paired
performance measurements. Original/copy hashes were unchanged, runtime guard
errors were empty, borrowed documents were preserved and cleanup reported no
error. The curve-family observations are under
`trials[0].entity_context_observations.stages[2].silhouette.expected.curve_reads`.
That run did not call the new B-curve getters.

## Documented call shape and limits

The bundled official `ICurve.GetBCurveParams5`, `GetEndParams`, `IsBcurve`,
`Identity`, `ISplineParamData` properties and bulk-getter docs define this control:

1. Require integer identity 3005 and literal native `IsBcurve == True`.
2. Read `GetEndParams()` once: native success, finite increasing domain, and
   native Boolean closure/periodicity. Preserve the returned domain.
3. Call `GetBCurveParams5(False, False, not periodic, closed)` once. This makes
   no cubic or nonrational request and does not force a periodic curve into a
   nonperiodic representation. The official spline-points example's final
   `True, True` describes its selected curve, not every silhouette.
4. Read `Dimension`, `Order`, `Periodic`, `ControlPointsCount` and
   `KnotPointsCount`. Check exact native types, counts and the documented knot
   relation: controls + order for nonperiodic; controls + 1 for periodic.
5. Read complete `GetControlPoints()` and `GetKnotPoints()` retval/out arrays,
   requiring native success, exact lengths, finite doubles and nondecreasing
   knots. Retain coefficients and weights without rounding, projection,
   dehomogenization or knot normalization.

The diagnostic permits dimension 3 or 4, order 2–64, up to 10,000 controls and
10,064 knots. These are bounded read budgets, not claimed SolidWorks limits.
The rational-array docs describe `(x, y, z, w)` for closed/periodic and
`(w*x, w*y, w*z, w)` for open/nonperiodic curves; neither is transformed here.

`GetBCurveParams5` documents modeler-tolerance-dependent accuracy. This control
does not change modeler tolerance or claim that a parameter object is exact BREP
serialization. It compares the returned values exactly. A silhouette exposes
`GetCurve`, `GetStartPoint` and `GetEndPoint`, not `IEdge.GetCurveParams3`: the
reader retains the curve domain and ordered silhouette endpoints, without
inventing an edge trim, sense or CurveTag.

The earlier [paired curve control](crankshaft-curve-readback-control.md) proved
these bulk getter shapes for two closed periodic **3004 intersection** edges
(dimension 3, order 4, 60 controls, 61 knots), alongside line/circle controls.
It does not prove their shape or cold stability for this **3005** silhouette.
Native drawing-scoped persistent identity, owning-view and underlying-face
identity remain independent requirements; matching coefficients cannot replace
them. Failed getter results and partial metadata remain in the trial journal.

## Owned replay

Use a confirmed exclusive seat and a newly confirmed licensed SolidWorks PID;
do not copy a historical PID. Set `HARMONIC_DIAGNOSTIC_SW_PID` to that current
PID before running. The existing attach-only parent/worker owns the lock and
unique copies. The protected source/guard root is deliberately separate from
the runtime checkout, whose output directory need not contain any source parts.
Those originals still must match the pilot's exact source pins.

```powershell
Set-Location C:/src/ha-silhouette-bcurve-3005
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_BSURF_GRID_CONTROL = 'column-row-reader'
$env:HARMONIC_SILHOUETTE_CURVE_CONTROL = 'bcurve-3005'
uv run --frozen python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --candidate <frozen-commit> --factory prepared --target crank_drive_gear
```

Invalid curve-control values fail before COM routing. With the control absent
or `off`, no new native curve getters run. The two controls are independent;
enabling the curve reader does not adopt the experimental surface indexing as
a default or bypass its evidence-sink requirement.

## Offline checks and remaining native work

The initial new tests failed before implementation (4 failures, 50 setup errors;
`pytest-telemetry/run-xxsbtaqt`). The first implemented reader plus unchanged
classifier tests passed 71 cases (`run-fdkzxq6z`). Further tests exercise the full
125-point surface/curve combination, actual pilot report retention, fresh cold
handles and actual recipe-gate enrollment.

These are mocked API controls, not native acceptance. The next owned run must
establish the actual 3005 getter shapes, complete selected/attached banks and
all unchanged subsequent gates. No native save, cold persistence, printed
acceptance or end-to-end speed benefit is claimed by this change.
