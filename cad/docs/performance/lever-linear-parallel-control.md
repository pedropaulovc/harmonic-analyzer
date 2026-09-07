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
3. Recognizes each measured rectangular BASIC frame, its separate horizontal
   dimension line and two vertical extensions by geometry, not segment index.
   Requires the observed nested spans, shorter-above-longer rank and arrow
   decorations horizontally clear of the other body. Unknown geometry fails.
   Derives paper pitch from the largest body-top reach above its own line plus
   1 mm. Before each pair, writes and reads back that view's calibrated
   drawing-local `swDetailingDimToDimOffset`: paper pitch for the model/type11
   pair, twice paper pitch for the reference/type2 pair. Both must have scale 0.5.
4. Selects each pair by native dimension name with exact selection identity,
   then calls `IModelDoc2.AlignParallelDimensions()` once per pair. This is a
   void method: return acceptance cannot prove movement.
5. Captures the scene again. Source parameters, native identities, dimension
   values/configurations/tolerance types, annotation semantics/formats and all
   unselected ink must remain unchanged. At least one actual anchor or displayed
   stroke must move in each pair; the receipt retains both coordinates and ink.
   The fresh measured line/body clearance must also be at least 1 mm (1e-10 m
   numerical classification allowance). This is separate from exact native
   parameter-value and semantic mutation checks.
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
It says displayed tolerances double the offset. It does not specify the observed
model/reference difference below. The gains 1 and 0.5 are calibrated only to the
exact four named dimensions, source categories, display types and scale 0.5 in
the retained trial. They are not a universal view-scale or BASIC-doubling rule.
The control measures actual movement and clearance; the original final full-sheet
crossing gate still decides whether later arrangement preserves readability.

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
The revised calibrated candidate's effectiveness and final readability remain
unproven until it runs. Offline tests establish only its measurement, selection,
scope and acceptance contract, including the retained failing native geometry.

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

## Native movement disproved the original spacing formula

Receipt `cad/out/reports/datum-policy-k5mypm3x/pilot.json`
(SHA-256 `c678cdf0b4f3b9f8b56524e0a540731ad78b533f859e8a5296919a409a0b98c0`)
captured complete controls before a separate keyword-only callback error.
The same requested document offset, 6.5798666667 mm, produced these paper pitches:

| Pair | Source / native display type | View scale | Actual pitch | Pitch/request |
| --- | --- | ---: | ---: | ---: |
| BarLength / TipCentreX | model / 11 | 0.5 | 6.5798666667 mm | 1 |
| RD1 / RD2 in hole view | drawing reference / 2 | 0.5 | 3.2899333333 mm | 0.5 |

The front native call took 10.5405 ms and the hole call 10.3532 ms. TipCentreX moved
down 0.5798666667 mm; hole RD2 moved up 2.7100666667 mm. Exact source, dimension,
layout and unselected-ink witnesses passed. Movement was real but insufficient:
all four measured BASIC bodies were 5.5798666667 mm high, starting 1.1012498236 mm
above their own dimension line. Their upper reach was therefore 6.6811164903 mm.
The resulting short line penetrated the long BASIC body by 0.1012498236 mm in the
front and 3.3911831569 mm in the hole view.

After the callback fix, the full trial
`cad/out/reports/datum-policy-0gv84nhn/pilot.json`
(SHA-256 `36b6955fc04d231a167fb4e54f4881f6ca22a6426bb49852d967ebaa3e7982e5`)
failed the unchanged final crossing gate with three pairs (front BarLength into
TipCentreX, hole RD1 into RD2, and hole RD2 into RD1), not the previous two.
Its recipe took 157.9774 s; it was not an accepted drawing or a speedup.

The revised single-step candidate uses measured upper reach plus 1 mm:
**7.6811164903 mm paper pitch**, with predicted document requests of
7.6811164903 mm for the front and 15.3622329806 mm for the hole view. The measured
extension stations and arrow boxes are horizontally outside the other BASIC
body, so this pitch addresses the observed line/frame conflicts without moving
feature identities or inventing a leader route. The parser rejects geometry that
does not establish those conditions. No retry or growing search is introduced.

The exact relevant native body/stroke/decoration subset is committed in
`cad/scripts/diagnostics/_linear_pair_k5mypm3x.py`, imported by the regression and
enrolled in `check:recipe`. The test recognizes all four real shapes, derives
the requests above, and rejects both retained after-arrangement clearances.
It also rejects movement without clearance, unsupported source/type/scale,
extra/jogged/ambiguous/open/diagonal geometry, unsafe arrows and value mutation.
The original body-height-plus-1 mm formula assertion was replaced only after its
native contradiction was explicitly raised; manufacturing equality assertions
and final crossing gates are unchanged.
