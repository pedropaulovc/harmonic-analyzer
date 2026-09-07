# Current tolerance getters in later diagnostic banks

This is an offline propagation of the accepted source-snapshot contract, not
native acceptance or a change to tolerance authoring.

Base: `ca899d7adecef5af8338c66193ff843a029d68c4`. Prerequisite
`3c970aebb4aa25be5b9f3f4b962eff698f7e2eba` was cherry-picked separately as
`40678881607cdd91f227dc9966fb6a1398d425db`. Its helper and retained recovery
evidence are documented in
[template defaults](../../scripts/diagnostics/template_defaults.md).

The bundled `IDimensionTolerance.GetMinValue2` / `GetMaxValue2` reference and
C#/VBA examples return an integer `swDimensionToleranceWarning_e` plus an out
double. Generated early-bound Python calls therefore take no arguments and
return `(status, value)`. Status `0` means valid for the tolerance type; `1`
means not valid for that type. The retained BASIC/NONE `(1, 0.0)` observations
remain observations, not fabricated valid zero limits.

The follow-on changes only diagnostic `_model_dimension_coverage._parameter`
and `_source_save_boundaries.capture`, both using the prerequisite's
`tolerance_limits` parser. Existing scalar keys remain unchanged:

- Model coverage keeps `tolerance_min` / `tolerance_max` and adds their
  `_status` companions.
- Save boundaries keep `minimum` / `maximum` and add `minimum_status` /
  `maximum_status`.

Statuses remain enum states in memory and native integers in JSON. Neither
consumer coerces booleans, strings, integers-as-doubles or unknown statuses;
there is no obsolete-getter fallback. Raw finite scalars remain exact even for
status `1`. Type validation still precedes the limit getters. Existing complete
bank comparisons therefore reject a status-only change as well as any scalar
drift. No source/hash, identity, dirty-state, printed-content, cold-reopen or
ownership predicates were removed. Production `_drawing_marks` is untouched.

## Offline evidence

`test_tolerance_consumers_drawing.py` initially failed all **84 cases** against
the old consumer calls (`run-b929esm8`). These cover both actual consumers,
valid/BASIC/NONE statuses, both getter bounds, malformed shapes and types,
nonfinite values, exact primary exceptions without obsolete retries, and saved
failed banks for status-only or `1e-20` scalar drift. Two additional model-bank
tests reject a status-only change during live and actual-pilot cold capture;
the cold case retains the changed status and unchanged scalar in its receipt.

Adjacent tests exposed integration-fixture omissions: three older pilot doubles
lacked the required explicit `coverage` enum, and the foundation snapshot double
lacked current `ShowDimensionValue`. These fields now match the current ABI;
all original assertions and expected failure cases remain. Four affected
tolerance doubles now implement the current no-argument getters with explicit
integer status and float values rather than the obsolete scalar methods.

Final focused/adjacent suite: **509 passed in 9.81 s**, receipt directory
`cad/out/reports/pytest-telemetry/run-a_bqjtms`. Ruff `F` and diff-check pass.
Run in the isolated checkout's own venv:

```powershell
$env:PYTHONPATH="$PWD/cad/scripts;$PWD/cad/comparisons/tools"
uv run --no-sync python -m pytest -q --tb=short cad/scripts/test_tolerance_consumers_drawing.py cad/scripts/test_model_dimension_coverage_drawing.py cad/scripts/test_source_save_boundaries_drawing.py cad/scripts/test_source_callout_authoring_drawing.py cad/scripts/test_lower_text_before_save_pilot_drawing.py cad/scripts/test_source_tolerance_snapshot_drawing.py cad/scripts/test_source_dirty_recipe_drawing.py cad/scripts/test_template_defaults_drawing.py cad/scripts/test_datum_policy_recipes_drawing.py cad/scripts/test_owned_native_documents_drawing.py
```

The existing `test_*_drawing.py` discovery enrolls the new regression module in
`check:recipe`. No COM ran, no native source pin was changed, and no saved or
printed native success is inferred from doubles. Native execution remains a
separate gate on the integrated top-stack head, not PR #681.
