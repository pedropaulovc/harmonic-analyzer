"""Trim background margins from build renders into README-friendly copies."""

from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[2]
PNG = ROOT / "cad" / "out" / "png"
OUT = ROOT / "docs" / "images"
PAD = 24
THRESHOLD = 30

RENDERS = {
    "hero.png": PNG / "harmonic-analyzer" / "harmonic-analyzer_isometric.png",
    "frame.png": PNG / "frame" / "frame_isometric.png",
    "drive-train.png": PNG / "drive-train" / "drive-train_isometric.png",
    "channel.png": PNG / "channel" / "channel_isometric.png",
    "output.png": PNG / "output" / "output_isometric.png",
}


def trim(src: Path, dst: Path) -> str:
    img = Image.open(src).convert("RGB")
    background = Image.new("RGB", img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, background).convert("L")
    bbox = diff.point(lambda p: 255 if p > THRESHOLD else 0).getbbox()
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
    cropped.save(dst)
    return f"{dst.name}: {img.size} -> {cropped.size}"


OUT.mkdir(parents=True, exist_ok=True)
for name, src in RENDERS.items():
    print(trim(src, OUT / name))
