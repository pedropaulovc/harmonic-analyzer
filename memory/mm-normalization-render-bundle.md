---
name: mm-normalization-render-bundle
description: Render cache + release normalized to mm; cut_release ships scene graph + per-config STLs so render_offline renders from a downloaded release
metadata: 
  node_type: memory
  type: project
  originSessionId: 532b8e19-586c-4c3d-aa5c-7896df30430f
---

2026-06-17, on main. Goal: a downloaded GitHub release should be renderable by `comparisons/tools/render_offline.py` with NO SolidWorks (replacing the throwaway `C:\ha-render` STEP→glb workaround).

**Unit insight:** Blender rendering is unit-agnostic — `blender_worker.py` frames from bbox *ratios*; it only requires mesh unit == transform unit. The old render cache (cad/out) was internally consistent in metres and rendered fine. The real bug was *inconsistency*: export_models wrote per-part STLs in metres but the monolithic asm STL in mm, and the scene JSON was metres while the release `stl/` is mm — so the release couldn't pair. User chose "normalize all to mm" (one clean convention; matches the project's mm sketches + slicer-friendly release stl/).

**Phase 1 (commit 2840e4b) — all mm:** export_models STL units m→mm (swExportStlUnits 0); scene-graph boxes + transform *translations* ×1000 (SW API reports metres); scene JSON `"unit":"mm"`. Removed the mono-STL toggle that flipped the pref back to metres mid-run (now a bug once default is mm). `_common.stl_bbox_mm` dropped its ×1000 (STLs already mm) — mirror_placement math unchanged (identical mm values). blender_worker doc-only. ⚠️ REQUIRES `export_models.py --force` (SW) to regen the cache so on-disk STLs match the changed stl_bbox_mm reader; until then a build's mirror_placement would break.

**Phase 2 (commit c5544f7) — render-ready release:** cut_release.export_neutral now exports one-per-part STL PLUS one extra STL per referenced config for the only 2 multi-config parts — `cone-gear` (20: T006–T120) and `transgear-removable` (3: T12/T18/T24), 23 total — named via the scene graph's `mesh` key (driven off the scene JSON so names match exactly, via doc.ShowConfiguration2). bundle copies the mm scene JSON to `boxes/harmonic-analyzer.json`. preflight requires the scene JSON exist, be `unit=="mm"` (rejects pre-normalization metre cache), and be ≥ SLDASM mtime.

**Findings:** only cone-gear + transgear-removable need per-config (single SLDPRT, configs = distinct geometry used at once); every other ~82 parts are fine one-per-part. The 12 parts absent from the render cache are NOT needed: `eccentric-cam` (only in build_fourbar_test.py), `pinion-drum` (superseded, never inserted — dead part), `channel-spring-installed-stretch00-09` (live, but inside the channel subassembly; don't surface in the top assembly Default config the gallery renders). *(NOTE 2026-07-04: part count is now ~94; `eccentric-cam` and `build_fourbar_test.py` were REMOVED 2026-06-21 — the cam is integral to the cylinder gear — so this absent-parts list is a 2026-06-17 snapshot.)*

**NOT YET VALIDATED** (no SW run; user's summing-lever work in flight, SW session was open — `~$` locks): needs `export_models.py --force` then a test `cut_release.py --draft` to confirm ShowConfiguration2 export + preflight + bundle. See [[comparison-camera-refinement]], [[harmonic-analyzer-project]], [[solidworks-3dx-launch]].
