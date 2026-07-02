"""Re-render final/*_annotated.png from final/*.json with collision-aware legend placement.

The legend box is placed at the first candidate anchor whose rectangle (plus margin)
contains no annotation dot, so a dot is never hidden under the legend.
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
SRC = HERE.parent / "references" / "albert-michelsons-harmonic-analyzer" / "ch30_images"
FINAL = HERE / "final"

COLORS = {
    "red": (255, 0, 0),
    "orange": (255, 140, 0),
    "magenta": (255, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
}


def wrap(text, font, draw, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
            continue
        lines.append(cur)
        cur = w
    if cur:
        lines.append(cur)
    return lines


def render(stem):
    meta = json.loads((FINAL / f"{stem}.json").read_text())
    im = Image.open(SRC / meta["image"]).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im)
    r = max(10, round(W / 125))

    for p in meta["points"]:
        x, y, c = p["x"], p["y"], COLORS[p["color"]]
        draw.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3], fill=(0, 0, 0))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c)

    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", max(18, round(W / 45)))
    lh = round(font.size * 1.35)
    sw = font.size  # swatch square side
    pad = round(font.size * 0.6)
    max_text_w = round(W * 0.52)

    rows = [(COLORS[p["color"]], p["feature"]) for p in meta["points"]]
    occ = ", ".join(o["feature"] for o in meta.get("occluded", []))
    occ_lines = wrap(f"occluded: {occ}", font, draw, max_text_w) if occ else []

    box_w = pad * 2 + sw + pad + max(
        [round(draw.textlength(t, font=font)) for _, t in rows]
        + [round(draw.textlength(t, font=font)) - sw - pad for t in occ_lines]
        + [1]
    )
    box_h = pad * 2 + lh * (len(rows) + len(occ_lines))

    margin = r + 8
    anchors = [(10, 10), (W - box_w - 10, 10), (10, H - box_h - 10),
               (W - box_w - 10, H - box_h - 10), (10, (H - box_h) // 2),
               (W - box_w - 10, (H - box_h) // 2)]
    bx, by = anchors[0]
    for ax, ay in anchors:
        clash = any(ax - margin <= p["x"] <= ax + box_w + margin
                    and ay - margin <= p["y"] <= ay + box_h + margin
                    for p in meta["points"])
        if not clash:
            bx, by = ax, ay
            break

    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([bx, by, bx + box_w, by + box_h], fill=(10, 10, 10, 215), outline=(255, 255, 255, 255), width=2)
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(im)

    y = by + pad
    for c, t in rows:
        draw.rectangle([bx + pad, y + (lh - sw) // 2, bx + pad + sw, y + (lh - sw) // 2 + sw], fill=c, outline=(255, 255, 255))
        draw.text((bx + pad + sw + pad, y), t, font=font, fill=(255, 255, 255))
        y += lh
    for t in occ_lines:
        draw.text((bx + pad, y), t, font=font, fill=(210, 210, 210))
        y += lh

    im.save(FINAL / f"{stem}_annotated.png")
    print(stem, "legend at", (bx, by), "box", (box_w, box_h))


for n in range(2, 10):
    render(f"page00{n}_img01")
