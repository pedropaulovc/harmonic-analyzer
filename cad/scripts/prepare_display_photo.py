"""Crop and tone-correct the display-case photograph used in the README.

The source is a first-party phone photo of the surviving analyzer in its glass
case. Two things have to happen before it can sit next to a CAD render:

* crop to the machine, dropping the wooden stand it sits on and the person who
  was standing beside it for scale;
* undo the display glass, which is green and costs about a stop.

Run it explicitly, like ``trim_renders.py`` -- it reads a file that is not in
the repository (the untouched original stays on the photographer's disk, since
it still has a person in it), so it is not part of any build::

    uv run python cad/scripts/prepare_display_photo.py --source <original.jpg>

Every number below is a decision about one specific photograph. If the source
changes, they all have to be re-derived by eye.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _telemetry  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "cad" / "docs" / "images" / "real-machine-display-case.jpg"

DEFAULT_SOURCE = Path.home() / "OneDrive/Imagens/Imagens da Câmera/2025/08/20250828_202633247_iOS.jpg"

# Tight to the machine in the 4032x3024 original: the pen-wire rod at the top,
# the whole green base at the bottom, and no wooden stand. The bottom edge is
# the tight one. The base sits directly on the stand, its underside runs from
# y=2405 on the left to y=2395 on the right, and the stand's top surface is
# visible to either side of it, so the left and right edges are set by the base
# rather than by the frame rails.
CROP = (1802, 560, 2392, 2405)

# The blank upper half of the sheet clipped to the platen, in CROP-relative
# coordinates, above the plotted trace and left of the pen. It is the one thing
# in frame that is known to be neutral, so it sets the white balance. (The back
# wall is painted cinder block and looks like a bigger, safer target, but it is
# lit by a different fixture than the machine and is partly in shadow.)
WHITE_PATCH = (73, 1350, 333, 1410)

GAMMA = 0.82  # < 1 lifts the midtones
CONTRAST_CUTOFF = 0.4  # percent of pixels sacrificed at each end of the ramp
SATURATION = 1.12


def white_balance(rgb: np.ndarray, patch: tuple[int, int, int, int]) -> np.ndarray:
    """Scale each channel so ``patch`` averages neutral, preserving its luma."""
    x0, y0, x1, y1 = patch
    sample = rgb[y0:y1, x0:x1].reshape(-1, 3)
    if sample.size == 0:
        raise ValueError(f"white patch {patch} is outside the cropped image")
    mean = sample.mean(axis=0)
    gains = mean.mean() / np.maximum(mean, 1e-6)
    _telemetry.info(f"white patch mean={mean.round(1).tolist()} gains={gains.round(3).tolist()}")
    return rgb * gains


def stretch(rgb: np.ndarray, cutoff: float) -> np.ndarray:
    """Map the cutoff-th and (100-cutoff)-th luma percentiles onto 0..1.

    Percentiles of LUMA, applied to all three channels together, so the ramp
    cannot introduce the colour shift that per-channel autocontrast does on an
    image this dominated by one hue.
    """
    luma = rgb @ np.array([0.2126, 0.7152, 0.0722])
    lo, hi = np.percentile(luma, [cutoff, 100.0 - cutoff])
    _telemetry.info(f"luma stretch {lo:.3f}..{hi:.3f} -> 0..1")
    return (rgb - lo) / max(hi - lo, 1e-6)


def saturate(rgb: np.ndarray, amount: float) -> np.ndarray:
    grey = (rgb @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
    return grey + (rgb - grey) * amount


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--dest", type=Path, default=DEST)
    args = ap.parse_args()

    if not args.source.exists():
        _telemetry.error(f"source photograph not found: {args.source}")
        return 1

    with _telemetry.span("photo.prepare", source=str(args.source)):
        original = Image.open(args.source).convert("RGB")
        cropped = original.crop(CROP)
        _telemetry.info(f"{original.size} -> crop {CROP} -> {cropped.size}")

        rgb = np.asarray(cropped, dtype=np.float64) / 255.0
        rgb = white_balance(rgb, WHITE_PATCH)
        rgb = stretch(rgb, CONTRAST_CUTOFF)
        rgb = np.clip(rgb, 0.0, 1.0) ** GAMMA
        rgb = np.clip(saturate(rgb, SATURATION), 0.0, 1.0)

        args.dest.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray((rgb * 255.0 + 0.5).astype(np.uint8)).save(
            args.dest, "JPEG", quality=92, optimize=True
        )
        _telemetry.success(f"{args.dest.relative_to(ROOT)} ({args.dest.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
