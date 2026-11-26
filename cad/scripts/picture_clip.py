"""Clip and collision check of the setup pictures on a rendered hobby traveler.

prechips embeds each plan picture (``cad/process/<stem>/diagrams/*.svg``) in
``traveler-hobby.html`` as a base64 ``data:image/svg+xml`` ``<img>``, with its
``{{cad.}}``/``{{process.}}`` bindings already resolved, so the text checked
here is the text that prints. For every picture except prechips' own picture
key it reports:

``CLIP``
    a text box past the picture's viewBox (the printed picture cuts it off);
``TEXT``
    two text boxes overlapping;
``LEADER``
    a leader line crossing a text box.

Text is measured in the font the sheet prints in: the traveler PDF is printed
by Edge or Chrome, and every picture names Arial (prechips gives one that
names no real font the sheet's ``Arial, Helvetica, sans-serif``), so the PDF
embeds ArialMT. Arial's advance widths are Helvetica's, and matplotlib ships
the Adobe Helvetica and Helvetica-Bold metrics (``pdfcorefonts/*.afm``), so the
measure is the same on every machine with no Arial installed. A glyph those
metrics lack (outside Latin-1 and the Adobe standard set: ≥, →, Δ) is measured
in DejaVu Sans, matplotlib's bundled font. Kerning is ignored.

``prechips_traveler.py`` runs :func:`check` on the hobby sheet it has just
rendered and fails the render (exit 2) on a finding that
``cad/config/picture-clip-baseline.toml`` does not list, or on a listed one
that no longer occurs (remove it from the baseline: the list only shrinks).

usage: uv run --frozen python cad/scripts/picture_clip.py <traveler-hobby.html | picture.svg>...
"""

from __future__ import annotations

import base64
import html
import math
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import matplotlib
from fontTools.agl import UV2AGL
from PIL import ImageFont

BASELINE = Path(__file__).resolve().parents[1] / "config" / "picture-clip-baseline.toml"
_SVG = "{http://www.w3.org/2000/svg}"
_IMG = re.compile(r"<img\b[^>]*>")
_DATA = re.compile(r'src="data:image/svg\+xml;base64,([^"]+)"')
_ALT = re.compile(r'alt="([^"]*)"')
# prechips' own legend picture, not a plan picture.
_KEY_ALT = "Picture key"
# A picture is named by the start of its alt text (bindings resolved).
_PICTURE_NAME = 60
_SKIPPED = {"defs", "symbol", "clipPath", "mask", "pattern", "marker", "title", "desc", "style"}


@dataclass(frozen=True)
class Finding:
    kind: str      # CLIP, TEXT or LEADER
    picture: str   # the picture's alt text, its first 60 characters
    text: str      # the text clipped or crossed; "a / b" for two overlapping
    where: str = ""

    @property
    def key(self) -> str:
        """The baseline's entry for it: kind, picture and text, no coordinates."""
        return f"{self.kind} | {self.picture} | {self.text}"

    def __str__(self) -> str:
        return f"{self.key}{f' ({self.where})' if self.where else ''}"


@cache
def _afm(bold: bool) -> dict[str, float]:
    """Glyph name → advance width (1/1000 em) from matplotlib's Adobe metrics."""
    name = "Helvetica-Bold.afm" if bold else "Helvetica.afm"
    path = Path(matplotlib.get_data_path()) / "fonts" / "pdfcorefonts" / name
    widths = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        if line.startswith("C "):
            fields = dict(part.strip().split(" ", 1) for part in line.split(";") if part.strip())
            widths[fields["N"]] = float(fields["WX"])
    return widths


@cache
def _fallback(bold: bool) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name), 1000)


def text_width(text: str, size: float, bold: bool = False) -> float:
    """The advance width of ``text`` in Arial at ``size`` px."""
    widths = _afm(bold)
    total = 0.0
    for char in text:
        glyph = UV2AGL.get(ord(char))
        total += widths[glyph] if glyph in widths else _fallback(bold).getlength(char)
    return total * size / 1000


def _size(element: ET.Element, default: float) -> float:
    style = re.search(r"font-size:\s*([\d.]+)", element.get("style", ""))
    if style:
        return float(style.group(1))
    attribute = re.match(r"([\d.]+)", element.get("font-size", ""))
    return float(attribute.group(1)) if attribute else default


def _bold(element: ET.Element, inherited: bool) -> bool:
    style = re.search(r"font-weight:\s*([\w]+)", element.get("style", ""))
    weight = style.group(1) if style else element.get("font-weight")
    if weight is None:
        return inherited
    return weight in {"bold", "bolder"} or (weight.isdigit() and int(weight) >= 600)


_Matrix = tuple[float, float, float, float, float, float]  # SVG (a b c d e f)
_IDENTITY: _Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_TRANSFORM = re.compile(r"(matrix|translate|scale|rotate)\s*\(([^)]*)\)")


def _multiply(m: _Matrix, n: _Matrix) -> _Matrix:
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2,
            a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def _transform(value: str) -> _Matrix:
    out = _IDENTITY
    for kind, args in _TRANSFORM.findall(value or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if kind == "matrix":
            m = tuple(v)
        elif kind == "translate":
            m = (1.0, 0.0, 0.0, 1.0, v[0], v[1] if len(v) > 1 else 0.0)
        elif kind == "scale":
            m = (v[0], 0.0, 0.0, v[1] if len(v) > 1 else v[0], 0.0, 0.0)
        else:
            r = math.radians(v[0])
            cx, cy = (v[1], v[2]) if len(v) > 2 else (0.0, 0.0)
            m = _multiply(_multiply((1.0, 0.0, 0.0, 1.0, cx, cy),
                                    (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0.0, 0.0)),
                          (1.0, 0.0, 0.0, 1.0, -cx, -cy))
        out = _multiply(out, m)
    return out


def _apply(m: _Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def _nested(element: ET.Element) -> _Matrix:
    """A nested <svg>'s placement: its x/y, and its viewBox scaled to its width/height."""
    m = (1.0, 0.0, 0.0, 1.0, float(element.get("x", 0)), float(element.get("y", 0)))
    box = element.get("viewBox")
    if box and element.get("width") and element.get("height"):
        vx, vy, vw, vh = (float(v) for v in box.replace(",", " ").split())
        sx, sy = float(element.get("width")) / vw, float(element.get("height")) / vh
        m = _multiply(m, (sx, 0.0, 0.0, sy, -vx * sx, -vy * sy))
    return m


def _walk(root: ET.Element):
    """The picture's text boxes (x0, y0, x1, y1, text) and leader segments, in
    the root's coordinates: every transform, nested <svg> placement, inherited
    font size, weight and class applied. Identical boxes (a halo under its
    text) count once."""
    boxes: dict[tuple, tuple] = {}
    leaders = []

    def visit(element, m: _Matrix, size: float, bold: bool, leader: bool, top: bool) -> None:
        tag = element.tag.removeprefix(_SVG)
        if tag in _SKIPPED:
            return
        if tag == "svg" and not top:
            m = _multiply(m, _nested(element))
        m = _multiply(m, _transform(element.get("transform", "")))
        size = _size(element, size)
        bold = _bold(element, bold)
        leader = leader or "leader" in (element.get("class") or "").split()
        if tag == "text":
            string = "".join(element.itertext())
            if string.strip():
                x, y = float(element.get("x", 0)), float(element.get("y", 0))
                w = text_width(string, size, bold)
                anchor = element.get("text-anchor", "start")
                x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
                # Cap height above the baseline, descenders below; 1 px of side
                # bearing each side.
                corners = [_apply(m, px, py) for px in (x0 + 1, x0 + w - 1)
                           for py in (y - 0.72 * size, y + 0.2 * size)]
                xs, ys = [p[0] for p in corners], [p[1] for p in corners]
                box = (min(xs), min(ys), max(xs), max(ys), string)
                boxes[(round(box[0], 1), round(box[1], 1), string)] = box
            return
        if tag == "line" and leader:
            p1 = _apply(m, float(element.get("x1", 0)), float(element.get("y1", 0)))
            p2 = _apply(m, float(element.get("x2", 0)), float(element.get("y2", 0)))
            leaders.append((*p1, *p2))
        for child in element:
            visit(child, m, size, bold, leader, False)

    visit(root, _IDENTITY, _size(root, 13.0), _bold(root, False), False, True)
    return list(boxes.values()), leaders


def _crosses(x1: float, y1: float, x2: float, y2: float, box) -> bool:
    bx0, by0, bx1, by1 = box[:4]
    for i in range(41):
        u = i / 40
        x, y = x1 + (x2 - x1) * u, y1 + (y2 - y1) * u
        if bx0 < x < bx1 and by0 < y < by1:
            return True
    return False


def svg_findings(svg: str, picture: str) -> list[Finding]:
    """The clip and collision findings of one picture's SVG."""
    root = ET.fromstring(svg)
    vx, vy, vw, vh = (float(v) for v in root.get("viewBox").replace(",", " ").split())
    boxes, leaders = _walk(root)
    found = [
        Finding("CLIP", picture, b[4],
                f"x {b[0]:.0f}..{b[2]:.0f} y {b[1]:.0f}..{b[3]:.0f} in {vx:g} {vy:g} {vw:g} {vh:g}")
        for b in boxes
        if b[0] < vx - 1 or b[2] > vx + vw + 1 or b[1] < vy - 1 or b[3] > vy + vh + 1
    ]
    for i, a in enumerate(boxes):
        found += [
            Finding("TEXT", picture, f"{a[4]} / {b[4]}")
            for b in boxes[i + 1:]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
        ]
    for x1, y1, x2, y2 in leaders:
        found += [
            Finding("LEADER", picture, b[4], f"({x1:.0f},{y1:.0f})->({x2:.0f},{y2:.0f})")
            for b in boxes if _crosses(x1, y1, x2, y2, b)
        ]
    return found


def findings(sheet: Path) -> list[Finding]:
    """Every finding on the plan pictures of a rendered traveler, or of one .svg."""
    sheet = Path(sheet)
    if sheet.suffix == ".svg":
        return svg_findings(sheet.read_text(encoding="utf-8"), sheet.name)
    out = []
    for tag in _IMG.findall(sheet.read_text(encoding="utf-8")):
        data = _DATA.search(tag)
        if not data:
            continue
        alt = _ALT.search(tag)
        alt = html.unescape(alt.group(1)) if alt else ""
        if alt.startswith(_KEY_ALT):
            continue
        out += svg_findings(base64.b64decode(data.group(1)).decode("utf-8"), alt[:_PICTURE_NAME])
    return out


def baseline(stem: str, path: Path | None = None) -> set[str]:
    """The findings ``stem``'s pictures are known to carry (their keys), from
    ``path`` or :data:`BASELINE`."""
    with (path or BASELINE).open("rb") as handle:
        plans = tomllib.load(handle).get("plans", {})
    return set(plans.get(stem, {}).get("findings", []))


def check(stem: str, sheet: Path, path: Path | None = None) -> list[str]:
    """What fails ``stem``'s render: each finding the baseline does not list,
    and each listed one that no longer occurs. Empty when it passes."""
    found = findings(sheet)
    known = baseline(stem, path)
    keys = {f.key for f in found}
    return [f"new: {f}" for f in found if f.key not in known] + [
        f"fixed, so remove it from {(path or BASELINE).name}: {key}"
        for key in sorted(known - keys)
    ]


def main(argv: list[str] | None = None) -> int:
    total = 0
    for arg in argv if argv is not None else sys.argv[1:]:
        for finding in findings(Path(arg)):
            print(f"{arg}: {finding}")
            total += 1
    print(f"picture_clip: {total} finding(s)")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
