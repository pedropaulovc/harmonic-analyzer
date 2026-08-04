# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""One-off parity check: Blender offline renders vs backed-up SolidWorks captures.

Both render sets are content-trimmed already; normalise to a common height and
compare silhouettes (content masks) via IoU. High IoU (>0.95) means the offline
camera/framing replicates the SolidWorks pipeline.

    uv run cad/comparisons/tools/parity_check.py
"""

import sys
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import composite  # noqa: E402

SW_DIR = composite.COMP / ".parity_sw"
WORK_H = 480


def silhouette(path: Path) -> Image.Image:
    img = Image.open(path)
    mask = composite._content_mask(img)
    bbox = mask.getbbox()
    if bbox:
        mask = mask.crop(bbox)
    w = max(1, round(mask.width * WORK_H / mask.height))
    return mask.resize((w, WORK_H), Image.Resampling.NEAREST)


def iou(a: Image.Image, b: Image.Image) -> float:
    w = max(a.width, b.width)
    ca = Image.new("L", (w, WORK_H), 0)
    cb = Image.new("L", (w, WORK_H), 0)
    ca.paste(a, ((w - a.width) // 2, 0))
    cb.paste(b, ((w - b.width) // 2, 0))
    inter = union = 0
    for va, vb in zip(ca.get_flattened_data(), cb.get_flattened_data(), strict=True):
        if va and vb:
            inter += 1
        if va or vb:
            union += 1
    return inter / union if union else 0.0


def main() -> int:
    rows = []
    for sw in sorted(SW_DIR.glob("*.jpg")):
        pid = sw.stem
        bl = composite.pair_paths(pid)["render"]
        if not bl.exists():
            rows.append((pid, None, "no offline render"))
            continue
        a, b = silhouette(sw), silhouette(bl)
        ar_a, ar_b = a.width / WORK_H, b.width / WORK_H
        rows.append((pid, iou(a, b), f"aspect sw={ar_a:.3f} blender={ar_b:.3f}"))
    for pid, v, note in rows:
        print(f"{'--' if v is None else f'{v:.3f}'}  {pid}  {note}")
    vals = [v for _, v, _ in rows if v is not None]
    if vals:
        print(f"mean IoU {sum(vals) / len(vals):.3f}  min {min(vals):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
