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

# 3. recompute composites/scores without rendering (e.g. after align edits)
uv run comparisons/tools/composite.py [--only id1,id2]

# 4. selective model rebuild after fixing a part script (dependent assemblies refresh)
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe -m doit part:cone_gear
```

## Interactive posing — Blender pose studio

`pose_studio.py` opens a pair's model **and** its book reference in Blender and
lets you dial the manifest camera live against the overlay, instead of
hand-editing `az/el/roll/zoom/target` and re-rendering. No SolidWorks needed —
just `uv` + Blender.

```powershell
# export the STL cache once after any rebuild (same prerequisite as render_offline)
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\export_models.py
# launch — the script relaunches itself inside Blender's GUI
uv run comparisons/tools/pose_studio.py --pair ch30-p003
```

`--pair` matches a manifest pair id or any substring. Point at a different
Blender with `--blender <path>` or `$HARMONIC_BLENDER` (default `Blender 5.1`).

In Blender, open the **Harmonic** tab of the N-panel (press `N`):

- **Build / Reload Scene** — loads the pair and seeds every slider from its saved pose.
- **Orientation / Target / Framing** — az/el/roll, the framing centre (the other 3 axes), zoom + lens (mm).
- **Reference** — book overlay opacity / scale / shift (shown in camera view only).
- **Navigate** — MMB orbit · Shift+MMB pan · scroll zoom. `Numpad 0` toggles camera view and drops you onto the camera's *exact* vantage — no jump. **Capture From View** bakes a free-orbit angle back into the pose; **Frame Model** recovers the orbit if it greys out.
- **Save Pose To Manifest** — writes az/el/roll/target/zoom/lens onto the pair.

The pose round-trips 1:1 with `render_offline.py`, so after saving,
`render_offline.py --only <id>` reproduces it exactly. **Create Pair** adds a
new id + model + reference to the manifest in place.

> Verify the camera behaviour after touching the studio: `pose_studio.py --pair
> <id> --shots <dir>` drives the real UI (build → toggle camera view → capture
> each state → quit) and drops before/after PNGs in `<dir>`.

Pair ids are `<model>--<source-id>`; `model` maps to
`cad/out/{sldprt,sldasm}/<dashed>.{SLDPRT,SLDASM}`. Camera convention:
az 0 / el 0 = SolidWorks Front, +az = camera toward the model's +X (right)
side, el = elevation; `target_mm`/`zoom` frame close-ups; poses are refined
by editing the manifest and re-rendering `--only <id>` (no rebuild needed).
