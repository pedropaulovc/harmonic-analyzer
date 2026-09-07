# Fillister source-owned whole dimension text

This additive candidate follows the cone-tip reference-field migration at
`c77ed41eb66e914737bc14ba73a5420f1b4d8cf8`. It moves the fillister thread-only
display into source authoring and makes the drawing verify its full inherited
state. Native source authoring, save, fresh copied-part reopen and initial
drawing import passed at `7f070434`. Full drawing save/cold/printed acceptance
remains pending.

## Pre-migration first-dirty control

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

## Saved source and read-only import positive control

The actual `part:fillister_screw` build at
`7f07043420ed110d0ee7dc267df2fb571af8af5d` passed. Trace
`0xa3ed1e72c66f4e8b0168639073198407` records task **60.013411 s** and
part **58.806453 s**. Both authoring spans passed: `Shank` in 1.832934 s and
`ShankProfile` in 2.270974 s. These are one build's durations, not a speedup.
The 80,596-byte saved source and its execution token are exactly
`e7b48995c9f2e87af473219edfca1500a14e77bd353a330c64883011ab4fb60d`.
Two shared-read hashes matched, with size and mtime unchanged
(`2026-09-07T13:51:35.5807985Z`).

The subsequent owned-copy control is
`cad/out/reports/source-dirty-1elj8tkj/source-dirty.json`, SHA-256
`29b1bbded891de9d9b167424d4d69b15deaf0cbe14283777a09570db63f82a33`.
It reopened a fresh copy of those saved bytes. Both actual drawing
`verify_dimension_callouts` calls returned successfully, including the complete
whole-text/hidden-number check on the imported `ShankDia` and its explicit
source/view/parameter identities. All **51 observed boundaries stayed clean**;
the control stopped intentionally before `finalize_drawing` at **22.7120578 s**.
It did not save or export the drawing.

An independent comparison of this receipt's source baseline against the fresh
pre-migration `nesqj5vt` baseline covered all **10 parameter records, 16 display
rows and 24 feature names**. Only the exact diagnostic copy-name suffix in the
dimension keys was normalized. The six changed leaves are the same three fields
in each of the two `ShankDia@ShankProfile` displays (`Shank`, `ShankProfile`):

| Field in each display | Pre-migration baseline | Authored saved-source baseline |
| --- | --- | --- |
| Text 1 | `<MOD-DIAM>` | `#4-40 UNC-2A` |
| Text 5 | `<MOD-DIAM>` | `#4-40 UNC-2A` |
| `ShowDimensionValue` | `True` | `False` |

After accounting for exactly those six intended leaves, **no differences
remain**. Every raw numeric value, tolerance type/min/max, configuration,
feature name, display count/type/index, drawing mark, precision and other text
compartment compares exactly. `ShankLg` retains `UNDERHEAD LENGTH` in fields
4/8. The raw `ShankDia` value remains `0.0020000000640000002` m. No numeric
rounding or display-row sorting was used. This compares recorded parameter and
presentation state across separate builds; it is not cross-build native-handle
identity or a complete body-geometry proof. Both raw receipts remain unchanged.

Original and copied source hashes stayed exactly `e7b48995...fb60d` through the
control. Ownership preserved the already-open clean, visible original fillister
part and closed its diagnostic documents, with null probe/cleanup errors.
Its `ownership.json` SHA-256 is
`a76a60b0c711d79a4aaae92bc9c06697899d985f327bdff11dc5102cb3d873e9`.
This positive control establishes saved-source persistence and read-only initial
import, but contains no printed-content or drawing cold-reopen evidence.

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
GetText is only called with 1 through 8 (0 is invalid for that getter). Full readback
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
True in the pre-migration control is retained as evidence, not used to weaken the
numeric-hidden requirement.

An additive review correction validates raw ShowDimensionValue as an exact
Boolean inside the native reader, then transmits `NumericVisibility.VISIBLE`
or `.HIDDEN` between helpers. The complete-state assertions are unchanged;
this satisfies the project's enum-state rule without accepting truthy values
or adding a property write. The original implementation commit is retained.
The correction passed 472 focused/adjacent tests in 31.82 s
(`pytest-telemetry/run-0a8xhabf`); its two new enum-boundary cases failed first.

The approved deliberate test changes replace the fillister drawing-literal
assertion with shared source authoring/read-only verification and add exactly
one full-text row. All 72 historical callout rows plus both tip reference rows
remain: 75 total author/verify rows across the same 35 part consumers. No
historical inventory fixture or geometry/tolerance assertion was rewritten.

## Offline checks and remaining native acceptance

All 30 initial new cases failed on the unsupported `all` location before the
implementation. The final focused/adjacent run passed **470 tests in 28.69 s**,
receipt `pytest-telemetry/run-9_7jcryf`, including unchanged tip/reference tests,
the native-shaped void All setter, full text/visibility rejection cases,
source-dirty/authoring/save guards, graph and part isolation. Ruff F and diff
checks passed. These are offline checks, not native acceptance.

The source build/reopen/import control above is complete. Run full drawing
acceptance on an owned source copy with unchanged source/hash/attachment/layout/
cold/print gates.
Explicitly inspect a thread-only `#4-40 UNC-2A`, with no residual numeric Ø2.00,
and the unchanged underhead length, head sizes and complete notes. Persistence
through drawing save and cold reopen, and actual printing, remain unproved.
A failed full-state check remains fatal; it cannot be replaced with a passing
prefix comparison.

The explicit seventeenth-target enrollment `a9a9a38f`, integrated as `b60afc56`,
pins this exact `e7b48995...fb60d` output. All sixteen prior pins/roles remain
unchanged. Fillister uses its four existing `DRAWING_DIMENSIONS` (`HeadDia`,
`ShankDia`, `HeadHt`, `ShankLg`), no BASIC or explicit entity roles, and its
existing 8:1 prepared-template spec. The prior two fasteners remain at 4:1.
The existing pilot can now run `--target fillister_screw --factory prepared`;
the enrollment does not itself establish a successful native drawing.

The helper bytes still invalidate 35 existing part closures. Complete the affected
part and final-stack build before merge; old artifacts do not prove this digest.
No COM, part rebuild, source-pin change or cache publication was performed in
the implementation or evidence-editing worktrees. The native evidence above
came from the main runner's frozen root checkout.
