# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Auto-tune each pair's 2D align (scale/dx/dy) by maximising silhouette IoU.

Only works for references on a dark studio background (the book photography):
the ref silhouette is everything brighter than --ref-thresh. The render
silhouette comes from the content mask. The search is a coarse grid + local
refinement at reduced resolution, then written back to the manifest with
status "aligned".

References crop the machine (e.g. the counter-spring rod leaves the frame)
while renders contain the whole model, so the default content-fit
misestimates scale — this recovers it per pair.

Usage:
    uv run comparisons/tools/tune_align.py --only id1,id2 [--write]
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import composite  # noqa: E402

MANIFEST = composite.MANIFEST
WORK_H = 240  # search resolution


def _count(mask: Image.Image) -> int:
    return mask.histogram()[255]


def _iou(a: Image.Image, b: Image.Image) -> float:
    inter = _count(ImageChops.darker(a, b))
    union = _count(ImageChops.lighter(a, b))
    return inter / union if union else 0.0


def _paste(canvas_size, mask: Image.Image, scale: float, dx: int, dy: int) -> Image.Image:
    w = max(1, round(mask.width * scale))
    h = max(1, round(mask.height * scale))
    canvas = Image.new("L", canvas_size, 0)
    canvas.paste(mask.resize((w, h), Image.NEAREST),
                 ((canvas_size[0] - w) // 2 + dx, (canvas_size[1] - h) // 2 + dy))
    return canvas


def tune_pair(pair: dict, ref_thresh: int) -> tuple[dict, float, float]:
    pid = pair["id"]
    ref = Image.open(composite.pair_paths(pid)["ref"]).convert("L")
    rw, rh = ref.size
    small = (max(1, round(rw * WORK_H / rh)), WORK_H)
    refmask = ref.resize(small, Image.BILINEAR).point(lambda v: 255 if v > ref_thresh else 0)

    ren = Image.open(composite.pair_paths(pid)["render"])
    mask = composite._content_mask(ren)
    bbox = mask.getbbox() or (0, 0, ren.width, ren.height)
    mask = mask.crop(bbox)
    # base content-fit scale at work resolution
    s0 = min(small[0] / mask.width, small[1] / mask.height)
    base = mask.resize((max(1, round(mask.width * s0)), max(1, round(mask.height * s0))),
                       Image.NEAREST)

    cur = pair.get("align") or {}
    before = _iou(refmask, _paste(small, base, cur.get("scale", 1.0),
                                  round(cur.get("dx_px", 0) * WORK_H / rh),
                                  round(cur.get("dy_px", 0) * WORK_H / rh)))

    best = (1.0, 0, 0)
    best_iou = -1.0
    for k100 in range(80, 185, 5):
        for dx in range(-48, 49, 8):
            for dy in range(-48, 49, 8):
                v = _iou(refmask, _paste(small, base, k100 / 100, dx, dy))
                if v > best_iou:
                    best_iou, best = v, (k100 / 100, dx, dy)
    k, bdx, bdy = best
    for k100 in range(round(k * 100) - 4, round(k * 100) + 5, 2):
        for dx in range(bdx - 7, bdx + 8, 2):
            for dy in range(bdy - 7, bdy + 8, 2):
                v = _iou(refmask, _paste(small, base, k100 / 100, dx, dy))
                if v > best_iou:
                    best_iou, best = v, (k100 / 100, dx, dy)

    k, dx, dy = best
    up = rh / WORK_H
    align = {"scale": round(k, 3), "dx_px": round(dx * up), "dy_px": round(dy * up)}
    return align, before, best_iou


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", required=True, help="comma-separated pair ids")
    ap.add_argument("--ref-thresh", type=int, default=40)
    ap.add_argument("--write", action="store_true", help="write manifest + regen composites")
    args = ap.parse_args()
    only = set(args.only.split(","))

    manifest = composite.load_manifest()
    touched = []
    for pair in manifest["pairs"]:
        if pair["id"] not in only:
            continue
        align, before, after = tune_pair(pair, args.ref_thresh)
        print(f"{pair['id']}: IoU {before:.3f} -> {after:.3f}  {align}")
        if args.write:
            pair["align"] = align
            pair["status"] = "aligned"
            touched.append(pair["id"])
    if touched:
        MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        composite.regenerate(set(touched))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
