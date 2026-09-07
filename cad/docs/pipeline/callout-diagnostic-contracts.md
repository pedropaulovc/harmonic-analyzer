# Callout diagnostic contracts

The alignment drawing now **verifies** a callout authored by its part recipe.
It no longer imports or invokes `set_dimension_callouts`. Diagnostic observers
must measure that actual call, not create a setter alias that the recipe retired.

The owned pilot recognizes two explicit recipe ABIs from the frozen recipe text,
before parent launch or worker attachment. It repeats the check on the retained
loaded recipe before opening the copied part and records the contract in the
trial and source-observer receipt.

| Contract | Required direct `_drawing_common` import | Permitted experiment |
| --- | --- | --- |
| `drawing_setter_v1` | `set_dimension_callouts` | Historical lower-text controls |
| `source_verifier_v1` | `verify_dimension_callouts` | Current source observation; explicit owned-part authoring control |

The verifier must be called once with `feature_name='ArborBoreProfile'` and
explicit `view` and `source_model` arguments. Its native checks run unchanged.
Mixed/aliased imports, a missing contract, and unsupported experiment/recipe
combinations fail rather than selecting a compatibility path.

`SourceSaveBoundaries` requires the versioned contract explicitly. It brackets
the actual selected helper under the existing `callouts` label; the four strict
stages and nine default banks are unchanged. A selected fresh drawing reader
still enables the full 25-bank observation. Exact source handles, raw values,
tolerances, dirty flags and hashes retain the same gates.

The explicit source-authoring arm still permits only its owned copied PART's
reviewed H0-to-H1 transition. It calls the real production drawing verifier with
the intended view and the exact reopened source model; it does not replace that
proof with its supplemental imported-text checks. Original/guard H0 protection,
both native save controls, printed text, cold reopening and cleanup remain
independent gates. The ordinary production observer performs no authoring.

## Historical negative controls

The old setter-interception source-authoring fixture is intentionally migrated
to the verifier ABI. Its manufacturing and ownership assertions remain. The
lower-text fixtures retain their explicitly historical setter ABI; they do not
model the new production recipe.

To reproduce the negative lower-text trials, use an independent checkout of
**`9f2f5d9a` and its matching tooling**, with its own venv and an explicitly
granted native seat. Passing that commit to the current CLI alone does not
restore its helper/runtime closure. From that frozen checkout, with the
diagnostic environment and protected source/guard paths established:

```powershell
uv run python cad/scripts/diagnostics/probe_datum_policy_recipes.py --candidate HEAD --source-root <protected-source-directory> --guard-root <protected-guard-directory> --target alignment_pinion --source-observation alignment_save --drawing-save legacy --callout-storage lower_text_before_save
```

Select `lower_text` instead for the early timing arm. The retained late receipt
`datum-policy-rqv9qa0l/pilot.json` has SHA-256
`7d9aa7f12dba466f92b15ab43595e643909516aee6b2f36e51ee3bff5dc3f5c3`:
storage survived, printed fit lines did not, and cold acceptance was not reached.
The new verifier recipe is explicitly unsupported by either lower-text arm.
These are negative results for the tested imported diameter/call form, not a
general claim that a native API cannot work.

Current production acceptance omits both `--callout-storage` and
`--source-callout-authoring`. Add `--source-observation alignment_save` to retain
the nine source banks around the actual verifier; the protected source must
already contain the part-recipe-authored callout.
