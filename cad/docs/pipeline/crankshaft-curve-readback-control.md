# Crankshaft edge-curve readback control

This is an unexecuted diagnostic, not a production geometry-witness change.
The line/circle reader and the MODEL/VIEW identity and cold-reopen gates remain
unchanged. No native acceptance or performance improvement is claimed.

## Reproduced boundary

At production `56223c49fa26fd4b1c133fce13adf4586685d06c`, the crankshaft
owned drawing pilot stopped after 27.803813 s when the VIEW observer inspected
the cross-hole true-position edge, before inserting that FCF:
`UnsupportedGeometry('edge is neither a line nor a circle')`.
This says nothing about the native curve API's ability to represent that edge.

Retained receipt:
`cad/out/reports/datum-policy-qzwh2cwm/pilot.json`, SHA-256
`5988c9ce981ee4352ce4651e56b94ea5b6e8651400bbf40be730acf6f0965700`.
The four protected originals and the owned crankshaft copy kept their exact
hashes; runtime final guards were empty. Ownership preserved the two initially
open pivot documents. Failure-capture outputs are not completed recipe acceptance.

## One bounded native invocation

After source review and an explicit shared-seat grant, the main native runner can
use its unchanged venv and actual imported adapter:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<freshly verified PID>'
uv run --no-sync python cad/scripts/diagnostics/probe_crankshaft_curves.py `
  --source C:/src/harmonic-analyzer/cad/out/sldprt/crankshaft.SLDPRT
```

The source SHA must equal the existing manifest:
`3c0224617322e3a10cca4a5c52e2b0a3b4c82e7be7969c0b21faf4db58b4cd94`.
Only a unique-basename bytecopy is opened. The shared attach-only lifecycle
protects existing documents and closes only owned documents without saving.
The report retains initial/final helper and actual imported-adapter fingerprints,
source/copy hashes, dirty flags, five named source values/tolerances and exact
same-session dimension identities. Cleanup errors cannot hide the primary
failure or prevent final hash checks. No source template is opened.

The probe reads one solid body's complete edge array, bounded at 256 entries,
and records exact `IsSame` membership of each edge's adjacent faces in the
named `PinHole` feature's returned faces. All adjacent surface types and cylinder
parameters are retained. Feature ownership is not assumed exclusive: SolidWorks
documents that a face may belong to multiple features. This model-context
inventory does not yet identify which edge a drawing view returns first.

For every edge it records native curve type, line/circle/B-curve flags,
`GetEndParams()` and the complete `GetCurveParams3()` trim, including sense/tag.
Line/circle rows also call the existing unchanged geometry reader as positive
controls. The bounded probe fails if either analytic control or a nonanalytic
`PinHole` edge is missing; it retains all attempted rows rather than inventing
another shape or a fallback selection.

For a nonanalytic `IsBcurve()` row, its single call shape is:
`GetBCurveParams5(False, False, not native_periodic, native_closed)`.
It does not request cubic/non-rational conversion or change the observed
closed/periodic form. It records dimension, order, periodicity, control/knot
counts and the complete retval/out arrays from `GetControlPoints()` and
`GetKnotPoints()`. Array shape, native status, numeric finiteness and metadata
consistency are checked without rounding or rational-coordinate normalization.
Raw values preceding any rejection remain in the receipt.

## API basis and remaining limits

Bundled official method pages were read for `ICurve.Identity`, `IsBcurve`,
`GetEndParams`, `GetBCurveParams5`, `IEdge.GetCurveParams3`, the spline data
properties/getters and the body/feature/face enumeration calls. The R2026x
generated wrapper confirms bool-plus-four-out parameters for `GetEndParams`
and bool-plus-array for the two spline getters. Native return shapes remain
part of this first control, not something the test doubles establish.

`IsBcurve` explicitly includes intersection, ellipse, trimming and surface
parametric curves; line/circle checks take precedence. `GetBCurveParams5`
documents modeler tolerance as relevant to representation accuracy. We neither
change that tolerance nor equate returned spline data with exact BREP identity.
This control does not sample a curve into an approximate acceptance witness.

Untested: the actual nonanalytic native kind and return shape, repeated/cold
parameter stability, original/selected/attached drawing-context equivalence,
and a full crankshaft recipe through save/reopen/printed acceptance. Those
remain separate gates before extending a production diagnostic comparator.

Offline verification: 205 focused/adjacent tests passed; Ruff passed. The new
fixtures include native retval/out failures, malformed/nonfinite arrays,
closed-nonperiodic versus periodic curves, rational coordinates retained raw,
same-radius wrong-face rejection, and owned-session cleanup/error preservation.
No native invocation has been run for this diagnostic.
