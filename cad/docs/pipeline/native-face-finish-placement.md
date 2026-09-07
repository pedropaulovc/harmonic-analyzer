# Native FACE placement for shank and bearing-journal finish

This two-recipe candidate changes drawing attachment/placement, not source
geometry or surface-finish specifications. Native acceptance is still pending.

## Why change the recipe rather than silhouette equality?

The spring boundary control at `9ef1f724` retained
`cad/out/reports/datum-policy-ydaui7tb/pilot.json`, SHA-256
`f104572a9040639e0cc8e53184421484766ea2043c914fcfbe4129ac984bbe71`.
Expected and selected silhouette IDs compare equal; the annotation's silhouette
ID differs already after styling, before clear/rebuild. Every object passes its
self-comparisons. After rebuild, all five owning-view comparisons and all 21
underlying-face comparisons return native equality. All five raw line/end-point
and cylindrical-surface records are exactly equal. The original PID predicate
fails, as recorded; this is not native layout acceptance.

The bundled `GetPersistReference3` and `IsSamePersistentID` contracts identify
objects. They do not promise that view-enumerated and annotation-returned
silhouette objects have identical IDs. `ISilhouetteEdge.GetFace` identifies the
underlying face. Both existing finish specifications control an entire cylinder,
so explicit FACE attachment states the physical requirement directly without
adding another silhouette equality rule or numeric allowance.

## Bounded change

- Spring hook uses `GetFace` on its existing shank resolver result, rejects null,
  and passes that exact VIEW-origin face to the existing surface-finish helper.
- Crankshaft reuses the journal face already selected for its centerline.
- Both omit `symbol_xy` and leader coordinates. The existing helper selects
  `swNO_LEADER`; `InsertSurfaceFinishSymbol3` documents that location arguments
  are ignored in this mode. No `SetPosition2` call is added.
- Fresh diagnostic roles now resolve these two FACE entities. All 21 explicit
  role names and 11 finish roles remain; only these two types change. The two
  tooth-tip FCF silhouette roles and historical SHANK/JOURNAL resolver controls
  remain unchanged, as do all silhouette PID/raw rejection predicates/tests.

The old recipe source-string tests deliberately required silhouette calls and
the old journal coordinates. That contradiction was raised and the two-recipe
contract change approved before updating those assertions. It is not a waiver
for different faces, unknown identity, another view, or geometry changes.

## Acceptance still required

Existing selected-to-attached native identity checks, controlled-face validation,
and the VIEW observer's complete built/fresh-cold banks remain mandatory. Its
visible/on-sheet/nondangling checks are distinct from insertion's anchor warning;
the full layout, source/content/BASIC, printed output and cold-reopen gates must
still pass. Neither adjacent FACE examples nor offline tests prove native
no-leader placement fits these two drawings. Use the existing owned full-recipe
pilot with explicit `spring_hook` and `crankshaft` targets, unique immutable source
copies, exact original/copy/runtime hashes, and scoped cleanup. No native run,
source rebuild, output publication or new equality tolerance belongs to this patch.

Offline verification: the seven initial recipe/resolver cases failed before the
change. After the approved callsite/enrollment assertion updates, 249 focused
tests passed in 11.64 s (`pytest-telemetry/run-qmsroqku`), including the unchanged
silhouette rejection controls. Another 144 attachment/surface-finish, buildgraph
and part-isolation tests passed in 19.54 s (`run-1hulcj49`). Ruff's F checks and
`git diff --check` passed. These are COM-free test results, not native acceptance.
