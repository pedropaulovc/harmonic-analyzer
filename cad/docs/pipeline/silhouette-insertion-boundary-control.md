# Silhouette SF insertion boundary control

This diagnostic preserves the failing production identity gate. It does not
accept a silhouette because its geometry or persistent-reference bytes match.
It has not yet run natively.

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

The existing owned full-recipe pilot installs the observer only for the existing
VIEW-origin JOURNAL/SHANK surface-finish roles. Production functions and their
acceptance logic remain unchanged.

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

Official bundled contracts used: `GetPersistReference3` is document-scoped and
its internal bytes may change across rebuilds; `IsSamePersistentID` compares the
referenced objects (0 different, 1 same, -1 unknown in the official example).
`GetAttachedEntities3` returns silhouettes as `ISilhouetteEdge`; `GetView`,
`GetFace`, `GetCurve` and endpoint getters provide the corresponding witnesses.
No source-context silhouette persistence is assumed.

Run the existing `probe_datum_policy_recipes.py --target spring_hook` (or
`--target crankshaft`) only with the main agent's explicit native seat grant,
frozen source/adapter, expected PID and existing disabled-autostart/cache flags.
There is no new acceptance mode or alternate runner.

Offline tests:

```powershell
uv run python -m pytest -q cad/scripts/test_silhouette_insertion_control_drawing.py cad/scripts/test_silhouette_identity_control_drawing.py cad/scripts/test_view_recipe_acceptance_drawing.py
```
