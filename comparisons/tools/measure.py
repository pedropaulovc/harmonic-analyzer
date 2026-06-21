# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Report RMS mismatch (scores.json metric, lower=better) AND silhouette IoU
(higher=better) per pair, so a tuning change can be verified holistically and
metric-gaming (shrinking the render to cherry-pick matching pixels) is caught.

    uv run comparisons/tools/measure.py [--only id,..] [--ref-thresh 40]
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import composite  # noqa: E402


def _count(mask: Image.Image) -> int:
    return mask.histogram()[255]


def iou_pair(pair: dict, ref_thresh: int) -> float:
    pid = pair["id"]
    ref = Image.open(composite.pair_paths(pid)["ref"]).convert("L")
    refmask = ref.point(lambda v: 255 if v > ref_thresh else 0)
    ren, mask, offset = composite._fitted_render(pid, ref.size, pair.get("align"))
    canvas = Image.new("L", ref.size, 0)
    canvas.paste(mask, offset)
    inter = _count(ImageChops.darker(refmask, canvas))
    union = _count(ImageChops.lighter(refmask, canvas))
    return inter / union if union else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--ref-thresh", type=int, default=40)
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None

    manifest = composite.load_manifest()
    rows = []
    for pair in manifest["pairs"]:
        if only and pair["id"] not in only:
            continue
        pid = pair["id"]
        if not composite.pair_paths(pid)["render"].exists():
            continue
        rms = composite.score_pair(pid, pair.get("align"))
        iou = iou_pair(pair, args.ref_thresh)
        rows.append((pid, rms, iou))
        print(f"{pid:38s} RMS {rms:6.2f} (lower=better)  IoU {iou:.3f} (higher=better)")
    if rows:
        mrms = sum(r[1] for r in rows) / len(rows)
        miou = sum(r[2] for r in rows) / len(rows)
        print(f"{'MEAN':38s} RMS {mrms:6.2f}              IoU {miou:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
