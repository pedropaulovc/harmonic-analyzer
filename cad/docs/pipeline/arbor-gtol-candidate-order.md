# Arbor GTol vertical candidate ordering

The production full build at `3c0c4a97e69ead5f04fa760b8aa507c16143172d`
(adapter `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`) failed its
arbor-pedestal drawing layout on 2026-09-08. The selected Front GTol bank had
clear leaders but made the decorated view too tall for the drawable sheet.

## Retained native evidence

`C:/src/ha-foundations-integration/cad/out/reports/arbor-layout-failure-3c0.json`
contains the three original telemetry records. SHA256:
`b9080db69598503acc966c3d6f47ffcc5f03093bafd5689aeaefed8db653b562`.
The [tracked failure receipt](evidence/arbor-layout-failure-3c0.json) is a
byte-identical copy.

The Front record at 02:12:43.810215Z captures these actual native attempts:

| Attempt | DX, metres | DY, metres | Leader crossings |
|---|---:|---:|---:|
| right | 0.08263995640277898 | 0 | 2 |
| left | -0.12003999996478651 | 0 | 2 |
| right-up | 0.08263995640277898 | 1.4823470246941766 | 0 |

All three reported body clearance. The third was immediately accepted by the
local GTol operation. The final sheet record at 02:12:58.118935Z reports
`no_fit`: Front bounds extend from Y=0.07860512469605922 to
Y=1.6620650246941766 m, while drawable Y is 0.0127 to 0.2667 m.
No rigid translation can fit that height inside the 254 mm drawable area.
That failed run did not attempt DOWN. The successful retry below records it.

## Bounded ordering correction

`column_vertical_candidates` still returns nearest free intervals in its
documented UP/DOWN order. `_place_clear_column` now tries each side's existing
pair in increasing `abs(dy_m)` order; equal costs retain the original order.
Horizontal candidates, side order and lazy per-side generation remain unchanged.
This adds no candidate or native call, and the maximum remains six translations.

The cost is a preference for less displacement, not proof of a smaller complete
view envelope or sheet fit. A smaller candidate can still cross native text or
fail final packing. Every attempted candidate keeps actual route/body screening;
final full XML, content, attachment, body-translation and sheet checks remain
unchanged. No coordinates select geometry, and no font, scale, clearance,
tolerance or body shape changes here.

## Rerunnable ordering regression

```powershell
uv run --frozen python -m pytest cad/scripts/test_gtol_leader_policy_drawing.py `
  -q -k smaller_solver_displacement
```

The test calls the real bounded interval solver and the production attempt loop,
with native-shaped movement/read doubles. It uses the observed 1.4823470246941766 m
UP distance and an explicitly synthetic 30 mm DOWN boundary. This proves ordering,
not a native arbor DOWN outcome. It also covers nearer UP, exact ties and a
nearer prediction rejected by actual route readback. Before the fix the two
DOWN-first cases failed; four controls passed (`run-hhel8e6_`, 0.64 s).

The existing lever test deliberately expects UP first: its measured 5.403 mm UP
candidate is already nearer than its 6.643 mm DOWN candidate. That assertion,
the UP/DOWN interval API assertions, six-attempt rejection and final identity/
geometry rejection tests remain unchanged. This test file is already enrolled
by the production recipe gate's drawing-test glob.

## Native retry

The normal `drawing:arbor_pedestal` task passed on 2026-09-08 at integration
`86fda61b600996dc840d1bfce37ab3de4ed223b3`, with runtime code identical to
`2afc0a447ee331fdb9b7563a860f39e06f496b3b` and the same adapter. The integration
also contains four test-only corrections. Trace
`0x38e3a9746b464813264c2fb99318611c` ran from 02:33:30.240643Z to
02:34:36.822951Z: 66.5823 s for the drawing task and about 68.5 s holding the seat.
These are single-run timings, not a matched performance comparison.

The [tracked retry receipt](evidence/arbor-layout-retry-86f.json) preserves all
three raw records from
`C:/src/ha-foundations-integration/cad/out/reports/arbor-layout-retry-86f.json`,
byte-identically. SHA256:
`9e2d59f3390714e4f79de18c5a670935f47efebb92315dee5c4e37b22a84cf71`.

Front again rejected right and left at the same horizontal displacements above,
with two crossings each. It then accepted right-down at
`(+0.08263995640277898, -0.03358116795402392)` m, with zero crossings and clear
bodies. Top accepted right at `(+0.05582202306944563, 0)` m. Final sheet status was
`applied` after 48 explored nodes. Validation clearance remained 0.002 m and
planning clearance 0.0025 m.

The saved output hashes are:

| Output | SHA256 |
|---|---|
| cad/out/slddrw/arbor-pedestal.SLDDRW | 8da3e5cdaee241bd340e643980583a52eceae72f16b0afdd9d93cbe96be33bb6 |
| cad/out/pdf/arbor-pedestal.pdf | ff0796d2b77a696d0b107f36506e5514b2250967480f5a8c40845d24c46abb26 |
| cad/out/png/arbor-pedestal_drawing.png | 7e2840ffcf50166c5a98b2fbf77fb80da94945ff66878941901738fb77974d1a |

The native SLDPRT hash was unchanged and still matched the SHA256 recorded in
its genuine execution token:
`c901727d21b909f7011cc72d3c2a4c103215a2b73009e9345a8a1e22adb62e24`.
The token file's own SHA256 remained
`54d9cb3f99295d5eac90416e6711747dd7a9f76447c053782b6b1e20f584b24a`.
The operator used shared-read hashing because SolidWorks still held the native
files open; no close or save was added for hashing. The operator inspected the
full PNG: complete notes and views fit, without obvious text loss or collisions.

An immediate repeat of the same normal task exited zero with both part and
drawing skipped; telemetry still ended at 02:34:36. This is a targeted zero-COM
no-op, not a completed full build.

For a native replay, use the existing production checkout and genuine local
outputs under confirmed exclusive seat ownership:

```powershell
uv run --frozen python -m doit drawing:arbor_pedestal
```

An unchanged task can skip, as the repeat did. Retain task/cache telemetry to
distinguish a native run from a skip; do not replace outputs or execution tokens
to manufacture a rebuild. The normal full pipeline and visual inspection of
saved drawings and their printed output remain the merge gate. Cold reopen and
full-fleet acceptance are still pending; this targeted save/PNG result does not
establish them.
