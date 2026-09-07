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
