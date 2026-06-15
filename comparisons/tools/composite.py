# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Composite + scoring helpers for the photo-vs-CAD comparison pairs.

Importable from the SolidWorks build venv (render_compare.py) and runnable
standalone with uv to regenerate composites/scores without SolidWorks:

    uv run comparisons/tools/composite.py [--only id1,id2]

Per pair (see ../manifest.json):
    ref/<id>.jpg                prepared reference (cropped/rotated copy)
    render/<id>.jpg             raw CAD render (content-trimmed)
    composite/<id>_cad.jpg      render fitted into the reference frame (same
                                scale/offset as the blend layer, black
                                background) — the gallery's reveal-slider top
    composite/<id>_blend.jpg    overlay: grayscale ref under red-tinted render
                                (render background knocked out)
    scores.json                 pair id -> RMS shape-mismatch score
"""

import argparse
import json
import time
from pathlib import Path

from PIL import Image, ImageOps

COMP = Path(__file__).resolve().parents[1]
REPO = COMP.parent
MANIFEST = COMP / "manifest.json"
SCORES = COMP / "scores.json"

def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


JPEG_OPTS = {"quality": 90, "optimize": True}


def pair_paths(pair_id: str) -> dict[str, Path]:
    # JPEG throughout: the full pair set is ~1.4 GB as PNG and is rewritten
    # every loop iteration; q90 JPEG is ~10x smaller with no inspection loss.
    return {
        "ref": COMP / "ref" / f"{pair_id}.jpg",
        "render": COMP / "render" / f"{pair_id}.jpg",
        "cad": COMP / "composite" / f"{pair_id}_cad.jpg",
        "blend": COMP / "composite" / f"{pair_id}_blend.jpg",
    }


def prepare_reference(pair: dict, max_px: int = 1600) -> Path:
    """Copy the pair's source reference into ref/<id>.png (crop/rotate/cap)."""
    src = REPO / pair["reference"]["path"]
    out = pair_paths(pair["id"])["ref"]
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src)
    img = ImageOps.exif_transpose(img)
    if pair["reference"].get("mirror"):
        # only for individually-verified flipped reproductions: confirm with a
        # chiral cue (text direction, crank-vs-platen side) before setting.
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
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


def _content_mask(img: Image.Image, thresh: int = 30) -> Image.Image:
    """255 where render content, 0 where viewport background.

    SolidWorks captures sit on a vertical-gradient background, so a plain
    corner-colour test fails; flood-filling from the corners follows the
    gradient and stops at content edges.
    """
    from PIL import ImageChops, ImageDraw

    rgb = img.convert("RGB")
    sentinel = (255, 0, 255)
    w, h = rgb.size
    for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if rgb.getpixel(xy) != sentinel:
            ImageDraw.floodfill(rgb, xy, sentinel, thresh=thresh)
    bg = Image.new("RGB", rgb.size, sentinel)
    return ImageChops.difference(rgb, bg).convert("L").point(lambda v: 255 if v else 0)


def trim_render_file(path: Path, margin_frac: float = 0.01) -> None:
    """Crop a captured render to its content + a small margin, in place.

    ViewZoomToFit2 fits the SolidWorks window aspect, not the capture canvas,
    so raw captures carry large background margins. render_compare captures
    on an oversized canvas and calls this to store a content-tight image.
    """
    # Load + close the source handle BEFORE writing back to the same path:
    # Image.open is lazy and keeps `path` open for reading, so saving to the same
    # path reopens it for w+b while the read handle is live -- a Windows sharing
    # race. An external scanner (Defender/indexer) touching the freshly-written
    # JPEG makes it intermittent (random EINVAL/EACCES across a 400-file batch).
    with Image.open(path) as src:
        src.load()
        bbox = _content_mask(src).getbbox()
        if not bbox:
            return
        m = round(max(src.size) * margin_frac)
        cropped = src.crop((max(0, bbox[0] - m), max(0, bbox[1] - m),
                            min(src.width, bbox[2] + m), min(src.height, bbox[3] + m)))
    for attempt in range(8):
        try:
            cropped.save(path, **JPEG_OPTS)
            return
        except OSError:
            if attempt == 7:
                raise
            time.sleep(0.25)


def _fitted_render(pair_id: str, ref_size: tuple[int, int], align: dict | None):
    """Content-trimmed render scaled to fit the ref frame.

    Returns (render RGB, content mask, paste offset). The capture fills only
    part of the viewport (zoom-to-fit margins), while references mostly fill
    their frame — so content-fit first, then apply the manifest's 2D
    fine-alignment (scale about centre + pixel offset).
    """
    align = align or {}
    ren = Image.open(pair_paths(pair_id)["render"])
    mask = _content_mask(ren)
    bbox = mask.getbbox() or (0, 0, ren.width, ren.height)
    ren, mask = ren.crop(bbox), mask.crop(bbox)
    rw, rh = ref_size
    s = min(rw / ren.width, rh / ren.height) * align.get("scale", 1.0)
    w, h = max(1, round(ren.width * s)), max(1, round(ren.height * s))
    ren = ren.resize((w, h), Image.LANCZOS)
    mask = mask.resize((w, h), Image.NEAREST)
    dx = align.get("dx_px", 0) + (rw - w) // 2
    dy = align.get("dy_px", 0) + (rh - h) // 2
    return ren, mask, (dx, dy)


def aligned_render(pair_id: str, align: dict | None) -> Path:
    """The render placed in the reference frame — identical scale/offset to
    the blend's red layer — on black, so the gallery's reveal slider swaps
    between two pixel-registered images."""
    p = pair_paths(pair_id)
    with Image.open(p["ref"]) as ref:
        ref_size = ref.size
    ren, mask, offset = _fitted_render(pair_id, ref_size, align)
    canvas = Image.new("RGB", ref_size, "black")
    canvas.paste(ren.convert("RGB"), offset, mask)
    p["cad"].parent.mkdir(parents=True, exist_ok=True)
    canvas.save(p["cad"], **JPEG_OPTS)
    return p["cad"]


def _render_rgba(render: Image.Image, mask: Image.Image) -> Image.Image:
    """Red-tint the render; alpha comes from the content mask."""
    g = render.convert("L")
    return Image.merge(
        "RGBA",
        (g.point(lambda v: 255), g, g, mask.point(lambda v: 230 if v else 0)),
    )


def blend_overlay(pair_id: str, align: dict | None) -> Path:
    p = pair_paths(pair_id)
    ref = Image.open(p["ref"]).convert("L").convert("RGB")
    ren, mask, offset = _fitted_render(pair_id, ref.size, align)
    layer = Image.new("RGBA", ref.size, (0, 0, 0, 0))
    layer.paste(_render_rgba(ren, mask), offset)
    out = Image.alpha_composite(ref.convert("RGBA"), layer).convert("RGB")
    p["blend"].parent.mkdir(parents=True, exist_ok=True)
    out.save(p["blend"], **JPEG_OPTS)
    return p["blend"]


def score_pair(pair_id: str, align: dict | None) -> float:
    """RMS grayscale mismatch where the render has content. Relative metric:
    only meaningful as a trend per pair across iterations."""
    p = pair_paths(pair_id)
    ref = Image.open(p["ref"]).convert("L")
    ren, mask, offset = _fitted_render(pair_id, ref.size, align)
    canvas = Image.new("L", ref.size, 0)
    canvas.paste(ren.convert("L"), offset)
    mcanvas = Image.new("L", ref.size, 0)
    mcanvas.paste(mask, offset)
    total = n = 0
    for rv, cv, mv in zip(ref.getdata(), canvas.getdata(), mcanvas.getdata(), strict=True):
        if mv:  # render content only
            d = rv - cv
            total += d * d
            n += 1
    return round((total / n) ** 0.5, 2) if n else 999.0


def regenerate(only: set[str] | None = None) -> dict[str, float]:
    import time

    manifest = load_manifest()
    scores = json.loads(SCORES.read_text(encoding="utf-8")) if SCORES.exists() else {}
    todo = [p for p in manifest["pairs"] if not only or p["id"] in only]
    print(f"regenerating composites for {len(todo)} pairs", flush=True)
    t0 = time.monotonic()
    for i, pair in enumerate(todo, 1):
        pid = pair["id"]
        p = pair_paths(pid)
        if not p["ref"].exists():
            prepare_reference(pair)
        if not p["render"].exists():
            print(f"  --  [{i}/{len(todo)}] {pid}: no render yet, skipping", flush=True)
            continue
        align = pair.get("align")
        aligned_render(pid, align)
        blend_overlay(pid, align)
        scores[pid] = score_pair(pid, align)
        print(f"  OK  [{i}/{len(todo)}] {pid}: score {scores[pid]}"
              f"  ({time.monotonic() - t0:.0f}s)", flush=True)
    SCORES.write_text(json.dumps(dict(sorted(scores.items())), indent=1), encoding="utf-8")
    print(f"composites done: {len(todo)} pairs in {time.monotonic() - t0:.0f}s", flush=True)
    return scores


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated pair ids")
    args = ap.parse_args()
    regenerate(set(args.only.split(",")) if args.only else None)
