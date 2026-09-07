# Factory Windows review: retained findings

This records the completed local CodeRabbit review for PR #681, not current
merge or native-fleet acceptance. No new review or COM invocation was needed.

## Receipt and scope

The CLI's `review findings` returned 13 findings for head
`c05953787a6e38fee440422da775b9e366c06068`. The effective explicit review base is
the stacked foundation `d8ec09f5`: all 197 stored diff blocks match that Git range
exactly after trailing-newline normalization. The range from main contains 368
files, including 171 not in this review. `git.json` records the base branch's main
tip `9e746e1513479290565e6d920e74dadb3c7062a2`, not the effective `--base-commit`;
it must not be used alone to infer review scope. The complete receipt remains at:

```text
C:/Users/pedro/AppData/Local/coderabbit/reviews/a07668f8/afb7845d/reviews/1788792958714
git.json SHA256: 6f5c2f41d2f4c9759db2e38ba2f1f836a5041c0ff09f262a531813e8120dd317
incrementalDiff.v2.json SHA256: cdb8ba30d43ccbbc77006831f39e0fd3c0bf985e5053d9b750e1625d39c12571
```

`.session-complete-v2` reports `complete`, with git metadata and incremental
diff present. Each finding is retained in its UUID-named JSON file. The table
uses unique UUID prefixes. Fixes were prepared separately from frozen native
checkouts, on `c0595378` plus `9499ac193fc17b5c0fb60bbf24cde18dba17fed0`.

## All 13 findings

| Finding | File / concern | Disposition |
|---|---|---|
| `03943118` | `test_silhouette_identity_control_drawing.py`: regex | Raw string; identical regex value. |
| `17493260` | `test_source_callout_authoring_drawing.py`: broad exception | Require `RuntimeError`; retain exact primary setter exception and reject unrelated assertion/value errors. |
| `28ce41a0` | `test_unsaved_dimension_owner_drawing.py`: missing fixture import | Disproved: tracked fixture exists and all 24 tests collect and pass. No replacement module or path fallback. |
| `567e2d12` | `test_linear_dimension_arrangement_drawing.py`: unchecked signature substitution | Require exactly one signature before substitution; missing/duplicate cases must stop before pilot invocation. |
| `64a1f22c` | `test_unsaved_dimension_owner_drawing.py`: two regexes | Raw strings; same owner predicates. |
| `749f6b4a` | `draw_bracket_screw.py`: invocation documentation | Document `uv run python -m doit drawing:bracket_screw`. |
| `7848dfd9` | `test_view_recipe_acceptance_drawing.py`: three regexes | Raw strings; unchanged identity/layout predicates. |
| `8aed1a09` | `draw_fulcrum_keeper.py`: unused sheet binding | `_sheet` in `9499ac19`; no native call change. |
| `b699a66e` | `test_silhouette_attachment_witness_drawing.py`: unused face and four regexes | `_face` from the same single fixture call; raw patterns; original raw/identity rejection tests retained. |
| `c252b559` | `_drawing_parallel_dimensions.py`: restore spacing | Not adopted: contradicts explicit persisted-document contract and deliberate call-count assertions. `9499ac19` clarifies `initial_offset`; no restore, extra setter or cleanup exception path. |
| `d14971ce` | `test_datum_policy_recipes_drawing.py`: recipe decoding | Explicit UTF-8; also mark its two existing metacharacter patterns raw. |
| `e4122708` | `draw_guide_lock.py`: unused sheet binding | `_sheet` in `9499ac19`; no native call change. |
| `f9372007` | `test_callout_recipe_contract_drawing.py`: recipe decoding | Explicit UTF-8; also mark its existing alternation pattern raw. |

Thus 11 findings receive narrow fixes; one import claim is false and one
suggested policy change conflicts with the accepted contract. The imported
`test_probe_drawing_attachments.py` has identical blob
`8013dc1a708841ea2a6d1fa371a8d49b1c3b0094` at both `d8ec09f5` and `c0595378`.

The spacing decision and retained native `93294cb6` evidence are documented in
[the parallel control](../performance/lever-linear-parallel-control.md).
That evidence supports the tested persisted setting, not a claim that restoring
it would leave geometry unchanged, nor full acceptance of this extracted head.

## Offline proof

Four new regressions failed before their fixes:

- Missing and duplicated fixture signatures reached the pilot instead of
  stopping at the fixture boundary: `run-yuemom4o`, 2 failed.
- Injected `AssertionError` and `ValueError` were swallowed by the broad
  negative-case assertion: `run-rurdwrme`, 2 failed. Both now propagate as the
  exact injected objects; all original authoring outcomes still pass.

Final 13-file focused/adjacent run: **415 passed in 13.11 s**,
`cad/out/reports/pytest-telemetry/run-nz881rxw`. Re-run with this checkout's venv:

```powershell
$env:PYTHONPATH="$PWD/cad/scripts;$PWD/cad/comparisons/tools"
uv run --no-sync python -m pytest -q --tb=short cad/scripts/test_unsaved_dimension_owner_drawing.py cad/scripts/test_view_recipe_acceptance_drawing.py cad/scripts/test_silhouette_identity_control_drawing.py cad/scripts/test_silhouette_attachment_witness_drawing.py cad/scripts/test_source_callout_authoring_drawing.py cad/scripts/test_linear_dimension_arrangement_drawing.py cad/scripts/test_datum_policy_recipes_drawing.py cad/scripts/test_callout_recipe_contract_drawing.py cad/scripts/test_parallel_dimensions_drawing.py cad/scripts/test_channel_lever_drawing.py cad/scripts/test_fulcrum_keeper_drawing.py cad/scripts/test_guide_lock_drawing.py cad/scripts/test_bracket_screw_drawing.py
```

Ruff `F,B017,RUF043,RUF059` passes for the changed Python files and the prior
three production files; `git diff --check` passes. An earlier aggregate command
mistyped the parallel test filename and ran zero tests (`run-acf4dzfn`); the
415-test result above is the corrected run. These checks do not establish native
save/render behavior or performance. No acceptance predicates, native helper
call order, ownership policy or manufacturing recipe operations changed.

## Completed review of `f0eed58a`

The next Windows `review findings` read returned **12 stored findings** for
`f0eed58aee67fce77e3ccd8dd7ef59284b9c0fc2`. No new review was started. All
198 stored diff blocks exactly match
`31b145837d5262dbe130c4509992895795bd7675..f0eed58a` after trailing-newline
normalization. `git.json` instead records main's branch tip `c6ab57db`; that
metadata is not the effective diff base.

Complete original receipt:

```text
C:/Users/pedro/AppData/Local/coderabbit/reviews/67bfeb62/20eb45af/reviews/1788799106057
git.json SHA256: 27fe706b101637b81d12ec879831e62c65dcd1e245c642b0c68efd8735dee13e
incrementalDiff.v2.json SHA256: db3797814073c0ac90c67de4edcbc32eb95dc280585c660b49480b01de88c448
```

All 16 files, including the completion marker, were copied without modification
to `cad/out/reports/coderabbit-factory-f0eed58a-1788799106057`; every copied
SHA-256 matched the original.

| Finding prefix | Verified disposition |
|---|---|
| `26dfe83f`, `85e9a917`, `b4b56b2e`, `bb85fc26`, `c0ae3da1`, `d3b54612`, `d4b99857`, `dd49021f` | Rename unused sheet bindings in pinion pivot block, lever, bracket, handle, spring, platen guide, cam and pen V-block. Factory calls and arguments unchanged. |
| `8a1cf77b`, `c81b7edb` | Raw regex strings in sheet-setup and finalizer-scale tests; same pattern values. |
| `5d50aeea` | Missing import disproved again: fixture blob `8013dc1a` is tracked at the reviewed head; all 24 unsaved-owner tests pass unchanged. |
| `f923456d` | Real finalization defect: failed authored-copy provenance could replace the primary exception and skip later copy/source/runtime guards and the checkpoint. Collect the expected-hash error, preserve the measured copy hash, and continue the existing failure path. |

Four fail-first cases (`run-xqvt63n9`) exercise the real provenance validator:
wrong original hash or missing baseline, each with a completed run or an earlier
recipe failure. The fix retains the exact primary exception when one exists;
otherwise the original guard exceptions reach the existing exception group.
Both trial hashes, protected source hashes, helper/adapter checks and the final
receipt survive. Provenance failure still fails the run; no fallback hash is
invented. The catch is confined to expected-hash resolution, including malformed
baseline data, not the recipe or acceptance comparisons.

The focused suite also exposed 16 inherited fixture failures after the
foundation's current tolerance getter change. The source-authoring double now
exposes `(0, float_value)` current getters, retaining its scalar getters solely
because this factory slice's save-boundary consumer still calls them. No
production fallback was added. Consumer propagation remains the separate
top-PR #675 migration, not this #681 fix; integer status `0` is valid and `1`
is not applicable, never a Boolean success flag.

Final focused/adjacent evidence: **226 passed in 5.82 s**, telemetry
`run-50v_b2df`; Ruff `F,RUF043,RUF059` and diff-check pass. This includes all
eight affected recipe tests, sheet setup/finalizer, owned pilot, source-authoring
and unsaved-owner tests. No COM, rebase, source artifact, review reply or
resolution action was performed. Native acceptance remains separate.

## Completed review of `6506ca2d`

The Windows CLI run completed with seven findings for exact head
`6506ca2d8553477d4b2cf37e3c0746101dafba92`. Its requested base and `git.json`
both name `0083e08be5b7a34bc6e74363d48422279b38a202`. The completion marker
reports `complete`; this is a completed review with findings, not a clean review.
The adapter gitlink is `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`.
All 196 stored diff blocks match the explicit base-to-head range after
trailing-newline normalization. That Git range has 198 blocks: the review
omitted `_drawing_common.py` and this triage file, both supplied as `--config`
context. The review therefore does not establish coverage of those two changed
files; the next clean-review gate must cover them as well.

The original receipt and its retained copy are:

```text
C:/Users/pedro/AppData/Local/coderabbit/reviews/67bfeb62/582e3d84/reviews/1788801702928
C:/src/ha-factory-review-contracts/cad/out/reports/coderabbit-681-6506ca2d/native-receipt
git.json SHA256: 84cee3c628806297f8014b95a35903ddb75d85ca4a5da5fc56d165dcc0ac7fa5
incrementalDiff.v2.json SHA256: 7bb401c9a8e00d3c51a0c9e406dc741c172e62f4df36649f66b89e236f6582f9
```

Triage and fixes ran offline in the separate `ha-factory-review-6506` worktree
at that exact head, with its own venv and pinned adapter. The reviewed parent
checkout remained untouched by this work.

| Finding prefix | Verified disposition |
|---|---|
| `abeb8ac9`, `ce0f4b14` | Rename unused `sheet` bindings in crank arm and crank handle. Ruff reproduced both RUF059 findings. Factory calls, arguments and layout are unchanged. |
| `0d51a8d5` | Give both VIEW observer test-double methods the real protocol's optional source-bank argument. Assert both positional call shapes; keep all original source, identity, title and cleanup assertions. |
| `478ed6ef` | Validate required retained-receipt fields before indexing. Errors identify the pinned receipt path and missing field or malformed spec; no substitute values or alternate input are accepted. Original hash, exact-template and TemplateSpec checks remain. |
| `e14c17b9` | Decode both recipe-contract source reads explicitly as UTF-8. Tests invoke the actual two contract checks and require the encoding at the read boundary. |
| `2f624e3d` | False count claim. The four explicit type46 entries sum to four, as the finding itself acknowledges. The separately coordinate-picked cone silhouette is the fifth call. Table and manifest remain unchanged. |
| `e3b50393` | Do not add drawing-side callout authoring. The actual part builder authors `DIMENSION_CALLOUTS` before saving; the drawing verifies the imported source text read-only. The proposal contradicts the deliberately tested source-authoring contract. |

The last two dispositions have existing re-runnable tests beside their code:
`test_complete_explicit_scope_and_default_order` proves the 21/11/4 manifest
totals, and `test_all_existing_explicit_recipe_calls_are_enrolled` checks all
ten recipe inventories. `test_alignment_authors_after_marking_and_verifies_in_drawing`
pins source authoring before save and the absence of a drawing setter;
`test_drawing_verifies_exact_import_read_only` and the owned source-authoring
pilot tests exercise import verification and rejection without repair. These
tests passed unchanged. No native evidence is newly claimed by this triage.

Fourteen fail-first cases were retained in `run-4q6n0vuq`: six missing receipt
fields raised bare KeyError, six VIEW protocol cases rejected the valid omitted
bank argument, and two actual recipe-contract readers omitted UTF-8. After the
fix, the same cases pass. Thirteen additional malformed receipt cases exercise
invalid root/nested objects, path/status text and TemplateSpec inputs.

Final focused/adjacent run: **421 passed in 14.88 s**, telemetry
`run-xgdntwou`, covering the prepared viewport, VIEW acceptance, factory
contracts, model/source callout authoring and all three affected recipe tests:

```powershell
$env:PYTHONPATH="$PWD/cad/scripts;$PWD/cad/comparisons/tools"
uv run --no-sync python -m pytest -q --tb=short cad/scripts/test_prepared_viewport_drawing.py cad/scripts/test_view_recipe_acceptance_drawing.py cad/scripts/test_drawing_build_factory_drawing.py cad/scripts/test_model_dimension_callouts.py cad/scripts/test_source_callout_authoring_drawing.py cad/scripts/test_crank_arm_drawing.py cad/scripts/test_crank_handle_drawing.py cad/scripts/test_alignment_pinion_drawing.py
```

Ruff `F,RUF043,RUF059` and `git diff --check` pass for the changed Python files.
An additional `B017` check reported six existing broad exception assertions in
`test_prepared_viewport_drawing.py`; those predate this review and remain
unchanged. They are not counted as a passing lint check or a reviewed fix here.

Full-stack native validation, exact integrated-head re-review, visual inspection
and merging remain VM1 integration work. This pass neither modifies the VM2
resolver files nor changes manufacturing content, source-authoring behavior,
native helpers, adapter code, memory files or the fillister enrollment assertion.
