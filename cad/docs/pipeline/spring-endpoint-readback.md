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

The owned-copy native reader is being prepared. No native readback has run.
It must preserve named helix definition, sketch-space profile geometry with its
native model-to-sketch transform, evaluated CoilBody face/edge endpoints, all-solid
body identities, original/copy hashes, dirty state and no-save cleanup.
The documented IHelixFeatureData interface exposes definition properties but no
endpoint method. Any unsupported endpoint exposure must remain explicitly
unmeasured, not calculated and labeled native. No angle, lead, tolerance, feature,
surface or export change is part of this investigation.
