# Installed spring endpoint investigation

This diagnostic investigates the exported upper-eye gap from the native full
build at `3c0c4a97e69ead5f04fa760b8aa507c16143172d` (adapter
`25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`). It is not a spring correction or
native geometry acceptance. The source and its execution token are pinned to
`c3f6c95e1b67184a743a412670d985a2efbaa45307849e46962c5c2695df011f`.

## Retained exported defect

The raw STL SHA is
`d154abf72744102e770dbf8a38e40fba168f2af4903a56a33602a6054076447b`.
Its 87,617 triangles have three exact-coordinate connected components: a
36-triangle upper-eye cap, a 4,861-triangle upper-eye shell and an
82,720-triangle coil/lower-eye component. The tiny cap/shell seam is not evidence
of separate native solids. The upper pieces lie entirely above Y=66.53340148925781
mm; the coil/lower component lies entirely below Y=66.46747589111328 mm.
The empty slab proves an exported gap of at least 0.06592559814453125 mm,
before any Blender processing. One zero-area triangle remains in this replay.

Run from this checkout's own uv environment, with explicitly selected protected
artifacts (these paths name the historical producer, not the runtime checkout):

```powershell
uv run --frozen python cad/scripts/diagnostics/probe_spring_mesh_gap.py `
  --source C:/src/ha-foundations-integration/cad/out/sldprt/channel-spring-installed.SLDPRT `
  --stl C:/src/ha-foundations-integration/cad/out/stl/channel-spring-installed.STL
```

Producer task `part:channel_spring_installed` ran 2026-09-08
00:24:37.839593 through 00:25:21.394547 UTC. Trace
`0xd5edea0a288dc2974cd75b3ac3c2f3d6` has task span `0x5e18a1322c671cd5` and
child `part.build` span `0xd7bcaf42384e2a30`, both OK. The original detailed
render receipt is `cad/out/reports/full3c-geometry-details/provenance.md` in
that producer checkout; both front/side upper-eye images show the separation.

`_spring.py` assumes the helix starts/ends at +X; `_features.py` authors each
hook from that assumed endpoint. Its volume interval permits a full-volume
hook with zero overlap. The native log reports top-hook added volume 11.75 mm3,
equal to its Pappus value; the lower hook added 11.60 mm3. This does not prove
native body count or identify the responsible helix/sweep argument.

## Native readback scope

`diagnostics/probe_spring_endpoints.py` reads only a unique-basename bytecopy.
No native readback has run. The source, execution token, copied bytes, runtime
HEAD, helper files and actual imported adapter are checked before and after the
read. It uses the existing attach-only parent/worker and machine-wide seat lock;
it never opens the original, selects geometry, rebuilds, redraws, saves or exports.
An unrelated visible borrowed document remains outside its close targets.

The reader captures these independent groups and their elapsed read times:

- Exact named feature inventory: `Helix/Spiral1`, `HelixBaseProfile`, `WireProfile`
  and `CoilBody`, including native self-identities. Missing, duplicate or wrong-type
  names fail rather than choosing a similar feature.
- `IHelixFeatureData` definition properties, with raw direction/taper/angle values.
- Both circular profiles in sketch space, their full native transform arrays and
  centers transformed into model space using native math objects.
- All solid bodies from `IPartDoc.GetBodies2(0, False)`, including hidden bodies.
  Native body identity must be distinct; body count is observed, not required to
  equal one. `GetBodyBox` is explicitly approximate and is not used to prove a gap.
- `CoilBody.GetFaces()` boundary edges: surface kind, plane data where applicable,
  exact owning-body identity, native curve kind, trim/tag/sense/start/end fields,
  and circle parameters for circular edges. This is an endpoint witness, not a
  complete BREP or spline-coefficient comparison.

The read budgets are 256 features, 16 solids, 64 coil faces, 64 edges per face and
256 face-edge occurrences in total. Raw returned numbers are not rounded,
reordered or normalized. Unsupported shapes and getter failures remain failures;
the partial receipt retains preceding values. Each group brackets current/active/
named document identity and native dirty state. Final hashes, cleanup and runtime
checks are attempted even after interruption, without replacing the primary error.

## Documented native calls and remaining proof

The bundled official `IFeature.GetTypeName2` table maps `Helix` to
`IHelixFeatureData`, `ProfileFeature` to `ISketch`, and `Sweep` to
`ISweepFeatureData`. The *Change Pitch of Helix* example reads the definition
through `GetDefinition`; the probe copies no setter from it. The *Evaluate Curves
Defined in Sketch Space* example supplies the read-only math sequence:
`ModelToSketchTransform.Inverse()` → `GetMathUtility().CreatePoint(center)` →
`MultiplyTransform(inverse)` → `ArrayData`. The center uses the existing adapter's
typed double-array marshalling (`VT_ARRAY | VT_R8`). No sketch-edit operations
are used.

`IEdge.GetCurveParams3` requires `GetCurve` first. `ICurveParamData.Sense=False`
changes the endpoint interpretation; the receipt keeps that flag and both raw
points instead of silently swapping them. None of these reads establishes that
the stored model is connected or that the assumed +X helix phase is correct.
The documented IHelixFeatureData interface exposes definition properties but no
endpoint method, so direct helix endpoints are explicitly unmeasured. No cast to
`IReferenceCurve` is attempted. No angle, lead, tolerance, feature, surface or export
change is part of this investigation.

After the active build has ended and the operator confirms exclusive seat
ownership, run from this clean candidate checkout. The source path names the
separate protected producer; it is not derived from the diagnostic runtime path.
Use a newly confirmed running PID, not a historical PID from another receipt:

```powershell
$confirmedSpringPid = Read-Host 'Confirmed current SOLIDWORKS PID on the exclusive seat'
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_DIAGNOSTIC_SW_PID = $confirmedSpringPid
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$springCandidate = git rev-parse HEAD
uv run --frozen python cad/scripts/diagnostics/probe_spring_endpoints.py `
  --source C:/src/ha-foundations-integration/cad/out/sldprt/channel-spring-installed.SLDPRT `
  --candidate $springCandidate
```

The command refuses an absent/mismatched source token, dirty runtime, foreign
adapter import, wrong adapter revision or implicit PID before entering the COM
parent. It cannot launch SOLIDWORKS. If the seat needs a licensed restart, use the
existing licensed-launch procedure before this command, not a COM startup path.

Offline tests exercise the actual owned callback with native-shaped doubles,
including two-body readback, borrowed dirty work, unsupported arrays/types,
partial getter errors, interruption and cleanup/checkpoint failures. Both new test
modules and diagnostic scripts are dependencies of the existing `check:recipe`
gate. These tests do not prove native getter success, model topology, or a repair.
