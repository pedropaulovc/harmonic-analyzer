# Cone-tip source-owned reference text

The production candidate authors the observed reference prefix/suffix in the
part build and verifies their import read-only. Native source-build, cold-import
and printed acceptance of this candidate are still pending. Geometry, marked
dimensions, tolerances, catalog thread and drawing layout are unchanged.

## Retained native attribution

At `5e7737560d1efba42ff03d75376565e3b4710962`, the normal-factory first-dirty
control stopped after `recipe.set_reference_dimensions`, at 24.6160887 s.
There are **62 total events: 61 clean, then one dirty**. The report is
`cad/out/reports/source-dirty-h1h1oz50/source-dirty.json`, SHA-256
`5a5d5356b1f471f10246a5a6a7a32ec78a3fc59ac82fba9f0d6fc1c9baa630c7`.

Only `BodyDiaDim@BodyProfile` changed, in both observed feature display rows:

| Native fields | Before | After |
| --- | --- | --- |
| Prefix 1 / definition 5 | `<MOD-DIAM>` | `(<MOD-DIAM>` |
| Suffix 2 / definition 6 | empty | `)` |
| Above 3 / definition 7 | `5/16-18 UNC-2A` | unchanged |
| Below 4 / definition 8 | empty | unchanged |

Numeric visibility remained native `True`; the diameter's raw system value
remained `0.006200000046` m. All ten observed source dimension identities,
values, tolerance/BASIC fields and remaining display properties were unchanged.
This is group-boundary attribution, not an individual setter timing or proof
that every source property was inventoried. No save/export occurred. Original
and copied part hashes stayed
`f3578ac2b2ab95e478bc7bd72c316ebab057c125d5244af6fa2c3e12f4d48468`;
ownership cleanup and baseline preservation passed.

The rerunnable control and command are in
[cone-tip first-dirty control](cone-tip-first-dirty-control.md). To replay that
historical call shape, use its exact `--candidate 5e773756` and the pinned
pre-migration part bytes; do not treat a newly rebuilt source as that control.
Execution always requires a fresh native seat grant and explicit current PID.

## Implementation and deliberate contract changes

`cone_tip_adjuster_spec.py` supplies two shared literal maps. The builder calls
the existing `author_model_callouts` after marking/tolerancing and after the
thread-above callout, before its normal save. Prefix/suffix modes set only
native selectors 1 or 2, then require the requested literal in its ordinary and
definition field, with all six other fields and numeric visibility preserved.
The full text readback repeats after the documented `GraphicsRedraw2`. Exact
current/active part and source-parameter identity are checked around writes;
the existing unique feature/name resolver rejects missing or ambiguous targets.
No rebuild, save, configuration switch or visibility setter is added.

The existing drawing verifier retains its explicit expected view, source PART,
feature/name and native source-parameter checks. For these new modes it also
requires all eight imported fields to equal the independently resolved source
display fields, with numeric visibility `True` on both. It performs no writes.
Existing above/below behavior is unchanged. The unused reference APIs remain.

Two deliberate test contracts were disclosed and approved: the tip-specific
assertion requiring a drawing-side reference writer, and the fleet's original
72-row author/verify inventory. Tests now require source authoring/read-only
verification and **exactly two additional cone-tip rows**, while retaining all
72 historical callout rows and the 35-part consumer set. The original inventory
fixture remains unchanged.

Bundled `IDisplayDimension.SetText`, `GetText`, `ShowDimensionValue`,
`swDimensionTextParts_e`, `IModelDoc2.GraphicsRedraw2`, `ISldWorks.ActiveDoc`
and `IsSame` contracts and examples were read. SetText is void; GetText(0) is
invalid. No claim is made that ShowParenthesis plus its documented redraw fails:
the inherited unsupported claim was corrected, not used as a decision gate.

## Offline and remaining native checks

The new 35-case first pass failed before implementation on unsupported
prefix/suffix locations. Final focused/adjacent tests passed **422 tests in
27.47 s**, receipt `pytest-telemetry/run-6in2g2vp`, including source-dirty,
source-authoring, source-save boundaries, graph and part-isolation suites.
Additional cases cover unknown/malformed native identity and numeric suppression.
These are offline doubles/static checks, not native persistence or performance.

The helper remains part-safe and is already in 35 part dependency closures;
changing its bytes invalidates those recipes even though only cone-tip uses the
new modes. The changed tip spec also reaches cone-tip-block, already in those
35. Do not reuse old native acceptance as evidence for the new recipe digest.

After review/integration, the native runner should:

1. Build `part:cone_tip_adjuster` through normal doit, retaining the new artifact
   and execution-token hashes. Do not pre-edit source pins or reuse the old SHA.
2. Reopen that source and verify full native fields 1–8, numeric visibility,
   values/tolerances/BASIC and exact parameter ownership; record the new pin.
3. Run the existing owned full-recipe pilot with `--target cone_tip_adjuster`
   and the prepared factory, on a unique exact copy of the new source. Preserve
   immutable-copy/source guards through save, cold reopen and PDF/PNG rendering.
4. Inspect `(Ø6.20)`, the unchanged `5/16-18 UNC-2A` thread callout and the
   complete sheet. All source/attachment/layout/printed gates remain mandatory.
   Rebuild the affected closures and run the final full-stack gate before merge.

No COM, source part rebuild, cache publication or source-pin change was executed
while preparing this candidate. A fresh fillister whole-text migration is a
separate follow-up, not implicitly covered by these reference-field checks.
