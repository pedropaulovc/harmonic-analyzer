---
name: sw-gltf-export
description: "SolidWorks exports assembly glTF (.glb) via plain SaveAs3 — meters, named component nodes, PBR materials; pattern-generated instances lose their friendly node name"
metadata:
  type: project
---

SolidWorks 2023+ exports glTF binary via plain `SaveAs3("<path>.glb", 0, silent)` — the
format is inferred from the extension (no format enum; the adapter's `export_file`
maps "glb"→41 but never passes it). Verified live on R2026x with `magnifier.SLDASM`
(2026-07-17): output is **metre units** (SW internal units), one node per visible
component named by `Name2` (`magnifying-wheel-1`), materials preserved as glTF PBR
(metallic appearances render dark in eevee without an environment — meshprobe's
`high_key` preset + white background fixes inspection renders).

**Quirk:** pattern-generated component instances (e.g. `clamp-screw-2` from
`linear_component_pattern`, chain links) export as **numeric node ids** (`13`), not
their `Name2`. Any name-keyed flow (meshprobe addressing, scene-JSON retirement
[[com-seat-lock]] → issue #338) loses identity for patterned children.

**Why:** since PR #339 assemblies ship `cad/out/gltf/<dashed>.glb` instead of the
monolithic assembly STL (nothing ever read its mesh bytes); parts keep mm STL + STEP.

**How to apply:** export assembly GLB on the COM seat with `_save_as(doc, OUT_GLTF/…)`;
inspect with meshprobe ([[meshprobe-usage]]); expect metres, not mm; don't rely on node
names for patterned instances.
