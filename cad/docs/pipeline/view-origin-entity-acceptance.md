# VIEW-origin annotation acceptance (diagnostic only)

The ten existing recipes in this slice obtain explicit annotation entities from
their drawing views, not `ModelEntities`. They need a VIEW witness, not the
MODEL observer's source-part reverse mapping. This does not migrate their
coordinate-picked annotations or prove native acceptance before a full owned
recipe run and cold/printed checks.

`diagnostics/_silhouette_attachment_witness.py` is the first bounded component.
It reads documented `ISilhouetteEdge.GetView/GetFace/GetCurve/GetStartPoint/
GetEndPoint`, `IMathPoint.ArrayData`, `ICurve.IsLine/IsCircle/LineParams/
CircleParams`, `IFace2.GetSurface`, and `ISurface.Identity/PlaneParams/
CylinderParams`. The bundled official references were read before implementation.
`GetFace` does not document a source-versus-view context: no reverse mapping or
persistent source-face provenance is inferred. Same-session `ISldWorks.IsSame`
must establish silhouette, face and view identity separately; matching geometry
never substitutes for that requirement.

Initial supported shape scope is line/circle silhouettes on planar/cylindrical
surfaces, with exact finite native array lengths, nonzero directions and positive
radii. Other shapes fail explicitly. Ordered endpoints and parameters remain
unrounded, so cold arithmetic differences remain enumerable. A circle plus
endpoints is not claimed to describe its complete trim parameterization.
`IFace2.GetBox` is deliberately absent from this new witness: its documented
approximate, rebuild-variant values are not exact geometry evidence.

Offline regression command (no SolidWorks):

```powershell
$env:PYTHONPATH='C:/src/ha-perf-shaft-entities/SolidworksMCP-python/src;C:/src/ha-perf-view-origin-acceptance/cad/scripts'
uv run --no-project --python C:/src/harmonic-analyzer/.venv/Scripts/python.exe python -m pytest cad/scripts/test_silhouette_attachment_witness_drawing.py -q
```

The initial 29 tests pass. Wrong/equal-geometry native identities, wrong views,
substituted faces, malformed/null/nonfinite arrays, unsupported shapes and tiny
unrounded parameter changes reject. No native invocation or production recipe
change is included in this checkpoint.

## Full-recipe enrollment

The separate `ViewEntityAcceptance` observer leaves `EntityAcceptance`'s MODEL
comparator and production recipes unchanged. It wraps the existing selector and
the existing datum/FCF/SF creation entrypoints, including typed PMI's internal
calls. It checks the **actual** selection-manager object/count/type, not the
legacy `edge_entity` helper's returned argument. Unknown explicit calls, omitted
manifest roles, changed native identities, owner views, annotation kinds or raw
silhouette geometry reject. Wrappers restore even on setup/insertion failure.

| recipe | explicit VIEW calls | of which SF | explicit type46 |
|---|---:|---:|---:|
| alignment_pinion | 1 | 1 | 0 |
| cone_gear_shaft | 4 | 2 | 0 |
| crank_drive_gear | 3 | 1 | 1 |
| crank_pinion | 3 | 1 | 1 |
| cylinder_gear | 2 | 1 | 0 |
| rack_pinion | 1 | 1 | 0 |
| transgear_feed_pinion | 1 | 1 | 0 |
| transgear_pinion | 1 | 1 | 0 |
| crankshaft | 4 | 1 | 1 |
| spring_hook | 1 | 1 | 1 |
| total | 21 | 11 | 4 |

The cone's coordinate-picked tip-runout silhouette is a fifth type46 call,
reported under `coordinate_picked`, not in the exact-origin/migration count.
Other coordinate-picked annotations retain the existing full generic content,
geometry, dimension and layout witnesses. A source-code coverage regression
derives every explicit datum/FCF/SF label (including typed placement entries)
and compares that inventory with this manifest.

After the full recipe and after cold reopen, each explicit role re-runs the
**existing** resolver in its freshly resolved exact native view, then requires
`IsSame(resolved, attached) == 1`. The same-session bank also retains the original
argument/selected identity, initial silhouette face handle and raw geometry.
Cold checks never call closed handles. This proves consistency with those
existing selectors, not unique feature ownership: the older radius/visibility
selectors are not newly promoted to source-feature identity proofs. Crankshaft
end roles additionally require two distinct end stations. Spring hook's existing
resolver calls `ActivateView`; that state change is explicitly reported, not
described as a getter-only read. No new geometry-selection mechanism is added.

Every target reuses its existing source `DRAWING_DIMENSIONS` manifest (spring
hook's is in `spring_hook_notes`), and pins its native source hash. All ten
registered hashes were independently re-read from root `cad/out/sldprt` and
matched on 2026-09-06. Spec/builder/recipe bytes, complete helper/config/template
closure and the **actual imported adapter origin** stay frozen. VIEW targets do
not call or fabricate the MODEL observer's source-face snapshot. Their source
parameter/tolerance/BASIC, immutable original/owned-copy hash, same-session
native drawing, native save, cold annotation/layout and output checks remain.

Existing edge/face geometry uses the legacy attachment witness plus explicit
finite/shape checks; the new unrounded silhouette witness is separate. Raw
before/after silhouette arithmetic is not given a new cold epsilon. Unsupported
native shape or a genuine existing recipe/layout failure is a failed pilot,
not permission to exclude the attachment or retry a fallback. Stage read timings
are instrumentation cost, not a drawing performance result.

The reused factory ABI consumes the normal/prepared factory exactly once. A
parent-reviewed, explicitly granted invocation can select one target at a time:

```powershell
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
$env:HARMONIC_DIAGNOSTIC_SW_PID='<freshly verified licensed PID>'
uv run python cad/scripts/diagnostics/probe_datum_policy_recipes.py --candidate HEAD --target alignment_pinion --factory normal --source-root C:/src/harmonic-analyzer/cad/out/sldprt --guard-root C:/src/harmonic-analyzer/cad/out/sldprt
```

No native invocation is included in this implementation. In particular,
passing offline tests is not full native/printed acceptance of any of the ten
recipes; the first real failure remains a retained failed result.

Combined verification: 391 offline tests passed in 9.83 s across the VIEW and
silhouette witnesses, existing full pilot, MODEL shaft observer, SF validation,
shaft PMI, context matrix, factory consumption and benchmark-loader suites.
The 56 VIEW tests include every explicit source-code call, both fresh/cold
identity banks, null fresh resolution, original-face substitution under the
same silhouette handle, source-save/title failures, actual manager substitution
despite a correct legacy helper return, and wrapper restoration. The unchanged
MODEL helper has no diff in this slice. Ruff and `git diff --check` pass.
