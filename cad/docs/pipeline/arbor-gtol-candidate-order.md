# Arbor GTol vertical candidate ordering

The production full build at `3c0c4a97e69ead5f04fa760b8aa507c16143172d`
(adapter `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`) failed its
arbor-pedestal drawing layout on 2026-09-08. The selected Front GTol bank had
clear leaders but made the decorated view too tall for the drawable sheet.

## Retained native evidence

`C:/src/ha-foundations-integration/cad/out/reports/arbor-layout-failure-3c0.json`
contains the three original telemetry records. SHA256:
`b9080db69598503acc966c3d6f47ffcc5f03093bafd5689aeaefed8db653b562`.

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
No DOWN native result is retained, so its clearance and final fit remain unknown.

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

## Native validation still required

After the parent verifies the frozen integration and owns the exclusive native
seat, retry the normal `drawing:arbor_pedestal` task in the existing native
checkout. Retain every attempted displacement, native crossings and final
packing result. Do not infer DOWN success from these offline controls. The
normal full pipeline and required saved/printed visual checks remain the merge
gate; this ordering change alone is not native drawing acceptance.
