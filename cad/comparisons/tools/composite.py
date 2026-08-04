# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Composite + scoring helpers for the photo-vs-CAD comparison pairs.

Importable from the SolidWorks build venv and runnable
standalone with uv to regenerate composites/scores without SolidWorks:

    uv run cad/comparisons/tools/composite.py [--only id1,id2]

Per pair (see ../manifest.json):
    ref/<id>.jpg                prepared reference (cropped/rotated copy)
    render/<id>.jpg             raw CAD render (registration in sidecar)
    composite/<id>_cad.jpg      render registered into the reference frame
                                (same scale/offset as the blend layer, black
                                background) — the gallery's reveal-slider top
    composite/<id>_blend.jpg    overlay: grayscale ref under red-tinted render
                                (render background knocked out)
    scores.json                 pair id -> RMS shape-mismatch score
"""

import argparse
import json
import time
from pathlib import Path
from typing import Literal

from PIL import Image, ImageOps

COMP = Path(__file__).resolve().parents[1]
REPO = COMP.parent.parent
MANIFEST = COMP / "manifest.json"
SCORES = COMP / "scores.json"
StaleStage = Literal["render", "composite"]

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


def sidecar_path(pair_id: str) -> Path:
    return COMP / "render" / f"{pair_id}.meta.json"


def blender_registration(pair: dict) -> str:
    """Choose framing from pose completeness, not pair-specific tuning.

    Pose Studio saves a concrete target. Legacy turntable poses leave it null
    and depend on content-fit plus the manifest's 2D alignment.
    """
    if pair.get("camera", {}).get("target_mm") is not None:
        return "camera_frame"
    return "content_fit"


def stale_stage(pair: dict, model_mtime: float) -> StaleStage | None:
    """Return the cheapest gallery stage needed to refresh ``pair``."""
    paths = pair_paths(pair["id"])
    sidecar = sidecar_path(pair["id"])
    if not paths["render"].exists() or not sidecar.exists():
        return "render"
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except ValueError:
        return "render"
    if (
        meta.get("camera") != pair["camera"]
        or meta.get("reference") != pair["reference"]
        or meta.get("model_mtime") != model_mtime
        or (
            meta.get("engine") == "blender"
            and meta.get("registration") != blender_registration(pair)
        )
    ):
        return "render"
    if (
        (
            meta.get("registration") != "camera_frame"
            and meta.get("align") != pair.get("align")
        )
        or not paths["cad"].exists()
        or not paths["blend"].exists()
    ):
        return "composite"
    return None


def record_composite_align(pair: dict) -> None:
    """Stamp a composite-only refresh without rewriting the raw render."""
    sidecar = sidecar_path(pair["id"])
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    meta["align"] = pair.get("align")
    sidecar.write_text(json.dumps(meta), encoding="utf-8")


def prepare_reference(pair: dict, max_px: int = 1600, out: Path | None = None) -> Path:
    """Copy the pair's source reference into ref/<id>.png (crop/rotate/cap).

    ``out`` overrides the destination (bench cad/comparisons/bench redirects refs
    out of the shipping cad/comparisons/ref/ tree cut_release ships wholesale).
    """
    src = REPO / pair["reference"]["path"]
    out = out or pair_paths(pair["id"])["ref"]
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src)
    img = ImageOps.exif_transpose(img)
    if pair["reference"].get("mirror"):
        # only for individually-verified flipped reproductions: confirm with a
        # chiral cue (text direction, crank-vs-platen side) before setting.
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    rot = pair["reference"].get("rotate_deg", 0)
    if rot:
        img = img.rotate(-rot, expand=True, fillcolor="white")
    crop = pair["reference"].get("crop")
    if crop:
        img = img.crop(tuple(crop))
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    img.convert("RGB").save(out, **JPEG_OPTS)
    return out


def _content_mask(img: Image.Image, thresh: int = 30,
                  background: str | None = None) -> Image.Image:
    """255 where render content, 0 where viewport background.

    SolidWorks captures sit on a vertical-gradient background, so a plain
    corner-colour test fails; flood-filling from the corners follows the
    gradient and stops at content edges.

    ``background`` (colour name/hex — the RENDER's own uniform backdrop, from
    the renderer's sidecar ``render_bg``, NOT the manifest's presentation
    colour): only corners actually SHOWING that colour seed the flood. Both
    engines lay the model over an exact uniform colour (Blender: the pair's
    reference background; SolidWorks: forced plain white), and a macro framing
    can put model at a corner (ch12-p001: the teal base plate spans the bottom
    edge) — an unconditional corner flood then starts inside the model and
    eats every connected region within thresh of it (the base plate AND the
    rocker-arm support). A corner showing model is simply skipped; if no
    corner matches, the mask is all-content. ``None`` (pre-``render_bg``
    sidecar) keeps the unconditional flood.
    """
    from PIL import ImageChops, ImageColor, ImageDraw

    rgb = img.convert("RGB")
    sentinel = (255, 0, 255)
    bg_rgb = ImageColor.getrgb(background) if background else None
    w, h = rgb.size
    for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        px = rgb.getpixel(xy)
        if px == sentinel:
            continue
        if bg_rgb is not None and max(
                abs(a - b) for a, b in zip(px, bg_rgb)) > thresh:
            continue  # corner shows model, not background -- don't seed here
        ImageDraw.floodfill(rgb, xy, sentinel, thresh=thresh)
    bg = Image.new("RGB", rgb.size, sentinel)
    return ImageChops.difference(rgb, bg).convert("L").point(lambda v: 255 if v else 0)


def trim_render_file(path: Path, margin_frac: float = 0.01,
                     background: str | None = None) -> None:
    """Crop a captured render to its content + a small margin, in place.

    ViewZoomToFit2 fits the SolidWorks window aspect, not the capture canvas,
    so raw captures carry large background margins. The offline renderer captures
    on an oversized canvas and calls this to store a content-tight image.

    ``background``: the capture's uniform backdrop colour, forwarded to
    ``_content_mask`` so a model region touching a corner is not flood-eaten
    out of the trim bbox (and thereby permanently cropped from the stored
    render). Both callers know their backdrop — render_offline composites onto
    the pair's reference colour; legacy white captures remain supported — so pass
    it; ``None`` keeps the legacy unconditional corner flood.
    """
    # Load + close the source handle BEFORE writing back to the same path:
    # Image.open is lazy and keeps `path` open for reading, so saving to the same
    # path reopens it for w+b while the read handle is live -- a Windows sharing
    # race. An external scanner (Defender/indexer) touching the freshly-written
    # JPEG makes it intermittent (random EINVAL/EACCES across a 400-file batch).
    with Image.open(path) as src:
        src.load()
        bbox = _content_mask(src, background=background).getbbox()
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


def render_metadata(pair_id: str) -> dict:
    sidecar = sidecar_path(pair_id)
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def render_bg(pair_id: str) -> str | None:
    """The uniform colour behind the render's pixels, recorded by the renderer
    in its sidecar (``render_bg``). Fallbacks for pre-key sidecars: an
    ``engine: blender`` tag proves the render used the pair's reference
    background, and a sidecar with NO engine key is provably a legacy
    legacy SolidWorks capture (older sidecars could omit the engine,
    always under force_plain_white_background) — so it reads as white rather
    than degrading to the model-corner-eating unconditional flood. Only a
    missing/unreadable sidecar returns None (unconditional flood)."""
    meta = render_metadata(pair_id)
    if not meta:
        return None
    if "render_bg" in meta:
        return meta["render_bg"]
    if meta.get("engine") == "blender":
        return meta.get("reference", {}).get("background", "black")
    return "white"


def _fitted_render(pair_id: str, ref_size: tuple[int, int], align: dict | None):
    """Place a render in the reference frame according to its sidecar contract.

    Blender renders tagged ``camera_frame`` preserve the exact frame authored
    in Pose Studio, including its target and zoom. SolidWorks captures retain
    the legacy content-fit path because their window-aspect margins are not a
    camera-frame contract. Only content-fit captures use the legacy manifest
    2D fine-alignment; applying it to a camera frame would transform the pose a
    second time.
    """
    align = align or {}
    ren = Image.open(pair_paths(pair_id)["render"])
    mask = _content_mask(ren, background=render_bg(pair_id))
    rw, rh = ref_size
    if render_metadata(pair_id).get("registration") == "camera_frame":
        ren = ren.resize((rw, rh), Image.Resampling.LANCZOS)
        mask = mask.resize((rw, rh), Image.Resampling.NEAREST)
        return ren, mask, (0, 0)

    bbox = mask.getbbox() or (0, 0, ren.width, ren.height)
    ren, mask = ren.crop(bbox), mask.crop(bbox)
    s = min(rw / ren.width, rh / ren.height) * align.get("scale", 1.0)
    w, h = max(1, round(ren.width * s)), max(1, round(ren.height * s))
    ren = ren.resize((w, h), Image.Resampling.LANCZOS)
    mask = mask.resize((w, h), Image.Resampling.NEAREST)
    dx = align.get("dx_px", 0) + (rw - w) // 2
    dy = align.get("dy_px", 0) + (rh - h) // 2
    return ren, mask, (dx, dy)


def aligned_render(pair_id: str, align: dict | None,
                   background: str = "black") -> Path:
    """The render placed in the reference frame — identical scale/offset to
    the blend's red layer — on the reference's background colour, so the
    gallery's reveal slider swaps between two pixel-registered images."""
    p = pair_paths(pair_id)
    with Image.open(p["ref"]) as ref:
        ref_size = ref.size
    ren, mask, offset = _fitted_render(pair_id, ref_size, align)
    canvas = Image.new("RGB", ref_size, background)
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
    for rv, cv, mv in zip(
        ref.get_flattened_data(),
        canvas.get_flattened_data(),
        mcanvas.get_flattened_data(),
        strict=True,
    ):
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
        aligned_render(pid, align, pair["reference"].get("background", "black"))
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
