"""Overlay the display-case photograph and the pose-matched CAD render.

The point of the pair is the claim that the reconstruction is faithful, and a
side-by-side does not actually demonstrate that: two images at slightly
different scales invite the eye to forgive a lot. This figure fixes the scale
from the two extremes only -- the top of the pen-wire rod and the underside of
the base -- and then rules horizontal lines across both panels at landmarks
nobody used for the fit. If the model is right, those lines land on the same
features on both sides. Where they miss, the miss is the finding.

    uv run python cad/scripts/compare_display_pose.py

Inputs are the two tracked images; the output is written to cad/out/ and is not
tracked. What it cannot prove is anything about depth: the photograph is a phone
lens close to the case and the render is a 50 mm perspective, so agreement in
the middle of the frame is weaker evidence than agreement at the ends.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _telemetry  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
IMAGES = ROOT / "cad" / "docs" / "images"
PHOTO = IMAGES / "real-machine-display-case.jpg"
RENDER = IMAGES / "cad-model-display-pose.png"
DEST = ROOT / "cad" / "out" / "reports" / "display-pose-alignment.jpg"

# Read off the 590x1845 photograph. The first two set the fit; the rest are the
# test, and are deliberately features the fit never saw.
FIT_TOP = 42  # topmost point of the pen-wire rod
FIT_BOTTOM = 1800  # underside of the green base
PHOTO_MACHINE_X = (22, 572)

# The same four landmarks in the render, as a fraction of its machine box height
# so the numbers survive a resolution change. They do NOT survive a pose change:
# re-read them off cad/out/reports/render_grid.jpg whenever the render moves.
LANDMARKS = [
    (566, 0.2606, "top beam, upper edge"),
    (1207, 0.6001, "magnifying wheel, centre"),
    (1338, 0.7080, "platen, top edge"),
    (1740, 0.9513, "base, top surface"),
]

# World Z span of the model, from the meshprobe snapshot's root_bounds. The fit
# maps it onto FIT_TOP..FIT_BOTTOM, which turns an offset in pixels into one in
# millimetres -- with the caveat in the module docstring.
SPAN_MM = 1394.0

PANEL_HEIGHT = 1500
GUTTER = 28
RULE = (214, 66, 66)


def render_machine_box(img: Image.Image) -> tuple[int, int, int, int]:
    """Bounding box of the rendered machine against its white background."""
    arr = np.asarray(img.convert("L"), dtype=np.int16)
    ink = arr < 245
    cols, rows = np.flatnonzero(ink.any(axis=0)), np.flatnonzero(ink.any(axis=1))
    if cols.size == 0 or rows.size == 0:
        raise ValueError("render appears to be blank")
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def main() -> int:
    for path in (PHOTO, RENDER):
        if not path.exists():
            _telemetry.error(f"missing input: {path}")
            return 1

    with _telemetry.span("compare.display_pose"):
        photo = Image.open(PHOTO).convert("RGB")
        render = Image.open(RENDER).convert("RGB")

        rx0, ry0, rx1, ry1 = render_machine_box(render)
        _telemetry.info(f"render machine box {(rx0, ry0, rx1, ry1)} in {render.size}")

        # Map the render's machine onto the photo's machine using the two fit
        # points, then crop the render to the photo's frame in that mapping, so
        # both panels share one coordinate system.
        scale = (FIT_BOTTOM - FIT_TOP) / (ry1 - ry0)
        photo_cx = sum(PHOTO_MACHINE_X) / 2
        render_cx = (rx0 + rx1) / 2
        _telemetry.info(f"scale render by {scale:.4f} to match the {FIT_BOTTOM - FIT_TOP}px fit span")

        placed = render.resize(
            (max(1, round(render.width * scale)), max(1, round(render.height * scale))),
            Image.LANCZOS,
        )
        left = round(render_cx * scale - photo_cx)
        top = round(ry0 * scale - FIT_TOP)
        aligned = Image.new("RGB", photo.size, "white")
        aligned.paste(placed, (-left, -top))

        k = PANEL_HEIGHT / photo.height
        panels = [im.resize((round(im.width * k), PANEL_HEIGHT), Image.LANCZOS) for im in (photo, aligned)]
        w = sum(p.width for p in panels) + GUTTER * 3
        sheet = Image.new("RGB", (w, PANEL_HEIGHT + GUTTER * 2), "white")
        xs = [GUTTER, GUTTER * 2 + panels[0].width]
        for x, p in zip(xs, panels):
            sheet.paste(p, (x, GUTTER))

        draw = ImageDraw.Draw(sheet)
        span = FIT_BOTTOM - FIT_TOP
        for y, frac, label in LANDMARKS:
            sy = GUTTER + round(y * k)
            offset_mm = ((y - FIT_TOP) / span - frac) * SPAN_MM
            _telemetry.info(f"{label}: photo {(y - FIT_TOP) / span:.4f} vs render {frac:.4f} = {offset_mm:+.0f} mm")
            for x, p in zip(xs, panels):
                for dash in range(x, x + p.width, 14):
                    draw.line([(dash, sy), (min(dash + 8, x + p.width), sy)], fill=RULE, width=2)
            draw.text((xs[0] + 6, sy + 4), f"{label}  ({offset_mm:+.0f} mm apparent)", fill=RULE)
        for y in (FIT_TOP, FIT_BOTTOM):
            sy = GUTTER + round(y * k)
            for x, p in zip(xs, panels):
                draw.line([(x, sy), (x + p.width, sy)], fill=(40, 40, 40), width=2)

        DEST.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(DEST, "JPEG", quality=92, optimize=True)
        _telemetry.success(f"{DEST.relative_to(ROOT)} {sheet.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
