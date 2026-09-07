# Generic drawing silhouette geometry coverage

Spring-hook receipt `datum-policy-_pfvu2ct/pilot.json` rejected only
`checked_empty`: three dimensions had complete semantics, but their sketch10/11
attachments were excluded and the sole surface finish's type46 attachment was
also excluded. The dedicated VIEW bank already supports raw silhouette reads
and passed selection, but post-insertion attachment identity failed separately.
The empty generic bank is missing coverage, not evidence of a detached
annotation; the next native run must read the actual attached silhouette.

The generic snapshot now uses the existing
`_silhouette_attachment_witness.snapshot(app, view, entity)` once per supported
type46 attachment, in its existing annotation loop. The checked row is tagged
`("silhouette", raw_geometry)`; the native face handle is not serialized.
Native GetView identity, finite line/circle parameters, ordered endpoints and
plane/cylinder surface parameters are required. Unsupported shapes fail; raw
values are neither rounded nor transformed. EDGE/FACE/VERTEX behavior is unchanged.

This supplies geometry evidence only. It does not prove persistent identity or
source-topology ownership. The separate VIEW observer still checks drawing-context
persistent IDs and native view/face identity against the freshly resolved role.
The generic empty-coverage, dimension/source, ownership, printed and cold-reopen
gates remain unchanged. Sketch10/11 exclusions remain; synthetic excluded46
fixtures testing the rejection/reporting contract remain unchanged too.

This reuses an implementation, not a measured native result: previously skipped
type46 now costs one helper read per attachment. It adds no whole-document pass
and does not call the two-snapshot identity helper merely to compare an entity
with itself. The existing independent VIEW reads are retained.

Bundled official `ISilhouetteEdge.GetView/GetFace/GetCurve/GetStartPoint/GetEndPoint`
contracts were read in full. They identify the returned objects but do not
establish cold-reopen or view-move/scale coordinate invariance. The next owned
spring-hook pilot must prove the exact raw before/after boundary; no new
tolerance, identity substitute or successful native result is asserted here.

The new spring-shaped fixture reproduced `checked_empty` before the change
(`run-2hio2anb`: 12 failed, 4 passed). It retains three manufactured dimensions,
one supported finish, the four remaining exclusions and exact source context.
Additional controls cover malformed/null/wrong-view silhouettes, sub-rounding
geometry changes, attachment inventory changes and fresh cold native wrappers.

Corrected offline verification: 389 tests passed in 12.72 seconds
(`run-nkiybwxh`), with Ruff and `git diff --check` clean. The exercised files were
`test_generic_silhouette_attachments_drawing.py`, `test_probe_drawing_attachments.py`,
`test_datum_policy_recipes_drawing.py`, `test_datum_semantic_attachment_drawing.py`,
`test_silhouette_attachment_witness_drawing.py`, `test_view_recipe_acceptance_drawing.py`,
`test_view_intersection_curve_witness_drawing.py`,
`test_silhouette_identity_control_drawing.py`, and
`test_drawing_silhouette_identity_drawing.py`. The new test's `_drawing.py`
suffix enrolls it in the existing `check:recipe` discovery rule.
