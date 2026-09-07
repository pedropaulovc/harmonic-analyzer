# Lever named linear-pair control

This is an opt-in diagnostic, not a production layout change or a speedup claim.
The five-view lever's retained PDF shows two remaining BASIC-box conflicts:
`BarLength` (169 mm) crosses `TipCentreX` (182.80 mm) in the profile view;
`RD1` (127 mm) crosses `RD2` (177.80 mm) in the hole view. The previous radial
SpaceEvenly control selected different dimensions and did not test these pairs.

The existing owned full-recipe pilot accepts `--linear-dimensions parallel`,
only with `--target channel_lever`. It injects the recipe's existing explicit
`layout=` argument, leaving its source, manufacturing content, normal default
and original layout callback unchanged. No diagnostic module is imported by
production recipes.

Before the original callout/GTol/packing callback, the control:

1. Captures native annotation ink, exact annotation/owner/attachment handles,
   every view's native dimensions (identities, configurations, values and
   tolerance types), and the declared source parameter witness.
2. Requires the four exact named, visible BASIC linear dimensions and their
   CAD-defined values. It never selects a geometric feature by coordinates.
3. Writes the drawing-local `swDetailingDimToDimOffset` once to the maximum
   measured selected BASIC-body height plus 1 mm, and checks native readback.
4. Selects each pair by native dimension name with exact selection identity,
   then calls `IModelDoc2.AlignParallelDimensions()` once per pair. This is a
   void method: return acceptance cannot prove movement.
5. Captures the scene again. Source parameters, native identities, dimension
   values/configurations/tolerance types, annotation semantics/formats and all
   unselected ink must remain unchanged. At least one actual anchor or displayed
   stroke must move in each pair; the receipt retains both coordinates and ink.
6. Runs the original layout and unchanged final GTol/dimension crossing gates.
   Successful construction still requires the pilot's existing source hashes,
   save/reopen and manufacturing/attachment checks. Failure retention remains
   active, including the separate unsaved-reference semantic error when present.

No model-value setter, native leader router, coordinate search, retry, new
rebuild, or app-global preference is introduced. The changed document preference
belongs only to the owned diagnostic drawing. It is not restored before final
acceptance because persistence of that candidate drawing is part of the test.

## Primary API contract and limits

The installed SW2026 bundle contains
`types/IModelDoc2/AlignParallelDimensions.md`: selected linear dimensions,
no arguments, void return. Its `docs/swconst/DP_Dimensions.md`, row
"Dimension to dimension offset", explicitly associates this document property
with baseline dimensions and Align Parallel/Concentric, measured in metres.
It says displayed tolerances double the offset. This experiment does **not**
assume how BASIC boxes affect that rule or how the native method ranks the pair.
It measures actual movement and delegates final clearance to the existing gate.

Official references:
[AlignParallelDimensions](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~AlignParallelDimensions.html),
[dimension document properties](https://help.solidworks.com/2026/english/api/swconst/DP_Dimensions.htm),
[SetUserPreferenceDouble](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SetUserPreferenceDouble.html).

## Re-run

In a frozen checkout with its matching venv/imported adapter and the coordinated
SolidWorks seat, use the existing pilot invocation and add these two options:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
# HARMONIC_DIAGNOSTIC_SW_PID must be the already-verified running PID.
uv run python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --candidate HEAD --source-root '<exact guarded part source directory>' `
  --guard-root '<independent original hash guard directory>' `
  --target channel_lever --factory prepared --linear-dimensions parallel
```

The parent entry acquires the existing seat lock; do not invoke `--worker`
directly. The report includes actual recipe/helper/imported-adapter fingerprints.
The `linear_dimension_control` receipt and `diagnostic.linear_dimensions.control`
span include diagnostic measurements, so they are not production layout timing.
Native effectiveness and final readability remain unproven until this control
runs; offline tests establish only its selection, scope and acceptance contract.

## First native attempt: nominal comparison rejected before mutation

At root `e9b3fde6` / adapter `e77bfda4`, receipt
`cad/out/reports/datum-policy-wepq18dc/pilot.json`
(SHA-256 `e2edccbb7923b050da32dd002630a1ca1c28566ab187e40f5218d774461669a2`)
captured all four candidates, then rejected `BarLength` before any spacing setter
or alignment call. The source identity, native type, BASIC type, visibility and
owner checks were correct. Captured SI values were:

| Named dimension | Native value (m) | Nominal (m) | Difference (nm) |
| --- | ---: | ---: | ---: |
| BarLength | 0.16900000007399998 | 0.169 | +0.074 |
| TipCentreX | 0.182799999906 | 0.1828 | -0.094 |
| Hole-view RD1 | 0.127 | 0.127 | 0 |
| Hole-view RD2 | 0.1778 | 0.1778 | 0 |

The original 1e-12 m nominal comparison was narrower than the observed native
model representation. The diagnostic now uses **1e-9 m absolute, zero relative
tolerance only when matching these four native values to their nominal design
values**. This is a bounded 1 nm recognition allowance, not a manufacturing
tolerance, a universal SolidWorks precision claim, or permission to mutate a
parameter. Exact native parameter handles and exact before/after raw values,
configuration, BASIC/other tolerance type and source witnesses remain mandatory.
The retained-value regression failed before this correction; a one-ULP parameter
change during the command still fails, while a 2 nm nominal mismatch also fails.
No native spacing effect was measured by this stopped attempt.
