# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""The 11 presentation arms for the pose benchmark (docs/pose-presentation-benchmark.md).

Every builder consumes the SAME fixed-frame ref + render pair (produced by
gen_cases.py -> render_offline.py --no-trim --fixed-frame) and emits a stimulus
normalised to the shared ~1.4 MP budget, so no arm wins by resolution. The ref
and render depict the same frozen framing; the pair's manifest 2-D align
(scale/dx/dy) registers the render into the ref frame as a constant of the case
family, so the control sits registered and perturbations move relative to it.

No content re-fit anywhere: trimming/fitting the render (the shipping composite
path) would cancel the target/zoom deltas under test. P1 reuses only
composite._render_rgba's tint math, never _fitted_render.

Entry point: build_stimulus(row, arm, out_dir, opaque_id, grid, side, order)
-> list[Path] (one image, or two for P10 flicker). ``row`` is a cases.jsonl dict.
"""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

BENCH = Path(__file__).resolve().parent
TOOLS = BENCH.parent / "tools"
sys.path.insert(0, str(TOOLS))
import composite  # noqa: E402

PIXEL_BUDGET = 1_400_000          # ~1.4 MP per stimulus
JPEG = {"quality": 90, "optimize": True}
ARMS = [f"P{i}" for i in range(1, 12)]


def _bg_rgb(name: str) -> tuple[int, int, int]:
    return (255, 255, 255) if name == "white" else (0, 0, 0)


def _content_mask_solid(render: Image.Image, bg: str, tol: int = 24) -> Image.Image:
    """255 where the render differs from its solid background colour, else 0."""
    rgb = render.convert("RGB")
    flat = Image.new("RGB", rgb.size, _bg_rgb(bg))
    diff = ImageChops.difference(rgb, flat).convert("L")
    return diff.point(lambda v: 255 if v > tol else 0)


_FIT_CACHE: dict[str, dict] = {}


def _family_fit(pid: str, align: dict, ref_size: tuple[int, int], bg: str) -> dict:
    """Freeze the CONTROL render's content-fit transform for the whole family.

    The shipping composite path fits the CONTENT-TRIMMED render to the ref, so the
    manifest align was tuned against that. Reproduce it ONCE from the pair's
    control render (its content bbox -> the min-fit scale + centred paste + align
    offset), then apply the SAME (scale, origin) to every case's UNTRIMMED canvas.
    The control therefore registers exactly as the gallery does, while a perturbed
    render's content — shifted/zoomed within the fixed canvas — moves relative to
    it (a per-case content re-fit would cancel that translation/zoom signal).
    """
    if pid in _FIT_CACHE:
        return _FIT_CACHE[pid]
    ctrl = Image.open(BENCH / "out" / "render" / f"{pid}+ctrl.jpg").convert("RGB")
    bb = _content_mask_solid(ctrl, bg).getbbox() or (0, 0, ctrl.width, ctrl.height)
    cx0, cy0, cx1, cy1 = bb
    cw, ch = cx1 - cx0, cy1 - cy0
    rw, rh = ref_size
    s = min(rw / cw, rh / ch) * align.get("scale", 1.0)
    px0 = align.get("dx_px", 0) + (rw - cw * s) / 2   # where the control content's
    py0 = align.get("dy_px", 0) + (rh - ch * s) / 2   # top-left lands in the ref frame
    fit = {"s": s, "cx0": cx0, "cy0": cy0, "px0": px0, "py0": py0}
    _FIT_CACHE[pid] = fit
    return fit


def _registered(row: dict, out_size: tuple[int, int] | None = None):
    """Render placed into the ref frame at the family's frozen content-fit.

    Returns (ref RGB, render RGB, content mask L) at a common size (the ref size,
    or ``out_size``). Uncovered frame stays the reference background colour.
    """
    pid = row["pair_id"]
    bg = row.get("background", "black")
    ref = Image.open(BENCH / "out" / "ref" / f"{pid}.jpg").convert("RGB")
    ren_src = Image.open(BENCH / "out" / "render" / f"{row['case_id']}.jpg").convert("RGB")
    size = out_size or ref.size
    if ref.size != size:
        ref = ref.resize(size, Image.Resampling.LANCZOS)
    fit = _family_fit(pid, row.get("align") or {}, size, bg)
    s = fit["s"]
    ren = ren_src.resize((max(1, round(ren_src.width * s)), max(1, round(ren_src.height * s))),
                         Image.Resampling.LANCZOS)
    mask = _content_mask_solid(ren, bg)
    ox = round(fit["px0"] - fit["cx0"] * s)   # frozen transform: control content
    oy = round(fit["py0"] - fit["cy0"] * s)   # lands at the align position; a case's
    canvas = Image.new("RGB", size, _bg_rgb(bg))  # shifted content moves with it
    mcanvas = Image.new("L", size, 0)
    canvas.paste(ren, (ox, oy), mask)
    mcanvas.paste(mask, (ox, oy))
    return ref, canvas, mcanvas


def _fit_budget(img: Image.Image, budget: int = PIXEL_BUDGET) -> Image.Image:
    w, h = img.size
    if w * h <= budget:
        return img
    s = (budget / (w * h)) ** 0.5
    return img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.Resampling.LANCZOS)


def _font(px: int):
    try:
        return ImageFont.truetype("arial.ttf", px)
    except OSError:
        return ImageFont.load_default()


def _grid_overlay(img: Image.Image, n: int = 10) -> Image.Image:
    """SoM-style labelled n x n grid: light lines + row/col speakable labels."""
    img = img.convert("RGB").copy()
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    fp = _font(max(10, w // 60))
    line = (255, 235, 0, 150)
    for i in range(1, n):
        d.line([(w * i // n, 0), (w * i // n, h)], fill=line, width=1)
        d.line([(0, h * i // n), (w, h * i // n)], fill=line, width=1)
    for i in range(n):
        d.text((w * i // n + 2, 1), str(i), font=fp, fill=(255, 235, 0, 230))
        d.text((1, h * i // n + 1), chr(ord("A") + i), font=fp, fill=(255, 235, 0, 230))
    return img


# --- side-by-side helpers ----------------------------------------------------
def _sbs(left: Image.Image, right: Image.Image, gap: int = 8) -> Image.Image:
    h = max(left.height, right.height)

    def pad(im):
        if im.height == h:
            return im
        c = Image.new("RGB", (im.width, h), (128, 128, 128))
        c.paste(im, (0, (h - im.height) // 2))
        return c
    left, right = pad(left), pad(right)
    out = Image.new("RGB", (left.width + gap + right.width, h), (128, 128, 128))
    out.paste(left, (0, 0))
    out.paste(right, (left.width + gap, 0))
    return out


# --- the 11 arms -------------------------------------------------------------
def _p1_blend(ref, ren, mask, alpha=230, desat=False):
    base = ref.convert("L").convert("RGB")
    g = ren.convert("L")
    if desat:
        tint = Image.merge("RGB", (g.point(lambda v: min(255, v + 60)), g, g))
    else:
        tint = Image.merge("RGB", (g.point(lambda v: 255), g, g))
    layer = tint.convert("RGBA")
    layer.putalpha(mask.point(lambda v: alpha if v else 0))
    return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


def _p6_checker(ref, ren, tiles=8):
    w, h = ref.size
    out = ref.copy()
    for ty in range(tiles):
        for tx in range(tiles):
            if (tx + ty) % 2 == 0:
                continue
            box = (w * tx // tiles, h * ty // tiles, w * (tx + 1) // tiles, h * (ty + 1) // tiles)
            out.paste(ren.crop(box), box)
    return out


def _p7_fusion(ref, ren):
    g_ref, g_ren = ref.convert("L"), ren.convert("L")
    # ref -> green, render -> magenta (R+B); registered structure sums to gray
    return Image.merge("RGB", (g_ren, g_ref, g_ren))


def _p8_diff(ref, ren, mask):
    from PIL import ImageOps
    d = ImageChops.difference(ref.convert("L"), ren.convert("L"))
    heat = ImageOps.colorize(d, black=(20, 0, 60), mid=(190, 40, 90), white=(255, 240, 90))
    thumb = _sbs(ref.resize((ref.width // 4, ref.height // 4)),
                 ren.resize((ren.width // 4, ren.height // 4)))
    return _stack(heat, thumb)


def _p9_edges(ref, ren, mask):
    from PIL import ImageFilter
    edges = ren.convert("L").filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 40 else 0)
    out = ref.convert("RGB").copy()
    red = Image.new("RGB", out.size, (255, 40, 40))
    out.paste(red, (0, 0), edges.convert("L"))
    return out


def _stack(top: Image.Image, bottom: Image.Image, gap: int = 8) -> Image.Image:
    w = max(top.width, bottom.width)

    def pad(im):
        if im.width == w:
            return im
        c = Image.new("RGB", (w, im.height), (128, 128, 128))
        c.paste(im, ((w - im.width) // 2, 0))
        return c
    top, bottom = pad(top), pad(bottom)
    out = Image.new("RGB", (w, top.height + gap + bottom.height), (128, 128, 128))
    out.paste(top, (0, 0))
    out.paste(bottom, (0, top.height + gap))
    return out


def _onion(ref, ren):
    strip = []
    for a in (0.0, 0.25, 0.5, 0.75, 1.0):
        strip.append(Image.blend(ref, ren, a))
    w = strip[0].width
    gap = 6
    out = Image.new("RGB", (w * 5 + gap * 4, strip[0].height), (128, 128, 128))
    for i, im in enumerate(strip):
        out.paste(im, (i * (w + gap), 0))
    return out


def build_stimulus(row, arm, out_dir: Path, opaque_id: str,
                   grid: bool = False, side: int = 0, order: int = 0) -> list[Path]:
    """Build one arm's stimulus for a case row. Returns served image path(s)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ref, ren, mask = _registered(row)

    if arm in ("P2", "P3"):
        # side 0: ref left / render right; side 1: swapped
        left, right = (ref, ren) if side == 0 else (ren, ref)
        sheet = _sbs(left, right)
        if arm == "P3" or grid:
            sheet = _grid_overlay(sheet)
    elif arm == "P1":
        sheet = _p1_blend(ref, ren, mask, alpha=230, desat=False)
    elif arm == "P5":
        sheet = _p1_blend(ref, ren, mask, alpha=100, desat=True)
    elif arm == "P4":
        sheet = _onion(ref, ren)
    elif arm == "P6":
        sheet = _p6_checker(ref, ren)
    elif arm == "P7":
        sheet = _p7_fusion(ref, ren)
    elif arm == "P8":
        sheet = _p8_diff(ref, ren, mask)
    elif arm == "P9":
        sheet = _p9_edges(ref, ren, mask)
    elif arm == "P11":
        small_sbs = _sbs(ref.resize((ref.width // 2, ref.height // 2)),
                         ren.resize((ren.width // 2, ren.height // 2)))
        sheet = _stack(small_sbs, _sbs(_p7_fusion(ref, ren).resize((ref.width // 2, ref.height // 2)),
                                       _p9_edges(ref, ren, mask).resize((ref.width // 2, ref.height // 2))))
    elif arm == "P10":
        # flicker: two full frames served as two images, each ~half budget
        frames = (ref, ren) if order == 0 else (ren, ref)
        paths = []
        for i, fr in enumerate(frames):
            im = _fit_budget(fr, PIXEL_BUDGET // 2)
            if grid:
                im = _grid_overlay(im)
            p = out_dir / f"{opaque_id}_{i}.jpg"
            im.convert("RGB").save(p, **JPEG)
            paths.append(p)
        return paths
    else:
        raise ValueError(f"unknown arm {arm}")

    if grid and arm not in ("P2", "P3"):
        sheet = _grid_overlay(sheet)
    sheet = _fit_budget(sheet)
    p = out_dir / f"{opaque_id}.jpg"
    sheet.convert("RGB").save(p, **JPEG)
    return [p]
