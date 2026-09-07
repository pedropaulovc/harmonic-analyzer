# Tooth-tip native control-point indexing experiment

The native full-domain control now supports testing column-first getter
arguments. This is an explicit diagnostic mode, not a production-default
change or native acceptance. Existing row-first tests remain unchanged because
their deliberate API assumption conflicts with the observed domain; the
contradiction has been raised to the user.

## Native positive control

Root/helper `a89a27b0b4f6b77b666a6d0418a013c07bd56436`, adapter
`25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`, ran the owned prepared
`crank_drive_gear` recipe with `HARMONIC_BSURF_GRID_CONTROL=column-row-grid`.
The retained report is
`C:/src/harmonic-analyzer/cad/out/reports/datum-policy-_3d4_qxm/pilot.json`,
SHA-256 `d82d7c472e50b934e45716e057f9440eddcc3416f0c5c0658716209024c7768b`.

The selected tooth-tip face reported 25 columns, 5 rows, dimension 4,
U/V orders 5/3 and knot counts 30/8. All 125 positional calls with first
argument 1..25 and second argument 1..5 returned finite four-double vectors;
all 125 vectors were distinct. The unchanged ordinary reader then rejected
`GetControlPoints(1,6)` returning `None`. The run failed; these observations
are not attachment acceptance or a speed benchmark.

Original and copied gear bytes remained
`a5a2e0882336d622a7e93fae4d326cb059e7d91758e536488fcc6bf6de4ce93f`.
The raw report retains all index/result pairs and source/runtime guards.
The bundled `IBSurfParamData.GetControlPoints` documentation describes Row,
Column with their respective reported counts. This experiment tests the
observed contradictory bounds; it does not relabel that documentation.

## Changed behavior

`HARMONIC_BSURF_GRID_CONTROL=column-row-reader` changes only actual getter
arguments to `(column, row)` while retaining a logical row-major matrix.
The completed bank is marked `control_point_order: column-row`; each journal
entry retains logical indices and actual arguments. It reads the matrix once,
without the 125 extra exploratory queries. No fallback or retry is added.

All finite-double, shape, knot, read-budget and first-failure checks remain.
Partial matrices cannot become accepted banks. Rational weights, coefficients,
surface request, native face/view/persistent identity and exact built/cold
comparisons are unchanged. An evidence sink is required before native reads.
Missing mode or `off` retains the existing row-first behavior.

## Offline evidence

The new suite first failed 11 cases, with one existing rejection passing,
before implementation (`run-kkbtae6l`). The four-file reader/boundary/observer
suite then passed 105 tests (`run-5ixwb5wj`). These include interior failures,
actual argument journaling, no partial-bank publication, unchanged default,
and the real FCF observer with fresh cold handles and wrong-identity or changed
coefficient rejection. Ruff and `git diff --check` passed. Mock results do not
establish native coefficient stability.

## Native trial

Use this checkout's own environment and adapter, a clean committed candidate,
and a freshly confirmed existing SolidWorks PID. The parent pilot acquires the
machine seat lock and the worker owns unique copies; borrowed documents and
original source pins stay protected. Freeze candidate/runtime files for the
whole run. Do not save or regenerate the protected originals.

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<confirmed existing PID>'
$env:HARMONIC_BSURF_GRID_CONTROL = 'column-row-reader'
$env:HARMONIC_TOOTH_SELECTOR_OBSERVATION = 'endpoints'
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --candidate HEAD --factory prepared --target crank_drive_gear `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt
```

Native insertion, repeated/built/cold geometry stability, all manufacturing
checks, source-copy preservation and printed clearance remain unproven until
that trial completes. Stop at its first failure and retain the original error.
Production adoption requires resolving the tested contract contradiction,
successful native acceptance and the full stack build/review/visual gates;
this opt-in experiment alone does not repair production.
