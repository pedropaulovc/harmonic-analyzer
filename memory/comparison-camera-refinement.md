---
name: comparison-camera-refinement
description: How the 8-view comparison cameras were pose-fit and how to regenerate the colored gallery offline without SolidWorks
metadata: 
  node_type: memory
  type: project
  originSessionId: 532b8e19-586c-4c3d-aa5c-7896df30430f
---

8-view comparison cameras (cad/comparisons/manifest.json, ch30 p002-p009) were a clean turntable approximation (el=0, roll=0, az in 45° steps). Refined 2026-06-17 on branch claude/harmonic-analyzer-stl-blender-c4gg33.

**Camera pose fit** (commit 9f842ec; the 2D-align half is SUPERSEDED — `tune_align.py` was deleted 2026-07-24 in PR #411 and align is ignored on the `camera_frame` path every pair now uses, see [[comparison-pose-vision-first]]): tune_align.py only fits 2D align (scale/dx/dy), never 3D orientation. Fit az/el/roll per view by maximizing silhouette IoU between a real Workbench render and each ref photo, scored like tune_align (render content-mask best-fit onto ref brightness-mask). el settled small/physical (−7..+10°), not 0. Then re-fit align (pan/zoom) via tune_align.tune_pair against new-camera renders (commit b15ed24) — changing orientation moves the silhouette so old align went stale (bases drifted).

**Offline colored gallery regen WITHOUT SolidWorks/fresh cad/out cache** (commit 1e541fa): render_offline.py needs cad/out cache (export_models.py → SolidWorks), which goes stale when geometry is in flight (e.g. summing-lever). Workaround:
- Geometry+positions: v0.1.1 release STEP `cad/out/release/.../step/harmonic-analyzer.STEP` → `cascadio.step_to_glb` (pip/uv `--with cascadio`). glb is Z-up, meters, 341 positioned objects; mesh data names carry part stems (`tube-frame.001`). Rotate −90° about X to match the SolidWorks/STL frame the camera convention assumes (az0/el0 from +Z, +Y up).
- STEP carries NO per-part colors (single mat_0). Recover colors from build scripts: per-part `MATERIAL` const → export_models.MATERIAL_RGB, OR `apply_color(adapter, CONST)` override (CASTING_GREEN=(0.13,0.45,0.42) teal frame, POLISHED_STEEL, PANEL_BLACK, SPRING_BLACK, STAINED_OAK, PAPER_WHITE, BAR_STEEL). Same cascade export_models.doc_rgb uses, so colors match the canonical pipeline.
- Render Blender Workbench STUDIO + color_type OBJECT (obj.color), black bg, then black-composite + trim like render_offline; place into ref frame with composite.aligned_render(manifest align).

**Washed-out colours fix** (commit 3df5b43): under `blender -b --factory-startup`, Blender 4.x/5.x defaults the view transform to **AgX**, a film tone-map that desaturates the per-part appearance RGBs — renders look pale vs SolidWorks (plain sRGB). Fix = `scene.view_settings.view_transform = "Standard"` (added to canonical `cad/comparisons/tools/blender_worker.py`; applies to Workbench too). STUDIO omnidirectional light also softens contrast vs SW; `light="FLAT"` = pure albedo if needed. NOTE: the committed gallery (1e541fa) predates this fix so it's still AgX-pale; regen after a model update will be faithful.

Result: RMS score (scores.json, lower=better) dropped on all 8 views (e.g. p005 103.5→81.0, p004 98.9→79.5). *(NOTE: 2026-06-17 refinement snapshot — the gallery has been re-tuned since; current `cad/comparisons/scores.json` reads lower, e.g. p005 ≈ 70.9, p004 ≈ 75.3. The `cascadio`/STEP→glb path is a documented workaround, not wired into the pipeline.)* Sidecar model_mtime set to release SLDASM so render_offline still treats them stale vs live cache. Headless Linux Workbench needs libEGL + LIBGL_ALWAYS_SOFTWARE=1/llvmpipe (slow); a real GPU (Windows) renders fast. See [[harmonic-analyzer-project]], [[motion-study-pipeline]].
