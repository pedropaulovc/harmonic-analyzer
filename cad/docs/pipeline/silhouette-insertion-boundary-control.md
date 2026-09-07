# Silhouette SF insertion boundary control

This historical diagnostic preserves the failing silhouette identity gate. It does not
accept a silhouette because its geometry or persistent-reference bytes match.
The two native boundary runs below retain the rejection unchanged.
Both current production SF roles have since migrated to controlled FACE/native
placement, so neither enrolls in this silhouette-only observer. Spring hook's
complete native FACE acceptance and the narrower crankshaft results are recorded
under [Native FACE-placement results](#native-face-placement-results-2026-09-07).

## Retained failures

Crankshaft, root `39615df9`, adapter `25bc99b1`, PID 31860:
`datum-policy-wzed5ja8/pilot.json`, SHA-256
`c93a0a2b071b715bec5fb996b80d53e951129568fe63caeca8b897af829ea30c`.
Recipe 41.6385514 s; complete pilot 182.4147805 s. Three EDGE roles passed
selection and insertion. Journal SF selection passed native PID comparison 1,
with equal raw line endpoints/cylinder parameters and two 1,288-byte references.
Production SF validation later returned 0. Its references were not retained.
Failure capture completed without errors; source/hash preservation and final
runtime guards passed. Owned copy SHA remained
`3c0224617322e3a10cca4a5c52e2b0a3b4c82e7be7969c0b21faf4db58b4cd94`.

Spring hook, root `335e6ad8`, same adapter/PID:
`datum-policy-_pfvu2ct/pilot.json`, SHA-256
`4d4a4fe9b7b37423ec22b810ec3cc596afcbcc53d2618899cffe4bfaa94f4284`.
Recipe 27.8232612 s; complete pilot 125.8308143 s. Selection also passed PID1,
then production SF validation returned PID0. Original/copy hashes and final
guards remained unchanged. Its generic semantic failure is now specifically
`checked_empty`: three dimensions were captured, zero dimensions excluded.
The unsupported generic geometry kinds are separate from dimension validity.

Neither receipt distinguishes a changed attachment from an invalidated wrapper.
`add_surface_finish` inserts, writes text, positions/styles, clears selection,
and calls `EditRebuild3` before its explicit attachment validator. Rebuild is
therefore a boundary to measure, not an established cause.

## Added observations

The observer supports only the historical VIEW-origin type46 JOURNAL/SHANK
surface-finish roles. After migration to JOURNAL_FACE/SHANK_FACE, zero current
`VIEW_ROLES` entries match. Explicit historical test manifests still exercise
the instrumentation and rejection/ownership controls. This is retained negative
repro support, not instrumentation claimed to run for current FACE recipes;
their ordinary VIEW selection/attachment/built/cold guards remain active.

1. `pre_insert_self`: reuse the exact reference bank already obtained by the
   successful selection gate; add native handle/reference self controls.
2. `post_style_pre_rebuild`: after the original style function returns, before
   the existing clear/rebuild, capture current expected/selected/attached IDs,
   self controls and document-native comparisons against stored references.
3. `production_predicate`: inject an evidence dictionary into the original
   shared predicate. Call both original validator and predicate exactly once;
   retain the exact IDs, native result, exception and validator duration.
4. Only after rejection, capture old handles' IDs, owning-view comparisons,
   raw supported curve/endpoints/surface and underlying-face comparisons. Then
   invoke the existing manifest resolver and compare its fresh result. No new
   nearest-geometry search or alternate attachment selection is introduced.

The SHANK resolver's existing `ActivateView` is explicitly reported; JOURNAL's
resolver only reads entities. Old-wrapper observations precede that resolution.
Each observation phase brackets the current owned drawing and referenced owned
part's dirty flags, checks ownership, and records elapsed time. It never clears
dirty flags, saves, rebuilds, reselects or retries insertion. Outer source-copy
hashes, original hashes and owned cleanup remain the existing pilot's gates.

The first two samples incur **proactive getter cost even on a successful run**;
only the expanded geometry/fresh-resolution bank is failure-only. Phase times
and recipe time include this instrumentation; this is not a speed comparison.
Secondary errors are retained without replacing the original rejection. PID0
remains fatal even when every additional control passes.

The fresh resolver has its own immediate context barrier, not just sample-entry
and exit checks: the exact captured drawing must still be current and active,
the original view must occur exactly once in that drawing's native view bank,
and its referenced part must still be the same owned source. Check again after
resolution before reading the returned entity. This addresses the reproduced
case where an earlier `GetFace` changes the active/current document: resolution
must not run, even if the replacement is another owned document. The refusal is
secondary evidence; the original PID rejection remains authoritative.

Official bundled contracts used: `GetPersistReference3` is document-scoped and
its internal bytes may change across rebuilds; `IsSamePersistentID` compares the
referenced objects (0 different, 1 same, -1 unknown in the official example).
`GetAttachedEntities3` returns silhouettes as `ISilhouetteEdge`; `GetView`,
`GetFace`, `GetCurve` and endpoint getters provide the corresponding witnesses.
No source-context silhouette persistence is assumed.

The native silhouette boundary is reproducible from frozen `9ef1f724` in an
isolated checkout with that revision's pinned source copies and adapter, using
`probe_datum_policy_recipes.py --target spring_hook` (or `--target crankshaft`).
Confirm exclusive seat ownership/current PID and use disabled-autostart/cache
flags. The same commands at the current revision test FACE placement and do not
activate this historical observer. No alternate acceptance mode was added.

Offline tests:

```powershell
uv run python -m pytest -q cad/scripts/test_silhouette_insertion_control_drawing.py cad/scripts/test_silhouette_identity_control_drawing.py cad/scripts/test_view_recipe_acceptance_drawing.py
```

## Native boundary results, 2026-09-07

Both runs used frozen root `9ef1f724`, adapter `25bc99b1`, attached PID 31860,
the existing prepared full-recipe pilot, and unchanged exact source pins.

| target | receipt under `cad/out/reports/` | receipt SHA-256 | recipe / pilot seconds |
| --- | --- | --- | --- |
| spring hook | `datum-policy-ydaui7tb/pilot.json` | `f104572a9040639e0cc8e53184421484766ea2043c914fcfbe4129ac984bbe71` | 57.885665 / 174.864755 |
| crankshaft | `datum-policy-atp42a38/pilot.json` | `3d6028992a30070518ad86a09b662249c810f48d52192c7b059b70648a1d2c52` | 76.701219 / 227.780206 |

These timings include proactive instrumentation and failure capture, not an
uninstrumented performance comparison. Both failure captures completed without
secondary errors. Original/source-copy hashes and source observations remained
unchanged; final runtime guards were empty. Neither recipe reached successful
built/cold acceptance.

In both runs, expected/selected references passed their own native and persistent
self controls. Expected, selected, stored pre-insertion references and the fresh
role resolution compared equal with native PID1. The attached entity passed its
own self controls but compared PID0 against the expected entity **already after
styling, before the existing clear/rebuild**. The same partition persisted after
rebuild. This rules out that rebuild as the onset of this mismatch; it does not
isolate insertion from the intervening text/leader/position/style calls.

All five owning-view checks and all 21 underlying-face native comparisons passed
in both runs. Spring's five complete raw geometry snapshots were exactly equal.
Crank's selected/fresh versus attached snapshots differed only in the line's
x origin/start/end: `-1.9880494890015018e-17` versus
`3.4865694628900976e-19` metres. Its cylindrical-surface parameters and remaining
curve/endpoint values were exact. Thus an exact raw-coordinate comparison is not
a demonstrated replacement for persistent object equality across these paths.
No geometric tolerance or alternate acceptance was introduced.

The generic type-46 observer also captured spring's actual attached silhouette:
the retained failure bank now has accepted semantics rather than the previous
`checked_empty` rejection. That geometry observation does not prove persistent
object identity and did not bypass the production rejection.

The subsequent candidate used explicit attachment to the already controlled cylindrical
FACE with native symbol placement, not relaxed silhouette identity. This matches
the surface-finish control's physical target while avoiding the need to assert
that view-returned and annotation-returned silhouette objects share a persistent
ID. The native FACE results below supply that separate proof for spring hook;
crankshaft's recorded partial results retain their stated cold-gate failures.
The original silhouette PID/raw-equality tests stay unchanged. The integrated
four-file diagnostic test run passed 174 tests in
13.84 s (`pytest-telemetry/run-rdhph0pf`).

## Native FACE-placement results, 2026-09-07

Frozen root `be38f5b5`, adapter `25bc99b1`, PID 31860 ran the existing owned
prepared pilot for spring hook and crankshaft. Receipt
`cad/out/reports/datum-policy-43xc6f6u/pilot.json`, SHA-256
`bc0aa118e95deaba84fa6de2289dad31df0804e43a25de79030822e1c1567d65`,
records 501.860751 seconds including both recipes, witnesses and failure capture.
Neither source pin changed. Original/source-copy hashes stayed exact, final
runtime guard errors were empty, and cleanup completed.

Spring hook passed the complete recipe, built/cold source and explicit FACE
attachment gates. Recipe time was 37.7598435 seconds. Its annotation comparison
had no rejected differences or coordinate exceptions. The fresh PNG was visually
inspected: Ra 1.6 sits directly on the lower shank, with no bent leader and a
readable 5:1 sheet. This proves this native sample, not a fleet failure rate.

Crankshaft's recipe passed in 25.7561287 seconds; its built four-role entity
bank and exact cold drawing semantics/view-layout comparison also passed. The
fresh PNG was inspected: the bearing-journal finish label is readable and placed
on the journal boundary. The pilot still **failed** before the cold source and
fresh FACE-role comparison. Fifteen Z-coordinate leaves on datum B (kind 2,
DetailItem351) and the end-face perpendicularity FCF (kind 5, DetailItem352)
changed from magnitudes at most `2.465190328815662e-32` metres to zero. Forty-two
other differences passed the pre-existing leaf-ULP rule. No rejected X/Y, text,
style or view-layout changes occurred. This is not completed cold acceptance.

The selected raw containers and the original fifteen rejected leaves are retained
in [the zero-Z evidence fixture](evidence/crankshaft-43xc6f6u-zero-z.json).
The cold-only comparator now reports `zero_z_serialization` separately: only a
complete documented XYZ vector with exactly unchanged X/Y and one exactly zero
Z may receive `min(1e-14 m, 16 ULP of the vector's largest absolute component)`.
Both Z magnitudes must fit. Original numbers and deltas are retained; there is
no rounding, blanket Z discard, or relaxed near-zero X/Y/nonzero-to-nonzero rule.
The FCF's actual nonzero body Z (`0.004762500000000003` m) remains significant.

This is an explicitly added representation policy based on the retained repro,
not an API guarantee that drawing Z is always zero. Bundled `IAnnotation.GetPosition`
documents sheet-relative XYZ; `IDisplayData.GetLineAtIndex3` documents ten slots
with start/end XYZ, and `GetTextPositionAtIndex` documents a three-component
display-data offset. Unknown fields, arcs, text planes, style, source parameters
and attachment identity remain outside this rule. The deliberate stricter
near-zero-X test and the previous 190-leaf audit's 187/3 classification remain
unchanged. Same-session export comparison is still exact. The focused five-file
suite passed 289 tests in 3.72 seconds (`run-5qi571og`); a fresh native crank
replay remains required to exercise the previously unreached gates.

The fresh replay at frozen `fb958fda` is retained as
`datum-policy-7vmq0092/pilot.json`, SHA-256
`197fc32a67467c084d8e05fa6fe7e53c3a3ceb8012f1b1aacffe4945ab7e5b89`.
Recipe 24.5471284 s, complete failed pilot 258.9274196 s. Annotation comparison
now passed with zero rejected leaves, 42 existing ULP differences and 15 zero-Z
transitions. The cold source bank passed. All four fresh role/attachment reads
completed, including the journal FACE, but exact built/cold bank comparison
still failed: the only difference was the cross-hole intersection edge's
`geometry/1/trim/CurveTag`, `537446` to `539344`. Every other recorded field
matched. Source-copy/original hashes remained exact, final runtime guards were
empty, and failure capture completed without errors. The fresh PNG was inspected
again with the same readable native journal finish placement.

The raw curve reader and strict same-session/cold CurveTag assertions remain
unchanged at this point. `ICurveParamData.CurveTag` documents a curve ID, without
a cross-reopen lifetime promise. Whether it is appropriate in a cold geometric
equality bank needs a separately reviewed distinction and native identity proof;
the changed tag is not automatically ignored. This replay remains a failure.
