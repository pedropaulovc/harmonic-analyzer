# Cold intersection-edge identity candidate

Diagnostic only. No production selector, curve reader, source part, template,
layout predicate or geometry tolerance changes. Native acceptance of the new
persistent-ID call shape remains pending.

## Retained failure

At root `fb958fdad1c55653ab6747c28eeaa31ca547850a`, adapter `25bc99b1`
and PID 31860, crankshaft receipt
`cad/out/reports/datum-policy-7vmq0092/pilot.json` has SHA-256
`197fc32a67467c084d8e05fa6fe7e53c3a3ceb8012f1b1aacffe4945ab7e5b89`.
The source remained exactly
`3c0224617322e3a10cca4a5c52e2b0a3b4c82e7be7969c0b21faf4db58b4cd94`.
The diagnostic took 258.927420 s, including 24.547128 s for the recipe;
the total excludes parent lock/attach and outer owned-session cleanup.

Cold source and annotation comparisons passed (zero rejected annotation leaves,
42 separately reported coordinate-ULP observations, 15 sheet-Z serialization
observations). The explicit entity bank failed on exactly one integer field:

`/explicit/cross-hole true position/geometry/1/trim/CurveTag`: 537446 → 539344.

All other raw fields, including spline controls, knots, trim endpoints, domain,
sense, curve type and the other FACE/EDGE roles, compared exactly. Runtime
guards and secondary capture errors were empty. This remains a **failed** native
pilot: that receipt contains no cross-cold edge persistent-ID proof.

The complete built/reopened cross-hole rows are retained in
`cad/scripts/fixtures/crankshaft-cold-curve-tag-7vmq0092.json`. These are JSON
observations, not live COM handles; JSON does not retain tuple/list distinctions.
The regression restores only the known outer geometry/key tuple boundaries.
Both row objects were extracted with `JsonElement.GetRawText` and independently
matched the original raw JSON after CRLF-to-LF normalization only. Numeric
spellings are retained; no coefficients are sampled, rounded or removed.

## Contract and deliberate test distinction

The official `ICurveParamData.CurveTag` page describes an ID, without a
cross-session stability promise. The persistent-reference programming guide
documents cross-session selectable-object identity. `GetPersistReference3`
documents model-scoped references whose encoding can change;
`IsSamePersistentID` supplies the native comparison (1 same, 0 different,
-1 invalid). Equal bytes or equal coefficients are not identity evidence.
The bundled selected-object C# comparison example and edge-parameterization
example were read alongside those method pages.

The new observer applies only to captured `INTERSECTION_TYPE` (3004) EDGEs.
After the existing exact fresh view/annotation/attachment checks, it records
the current saved drawing path, annotation key and unsigned-byte reference,
and requires native self-comparison 1. On cold reopen it uses only the new
drawing extension and freshly resolved edge, never closed wrappers. It requires
the same saved drawing path/key, self-comparison 1 and cross-cold comparison 1.
Null/empty/malformed references, native errors and 0/-1/non-integer results fail;
failed observations do not publish comparison permission.

The caller retains the full original raw banks. A separate comparison may
classify only an integer CurveTag delta on the corresponding observed edge.
Every other field, type, container, coefficient and coordinate remains exact;
the annotation coordinate budget is not used for these banks. The original
`trim_tag` test still asserts raw built/reopened inequality, and the original
live-session `tag` test still rejects the change. This explicitly revises the
cold caller policy, not either raw test's assertion. MODEL comparison is
unchanged.

## Offline reproduction and native gate

```powershell
uv run --no-sync python -m pytest -q `
  cad/scripts/test_view_curve_cold_identity_drawing.py `
  cad/scripts/test_view_intersection_curve_witness_drawing.py `
  cad/scripts/test_view_recipe_acceptance_drawing.py
```

The retained fixture fails without identity proof. A native-shaped test double
then proves only the policy wiring; it is not a SolidWorks success receipt.
Full-pilot fixtures use the real cold comparator and retain its rejection report.
Offline focused/adjacent verification passed 451 tests in 17.57 s
(`pytest-telemetry/run-nbc31vqt`); Ruff F and `git diff --check` passed.

After review and an explicit seat grant, the existing full owned pilot is the
native positive control, with no new launcher or callout authoring:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '31860'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --candidate HEAD --factory prepared --target crankshaft
```

The PID must be the separately granted existing seat. Existing source hashes,
runtime fingerprints, ownership, save/reopen, source/annotation/attachment and
layout gates remain mandatory. The new proof must return native 1 in that
actual drawing context before the candidate can be accepted. No speedup claim.
