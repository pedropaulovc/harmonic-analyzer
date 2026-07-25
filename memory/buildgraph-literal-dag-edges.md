---
name: buildgraph-literal-dag-edges
description: "_buildgraph derives assembly DAG edges by scanning build scripts for quoted stem names — so a _config.machine(\"frame\", ...) call inside an assembly script reads as a false dependency on frame.SLDASM"
metadata:
  type: project
---

`_buildgraph._references(asm, candidate)` decides an assembly's prerequisite
edges with a regex over its build script's SOURCE:
`"<dashed-stem>` followed by a non-alphanumeric. That is deliberate (it is the
single primitive `references_of`/`dependents_of` invert), and its docstring
already warns about the `"channels"` vs `channel` near-miss.

The sharper edge: **subsystem names that are ALSO assembly stems.** `frame` is
both `cad/config/machine/frame.yaml` and `frame.SLDASM`, so writing the ordinary
config accessor

```python
COLUMN_X = float(_config.machine("frame", "column_x_mm"))
```

inside `build_summing_assembly.py` makes the graph believe summing depends on
`frame.SLDASM` — and `check:graph`'s `test_output_subs_reference_their_parts_only`
fails with `summing references non-parts: {'frame'}`. Nothing about the call is
wrong; the LITERAL is what is seen.

**Fix (2026-07-24, [[upper-frame-reanchor]]):** put the accessor calls in a
pure-data module the matcher never scans as a source — `cad/scripts/frame_anchors.py`
— and import the constants. `config_files_of`/`module_deps_of` follow the import
transitively, so `machine/frame.yaml` stays in every consumer's recipe and cache
key; only the false artefact edge disappears. This is also the better shape
anyway: one chokepoint for the four stations instead of a literal per script.

Applies to any future subsystem file whose name collides with an assembly stem
(`channel`, `pen`, `magnifier`, `summing`, `paper-drive`, `drive-train`,
`frame`). Reach for a `*_anchors`/`*_geom` module rather than a bare accessor
inside an assembly script.
