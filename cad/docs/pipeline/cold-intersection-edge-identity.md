# Cold intersection-edge identity candidate

Diagnostic only. No production selector, curve reader, source part, template,
layout predicate or geometry tolerance changes. One full crankshaft pilot now
passes with native cross-cold persistent-ID proof; this is not fleet or cold
pixel-equivalence acceptance.

## Native positive control

At frozen root `5e7737560d1efba42ff03d75376565e3b4710962`, the prepared-factory
crankshaft pilot exited 0 and reports `passed`:

- `cad/out/reports/datum-policy-_ombplu9/pilot.json`, SHA-256
  `f9dd490db1d4d3527670243379d2a0cec8d56ed308e79b3071549947f2f39319`.
- Its `ownership.json`, SHA-256
  `a5bb24df288e3652dd5c4b3d23890fb68d559bed9f4587a366b08e20652f3eeb`.

For `cross-hole true position` at `Drawing View2/DetailItem353`, both built and
cold observations resolved one attached EDGE. `GetPersistReference3` returned
an 805-byte `memoryview` in each phase. Native self-comparisons and the cold
`IsSamePersistentID` comparison returned integer **1** on the same saved
drawing path. The only raw explicit-bank delta was
`/explicit/cross-hole true position/geometry/1/trim/CurveTag`,
**549654 → 551552**. The comparison retained that delta as native-identity-proven
metadata and rejected nothing; the complete raw banks remain in the receipt.
Every other explicit-bank field was exact, including the new journal FACE
finish. Fresh resolver/owner/attachment checks remained active; no live-session
CurveTag or physical-geometry check was relaxed.

Built/cold source and semantic banks matched. The annotation comparison passed
with zero rejected leaves, 42 separately reported coordinate-ULP observations
and 15 sheet-Z serialization observations under the existing annotation-only
policy. Four explicit VIEW roles were checked: crank-end datum face, end-face
perpendicularity, cross-hole true position and bearing-journal finish. The
bearing-journal datum axis remains explicitly `coordinate_pick_not_migrated`;
this result does not confer explicit selected-entity identity on that role.

The actual drawing recipe took **24.4898122 s**, including its **1.7895901 s**
inner prepared-factory setup. Separately, the accessor miss/preparation took
**42.9095518 s**, and the verified hit took **0.0423147 s**. Total pilot time
was **183.0649552 s**, covering its guards, preparation, recipe and cold
witnesses but excluding parent lock/attach and outer owned-session cleanup.
It is one functional sample, not a paired speedup measurement.

Original and copied crankshaft bytes stayed exactly
`3c0224617322e3a10cca4a5c52e2b0a3b4c82e7be7969c0b21faf4db58b4cd94`
after recipe, close and cold reopen/close. Protected rocker/lever sources also
stayed exact. The original `2b1bbe3d...5e849` template, prepared bytes, manifest,
preparation receipt and helper/adapter fingerprints passed final guards, with
no runtime guard errors. Cleanup closed only owned documents and preserved the
already-open visible, clean original fillister part; ownership reports
`preserved` and null probe/cleanup errors.

The native drawing, PDF and PNG were produced. Main's visual inspection of the
**built**, not cold-exported, PNG found readable geometry, populated title block,
hole/fit callouts and journal FACE finish. The lower cross-hole cluster
is crowded, with no missing manufacturing callout observed. There was no
cold-export pixel comparison or overall layout redesign. Full-fleet/build gates
and other targets remain separate; this does not retroactively pass the older
failure below, which lacked native persistent-ID evidence.

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

The existing full owned pilot reproduces the native control from its frozen
checkout on the serialized seat, with no new launcher or callout authoring:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '31860'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --candidate HEAD --factory prepared --target crankshaft
```

Use the confirmed current PID, not an assumed persistent process. Source hashes,
runtime fingerprints, ownership, save/reopen, source/annotation/attachment and
layout gates remain mandatory. Each replay must obtain native 1 in its actual
drawing context; the recorded positive control is not permission to skip that
proof. No speedup claim.
