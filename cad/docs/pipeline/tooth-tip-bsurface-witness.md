# Tooth-tip BSURF attachment readback

Diagnostic candidate, not native acceptance. No drawing recipe, circular-runout
FCF, manufacturing requirement, source pin, resolver or production identity
predicate changes. The existing owned full-recipe pilot acquires the seat,
opens unique bytecopies, protects source/template/runtime hashes, and retains
its complete source/content/BASIC/layout/save/cold/printed gates.

## Retained failure

At `bd7e33843eb65d1d22afa4fa8e413b1b78cd59cd`, prepared-factory trial
`cad/out/reports/datum-policy-uunvyftg/pilot.json` stopped in the first target,
`crank_drive_gear`, at the selected `gear tooth-tip circular runout` role:
`RuntimeError('unsupported silhouette surface identity 4006')`.

- Pilot SHA256: `ba2c1b0ea52bcbcabf293b62df507b8dbbb61bf5ab4d6a4cdef494d0c79e4652`.
- Recipe: 81.19213010009844 s; pilot: 174.995303099975 s. Neither is a new timing measurement.
- One selected kind46 entity; the drawing persistent-ID selection controls
  returned 1. The earlier bore datum selected/inserted stages passed. The tooth
  FCF did **not** reach an inserted stage.
- `surface.Identity()` reached 4006 (BSURF); the old reader raised before
  retrieving its coefficients or the silhouette curve. This receipt therefore
  establishes the missing surface branch, **not** a native B-spline return shape
  or supported tooth-tip curve kind.
- Original and copied gear bytes remained
  `a5a2e0882336d622a7e93fae4d326cb059e7d91758e536488fcc6bf6de4ce93f`.
  All eight source pins and the template were unchanged; final runtime guard
  errors and failure-evidence errors were empty.
- `ownership.json` SHA256
  `5aedbc3b61c894bc9aa1996416a0aa1bf376ed5da1b89b017b1b09a769658091`
  records cleanup without error and preservation of the one pre-existing,
  clean, visible `cylinder-gear.SLDPRT`. It was not an empty baseline.

Read-only replay on the retaining seat (no SolidWorks access):

```powershell
$base = 'C:/src/harmonic-analyzer/cad/out/reports/datum-policy-uunvyftg'
Get-FileHash "$base/pilot.json", "$base/ownership.json" -Algorithm SHA256
$report = Get-Content "$base/pilot.json" -Raw | ConvertFrom-Json
$trial = $report.trials[0]
$trial | Select-Object target, recipe_seconds, error, copy_hashes, copy_final
$trial.entity_context_observations.stages |
    Select-Object label, stage, selected_count, selected_kind, error
$report | Select-Object status, elapsed_seconds, runtime_final_guard_errors
Get-Content "$base/ownership.json"
```

## First BSURF native attempt and partial-read journal

At `599d3ac483817c94d766e783228cc71b5a9daff2`, the prepared
`crank_drive_gear` trial in `datum-policy-ous640en/pilot.json` reached
`GetControlPoints(1,6)` and rejected its `None` return: four native doubles were
required. The sequential reader had validated `(1,1)` through `(1,5)` first.
It did not retain their values or the preceding parameter/grid metadata, so this
receipt cannot establish the actual row/column counts or explain the null.
The tooth-tip FCF still did not reach insertion. This is a failed read request,
not a finding that BSURF readback is unsupported.

- Pilot SHA256: `cef8018e814e2fddb9a04f36f9b77e4143eccf5641e439c3f1f3bafbfd2814d6`.
- Recipe: 58.822418600087985 s; pilot: 142.81831939995755 s. These include the failed
  diagnostic and are not a performance comparison.
- Original and copied gear hashes remained `a5a2e0882336d622a7e93fae4d326cb059e7d91758e536488fcc6bf6de4ce93f`.
  Final runtime guard errors were empty.
- Ownership SHA256: `d6317fa06161ee68bc31019a36fc294cc97934d92a86e5bec37ebfd33d264055`.
  All four protected hashes (rocker, channel, crank gear and template) remained
  exact; initial/final inventories were empty and cleanup had no error.

The follow-up journals validated parameterization, grid counts, orders, senses
and knots before requesting the grid. It also retains each raw metadata return
with its type and each requested `(row, column)` with its actual result,
including `None`, or the getter exception. Partial data stays in the existing
selected/attached evidence sink when validation fails. A completed geometry
bank has the same fields and exact comparison as before; a partial journal
never becomes an accepted snapshot. Journal encoding errors are recorded
without replacing the original native validation failure. No getters are
repeated and no calls, indices, tolerance, or acceptance rules change.

The official `GetControlPoints` contract and generated 2026 ABI both take
integer arguments in **Row, Column** order. The documented bounds are one
through the respective row/column counts; the C# example reads `(2,3)`.
Neither a zero-based nor a transposed request is justified by this receipt.
The next native control can compare the documented example index and boundary
indices against the now-retained counts. Its result remains untested.

## Retained metadata and opt-in boundary-domain control

The second prepared trial, at `37b13401` in
`cad/out/reports/datum-policy-vxy0llpy/pilot.json`, failed at the same `(1,6)`
request. SHA256:
`deaa6c9be61e313c3220b092dee695cbcb0b517c0a69d3209fb1192909eff8e1`.
Its journal now records **25 columns, 5 rows, dimension 4, U/V orders 5/3,
and U/V knot counts 30/8**. The first five `(1,column)` requests returned
four-double tuples; `(1,6)` returned `None`. These are observed property values
and calls, not a conclusion about the API's actual index domain or a reason to
transpose its arguments. Recipe time was 64.34269279998261 s and total pilot
time 137.11865799990483 s, including the failed witness. The copied gear hash
stayed exact; all four protected hashes were unchanged, initial/final native
inventories were empty, and cleanup had no error.

`HARMONIC_BSURF_GRID_CONTROL=boundary-domain` explicitly enables a separate
raw observation group before the unchanged full grid. Missing variable or `off`
adds no calls; any other value is rejected in parent/worker routing before COM
and at the direct surface entry. An opt-in surface read requires an evidence
sink. The pilot records its mode as `bsurf_grid_control`; the surface journal
stores `grid_control` with the requested indices, literal returns and exceptions.

The bounded plan starts with the official example's `(2,3)`, then varies one
argument using each measured count and count+1. For this observed grid it is:

```text
(2,3), (1,5), (1,6), (5,1), (6,1),
(25,1), (26,1), (1,25), (1,26), (0,1), (1,0)
```

The last two are explicit **out-of-documented-domain negative probes**, never
normal requests. Smaller/square grids deduplicate this fixed plan; there are
at most 11 queries, not an expanded grid search. The generated ABI still gets
Row then Column. The request remains `GetBSurfParams3(False, False, VP0, 0.01)`.
No conversion, tolerance, zero-based acceptance or transpose is introduced.
Getter errors stay in the observation group and do not skip later planned
observations. Then the original full-grid reader runs from `(1,1)`, with the
same strict shape/finite checks and first-failure behavior. Exploratory values
never populate its geometry bank or replace its rejection. The separate
`diagnostic.silhouette.bsurface.boundary_domain` span exposes added read time;
this instrumented run is not a performance comparison.

For one owned control, set the environment only for the existing pilot command
below (same source/guard paths and confirmed exclusive seat/PID):

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<confirmed existing PID>'
$env:HARMONIC_BSURF_GRID_CONTROL = 'boundary-domain'
try {
    uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
      --candidate HEAD --factory prepared --target crank_drive_gear `
      --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
      --guard-root C:/src/harmonic-analyzer/cad/out/sldprt
} finally {
    Remove-Item Env:HARMONIC_BSURF_GRID_CONTROL
}
```

This uses the existing locked attach-only worker and owned source/drawing
lifecycle. It does not authorize another recipe attempt or a save of the copied
source. The completed boundary-control result is recorded below.

Offline boundary tests first reported 21 failures and 2 unchanged-default
passes (`run-x35zngby`). They now cover strict enum routing, missing evidence,
bounded deduplication, the observed native metadata shape, literal null/errors,
and refusal to substitute exploratory coefficients for the full grid. The
12-file adjacent run passed 484 tests in 18.84 s (`run-nqyfz0zi`); the final
25-case boundary suite, including original getter-exception preservation,
passed in 0.64 s (`run-ruu9ckp1`). Ruff F/RUF043/RUF059 and diff checks passed.
These fixtures establish instrumentation behavior, not native domain results.

## Native index-boundary result

At root/helper `d93b88503769b9be23b8a10f12d95307ae53adab`, the owned prepared
`crank_drive_gear` pilot `datum-policy-5fe0i713` reached all eleven planned
boundary reads. The preceding observer-only `datum-policy-w4090gdy` run had
reached the same strict sixth-point failure. Both selected one of nine tooth
silhouettes with exact view/source ownership. Complete receipt hashes, timings
and cleanup evidence are in the [selector observation results](tooth-selector-observation.md#native-observations-on-2026-09-07).

The reported grid remained 5 rows, 25 columns, dimension 4, with U/V orders 5/3
and knot counts 30/8. Actual positional calls returned:

| first argument | second argument | raw result |
|---:|---:|---|
| 2 | 3 | four doubles; documented example control |
| 1 | 5 | four doubles |
| 1 | 6 | `None` |
| 5 | 1 | four doubles |
| 6 | 1 | four doubles |
| 25 | 1 | four doubles |
| 26 | 1 | `None` |
| 1 | 25 | `None` |
| 1 | 26 | `None` |
| 0 | 1 | `None` |
| 1 | 0 | `None` |

The generated early-bound ABI still forwards `Row, Column` in that order; no
Python argument reversal explains this result. These observations contradict
the documented respective row/column upper bounds on this native surface.
They support testing a first-argument 1..25 / second-argument 1..5 grid, but do
not prove every pair, including `(25,5)`, succeeds or establishes a stable
same-session/cold identity witness. No production acceptance rule or existing
matrix assertion has been changed to accommodate the observation.

After the exploratory reads, the unchanged strict reader again rejected
`GetControlPoints(1,6)`. No partial grid was accepted and the tooth FCF did not
reach insertion. A complete correction requires a full-grid native control,
reconciliation of the documented/tested index contract with the observed ABI,
then repeated/attached/cold identity and printed manufacturing acceptance.

## Full proposed-domain observation

`HARMONIC_BSURF_GRID_CONTROL=column-row-grid` requests every pair in
`1..ControlPointColumnCount` by `1..ControlPointRowCount` before the unchanged
ordinary reader. It replaces the eleven boundary observations for that run;
it does not run both observation modes or alter the native approximation request.
For the observed grid this means 125 queries, including `(25,5)`. The existing
4096-vector total budget is checked before any control-point request.

Each record names the actual positional arguments `first` and `second` and
retains the raw return or getter exception. Finite-vector validation checks the
reported dimension without rounding coordinates or dividing rational weights.
An interior rejection is retained and the remaining bounded observations still
run. `all_vectors_finite` describes only these proposed-domain returns, never
an accepted surface or native attachment; serialization errors remain visible
in individual raw records. The ordinary reader then executes its original
row/column calls and propagates its original failure. Exploratory values never
populate `bspline.control_points`.

The mode is explicit, rejected without an evidence sink before native access,
and journaled in the existing pilot receipt. Use the same owned pilot command
with only `HARMONIC_BSURF_GRID_CONTROL` changed to `column-row-grid`; leave source
pins, view ownership, selection and manufacturing gates unchanged. Native
execution of this full-grid control remains pending while the foundation full
build owns the seat. Existing matrix assertions were not rewritten.

## Supported request, not an exactness assumption

The bundled official **Get B-Spline Surface Parameterization Data (C#)** example
calls `Parameterization2()` then
`GetBSurfParams3(false, false, parameterization, 0.01, out sense)`.
The generated 2026 early-bound ABI has a dispatch return plus an output Boolean;
the Python candidate checks `(data, sense)` explicitly.

The [GetBSurfParams3 contract](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISurface~GetBSurfParams3.html)
describes tolerance in metres between an **approximated** B-spline and its
underlying surface. It does **not** explicitly say tolerance is ignored for an
already-BSURF surface. False/False requests neither cubic nor non-rational
conversion; it is not a proof that no approximation occurs. The candidate uses
the documented example's 0.01, records that request, and never uses it as an
equality allowance. A 0.0 request would be a separate one-variable native
follow-up, not an automatic retry or an exactness guarantee from its number.

Readback captures all finite U/V ranges, boundary enums, property counts and
ordered property arrays; face UV bounds and face/surface sense; B-spline sense,
U/V orders, matrix dimensions, rational dimension 3/4, periodicity, both complete
knot vectors and **every** 1-based row/column control vector. Rational weights and
all coefficients remain raw: no rounding, weight division or coordinate change.
Native Booleans are validated locally and serialized as explicit state strings.

The official `IBSurfParamData.UKnots/VKnots` counts are respectively
column-count+U-order and row-count+V-order, including periodic output (which the
docs describe as converted to non-periodic form with extra end knots). This is
not the separate `ICurve` periodic-knot formula. `IFace2.FaceInSurfaceSense=True`
means **opposite**, whereas the `GetBSurfParams3` output `Sense=True` means same.
Periodic face UV bounds may straddle the underlying range, so no simple
containment test is imposed. UV bounds are not trim loops or full BREP; the
official method directs combined surface/trim extraction to `GetTrimCurves2`,
which this diagnostic does not call or claim to capture.

Read-budget limits are 32 orders, 64 properties per direction and 4096 total
control vectors, not claimed API limits. Unknown enums, nulls, unsupported
types, nonfinite values, malformed lengths/ranges or excessive grids fail
before acceptance. Zero-property arrays must be actual empty arrays; undocumented
null-as-empty conversion is not assumed. Native getter failures propagate
without retries. The `diagnostic.silhouette.bsurface` span exposes getter cost.

`_silhouette_attachment_witness` adds only the 4006 reader and an optional
partial-evidence sink. Partial surface metadata survives a surface getter
rejection; a successful surface read survives a subsequent curve rejection
in the existing selected/attached stage. Partial evidence cannot pass.
Plane/cylinder readers, supported line/circle curve predicates, drawing-scoped
native persistent IDs, owning-view/underlying-face `IsSame`, exact same-session
raw comparison, and the existing fresh cold role resolution remain intact.

## Offline checks and native boundary

The initial fail-first file produced 25 failures at the old unsupported 4006
branch (`run-2md12sef`). Subsequent fixtures cover rational/non-rational and
periodic/non-periodic data, complete 1-based grid reads, malformed metadata and
arrays, wrong PID/face/view, exact coefficient deltas, partial failure evidence,
and the real VIEW FCF observer's selected/inserted/built/fresh-cold stages. The
cold test makes old native handles unusable, rejects a fresh wrong PID, and
enumerates every changed coefficient without permitting a CurveTag exception.
The 10-file focused/adjacent suite passed 379 tests in 21.35 s
(`run-ruj4091n`); Ruff F/RUF043 and `git diff --check` passed. These are COM-free
control-shape tests, not native success.

For the partial-read follow-up, three fail-first cases reproduced the missing
surface journal (`run-3atzjyb2`): a null sixth vector, a thrown sixth getter, and
an invalid native count. The synthetic grid does not infer the missing native
counts. Added controls preserve partial parameter arrays and the original
validation error if journal encoding fails, and prove that successful geometry
and native call counts are unchanged. The ten-file adjacent suite passed
389 tests in 20.02 s (`run-pb9a7cir`); Ruff F/RUF043/RUF059 and
`git diff --check` passed. The journaling follow-up subsequently produced the
second failed native receipt described above.

The native attempts failed as recorded above; complete native acceptance
remains pending. Use the existing pilot after source review
and confirmed exclusive seat ownership/current PID; the prepared factory keeps
the preceding failure's setup arm. Stop at the first failure; no second variant
or fallback is authorized by this command. Freeze the actual imported adapter
and helper tree as usual. The owned pilot hashes this new diagnostic module too.

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<confirmed existing PID>'
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --candidate HEAD --factory prepared --target crank_drive_gear `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt
```

Untested: a complete successful 4006 metadata/grid read, tooth-tip silhouette curve
class, repeated/attached/cold raw coefficient stability, FCF native insertion
and printed clearance, full-recipe source-copy preservation and total runtime.
Existing native source hashes and owned lifecycle are not waived by this reader.
The current tests cannot establish any of these native boundaries or a speedup.
