# VIEW intersection-curve witness

This is diagnostic-only support for the existing crankshaft cross-hole role.
It does not change its production selector, PMI specification, source part or
the generic attachment reader. Drawing-context and cold native acceptance are
still required; source API readback alone does not establish either.

The original exact cold-bank contract below is historical. The
[native persistent-edge cold candidate](cold-intersection-edge-identity.md)
retains those raw banks and the live comparator, but introduces a separate
caller classification for an integer CurveTag change after native same-edge
proof. Its native cold acceptance is not yet established.

## Evidence and boundary

The [source curve control](crankshaft-curve-readback-control.md) retained two
`PinHole`-adjacent edges with `Identity=3004`, `IsBcurve=True`, closed/periodic
3D order-4 representations, 60 controls and 61 knots. The complete getter and
trim rows are preserved in
`cad/scripts/fixtures/crankshaft-intersection-curves-zj92q9yo.json`.
They come from the **failed** single-part receipt
`cad/out/reports/crankshaft-curves-zj92q9yo/curves.json`, SHA-256
`77c14f47269c00088fd88cd46c3f0d211a43260abd705fd53f2f18969ba0b647`.
That failure remains mandatory because the crankshaft has no LINE control;
the separately guarded paired-source mode supplies that positive control.

The fixture's two JSON objects were copied with `JsonElement.GetRawText`, not
reserialized as floating-point values. Offline comparison against both original
objects passed after CRLF-to-LF normalization only: every numeric spelling,
boolean, parameter, array entry and metadata field is retained. The fixture is
source-context data, not a fabricated drawing-context receipt.

## Diagnostic change

`_recipe_view_entity_acceptance.geometry` first uses its unchanged analytic
reader. Only an unsupported EDGE enters `_view_intersection_curve_witness`;
the new reader requires exact integer kind 3004 before requesting spline data.
Other unsupported kinds and malformed analytic reads still fail.

The new reader reuses `_raw_edge_curve.read_edge`, preserving all native status
and data: curve kind/predicates, complete `GetEndParams`, `CurveType`, `CurveTag`,
sense, edge parameter range, endpoints, getter arguments, spline metadata and
both complete retval/out arrays. Arrays have bounded shapes and finite numbers.
There is no sampling, rounding, rational-coordinate normalization, modeler
tolerance change, BREP write, or fallback identity acceptance.

Argument, selected and attached reads retain raw evidence in the existing stage
report, including partial getter failures. Initial geometry is detached from
mutable returned arrays. Exact original/selected/attached `IsSame`, annotation
view ownership, type, visibility, non-dangling and on-sheet checks remain.
Fresh cold role resolution uses reopened handles; the existing pilot still
compares the whole built/reopened entity banks with `!=`. Even a one-ULP
coefficient/domain change or a changed curve tag is a failed exact witness,
not a tolerated serialization difference. No MODEL comparator changes.

Bundled `GetBCurveParams5`, `GetEndParams`, `Identity`, spline getter/periodicity
pages, `GetCurveParams3` and the B-curve C# example were read. The method documents
that modeler tolerance affects representation accuracy: these coefficients are
an additional raw witness alongside native identity, not a claim of exact BREP
serialization. The call does not request cubic/non-rational conversion or alter
the curve's observed closure/periodicity.

## Reproduction and remaining native gate

The focused fixture and observer regression suite is COM-free:

```powershell
uv run --no-sync python -m pytest -q `
  cad/scripts/test_view_intersection_curve_witness_drawing.py `
  cad/scripts/test_view_recipe_acceptance_drawing.py `
  cad/scripts/test_crankshaft_curve_readback_drawing.py
```

Tests retain both full native rows, reject failed/nonfinite/short arrays and
unproven kinds, reject equal-geometry substituted handles and wrong views, use
fresh cold handles, and reject one-ULP controls/knots/trim/domain changes.
Existing line/circle positive controls bypass the new reader entirely.

Offline verification: 365 focused/adjacent tests passed in 7.33 s
(`pytest-telemetry/run-mpmrqwgn`); Ruff and `git diff --check` passed. These are
test-double/retained-data results, not a new native drawing invocation.

After review, the main runner can use the existing owned full-recipe pilot with
`--target crankshaft`; no new runner is introduced. It must still pass source
and copy hashes, complete annotation inventory/content/attachment checks, native
save, cold role and drawing checks, PDF/PNG output and visual inspection. A
coefficient or curve-tag difference will remain explicit in the raw stage rows
and fail rather than being classified harmless without evidence.

## First native VIEW result

At `b1a12523`, adapter `25bc99b1` and PID 31860, the prepared-factory crankshaft
pilot reached and inserted the cross-hole true-position FCF successfully.
Receipt `datum-policy-e9ii3a93/pilot.json`, SHA-256
`dbaddaeea87584ed969ab67262ac7afa81d212f27afbf74c027248f8ed7ae918`,
retains identical raw 3004 rows for the requested edge, actual selection and
inserted attachment, with exactly one attachment of type 1. Native identity and
owning-view checks passed at those stages. This includes all coefficients,
knots, trim/domain fields and curve tag (434454 in this session).

The overall pilot remains **failed**: the later bearing-journal surface finish
hit the separate type-46 silhouette `IsSame` rejection. Built/final and cold
banks were therefore not reached. Recipe/pilot times were 38.280/160.230 s.
Failure evidence completed with no secondary errors, original/copy source
hashes stayed exact, owned cleanup succeeded and final runtime guards were
empty. This establishes immediate VIEW selection/attachment readback, not full
crankshaft or cold-serialization acceptance.
