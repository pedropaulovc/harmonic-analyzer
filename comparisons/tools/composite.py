# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Composite + scoring helpers for the photo-vs-CAD comparison pairs.

Importable from the SolidWorks build venv (render_compare.py) and runnable
standalone with uv to regenerate composites/scores without SolidWorks:

    uv run comparisons/tools/composite.py [--only id1,id2]

Per pair (see ../manifest.json):
    ref/<id>.png                prepared reference (cropped/rotated copy)
    render/<id>.png             aligned CAD render
    composite/<id>_sbs.png      side-by-side
    composite/<id>_blend.png    overlay: grayscale ref under red-tinted render
                                (render's white background knocked out)
    scores.json                 pair id -> RMS shape-mismatch score
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

COMP = Path(__file__).resolve().parents[1]
REPO = COMP.parent
MANIFEST = COMP / "manifest.json"
SCORES = COMP / "scores.json"

WHITE_THRESH = 235  # render background knock-out
PANEL_H = 1000


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


JPEG_OPTS = {"quality": 90, "optimize": True}


def pair_paths(pair_id: str) -> dict[str, Path]:
    # JPEG throughout: the full pair set is ~1.4 GB as PNG and is rewritten
    # every loop iteration; q90 JPEG is ~10x smaller with no inspection loss.
    return {
        "ref": COMP / "ref" / f"{pair_id}.jpg",
        "render": COMP / "render" / f"{pair_id}.jpg",
        "sbs": COMP / "composite" / f"{pair_id}_sbs.jpg",
        "blend": COMP / "composite" / f"{pair_id}_blend.jpg",
    }


def prepare_reference(pair: dict, max_px: int = 1600) -> Path:
    """Copy the pair's source reference into ref/<id>.png (crop/rotate/cap)."""
    src = REPO / pair["reference"]["path"]
    out = pair_paths(pair["id"])["ref"]
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src)
    img = ImageOps.exif_transpose(img)
    rot = pair["reference"].get("rotate_deg", 0)
    if rot:
        img = img.rotate(-rot, expand=True, fillcolor="white")
    crop = pair["reference"].get("crop")
    if crop:
        img = img.crop(tuple(crop))
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px), Image.LANCZOS)
    img.convert("RGB").save(out, **JPEG_OPTS)
    return out


def _fit_height(img: Image.Image, h: int) -> Image.Image:
    w = max(1, round(img.width * h / img.height))
    return img.resize((w, h), Image.LANCZOS)


def _trim_uniform_border(img: Image.Image, tol: int = 12) -> Image.Image:
    """Crop the render's uniform background margin (zoom-to-fit underfills)."""
    from PIL import ImageChops

    rgb = img.convert("RGB")
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    bbox = ImageChops.difference(rgb, bg).convert("L").point(
        lambda v: 255 if v > tol else 0
    ).getbbox()
    return img.crop(bbox) if bbox else img


def _fitted_render(pair_id: str, ref_size: tuple[int, int], align: dict | None):
    """Trimmed render scaled to fit the ref frame + its paste offset.

    The capture fills only part of the viewport (zoom-to-fit margins), while
    references mostly fill their frame — so content-fit first, then apply the
    manifest's 2D fine-alignment (scale about centre + pixel offset).
    """
    align = align or {}
    ren = _trim_uniform_border(Image.open(pair_paths(pair_id)["render"]))
    rw, rh = ref_size
    s = min(rw / ren.width, rh / ren.height) * align.get("scale", 1.0)
    w, h = max(1, round(ren.width * s)), max(1, round(ren.height * s))
    ren = ren.resize((w, h), Image.LANCZOS)
    dx = align.get("dx_px", 0) + (rw - w) // 2
    dy = align.get("dy_px", 0) + (rh - h) // 2
    return ren, (dx, dy)


def side_by_side(pair_id: str) -> Path:
    p = pair_paths(pair_id)
    ref = _fit_height(Image.open(p["ref"]).convert("RGB"), PANEL_H)
    ren = _fit_height(_trim_uniform_border(Image.open(p["render"])).convert("RGB"), PANEL_H)
    gap, bar = 8, 28
    canvas = Image.new("RGB", (ref.width + gap + ren.width, PANEL_H + bar), "white")
    canvas.paste(ref, (0, bar))
    canvas.paste(ren, (ref.width + gap, bar))
    draw = ImageDraw.Draw(canvas)
    draw.text((4, 6), f"REF  {pair_id}", fill="black")
    draw.text((ref.width + gap + 4, 6), "CAD", fill="black")
    p["sbs"].parent.mkdir(parents=True, exist_ok=True)
    canvas.save(p["sbs"], **JPEG_OPTS)
    return p["sbs"]


def _render_rgba(render: Image.Image) -> Image.Image:
    """Red-tint the render and knock out its near-white background."""
    g = render.convert("L")
    rgba = Image.merge(
        "RGBA",
        (
            g.point(lambda v: 255),                       # R
            g,                                            # G
            g,                                            # B
            g.point(lambda v: 0 if v >= WHITE_THRESH else 230),  # A
        ),
    )
    return rgba


def blend_overlay(pair_id: str, align: dict | None) -> Path:
    p = pair_paths(pair_id)
    ref = Image.open(p["ref"]).convert("L").convert("RGB")
    ren, offset = _fitted_render(pair_id, ref.size, align)
    layer = Image.new("RGBA", ref.size, (0, 0, 0, 0))
    layer.paste(_render_rgba(ren), offset)
    out = Image.alpha_composite(ref.convert("RGBA"), layer).convert("RGB")
    p["blend"].parent.mkdir(parents=True, exist_ok=True)
    out.save(p["blend"], **JPEG_OPTS)
    return p["blend"]


def score_pair(pair_id: str, align: dict | None) -> float:
    """RMS grayscale mismatch where the render has content. Relative metric:
    only meaningful as a trend per pair across iterations."""
    p = pair_paths(pair_id)
    ref = Image.open(p["ref"]).convert("L")
    ren, offset = _fitted_render(pair_id, ref.size, align)
    ren = ren.convert("L")
    canvas = Image.new("L", ref.size, 255)
    canvas.paste(ren, offset)
    total = n = 0
    for rv, cv in zip(ref.getdata(), canvas.getdata(), strict=True):
        if cv < WHITE_THRESH:  # render content only
            d = rv - cv
            total += d * d
            n += 1
    return round((total / n) ** 0.5, 2) if n else 999.0


def regenerate(only: set[str] | None = None) -> dict[str, float]:
    manifest = load_manifest()
    scores = json.loads(SCORES.read_text(encoding="utf-8")) if SCORES.exists() else {}
    for pair in manifest["pairs"]:
        pid = pair["id"]
        if only and pid not in only:
            continue
        p = pair_paths(pid)
        if not p["ref"].exists():
            prepare_reference(pair)
        if not p["render"].exists():
            print(f"  --  {pid}: no render yet, skipping composites")
            continue
        align = pair.get("align")
        side_by_side(pid)
        blend_overlay(pid, align)
        scores[pid] = score_pair(pid, align)
        print(f"  OK  {pid}: score {scores[pid]}")
    SCORES.write_text(json.dumps(dict(sorted(scores.items())), indent=1), encoding="utf-8")
    return scores


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated pair ids")
    args = ap.parse_args()
    regenerate(set(args.only.split(",")) if args.only else None)
