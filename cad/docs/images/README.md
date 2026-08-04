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
fits. Cropped from `20250828_202633247_iOS.jpg` (4032x3024) at box
`(1690, 210, 2740, 3024)`, which removes the person standing beside the case for
scale. No third-party rights attach to it: this is our own photograph, which is
the point of using it rather than a plate from the 2014 book.

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
uv run meshprobe -s ha view-frame @ids --azimuth 100 --elevation 8 --margin 0.60 --aspect-ratio 0.3731
uv run meshprobe -s ha render-image --output cad/docs/images/cad-model-display-pose.png `
    --width 1050 --height 2814 --style screen_edges --samples 128
```

Four things in there are load-bearing, and each one cost a wasted render:

- **`--aspect-ratio` must equal `width / height`** (1050 / 2814 = 0.3731).
  `view-frame` persists the framing it computed, and `render-image` warns and
  reframes if the resolution disagrees.
- **`--margin 0.60`**, not the 1.25 default. The default fits a bounding sphere,
  and this machine is 1394 mm tall in a 468 x 405 mm footprint, so the sphere is
  nearly three times the silhouette and the machine ends up filling half the
  frame.
- **`--background-srgb`, not `--background-rgb`.** The latter is
  linear-referred and tone-mapped, so `1 1 1` comes out mid-grey.
- **`high_key`.** `neutral_studio` washes the teal out and `raking_left` renders
  this pose almost black. `--style shaded_edges` is also worth skipping here:
  it is slower and, at this camera angle, flatter.

Finally, confirm the pose still matches rather than assuming it does. Scale both
images to the same height, put them side by side, and check the landmarks: the
platen and its paper low on the left, the magnifying wheel above it, the
pen-wire rod rising past the top beam on the right, the crank at the bottom
right.
