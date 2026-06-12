# Photo-vs-CAD comparison pairs

Aligned pairs of real-machine reference images and SolidWorks renders, used
to iteratively tune the models toward the physical device. See
`ATTRIBUTION.md` for reference-image licensing.

## Layout

| path | content |
|---|---|
| `manifest.json` | source of truth: pair id → reference, model, camera pose, 2D align, tier, status |
| `index.html` | inspection gallery (tier + text filters; drag the ref⇆cad reveal slider) — `uv run comparisons/tools/gallery.py` |
| `ref/<id>.jpg` | prepared reference (cropped/rotated, ≤1600 px) |
| `render/<id>.jpg` | raw CAD render, content-trimmed, black background (+ `.meta.json` staleness/engine sidecar) |
| `composite/<id>_cad.jpg` | render fitted into the reference frame (same scale/offset as the blend layer) — the slider's top image |
| `composite/<id>_blend.jpg` | red-tinted render over grayscale ref — misalignment is instantly visible |
| `scores.json` | pair → RMS shape score (regression trend only; compare across commits, same engine) |
| `findings/iter_NNN.json` | per-iteration vision findings |

## Workflow

```powershell
# 1. curate / re-seed pairs (merge keeps hand-tuned poses)
uv run comparisons/tools/dedup_stills.py
# ... vision agents write references/curation/batches/*.json ...
uv run comparisons/tools/merge_catalog.py
uv run comparisons/tools/extract_frames.py          # full-res video keepers
uv run comparisons/tools/seed_manifest.py

# 2a. render via SolidWorks (SolidWorks open; sibling venv)
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\render_compare.py --stale-only
#    --selftest validates the euler camera against named views pixel-wise

# 2b. or render offline (no SolidWorks): refresh the STL cache once after
#     any rebuild, then Blender replays the same manifest cameras
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\export_models.py
uv run comparisons/tools/render_offline.py [--only id,..] [--stale-only]
#    parts render from their own STL; assemblies instance per-part STLs
#    (metres, untranslated) through the scene graph in cad/out/boxes/*.json,
#    with each component's SolidWorks appearance RGB as Workbench object
#    colour. Ortho only; sidecars carry "engine" — score trends are only
#    comparable within one engine. parity_check.py measures silhouette IoU
#    between the backed-up and current renders (instanced-vs-monolith
#    baseline: 0.99+).

# 3. hand-tune a pose: windowed Blender opens the pair's render scene with
#    the photo as a half-transparent camera background; the viewport is
#    locked to the render camera, so orbit/pan IS the adjustment (sidebar
#    N > Pose: ortho scale = zoom, photo opacity, Save pose to manifest).
#    Saved az/el/roll/target_mm/zoom re-render via --stale-only above.
uv run comparisons/tools/pose_edit.py <pair-id>    # --selftest: math check

# 4. recompute composites/scores without rendering (e.g. after align edits)
uv run comparisons/tools/composite.py [--only id1,id2]

# 5. selective model rebuild after fixing a part script
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_all.py --rebuild cone_gear
```

Pair ids are `<model>--<source-id>`; `model` maps to
`cad/out/{sldprt,sldasm}/<dashed>.{SLDPRT,SLDASM}`. Camera convention:
az 0 / el 0 = SolidWorks Front, +az = camera toward the model's +X (right)
side, el = elevation; `target_mm`/`zoom` frame close-ups; poses are refined
by editing the manifest and re-rendering `--only <id>` (no rebuild needed).
