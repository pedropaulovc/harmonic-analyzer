# Fillister source-owned whole dimension text

This additive candidate follows the cone-tip reference-field migration at
`c77ed41eb66e914737bc14ba73a5420f1b4d8cf8`. It moves the fillister thread-only
display into source authoring and makes the drawing verify its full inherited
state. Native authoring, save/cold import and printed acceptance are pending.

## Fresh-source native evidence

The normal `part:fillister_screw` build at `5e773756` produced a 79,634-byte
source and identical execution token with SHA-256
`5ca2e24ed0a67672d77645c8ddbc5ada3806ecec763794a3652338044692be2a`.
The main runner recorded task 58.407867 s / part 57.138711 s, trace
`0x2100fc633482e116f0dfa7580b977644`. This is fresh source provenance, not the
performance of the proposed migration.

The subsequent first-dirty control is
`cad/out/reports/source-dirty-nesqj5vt/source-dirty.json`, SHA-256
`a159a7a7e72e7ac1c691eeb81cb99bd33f905ad40a0dcb612191782559137ebe`.
Its 46 events comprise **45 clean, then one dirty**, after
`recipe.set_dimension_text` at 21.7003553 s. Baseline getters stayed clean.
Only `ShankDia@ShankProfile` changed: prefix 1 and definition 5 went from
`<MOD-DIAM>` to `#4-40 UNC-2A`. Fields 2/3/4/6/7/8 remained empty.

Crucially, both observed source display rows (`Shank` and `ShankProfile`)
still reported numeric visibility **True**. This does not prove the drawing's
visibility state, source-side SetText(All) behavior, persistence or imported
visibility. All ten observed native parameter identities/values/tolerances
were unchanged; `ShankLg` retained `UNDERHEAD LENGTH`. The source/copy SHA
above matched before and after; no save/export, reset or retry followed the
first-dirty stop, and baseline/owned cleanup passed.

The existing [fillister first-dirty control](fillister-first-dirty-control.md)
is the rerunnable historical witness. Use candidate `5e773756` and this fresh
source SHA to reproduce this receipt, not the older part pin in its original
pre-run command. Execution needs confirmed exclusive seat ownership and the
explicit current PID, not another user approval.

## Complete source and drawing contract

`fillister_screw_spec.DIMENSION_TEXT` maps the exact `ShankDia` to the existing
catalog-derived `THREAD_DESIGNATION`. The builder authors it on `ShankProfile`
after marking/tolerancing and the distinct `ShankLg` callout, before normal save.
No part geometry, values, configuration, notes, tolerances or view layout change.

The existing author/verifier gain explicit `location="all"`. The author invokes
documented **void SetText(0, designation)**, then requires:

- Fields 1 and 5 equal the exact designation.
- Fields 2/3/4/6/7/8 are empty.
- `ShowDimensionValue` is native `False`.

This is the entire intended replacement, not a prefix-only equivalence.
GetText is only called with 1–8 (0 is invalid for that getter). Full readback
repeats after the documented GraphicsRedraw2. The same exact current/active part
and named native source parameter guards from the tip path remain. The author
does not save, rebuild, activate, change configuration or set visibility itself.

The drawing resolves the expected source dimension independently and requires
exact view/source/parameter identities, then verifies that **both** source and
imported display have that complete state. There is no repair or fallback if
native import restores numeric visibility. The former drawing writer remains
as an unrelated API but is no longer called by this recipe. Existing above/below
and tip prefix/suffix contracts stay unchanged.

Bundled SetText/GetText/ShowDimensionValue, swDimensionTextParts_e and redraw
method documentation and examples were read. The observed source flag staying
True is retained as evidence, not used to weaken the documented candidate's
numeric-hidden requirement.

The approved deliberate test changes replace the fillister drawing-literal
assertion with shared source authoring/read-only verification and add exactly
one full-text row. All 72 historical callout rows plus both tip reference rows
remain: 75 total author/verify rows across the same 35 part consumers. No
historical inventory fixture or geometry/tolerance assertion was rewritten.

## Required native follow-through

All 30 initial new cases failed on the unsupported `all` location before the
implementation. The final focused/adjacent run passed **470 tests in 28.69 s**,
receipt `pytest-telemetry/run-9_7jcryf`, including unchanged tip/reference tests,
the native-shaped void All setter, full text/visibility rejection cases,
source-dirty/authoring/save guards, graph and part isolation. Ruff F and diff
checks passed. These are offline checks, not native acceptance.

After review/integration, rebuild `part:fillister_screw` normally and record its
actual new artifact/execution-token bytes; do not pre-edit a source pin. Reopen
and verify the entire source state above, then run an owned copied-source full
drawing acceptance with unchanged source/hash/attachment/layout/cold/print gates.
Explicitly inspect a thread-only `#4-40 UNC-2A`, with no residual numeric Ø2.00,
and the unchanged underhead length, head sizes and complete notes. Native import
visibility is an open acceptance question. A failed full-state check remains
fatal; it cannot be replaced with a passing prefix comparison.

The full-recipe pilot does not yet enroll `fillister_screw` (the first-dirty
registry does). After the actual source build, add its exact new byte pin and
four `DRAWING_DIMENSIONS` to the existing `RecipeTarget` manifest, with no BASIC
or explicit entity roles. That small enrollment is a required separate
integration step before invoking the owned full-recipe target; do not assume
the current pilot already supports it.

The helper bytes still invalidate 35 existing part closures. Complete the affected
part and final-stack build before merge; old artifacts do not prove this digest.
No COM, part rebuild, source-pin change or cache publication was performed in
this implementation worktree.
