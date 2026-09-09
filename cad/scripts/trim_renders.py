"""Refresh tracked README images from the latest generated render output.

Run this explicitly after a model or drawing change to refresh
``cad/docs/images`` from the latest ``cad/out/png`` build output, then commit
the result::

    uv run python cad/scripts/trim_renders.py

Decoupled from the build on purpose: normal build and release tasks never write
tracked files, which would dirty the tree and fail ``doit release``'s clean-tree
preflight. Assembly renders are cropped deterministically; drawing sheets are
copied byte-for-byte.
"""

from __future__ import annotations

import sys
from shutil import copyfile
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _telemetry  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT_PNG = ROOT / "cad" / "out" / "png"
DOCS_IMAGES = ROOT / "cad" / "docs" / "images"
PAD = 24
THRESHOLD = 30

README_RENDERS = {
    "harmonic-analyzer": "hero.png",
    "frame": "frame.png",
    "drive-train": "drive-train.png",
    "channel": "channel.png",
    "summing": "summing.png",
    "magnifier": "magnifier.png",
    "pen": "pen.png",
    "paper-drive": "paper-drive.png",
}

README_DRAWINGS = {
    "rocker-arm-support": "rocker-arm-support-drawing.png",
    "platen-guide": "platen-guide-drawing.png",
}


def trim(src: Path, dst: Path) -> str:
    """Crop ``src`` to its content (vs the corner background colour) + PAD."""
    img = Image.open(src).convert("RGB")
    background = Image.new("RGB", img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, background).convert("L")
    bbox = diff.point(lambda p: 255 if p > THRESHOLD else 0).getbbox()  # type: ignore[operator]  # PIL stubs type ImagePointTransform too broadly
    if bbox is None:
        raise ValueError(f"{src}: no content found above threshold")
    left, top, right, bottom = bbox
    bbox = (
        max(0, left - PAD),
        max(0, top - PAD),
        min(img.width, right + PAD),
        min(img.height, bottom + PAD),
    )
    cropped = img.crop(bbox)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(dst)
    return f"{dst.relative_to(ROOT)}: {img.size} -> {cropped.size}"


def trim_readme_render(asm_name: str) -> str | None:
    """Trim ``<asm>_isometric.png`` into cad/docs/images if the README uses it."""
    docs_name = README_RENDERS.get(asm_name)
    if docs_name is None:
        return None
    src = OUT_PNG / asm_name / f"{asm_name}_isometric.png"
    if not src.exists():
        return None
    return trim(src, DOCS_IMAGES / docs_name)


def copy_readme_drawing(drawing_name: str, docs_name: str) -> str:
    """Copy a required generated drawing sheet into the tracked README images."""
    src = OUT_PNG / f"{drawing_name}_drawing.png"
    if not src.exists():
        raise FileNotFoundError(f"required README drawing render is missing: {src}")
    dst = DOCS_IMAGES / docs_name
    copyfile(src, dst)
    return f"{dst.relative_to(ROOT)}: copied {src.relative_to(ROOT)}"


if __name__ == "__main__":
    for asm in README_RENDERS:
        _telemetry.info(trim_readme_render(asm) or f"skip {asm} (no isometric render)")
    for drawing, docs_name in README_DRAWINGS.items():
        _telemetry.info(copy_readme_drawing(drawing, docs_name))
