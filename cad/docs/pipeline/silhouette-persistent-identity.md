# Drawing-context silhouette identity

This corrects the identity predicate in the new explicit-position attachment
guard and its owned VIEW diagnostic. It does not migrate another recipe's
attachment or change its dimensions, geometry or layout.

## Native premise

The retained spring-hook control at `fc0139e2` (`datum-policy-0akutfu6`) obtained
different direct `IsSame` handles for the original and selected silhouette but
byte-identical, 1239-byte references from the **drawing** extension. The source
extension did not supply an original-silhouette reference. Byte equality alone
was not accepted as proof.

The subsequent comparator control at `7f382136`
(`cad/out/reports/datum-policy-rm_6b7hu/pilot.json`) returned native
`IsSamePersistentID=1` for all five drawing-context comparisons, including
original/selected silhouettes. The owned source `Hook` feature independently
passed self-identity and persistent round trip. Source-context silhouette
references/comparisons did not provide a valid identity witness. Both document
dirty flags were unchanged. The main evidence receipt remains authoritative;
these are comparator controls, not full drawing/cold acceptance.

Official `GetPersistReference3`, `IsSamePersistentID`, the persistent-reference
guide and the selected-object comparison C# example were read. References are
document-related, and their encoding can change across rebuilds/releases.
Accordingly, the new predicate calls the native comparator on two checked
`VT_ARRAY | VT_UI1` values and accepts only integer `1`. Neither raw byte equality
nor direct wrapper inequality decides silhouette identity. Missing, malformed,
different and unknown IDs still fail. The native 1D contiguous `memoryview`
format `B` is supported without reinterpreting other buffer types.

## Changed consumers

One production-safe module, `_drawing_silhouette_identity`, owns the byte
decoder, typed variant and drawing-only predicate. It imports no diagnostics.
The diagnostic control reuses the same byte handling.

| Consumer | Type-46 comparison |
|---|---|
| `_drawing_common._validate_explicit_annotation_attachment` | Original VIEW entity versus actual attachment |
| VIEW observer selection | Original VIEW argument versus actual selected silhouette |
| VIEW observer attached/final/cold bank | Fresh resolved silhouette versus actual attachment |
| VIEW observer built bank | Original silhouette versus freshly resolved VIEW role |

Every call receives `adapter.currentModel`, not `view.ReferencedDocument`; the
helper requires native document kind 3. Production already checks the exact
annotation owning view before calling it. The diagnostic's existing owned
lifecycle supplies current-document identity, while the raw silhouette reader
still checks each `GetView()` with native `IsSame`. Cold calls use only the
reopened drawing and newly resolved handles; old reference bytes are evidence,
not a cold lookup or equality key.

EDGE/FACE, MODEL reverse mapping, annotation/view identity and underlying-face
`IsSame` remain unchanged. Complete raw geometry and built/cold bank equality
remain unchanged. Equal PIDs cannot excuse a wrong face/view or changed curve.

Current explicit type-46 roles are crank-drive-gear and crank-pinion tooth-tip
GTols, crankshaft journal finish, and spring-hook shank finish. The cone-shaft
coordinate-picked silhouette remains separately identified as such; no original
explicit entity is invented for it.

## Intentionally unchanged paths

`_validate_native_annotation`'s no-position branch still uses direct `IsSame`.
The generalized native-callout symbol/obstacle, GTol, and final packing attachment
loops also retain their existing predicates. The affected explicit-position
recipes do not invoke `repair_project_drawing_layout`; no native evidence yet
justifies migrating these latent type-46 paths. A future use there must be tested,
not assumed covered by this change.

The old experimental tests asserting that direct silhouette `IsSame=0` alone
means wrong attachment conflicted with the native positive control. That
contradiction was raised before editing them. Their rejection cases now return
native PID `0`, `-1`, invalid data or failed calls; failure-evidence preservation
still runs. Added positives reproduce direct `IsSame=0` with drawing PID `1`,
including a fresh built wrapper and cold resolved/attached wrappers. Wrong
view/face and exact raw-arithmetic rejection tests retain their requirements.

Native full-recipe, save/cold and printed acceptance remain required. There is
no performance claim: exact PID validation adds getter/comparator work and does
not remove source/hash/content or whole-sheet gates.

Offline verification: 413 focused/adjacent tests passed in 23.39 s, including
part isolation (`pytest-telemetry/run-2cbj52wm`). No COM invocation was performed
in the implementation worktree.

## Full-recipe controls: selection passes, post-rebuild attachment fails

The integrated predicate passed 223 focused tests in the root (`run-wa5cptvr`,
12.04 seconds). Native controls with adapter `25bc99b1` and licensed PID 31860
then advanced beyond the old selection failure, but neither passed the recipe:

| Target / frozen root | Receipt SHA-256 | Recipe / full pilot seconds |
|---|---|---:|
| crankshaft / `39615df9` | `c93a0a2b071b715bec5fb996b80d53e951129568fe63caeca8b897af829ea30c` | 41.638551 / 182.414780 |
| spring-hook / `335e6ad8` | `4d4a4fe9b7b37423ec22b810ec3cc596afcbcc53d2618899cffe4bfaa94f4284` | 27.823261 / 125.830814 |

Receipts are respectively `cad/out/reports/datum-policy-wzed5ja8/pilot.json`
and `cad/out/reports/datum-policy-_pfvu2ct/pilot.json`. Both selected-stage
silhouette comparisons returned native PID `1`, with the raw geometry checks
passing. Crankshaft's three EDGE roles also passed selection and insertion,
including the cross-hole intersection curve. Both recipes subsequently failed
the production SF attachment predicate with native PID `0`, after the existing
`ClearSelection2` / `EditRebuild3` sequence. The validator's failed comparison
did not retain its raw references, so these receipts cannot distinguish a changed
attachment from an earlier silhouette wrapper invalidated by insertion/rebuild.
No identity predicate was bypassed and no built/cold acceptance was reached.

Both original/owned-copy source hash and source-parameter preservation checks
passed, with no final runtime guard errors. Crankshaft failure capture completed
without secondary errors. Spring's improved rejected-snapshot evidence proves
its separate generic coverage failure is **`checked_empty`**, not dimension
exclusion: all three dimensions were captured, with zero excluded dimensions.
The generic geometry reader supports only EDGE/FACE/VERTEX, whereas this drawing
has an SF silhouette (46), dimension sketch points (11), a sketch segment (10)
and a center mark (annotation 13). Both rejected snapshots retain those exact
reasons. This observation does not waive either the generic coverage gate or the
dedicated VIEW entity bank; that composition still needs a supported contract.
