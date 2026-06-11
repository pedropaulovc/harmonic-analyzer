# Photo-vs-CAD comparison pairs

Aligned pairs of real-machine reference images and SolidWorks renders, used
to iteratively tune the models toward the physical device. See
`ATTRIBUTION.md` for reference-image licensing.

## Layout

| path | content |
|---|---|
| `manifest.json` | source of truth: pair id → reference, model, camera pose, 2D align, status |
| `ref/<id>.png` | prepared reference (cropped/rotated, ≤1600 px) |
| `render/<id>.png` | aligned CAD render (+ `.meta.json` staleness sidecar) |
| `composite/<id>_sbs.png` | side-by-side |
| `composite/<id>_blend.png` | red-tinted render over grayscale ref — misalignment is instantly visible |
| `scores.json` | pair → RMS shape score (regression trend only; compare across commits) |
| `findings/iter_NNN.json` | per-iteration vision findings |

## Workflow

```powershell
# 1. curate / re-seed pairs (merge keeps hand-tuned poses)
uv run comparisons/tools/dedup_stills.py
# ... vision agents write references/curation/batches/*.json ...
uv run comparisons/tools/merge_catalog.py
uv run comparisons/tools/extract_frames.py          # full-res video keepers
uv run comparisons/tools/seed_manifest.py

# 2. render (SolidWorks open; sibling venv)
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\render_compare.py --stale-only
#    --selftest validates the euler camera against named views pixel-wise

# 3. recompute composites/scores without SolidWorks (e.g. after align edits)
uv run comparisons/tools/composite.py [--only id1,id2]

# 4. selective model rebuild after fixing a part script
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_all.py --rebuild cone_gear
```

Pair ids are `<model>--<source-id>`; `model` maps to
`cad/out/{sldprt,sldasm}/<dashed>.{SLDPRT,SLDASM}`. Camera convention:
az 0 / el 0 = SolidWorks Front, +az = camera toward the model's +X (right)
side, el = elevation; `target_mm`/`zoom` frame close-ups; poses are refined
by editing the manifest and re-rendering `--only <id>` (no rebuild needed).
