# Tracked images

Everything in this folder is committed, so every file here needs a story: where
it came from and how to make it again when the model moves. `cad/out/` is
gitignored and regenerated; this folder is not.

## README-generated CAD images

The seven root README assembly thumbnails and CAD pose render are generated
from one pinned release package, not mixed from whichever files happen to be
in `cad/out/`. The refresh also keeps `hero.png` current; that image is not
linked from the root README. For a deliberate manual refresh:

```powershell
uv run python cad/scripts/trim_renders.py --release-root cad/out/release/harmonic-analyzer-vNN
```

`--release-root` names the versioned package directory and supplies its `png/`,
`pdf/` and `gltf/` inputs. The generator refreshes the README-linked assembly
thumbnails, drawing illustrations below and `cad-model-display-pose.png`. The
pose keeps the meshprobe camera, illumination and render settings documented
below. The real-machine photograph is fixed and is never regenerated here.

The manual command writes tracked files, so run it deliberately, not before the
release clean-tree preflight. The publisher calls the same image generator
in-process against the staged versioned package, writing into untracked
staging. Missing inputs or rendering tools fail before the tag; only after
successful publication does it install the prepared images alongside
`cad/config/release.yaml`'s `next_revision` bump. It never falls back to stale
tracked images.

## Drawing illustrations

The part-sheet examples (`rocker-arm-support-drawing.png` and
`pinion-arbor-drawing.png`) are copied from the matching full-sheet PNGs in the
package's `png/` directory. The assembly examples are rendered from selected
pages of its multi-sheet PDFs: zero-based PDF page 3 is drive-train assembly
sheet 4, **Cone Set + Crank Exploded (MHA-A03)**; page 2 is frame assembly
sheet 3, **Match-Fit and Assembly Sequence (MHA-A04)** (recipe `FITTING + ASSEMBLY`).
These are selected PDF pages, not the all-pages drawing contact previews. Keep
the mappings in `trim_renders.py` so the README cannot silently retain a sheet
from an older release.

## The matched pair: `real-machine-display-case.jpg` + `cad-model-display-pose.png`

The photograph is fixed; release image refresh never modifies it. The render
has to be regenerated whenever the geometry changes, or the pair stops being a
fair comparison.

### The photograph

First-party, taken 2025-08-28 at the University of Illinois, where the machine
lives in a glass case in a corridor outside room 241, stood on its end so it
fits. No third-party rights attach to it, which is the point of using it rather
than a plate from the 2014 book.

```powershell
uv run python cad/scripts/prepare_display_photo.py --source <original.jpg>
```

The source is `references/photogrammetry/raw/20250828_202633247_iOS.jpg`, and
the script does two things to it: crops to the machine, dropping the wooden
stand and the person who was standing beside the case for scale, and undoes the
display glass, which is green and costs about a stop. Both are recorded as
constants at the top of the script, and both are decisions about one specific
photograph rather than anything reusable.

The tone work is white balance off the blank half of the sheet on the platen,
then a luma-percentile stretch, gamma 0.82, and a little saturation. It is a
tonal correction and nothing else: no cloning, no retouching, no geometry.

Note what the photo does *not* show. It is shot through display glass at an
angle, the case is lit by a corridor fixture, and the machine is at rest with a
sample trace already on the platen. It is evidence of the real object, not a
measurement source. Dimensions still come from
[`../assumptions.md`](../assumptions.md) and the photogrammetry set.

### The render

Produced with [meshprobe](https://github.com/pedropaulovc/meshprobe) against the
exported glTF, so it needs no SolidWorks seat, only the export and a GPU. It
does need Blender >= 5.2.

Use the same pinned release package as the rest of the README image refresh:
`cad/out/release/harmonic-analyzer-vNN/gltf/harmonic-analyzer.glb`. These
meshprobe steps document the pose and settings retained by `trim_renders.py`:

```powershell
$releaseRoot = 'cad/out/release/harmonic-analyzer-vNN'
uv run meshprobe -s ha open "$releaseRoot/gltf/harmonic-analyzer.glb"
```

The glTF hierarchy is flattened and component names can repeat across
subassemblies, so frame the whole model rather than relying on a single root or
name. `view-frame --all` selects every component, equivalent to collecting the
stable IDs from a snapshot. The camera and render values are the pose match
against the photograph; don't change them casually:

```powershell
uv run meshprobe -s ha illumination-set high_key --background-srgb 1 1 1
uv run meshprobe -s ha view-frame --all --azimuth 95 --elevation 8 --margin 0.71 --aspect-ratio 0.3198
uv run meshprobe -s ha render-image --output cad/docs/images/cad-model-display-pose.png `
    --width 1180 --height 3690 --style screen_edges --samples 128
```

Azimuth 90 is a straight front view, so 95 is the machine turned five degrees
right, which is what the photograph shows. It was picked by rendering the sweep
from 15 to 165 degrees and comparing against the photo; anything in the first
hemisphere is mirrored, which is obvious once you notice the pen-wire rod is
upper-left in the case and upper-right at azimuth 45.

Four things in there are load-bearing, and each one cost a wasted render:

- **`--aspect-ratio` must equal `width / height`** (1180 / 3690 = 0.3198, which
  is the photograph's aspect). `view-frame` persists the framing it computed,
  and `render-image` warns and reframes if the resolution disagrees.
- **`--margin 0.71`**, calibrated against the v38 silhouette after meshprobe
  1.4 changed to tight per-component corner fitting. On the 424-component
  release model, 0.71 preserves 94.0% width against 94.3% original; the legacy
  0.60 clips, while 1.0 shrinks the silhouette to 66.8% width.
- **`--background-srgb`, not `--background-rgb`.** The latter is
  linear-referred and tone-mapped, so `1 1 1` comes out mid-grey.
- **`high_key`.** `neutral_studio` washes the teal out and `raking_left` renders
  this pose almost black. Note that the presets are fixed in world space, so
  moving the camera changes the exposure as well as the angle: the same preset
  that reads richly at azimuth 45 reads bright and flat at azimuth 100. Judge
  tone only after the azimuth is settled.

`--style screen_edges` is the default and is what this render uses, but only
because it is 12x cheaper (3.3 s against 42.4 s here). It is not the better
image: a controlled comparison at one camera and one sample count
([meshprobe#179](https://github.com/pedropaulovc/meshprobe/issues/179)) had
`shaded_edges` brighter, wider in tonal range, and clearly better at separating
the chain, the gear teeth and the crank rig. Use it if this figure ever needs to
show the base mechanism rather than the machine's overall shape.

Finally, confirm the pose still matches rather than assuming it does:

```powershell
uv run python cad/scripts/compare_display_pose.py
```

That writes `cad/out/reports/display-pose-alignment.jpg`. It fixes the scale
from two points only, the top of the pen-wire rod and the underside of the base,
then rules lines across both panels at four landmarks the fit never saw, and
prints how far each one moved.

### What the alignment currently shows

| landmark | apparent offset |
|---|---|
| base, top surface | +20 mm |
| platen, top edge | +41 mm |
| top beam, upper edge | +52 mm |
| magnifying wheel, centre | +87 mm |

Read those carefully, because it is easy to read them as accuracy figures and
they are not. The photograph is uncalibrated: a phone lens close to the case, at
an unknown height, shooting through glass. Vertical position in a perspective
image is not linear in height, so a two-point fit cannot remove the difference
between that camera and a 50 mm render, and the residue lands in exactly this
pattern, growing with distance from the fit points. Positive offsets throughout
are what an uncorrected camera difference looks like, not evidence of anything.

What *is* worth following up is the magnifying wheel, because it breaks the
pattern. It sits lower than the trend of its neighbours by roughly 40 mm, even
though the top beam above it and the platen below it both agree more closely.
The most likely explanation is not a modelling error at all: the magnifying
bracket slides on its vertical rod, and where it sits is how the x4 lever
magnification gets set. The real machine is wherever somebody last left it, and
the model is at its as-built rest pose. Confirming that means checking the
photogrammetry set, not re-cutting a part.

So the figure is a qualitative check on pose and layout, and a way to notice
something like the wheel. For real fidelity numbers, use the comparison gallery
in [`../../comparisons/`](../../comparisons), which aligns against known camera
poses and scores RMS per pair.
