# Tracked images

Everything in this folder is committed, so every file here needs a story: where
it came from and how to make it again when the model moves. `cad/out/` is
gitignored and regenerated; this folder is not.

## Assembly renders (`hero.png`, `frame.png`, `channel.png`, ...)

Built by the pipeline into `cad/out/png/`, then cropped into this folder by an
explicit script:

```powershell
uv run python cad/scripts/trim_renders.py
```

Deliberately not wired into the build, because writing a tracked file during a
build would dirty the tree and fail `doit release`'s clean-tree preflight. The
crop is deterministic, so re-running it on unchanged renders changes nothing.

## The matched pair: `real-machine-display-case.jpg` + `cad-model-display-pose.png`

The README shows the surviving machine next to the CAD model in the same pose.
The photograph is fixed; the render has to be regenerated whenever the geometry
changes, or the pair stops being a fair comparison.

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

Start from a current `harmonic-analyzer.glb`, either from
`uv run python -m doit export` or out of a release bundle:

```powershell
uv run meshprobe -s ha open cad/out/gltf/harmonic-analyzer.glb
```

The glTF hierarchy arrives flattened, with no single root node to aim at, and a
few component names repeat across subassemblies (`clamp-screw-1` exists in both
`magnifier` and `paper-drive`), so framing the whole machine means passing every
component's stable id rather than a name:

```powershell
uv run meshprobe -s ha snapshot --raw | Out-File -Encoding utf8 $env:TEMP\ha_snap.json
uv run python -c "import json,os; d=json.load(open(os.environ['TEMP']+'/ha_snap.json',encoding='utf-8-sig')); open(os.environ['TEMP']+'/ha_ids.txt','w').write('\n'.join(c['id'] for c in d['scene']['components']))"
$ids = Get-Content $env:TEMP\ha_ids.txt
```

Then the camera and the render. These numbers are the pose match against the
photograph and should not be changed casually: re-deriving them means another
azimuth sweep against the photo.

```powershell
uv run meshprobe -s ha illumination-set high_key --background-srgb 1 1 1
uv run meshprobe -s ha view-frame @ids --azimuth 95 --elevation 8 --margin 0.60 --aspect-ratio 0.3198
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
- **`--margin 0.60`**, not the 1.25 default. The default fits a bounding sphere,
  and this machine is 1394 mm tall in a 468 x 405 mm footprint, so the sphere is
  nearly three times the silhouette and the machine ends up filling half the
  frame.
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
