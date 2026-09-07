# Drawing semantic coverage failure evidence

The retained `datum-policy-rm_6b7hu/pilot.json` spring-hook failure reports
`functional pilot needs nonempty geometry/dimensions without dimension exclusions`.
That message covers three independent predicates: no checked geometry, no captured
dimensions, or at least one excluded dimension. It does **not** establish which
failed. The rejected semantic snapshot was not retained; the separately measured
three layout dimensions cannot determine the semantic gate's result.

The pilot now reports every failed predicate, section counts, and counts of the
exact exclusion reasons. Its unchanged raw snapshot retains annotation keys,
attachment kinds, source/configuration, dimension observations and exclusion
details. A primary coverage rejection is stored as `trial.semantic_failure`;
failure-only before/after rejections are stored in the corresponding `errors`
entry with `snapshot` and `validation`. These are rejected observations, never
accepted `drawing.semantics`: the trial remains failed, evidence remains partial,
and no semantic-preservation pass is asserted for rejected fields.

No acceptance predicate, native getter, export, ownership or hash guard changes.
The existing injected arbitrary snapshot-error test remains unchanged. Tests
reproduce each predicate separately, simultaneous failures, receipt serialization
and primary-snapshot survival when later evidence collection fails:

```powershell
uv run python -m pytest -q cad/scripts/test_datum_policy_recipes_drawing.py cad/scripts/test_failed_recipe_evidence_drawing.py
```

This is an offline observability correction. A subsequent native run must supply
the actual rejected snapshot before classifying the spring-hook failure.
