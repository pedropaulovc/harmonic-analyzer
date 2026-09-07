# Crankshaft edge-curve readback control

This is a diagnostic, not a production geometry-witness change. The retained
single-part invocation failed its coverage gate after capturing all eight edges;
the separate paired-source invocation subsequently passed the native LINE,
CIRCLE and PinHole intersection controls, as recorded below.
The line/circle reader and the MODEL/VIEW identity and cold-reopen gates remain
unchanged. That source-reader proof is not drawing/cold acceptance or a
performance improvement claim.

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

## Paired-source positive-control route

After source review and an explicit shared-seat grant, the main native runner can
use its unchanged venv and actual imported adapter:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<freshly verified PID>'
uv run --no-sync python cad/scripts/diagnostics/probe_crankshaft_curves.py `
  --mode paired_sources `
  --source C:/src/harmonic-analyzer/cad/out/sldprt/crankshaft.SLDPRT `
  --rocker-source C:/src/harmonic-analyzer/cad/out/sldprt/rocker-arm.SLDPRT
```

The source SHA must equal the existing manifest:
`3c0224617322e3a10cca4a5c52e2b0a3b4c82e7be7969c0b21faf4db58b4cd94`.
The rocker source is independently pinned to
`3bfb6da45b91e5a73b24c74baf81141899149e3c327aa943930baed3fba4d4a0`.
Both originals are protected and checked before either part opens. Rocker runs
first, capturing the first actual native LINE edge with the unchanged analytic
reader. After its owned copy closes, crankshaft must supply both CIRCLE and
exact `PinHole`-adjacent `INTERSECTION_TYPE` 3004 B-curve rows. The retained paired
invocation below establishes that three-kind coverage for its pinned sources.
There is no retry or second stage after a failure. A parent receipt links both
child receipts (including a failed child), captures stage/total time, and rechecks
both originals and every created copy at the end.

Only unique-basename bytecopies are opened. The shared attach-only lifecycle
protects existing documents and closes only owned documents without saving.
The report retains initial/final helper and actual imported-adapter fingerprints,
source/copy hashes, dirty flags, the existing per-part named dimension manifest
(five crankshaft dimensions; rocker uses its existing pilot manifest), and exact
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
controls. The named `single_part_negative` mode retains the original assertion
requiring both analytic controls and a nonanalytic `PinHole` edge in the same
crankshaft. It is a reproducible negative coverage control, not the default happy
path. Invoke it with `--mode single_part_negative --source <crankshaft-path>`
and no `--rocker-source`. The paired mode does not remove its missing-LINE failure.
All attempted rows are retained rather than inventing another shape or selection.

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
and bool-plus-array for the two spline getters. The retained native crankshaft
receipt below now verifies those return shapes for its actual intersection curves.

`IsBcurve` explicitly includes intersection, ellipse, trimming and surface
parametric curves; line/circle checks take precedence. `GetBCurveParams5`
documents modeler tolerance as relevant to representation accuracy. We neither
change that tolerance nor equate returned spline data with exact BREP identity.
This control does not sample a curve into an approximate acceptance witness.

Untested at that stage: the paired rocker LINE control, repeated/cold parameter stability,
original/selected/attached drawing-context equivalence,
and a full crankshaft recipe through save/reopen/printed acceptance. Those
remain separate gates before extending a production diagnostic comparator.

Offline verification: 205 focused/adjacent tests passed; Ruff passed. The new
fixtures include native retval/out failures, malformed/nonfinite arrays,
closed-nonperiodic versus periodic curves, rational coordinates retained raw,
same-radius wrong-face rejection, and owned-session cleanup/error preservation.
Those results predate the paired extension; they did not establish native success.

## Retained single-part native failure

At root `c05953787a6e38fee440422da775b9e366c06068`,
`cad/out/reports/crankshaft-curves-zj92q9yo/curves.json` has SHA-256
`77c14f47269c00088fd88cd46c3f0d211a43260abd705fd53f2f18969ba0b647`.
The read-only invocation took **30.9728903 s** and remains **failed** with
`native line/circle/PinHole nonanalytic coverage incomplete`.

All eight rows were captured: indices 1–6 are CIRCLE 3002; indices 0 and 7 are
`PinHole` face 0 intersections, type 3004 with `IsBcurve=True`. Neither is a line.
Both intersections are closed, periodic, 3D, order 4, with 60 control points and
61 knots. `GetBCurveParams5(False, False, False, True)` and both complete array
getters succeeded. The raw receipt retains their distinct parameter domains;
no coefficients, trim, or endpoints were rounded.

Dirty flags remained false; original/copy SHA-256 stayed exact, final guard
errors were empty, and only owned documents were closed without saving. There
was no drawing, save, export or BREP modification. This establishes the tested
source API call shape, not drawing-context or cold acceptance. The paired
extension retains the original assertion verbatim, with a fixture reproducing
this eight-row/no-LINE coverage failure.

Paired extension offline verification: 227 focused/adjacent tests passed in
3.00 s (`pytest-telemetry/run-3ch22c6w`); Ruff and `git diff --check` passed.
Tests include either wrong original rejected before any copy opens, first-copy
mutation during the second stage, failed-child receipt retention and unrelated
document survival. This offline checkpoint preceded the paired native invocation
recorded next; it was not itself native proof.

## Paired native positive control

The explicit paired invocation passed at root `925dace0`, adapter `25bc99b1`
and licensed PID 31860 with remote caching disabled. Receipt
`paired-curves-vzrh7ohz/paired-curves.json`, SHA-256
`84f3f85e4abf8d64f576a3621ac85e9beebece4ca68ef5c619fa0e45e3bb9eee`,
records 47.075 s total. Rocker-arm edge 1 supplied the LINE control (19.277 s);
crankshaft supplied six CIRCLE edges and both exact PinHole INTERSECTION 3004
edges, indices 0 and 7 (27.412 s). Every attempted raw edge row was captured.

The respective child receipt hashes are
`00246115a565c8a70aff3164159f5aca5c488286a7976b900e586d77be10f279`
and `a41bad07a9170d5443dee60319eccf7e0f6bf1be70deb9c790ea163df7b1cfed`.
Both source dirty flags stayed false. Original and owned-copy hashes retained
their exact pinned values, including the first copy after the second stage;
aggregate errors and final guard errors were empty. Owned cleanup succeeded.

This proves the paired source-reader call shapes, not drawing attachment or
cold serialization equality. The historical crankshaft-only missing-LINE
receipt remains a failed negative control. Integrated paired/fleet/preflight
tests passed 210 tests in 5.31 s (`run-w1vvvgj0`).
