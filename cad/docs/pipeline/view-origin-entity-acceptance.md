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
