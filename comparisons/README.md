# Photo-vs-CAD comparison pairs

Aligned pairs of real-machine reference images and SolidWorks renders, used
to iteratively tune the models toward the physical device. See
`ATTRIBUTION.md` for reference-image licensing.

## Layout

Tracked = source; **regen** = derived, gitignored and rebuilt by the tools below
(they drift as the model or the reference crops change). The `export` stage
produces the gallery from the freshly-exported STLs
(`cad/scripts/export_models.py:refresh_comparison_gallery`, best-effort: needs
Blender), and each release then **ships that snapshot inside its bundle** under
`comparisons/` (`cad/scripts/cut_release.py:stage_comparisons`). The only tracked
inputs are `manifest.json`, `ATTRIBUTION.md`, this README and `tools/`; everything
else regenerates (the reference *source* photos live in the pinned `references`
submodule).

| path | tracked? | content |
|---|---|---|
| `manifest.json` | tracked | source of truth: pair id → reference, model, camera pose, legacy content-fit 2D align, tier, status |
| `ATTRIBUTION.md` | tracked | CC BY credits/licensing for the reference photos (ships in every release bundle) |
| `ref/<id>.jpg` | regen | prepared reference (cropped/rotated, ≤1600 px) — re-derived from the `references` submodule by `prepare_reference` |
| `index.html` | regen | inspection gallery (tier + text filters; drag the ref⇆cad reveal slider) — `uv run comparisons/tools/gallery.py` |
| `render/<id>.jpg` | regen | raw CAD render (+ `.meta.json` staleness/engine/registration sidecar); Blender preserves the authored camera frame, while SolidWorks captures are content-trimmed |
| `composite/<id>_cad.jpg` | regen | render registered from sidecar metadata into the reference frame (same scale/offset as the blend layer) — the slider's top image |
| `composite/<id>_blend.jpg` | regen | red-tinted render over grayscale ref — misalignment is instantly visible |
| `scores.json` | regen | pair → RMS shape score (regression trend only; compare across commits, same engine) |
| `findings/iter_NNN.json` | — | per-iteration vision findings |

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

## Head-less inspection — meshprobe

`pose_to_meshprobe.py` replays a manifest pose into
[meshprobe](https://github.com/pedropaulovc/meshprobe) — the same vantage,
head-less, on the assembly **GLB** instead of the STL cache. It reads a pose
(a `manifest.json` pair, a `findings/<pair>_deltas.json`, or a bare camera
dict) and **emits** the `meshprobe` command sequence (`open → view-orbit →
illumination-set → render-image`); it does not run meshprobe itself.

**Prerequisite — the machine GLB** at `cad/out/gltf/<dashed>.glb` (the same
metre-unit glTF `export_models.py` writes). Produce one either way:

```powershell
# from the SolidWorks seat: open a .SLDASM and SaveAs3 it to .glb
uv run python cad/scripts/export_glb.py <dir-with-the-assembly>/harmonic-analyzer.SLDASM
# or add --fetch-glb below to pull gltf/<model>.glb from the latest release bundle
```

```powershell
# print the commands for one pair (id substring)
uv run comparisons/tools/pose_to_meshprobe.py --pair ch30-p002

# actually render it: pipe the emitted commands to a shell (bash — see quoting note)
uv run comparisons/tools/pose_to_meshprobe.py --pair ch30-p002 | bash
uv run meshprobe close --all            # stop the Blender daemon when done

# many poses, ONE open: --batch shares a single meshprobe session so the (large)
# GLB is imported once instead of re-opened per pair
uv run comparisons/tools/pose_to_meshprobe.py --batch | bash

# just the computed params, no shell
uv run comparisons/tools/pose_to_meshprobe.py --pair ch30-p002 --format json
```

The emitted commands invoke `uv run meshprobe` (so the pipe-to-`bash` flow works
without a global install; override with `--meshprobe`). Renders land in
`comparisons/render/meshprobe/<id>.png`. Useful flags: `--batch` / `--session
<name>` (one shared session, open once), `--canvas WxH` (forces the render
canvas — **distance depends on its portrait/landscape aspect**, so pass it when
no reference image is available or the run warns about the landscape default),
`--glb <path>` / `--fetch-glb` (GLB source; the scene-bbox source tracks it),
`--boxes <path>` (explicit per-part boxes; required for `frame_components`
poses), `--blender <path>` (override; by default the emitted `open` omits it so
meshprobe locates Blender itself).

Mapping (verified against the `open` receipt): pose_studio model coords
`(x, y, z)` → meshprobe world `(x, −z, y)`; `azimuth = az − 90`,
`elevation = el`, roll passthrough; distance = the same fitted `cam_dist` as
`render_offline`. The GLB is metres and meshprobe reports/accepts mm, so the
default `--unit-scale 1.0` is correct.

> **PowerShell quoting**: the emitted `--projection-json '{…}'` uses bash
> single-quotes. On PowerShell run the pipe under `bash`/Git Bash, or use
> `--format json` and build the call yourself.
