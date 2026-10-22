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
`cad/comparisons/` (`cad/scripts/cut_release.py:stage_comparisons`). The only tracked
inputs are `manifest.json`, `ATTRIBUTION.md`, this README and `tools/`; everything
else regenerates (the reference *source* photos live in the pinned `references`
submodule).

| path | tracked? | content |
|---|---|---|
| `manifest.json` | tracked | source of truth: pair id → reference, model, camera pose, legacy content-fit 2D align, tier, status |
| `ATTRIBUTION.md` | tracked | CC BY credits/licensing for the reference photos (ships in every release bundle) |
| `ref/<id>.jpg` | regen | prepared reference (cropped/rotated, ≤1600 px) — re-derived from the `references` submodule by `prepare_reference` |
| `index.html` | regen | inspection gallery (tier + text filters; drag the ref⇆cad reveal slider) — `uv run cad/comparisons/tools/gallery.py` |
| `render/<id>.jpg` | regen | raw CAD render (+ `.meta.json` staleness/engine/registration sidecar); Blender preserves concrete Pose Studio camera frames, while legacy target-less poses and SolidWorks captures are content-fit |
| `composite/<id>_cad.jpg` | regen | render registered from sidecar metadata into the reference frame (same scale/offset as the blend layer) — the slider's top image |
| `composite/<id>_blend.jpg` | regen | red-tinted render over grayscale ref — misalignment is instantly visible |
| `scores.json` | regen | pair → RMS shape score (regression trend only; compare across commits, same engine) |
| `findings/iter_NNN.json` | — | per-iteration vision findings |

## Identity boundaries

Current export and gallery inputs use canonical subsystem-prefixed stems;
repeated supplier-qualified SKUs use the eight `sh-vn-*` shared identities.
Historical released bundles remain unchanged. `release_diff.py`,
`render_diff.py`, drawing overlays and pose source resolution compose the
additive schema-1 [`current-identity-map.json`](../config/current-identity-map.json)
with the sealed schema-2
[`identity-migration-map.json`](../config/identity-migration-map.json).
The current map retains each prior stem/Number, semantic role and exact member
configuration. Repeated shared target stems/Numbers are legitimate convergence,
not duplicate physical files. Within one inventory, only declared distinct
same-generation prior sources may converge. Mixed archive generations, stale
prior/current aliases, overlapping aliases for the same prior source and
case-insensitive duplicate members remain errors. The declared current
bare-STEP/qualified-STL first-member pair is a per-format association, not
multiple geometry candidates.

The chain, wire and clamping-kit members stay distinct: `InnerLink`/`OuterLink`,
`LeverWire`/`PenWire`, and `HoldDownStud`/`TNut`/`FlangeNut`. Exporter mesh keys
lowercase full configuration names, e.g. historical `pd-vn-chain-outer-link`
pairs with `sh-vn-chain-link--outerlink`, not with the bare shared file. A bare
neutral artifact represents **only** its declared active member: `InnerLink`,
`LeverWire` or `HoldDownStud`, respectively. There is no heterogeneous `Default`
alias. Ordinary shared screws retain `Default` and bare geometry names, without
invented role configurations. Every distinct member must ship its STEP and PNG:
the first member uses the bare STEP/PNG export, while all member STLs and
nonfirst STEP/PNG exports use the same existing lowercase mesh-key sanitizer
(for example `--outerlink`). Comparison format association imports the pure
`member_export_paths` producer helper, with the map's declared neutral member;
it never guesses one common basename for STEP and STL. Geometry lookup is
case-insensitive but never first-match ambiguous.

For unrelated configurations the entire suffix from the first `--` remains
intact. Thus `transgear-removable--t12` pairs with
`pd-transgear-removable--t12`, `crank-handle-ferrule--installed` with
`dt-crank-handle-ferrule--installed`, and `cone-gear--t006` with
`dt-cone-gear--t006`. Generated `-stretchN` qualifiers are also retained, for
example `channel-spring-installed-stretch07` becomes
`ch-vn-channel-spring-installed-stretch07`; an exporter `--configuration` takes
precedence over that generated suffix rule. Geometry verdicts and highlights
remain per exact qualified mesh. The changed-part summary groups only trailing
`--t<digits>` and `-stretch<digits>` variants by base stem.

Many-to-one comparisons retain **all** historical candidates, including old
parent-specific clones and archive spellings. Release geometry output compares
each actual source; render summaries preserve every source deviation in
`candidate_mesh_deviations_mm`, and any changed candidate highlights the target.
`renamed_meshes` and drawing-overlay `renamed_drawings` contain lists of actual
prior names; drawing summaries use schema 2 for this many-candidate contract.
Drawing overlays compare every prior PDF with the shared reference
drawing, which depicts all its member configurations, and source-qualify image
paths when multiple historical PDFs converge. One equal candidate cannot hide a
different clone.

The release CLI inventories STEP **and** STL once per logical member and compares
CRCs by format, never STEP against STL. A first member's declared bare STEP and
qualified STL form one source, so identical current bundles do not become
changed/renamed and OCP/mesh comparisons run once per source pair. A configured
STL whose declared STEP is missing still receives mesh comparison, while its
exact STEP boolean is explicitly skipped; a bare STEP is never used for another member. This
honest diagnostic is not permission to omit required member STEP/PNG exports.
For the human-typed `--parts` selector, a bare shared SKU expands **all** declared
members; use `<stem>--membername` to select one. Missing requested members are reported,
not silently replaced by the neutral member. This selector expansion does not
change the meaning of any actual bare neutral artifact.
Single-file pose/GLB/boxes/PDF resolution accepts a literal actual artifact key
as explicit source identity context, after validating its variant and inventory.
A canonical shared alias against multiple prior candidates remains ambiguous;
no clone is selected by sort order. With an explicit release tag it reuses a cached
complete bundle without GitHub access and checks that bundle's full inventory
even if one candidate was previously extracted.

These maps are archive-input boundaries, not current-file or command aliases.
Geometry selectors are artifact mesh keys, not occurrence paths. Projected
`archive-role-local` ordinals (including `--Member-N` and `__FootScrew-N`) are
not native `Component2.Name2` ordinals and are rejected here, never silently
joined to raw native paths. Native linkage requires independently checked
file/configuration plus a semantic `ComponentReference` such as `Role:1`.
Pose Studio and meshprobe framing also reject projected archive occurrence
selectors. An explicit camera `occurrenceNamespace: "native-name2"` may select
only an exact raw name already present in its supplied native boxes evidence;
no stem/leaf rewrite or projected ordinal bridge is performed.

Historical curation catalogs likewise remain immutable provenance.
`seed_manifest.py` normalizes catalog components only when their
`old_underscore` identity is assigned by that same sealed map, before selecting
a studio part or the top assembly and emitting `focus`/`frame_components`.
Unknown semantic or retired unmapped labels, such as `crank_pedestal`, remain
unchanged; they require owner curation, not a guessed alias.
The normal merge retains existing tuned pairs; `--reset`
regenerates pairs using current identities. Explicit `PHOTO_FOCUS` mappings are
unchanged.

## Workflow

```powershell
# 1. curate / re-seed pairs (merge keeps hand-tuned poses)
uv run cad/comparisons/tools/dedup_stills.py
# ... vision agents write references/curation/batches/*.json ...
uv run cad/comparisons/tools/merge_catalog.py
uv run cad/comparisons/tools/extract_frames.py          # full-res video keepers
uv run cad/comparisons/tools/seed_manifest.py

# 2. render offline (no SolidWorks): refresh the STL cache once after
#     any rebuild, then Blender replays the same manifest cameras
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\export_models.py
uv run cad/comparisons/tools/render_offline.py [--only id,..] [--stale-only]
#    parts render from their own STL; assemblies instance per-part STLs
#    (metres, untranslated) through the scene graph in cad/out/boxes/*.json,
#    with each component's SolidWorks appearance RGB as Workbench object
#    colour. Ortho only; sidecars carry "engine" — score trends are only
#    comparable within one engine. parity_check.py measures silhouette IoU
#    between the backed-up and current renders (instanced-vs-monolith
#    baseline: 0.99+).

# 3. recompute composites/scores without rendering (e.g. after align edits)
uv run cad/comparisons/tools/composite.py [--only id1,id2]

# 4. selective model rebuild after fixing a part script (dependent assemblies refresh)
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe -m doit part:dt_cone_gear
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
uv run cad/comparisons/tools/pose_studio.py --pair ch30-p003
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
uv run python cad/scripts/export_glb.py <dir-with-the-assembly>/ha-harmonic-analyzer.SLDASM
# or add --fetch-glb below to pull gltf/<model>.glb from the latest release bundle
```

```powershell
# print the commands for one pair (id substring)
uv run cad/comparisons/tools/pose_to_meshprobe.py --pair ch30-p002

# actually render it: pipe the emitted commands to a shell (bash — see quoting note)
uv run cad/comparisons/tools/pose_to_meshprobe.py --pair ch30-p002 | bash
uv run meshprobe close --all            # stop the Blender daemon when done

# many poses, ONE open: --batch shares a single meshprobe session so the (large)
# GLB is imported once instead of re-opened per pair
uv run cad/comparisons/tools/pose_to_meshprobe.py --batch | bash

# just the computed params, no shell
uv run cad/comparisons/tools/pose_to_meshprobe.py --pair ch30-p002 --format json
```

The emitted commands invoke `uv run meshprobe` (so the pipe-to-`bash` flow works
without a global install; override with `--meshprobe`). Renders land in
`cad/comparisons/render/meshprobe/<id>.png`. Useful flags: `--batch` / `--session
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
