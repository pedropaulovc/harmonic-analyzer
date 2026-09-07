# Cone-tip source-owned reference text

Production authors the observed reference prefix/suffix in the part build and
verifies their import read-only. The native source build, clean-before-finalization
import control and full owned drawing/cold replay passed; the latter ran at
`f6370560303f9025f6cd48ab9230edc0fd0410dd` with a visually inspected built PNG.
This does not complete the affected-build/final-stack gate. Geometry, marked
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
Execution requires confirmed exclusive seat ownership and explicit current PID;
testing is already authorized, not a request for another user approval.

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

The original native validation sequence was:

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

## Native source build and clean import

The real cache-disabled `doit -a part:cone_tip_adjuster` build at frozen
`c77ed41eb66e914737bc14ba73a5420f1b4d8cf8` passed: task 80.443439 s,
`part.build` 79.301386 s, trace `0x87d900f724ad3b4518891e2a04249acd`.
The 83,667-byte saved part and its producer execution token both read
`18d0c1669c8de923420655d621f58d24afe404bc1d3a5a787930ebeeb2fefbf2`.
The prior `f3578ac2...48468` part and token remain in
`cad/out/reports/tip-before-reference-authoring-dd89429e19184220a24ce86cb031b517/`.

The subsequent owned-copy control at that same frozen head passed through
the drawing recipe to `clean_before_finalize`: all **105 observations were
clean**, ending at 33.2241202 s. Receipt:
`cad/out/reports/source-dirty-ioy1d3sh/source-dirty.json`, SHA-256
`dfda3b758b11d241ff29d16ee193505da786478c05d5ddd922a32c9a917e56d1`.
The reopened part's two observed BodyDiaDim displays retained prefix/definition
`(<MOD-DIAM>`, suffix/definition `)`, thread-above `5/16-18 UNC-2A`, empty
below fields, and numeric visibility `True`. The exact imported presentation
checks passed without a drawing-side text write.

Comparing the ten observed source-dimension records with the earlier source
bank, after removing only the diagnostic document-name suffix and applying
those four intended fields to the two BodyDiaDim display rows, found no other
difference. All observed values, tolerance bounds/types, markings and precision
were unchanged. This is a dimension/display-bank comparison, not a complete
BREP comparison. Original/copy bytes stayed at the new SHA throughout; owned
cleanup preserved the already-open clean source, with no probe/cleanup error.

The acceptance manifest and its two exact-pin fixtures now name this actual
builder output. No token restamp, automatic pin discovery or diagnostic source
save was used. The control intentionally stopped before finalization, so native
drawing save, cold drawing reopen and PDF/PNG were not proved by that control.
The later full replay below supplies the drawing evidence; the full affected-build
gate remains separate.

## Full owned drawing and cold replay, 2026-09-07

At frozen `f6370560303f9025f6cd48ab9230edc0fd0410dd`, the prepared-factory
`cone_tip_adjuster` row passed in
`cad/out/reports/datum-policy-e0vlt1wm/pilot.json`, SHA-256
`66a97d1528ee5eefc6ac85ee24f2e9115946b32f843c55100eefb29519ed27b5`.
The original and uniquely copied source retained the authored `18d0c166...efbf2`
identity above, including after recipe save, closing all owned documents,
fresh drawing/source reopen and final close. All five required source dimension
records and configuration `Default` matched before, after and cold; the existing
same-session source-handle checks also passed. This is the named dimension bank,
not full in-memory source immutability.

Built/cold drawing semantics, measured annotations and view layout were exact:
the comparator recorded zero rejected, coordinate-roundoff or zero-Z differences.
Native drawing/PDF/PNG artifacts were retained. The main runner inspected the
built PNG, including the reference diameter and unchanged thread callout. There
was no separate cold PDF/PNG export or pixel-equivalence comparison.

The recipe took **24.9530979 s**, including **1.6674348 s** setup. Separate
prepared-cache miss/hit accessors took **46.5258049 / 0.0519504 s**. The entire
three-target pilot took **651.7559998 s**, including guards, preparation and
cold witnesses but excluding parent lock/attach and outer cleanup. Concurrent
offline tests used the same host; this is not an isolated performance comparison.

The second row, `cone_pivot_screw`, also passed; the batch nevertheless failed
on the third target, `cone_gear_shaft`, at its explicit pivot-journal-finish
attachment check. The shared ownership receipt (SHA-256
`f5c57baa5383ec38faa10368a6dcdb3057c43bb55ea3f77b38e72990866ad7d5`)
retains that probe error, no cleanup error, and the same already-open clean
cone-tip part as its initial/final inventory. All five protected originals and
template/cache/helper/adapter guards matched; runtime final errors were empty.
The [fastener report](../../scripts/diagnostics/fastener_source_manifest.md#full-cold-replay-of-both-fasteners-2026-09-07)
records both passing rows without treating the failed batch as green.
