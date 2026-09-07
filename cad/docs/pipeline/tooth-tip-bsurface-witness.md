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
partial-evidence sink. A successful surface read survives a subsequent curve
rejection in the existing selected/attached stage; partial evidence cannot pass.
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

Native integration remains pending. Use the existing pilot after source review
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

Untested: the actual 4006 metadata/grid call shape, tooth-tip silhouette curve
class, repeated/attached/cold raw coefficient stability, FCF native insertion
and printed clearance, full-recipe source-copy preservation and total runtime.
Existing native source hashes and owned lifecycle are not waived by this reader.
The current tests cannot establish any of these native boundaries or a speedup.
