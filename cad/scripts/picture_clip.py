"""Clip and collision check of the setup pictures on a rendered hobby traveler.

prechips embeds each plan picture (``cad/process/<stem>/diagrams/*.svg``) in
``traveler-hobby.html`` as a base64 ``data:image/svg+xml`` ``<img>``, with its
``{{cad.}}``/``{{process.}}`` bindings already resolved, so the text checked
here is the text that prints. For every picture except prechips' own picture
key it reports:

``CLIP``
    a text box past the picture's viewBox (the printed picture cuts it off), or
    a picture with no viewBox, width or height, whose extent is unknown;
``TEXT``
    two text boxes overlapping;
``LEADER``
    a leader crossing a text box: a ``<line>``, ``<polyline>``, ``<polygon>`` or
    ``<path>`` with class ``leader`` or inside a ``<g class="leader">``, its
    curves flattened to chords; the crossing is exact, not sampled.

Each text run is boxed on its own: a ``<text>``, and each ``<tspan>`` placed by
its own ``x``/``y`` (a tspan moved only by ``dx``/``dy`` stays in its run).
Font size, weight and ``text-anchor`` inherit from the enclosing elements, as
attributes or ``style=``.

Text is measured in the font the sheet prints in: the traveler PDF is printed
by Edge or Chrome, and every picture names Arial (prechips gives one that
names no real font the sheet's ``Arial, Helvetica, sans-serif``), so the PDF
embeds ArialMT. Arial's advance widths are Helvetica's, and matplotlib ships
the Adobe Helvetica and Helvetica-Bold metrics (``pdfcorefonts/*.afm``), so the
measure is the same on every machine with no Arial installed. A glyph those
metrics lack (outside Latin-1 and the Adobe standard set: ≥, →, Δ) is measured
in DejaVu Sans, matplotlib's bundled font. Kerning is ignored.

A finding's key is ``KIND | picture | text``: the picture is its whole alt
text (bindings resolved), with `` (picture N)``, its 1-based place among the
sheet's pictures, appended when two pictures on the sheet share that alt.

``prechips_traveler.py`` runs :func:`check` on the hobby sheet it has just
rendered and fails the render (exit 2) on a finding that
``cad/config/picture-clip-baseline.toml`` does not list, or on a listed one
that no longer occurs (remove it from the baseline: the list only shrinks).
Keys count: two identical findings in one picture need two entries.

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
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import ImageFont

BASELINE = Path(__file__).resolve().parents[1] / "config" / "picture-clip-baseline.toml"
_SVG = "{http://www.w3.org/2000/svg}"
_IMG = re.compile(r"<img\b[^>]*>")
_DATA = re.compile(r'src="data:image/svg\+xml;base64,([^"]+)"')
_ALT = re.compile(r'alt="([^"]*)"')
# prechips' own legend picture, not a plan picture.
_KEY_ALT = "Picture key"
_SKIPPED = {
    "defs",
    "symbol",
    "clipPath",
    "mask",
    "pattern",
    "marker",
    "title",
    "desc",
    "style",
}
# Chords per Bézier curve or elliptical arc of a leader path.
_CURVE_STEPS = 16
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_NO_EXTENT = "(no viewBox, width or height: the picture's extent is unknown)"


@dataclass(frozen=True)
class Finding:
    kind: str  # CLIP, TEXT or LEADER
    picture: str  # the picture's alt text, " (picture N)" when the sheet repeats it
    text: str  # the text clipped or crossed; "a / b" for two overlapping
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
    import matplotlib

    name = "Helvetica-Bold.afm" if bold else "Helvetica.afm"
    path = Path(matplotlib.get_data_path()) / "fonts" / "pdfcorefonts" / name
    widths = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        if line.startswith("C "):
            fields = dict(
                part.strip().split(" ", 1) for part in line.split(";") if part.strip()
            )
            widths[fields["N"]] = float(fields["WX"])
    return widths


@cache
def _fallback(bold: bool) -> ImageFont.FreeTypeFont:
    import matplotlib
    from PIL import ImageFont

    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(
        str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name), 1000
    )


def text_width(text: str, size: float, bold: bool = False) -> float:
    """The advance width of ``text`` in Arial at ``size`` px."""
    from fontTools.agl import UV2AGL

    widths = _afm(bold)
    total = 0.0
    for char in text:
        glyph = UV2AGL.get(ord(char))
        total += widths[glyph] if glyph in widths else _fallback(bold).getlength(char)
    return total * size / 1000


def _property(element: ET.Element, name: str) -> str | None:
    """A presentation property, from ``style=`` before the attribute."""
    style = re.search(rf"(?:^|;)\s*{name}\s*:\s*([^;]+)", element.get("style", ""))
    value = style.group(1) if style else element.get(name)
    return value.strip() if value is not None else None


def _size(element: ET.Element, default: float) -> float:
    number = re.match(r"([\d.]+)", _property(element, "font-size") or "")
    return float(number.group(1)) if number else default


def _bold(element: ET.Element, inherited: bool) -> bool:
    weight = _property(element, "font-weight")
    if weight is None:
        return inherited
    return weight in {"bold", "bolder"} or (weight.isdigit() and int(weight) >= 600)


def _anchor(element: ET.Element, inherited: str) -> str:
    anchor = _property(element, "text-anchor")
    return anchor if anchor in {"start", "middle", "end"} else inherited


_Matrix = tuple[float, float, float, float, float, float]  # SVG (a b c d e f)
_IDENTITY: _Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_TRANSFORM = re.compile(r"(matrix|translate|scale|rotate)\s*\(([^)]*)\)")


def _multiply(m: _Matrix, n: _Matrix) -> _Matrix:
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + c * b2,
        b * a2 + d * b2,
        a * c2 + c * d2,
        b * c2 + d * d2,
        a * e2 + c * f2 + e,
        b * e2 + d * f2 + f,
    )


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
            m = _multiply(
                _multiply(
                    (1.0, 0.0, 0.0, 1.0, cx, cy),
                    (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0.0, 0.0),
                ),
                (1.0, 0.0, 0.0, 1.0, -cx, -cy),
            )
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


def _numbers(value: str) -> list[float]:
    return [float(v) for v in _NUMBER.findall(value or "")]


def _first(value: str | None) -> float | None:
    """The first of an x/y/dx/dy attribute's list of lengths, or None."""
    numbers = _numbers(value or "")
    return numbers[0] if numbers else None


def _arc(start, rx, ry, phi, large, sweep, end) -> list[tuple[float, float]]:
    """An elliptical arc's points after ``start``, by the SVG endpoint-to-centre
    conversion (SVG 1.1 F.6.5), sampled at :data:`_CURVE_STEPS` chords."""
    (x1, y1), (x2, y2) = start, end
    rx, ry = abs(rx), abs(ry)
    if (x1, y1) == (x2, y2):
        return []
    if rx == 0 or ry == 0:
        return [end]
    cos, sin = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    hx, hy = (x1 - x2) / 2, (y1 - y2) / 2
    xp, yp = cos * hx + sin * hy, -sin * hx + cos * hy
    scale = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    numerator = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    denominator = rx * rx * yp * yp + ry * ry * xp * xp
    root = math.sqrt(max(0.0, numerator / denominator))
    if large == sweep:
        root = -root
    cxp, cyp = root * rx * yp / ry, -root * ry * xp / rx
    cx, cy = (
        cos * cxp - sin * cyp + (x1 + x2) / 2,
        sin * cxp + cos * cyp + (y1 + y2) / 2,
    )
    theta = math.atan2((yp - cyp) / ry, (xp - cxp) / rx)
    delta = math.atan2((-yp - cyp) / ry, (-xp - cxp) / rx) - theta
    if sweep and delta < 0:
        delta += 2 * math.pi
    elif not sweep and delta > 0:
        delta -= 2 * math.pi
    points = []
    for i in range(1, _CURVE_STEPS + 1):
        t = theta + delta * i / _CURVE_STEPS
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        points.append((cos * ex - sin * ey + cx, sin * ex + cos * ey + cy))
    points[-1] = end
    return points


def _bezier(*controls: tuple[float, float]) -> list[tuple[float, float]]:
    """A quadratic or cubic Bézier's points after its start, at :data:`_CURVE_STEPS` chords."""
    points = []
    for i in range(1, _CURVE_STEPS + 1):
        t = i / _CURVE_STEPS
        level = list(controls)
        while len(level) > 1:
            level = [
                (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                for a, b in zip(level, level[1:], strict=False)
            ]
        points.append(level[0])
    return points


def _path(d: str) -> list[list[tuple[float, float]]]:
    """A path's subpaths as polylines: lines exact, curves and arcs flattened."""
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|" + _NUMBER.pattern, d or "")
    subpaths: list[list[tuple[float, float]]] = []
    current = start = (0.0, 0.0)
    control = None  # the last curve's reflected control point, for S and T
    command, last = "", ""
    i = 0

    def take(count: int) -> list[float] | None:
        nonlocal i
        if i + count > len(tokens) or any(t.isalpha() for t in tokens[i : i + count]):
            return None
        values = [float(t) for t in tokens[i : i + count]]
        i += count
        return values

    def arc_args() -> list[float] | None:
        # The flags may run into the next number ("a5 5 0 01 10 10").
        nonlocal i
        values = take(3)
        if values is None:
            return None
        flags = []
        while len(flags) < 2 and i < len(tokens) and not tokens[i].isalpha():
            digits = tokens[i].lstrip("+")
            flags.append(float(digits[0]))
            rest = digits[1:]
            if rest:
                tokens[i] = rest
            else:
                i += 1
        end = take(2)
        return None if len(flags) < 2 or end is None else [*values, *flags, *end]

    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        elif not command:
            break
        upper, relative = command.upper(), command.islower()
        ox, oy = current if relative else (0.0, 0.0)
        if upper == "Z":
            if subpaths and subpaths[-1][-1] != start:
                subpaths[-1].append(start)
            current, control, last = start, None, "Z"
            command = ""
            continue
        count = {
            "M": 2,
            "L": 2,
            "H": 1,
            "V": 1,
            "C": 6,
            "S": 4,
            "Q": 4,
            "T": 2,
            "A": 7,
        }[upper]
        args = arc_args() if upper == "A" else take(count)
        if args is None:
            break
        new_control = None
        if upper == "M":
            current = start = (ox + args[0], oy + args[1])
            subpaths.append([current])
            command = "l" if relative else "L"
            last = "M"
            continue
        if not subpaths:
            subpaths.append([current])
        if upper == "L":
            points = [(ox + args[0], oy + args[1])]
        elif upper == "H":
            points = [((ox if relative else 0.0) + args[0], current[1])]
        elif upper == "V":
            points = [(current[0], (oy if relative else 0.0) + args[0])]
        elif upper in {"C", "S"}:
            if upper == "C":
                c1 = (ox + args[0], oy + args[1])
                rest = args[2:]
            else:
                c1 = control if control and last in {"C", "S"} else current
                rest = args
            c2, end = (ox + rest[0], oy + rest[1]), (ox + rest[2], oy + rest[3])
            points = _bezier(current, c1, c2, end)
            new_control = (2 * end[0] - c2[0], 2 * end[1] - c2[1])
        elif upper in {"Q", "T"}:
            if upper == "Q":
                c1 = (ox + args[0], oy + args[1])
                end = (ox + args[2], oy + args[3])
            else:
                c1 = control if control and last in {"Q", "T"} else current
                end = (ox + args[0], oy + args[1])
            points = _bezier(current, c1, end)
            new_control = (2 * end[0] - c1[0], 2 * end[1] - c1[1])
        else:
            end = (ox + args[5], oy + args[6])
            points = _arc(
                current, args[0], args[1], args[2], bool(args[3]), bool(args[4]), end
            )
            points = points or [end]
        subpaths[-1].extend(points)
        current, control, last = points[-1], new_control, upper
    return subpaths


def _leader_polylines(tag: str, element: ET.Element) -> list[list[tuple[float, float]]]:
    """A leader element's polylines in its own coordinates."""
    if tag == "line":
        return [
            [
                (float(element.get("x1", 0)), float(element.get("y1", 0))),
                (float(element.get("x2", 0)), float(element.get("y2", 0))),
            ]
        ]
    if tag in {"polyline", "polygon"}:
        values = _numbers(element.get("points", ""))
        points = list(zip(values[0::2], values[1::2], strict=False))
        if tag == "polygon" and len(points) > 2:
            points.append(points[0])
        return [points]
    if tag == "path":
        return _path(element.get("d", ""))
    return []


def _text_boxes(element: ET.Element, m: _Matrix, size: float, bold: bool, anchor: str):
    """A <text>'s boxes (x0, y0, x1, y1, text): one per run and line. A run
    starts where a <text> or <tspan> gives its own x or y; text-anchor shifts the
    whole run; dx/dy move within it."""
    runs: list[dict] = []
    position = [0.0, 0.0]

    def piece(text: str | None, size: float, bold: bool) -> None:
        run = runs[-1]
        text = re.sub(r"\s+", " ", text or "")
        if not run["pieces"]:
            text = text.lstrip()
        if not text:
            return
        width = text_width(text, size, bold)
        run["pieces"].append((run["advance"], width, position[1], size, text))
        run["advance"] += width
        position[0] += width

    def visit(
        node: ET.Element, size: float, bold: bool, anchor: str, first: bool
    ) -> None:
        size, bold, anchor = _size(node, size), _bold(node, bold), _anchor(node, anchor)
        x, y = _first(node.get("x")), _first(node.get("y"))
        if first or x is not None or y is not None:
            position[:] = [
                x if x is not None else position[0],
                y if y is not None else position[1],
            ]
            runs.append(
                {"x": position[0], "anchor": anchor, "advance": 0.0, "pieces": []}
            )
        dx, dy = _first(node.get("dx")) or 0.0, _first(node.get("dy")) or 0.0
        position[0] += dx
        position[1] += dy
        runs[-1]["advance"] += dx
        piece(node.text, size, bold)
        for child in node:
            if child.tag.removeprefix(_SVG) == "tspan":
                visit(child, size, bold, anchor, False)
            piece(child.tail, size, bold)

    visit(element, size, bold, anchor, True)
    boxes = []
    for run in runs:
        shift = {"end": -run["advance"], "middle": -run["advance"] / 2}.get(
            run["anchor"], 0.0
        )
        lines: dict[float, list] = {}
        for offset, width, y, size, text in run["pieces"]:
            lines.setdefault(round(y, 3), []).append((offset, width, size, text))
        for y, pieces in lines.items():
            string = "".join(p[3] for p in pieces).strip()
            if not string:
                continue
            x0 = run["x"] + shift + min(p[0] for p in pieces)
            x1 = run["x"] + shift + max(p[0] + p[1] for p in pieces)
            size = max(p[2] for p in pieces)
            # Cap height above the baseline, descenders below; 1 px of side
            # bearing each side.
            corners = [
                _apply(m, px, py)
                for px in (x0 + 1, x1 - 1)
                for py in (y - 0.72 * size, y + 0.2 * size)
            ]
            xs, ys = [p[0] for p in corners], [p[1] for p in corners]
            boxes.append((min(xs), min(ys), max(xs), max(ys), string))
    return boxes


def _walk(root: ET.Element):
    """The picture's text boxes (x0, y0, x1, y1, text) and leader segments, in
    the root's coordinates: every transform, nested <svg> placement, inherited
    font size, weight, text-anchor and class applied. Identical boxes (a halo
    under its text) count once."""
    boxes: dict[tuple, tuple] = {}
    leaders = []

    def visit(
        element,
        m: _Matrix,
        size: float,
        bold: bool,
        anchor: str,
        leader: bool,
        top: bool,
    ) -> None:
        tag = element.tag.removeprefix(_SVG)
        if tag in _SKIPPED:
            return
        if tag == "svg" and not top:
            m = _multiply(m, _nested(element))
        m = _multiply(m, _transform(element.get("transform", "")))
        leader = leader or "leader" in (element.get("class") or "").split()
        if tag == "text":
            for box in _text_boxes(element, m, size, bold, anchor):
                boxes[(round(box[0], 1), round(box[1], 1), box[4])] = box
            return
        size, bold, anchor = (
            _size(element, size),
            _bold(element, bold),
            _anchor(element, anchor),
        )
        if leader:
            for points in _leader_polylines(tag, element):
                placed = [_apply(m, x, y) for x, y in points]
                leaders.extend(
                    (*p, *q) for p, q in zip(placed, placed[1:], strict=False) if p != q
                )
        for child in element:
            visit(child, m, size, bold, anchor, leader, False)

    visit(root, _IDENTITY, 13.0, False, "start", False, True)
    return list(boxes.values()), leaders


def _crosses(x1: float, y1: float, x2: float, y2: float, box) -> bool:
    """Whether the segment passes through the box's interior (Liang–Barsky): a
    segment only touching its edge or corner does not cross it."""
    bx0, by0, bx1, by1 = box[:4]
    t0, t1 = 0.0, 1.0
    dx, dy = x2 - x1, y2 - y1
    for p, q in ((-dx, x1 - bx0), (dx, bx1 - x1), (-dy, y1 - by0), (dy, by1 - y1)):
        if p == 0:
            if q <= 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    # The open box meets the segment in an open stretch around this midpoint.
    t = (t0 + t1) / 2
    x, y = x1 + dx * t, y1 + dy * t
    return bx0 < x < bx1 and by0 < y < by1


def _extent(root: ET.Element) -> tuple[float, float, float, float] | None:
    """The picture's viewBox, or (0, 0, width, height) without one; None when
    it has neither."""
    box = _numbers(root.get("viewBox", ""))
    if len(box) == 4:
        return box[0], box[1], box[2], box[3]
    width, height = (
        re.fullmatch(r"\s*([\d.]+)\s*(px)?\s*", root.get(a, ""))
        for a in ("width", "height")
    )
    if width and height:
        return 0.0, 0.0, float(width.group(1)), float(height.group(1))
    return None


def svg_findings(svg: str, picture: str) -> list[Finding]:
    """The clip and collision findings of one picture's SVG."""
    root = ET.fromstring(svg)
    boxes, leaders = _walk(root)
    extent = _extent(root)
    if extent is None:
        found = [Finding("CLIP", picture, _NO_EXTENT)]
    else:
        vx, vy, vw, vh = extent
        found = [
            Finding(
                "CLIP",
                picture,
                b[4],
                f"x {b[0]:.0f}..{b[2]:.0f} y {b[1]:.0f}..{b[3]:.0f} in {vx:g} {vy:g} {vw:g} {vh:g}",
            )
            for b in boxes
            if b[0] < vx - 1
            or b[2] > vx + vw + 1
            or b[1] < vy - 1
            or b[3] > vy + vh + 1
        ]
    for i, a in enumerate(boxes):
        found += [
            Finding("TEXT", picture, f"{a[4]} / {b[4]}")
            for b in boxes[i + 1 :]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
        ]
    for x1, y1, x2, y2 in leaders:
        found += [
            Finding(
                "LEADER", picture, b[4], f"({x1:.0f},{y1:.0f})->({x2:.0f},{y2:.0f})"
            )
            for b in boxes
            if _crosses(x1, y1, x2, y2, b)
        ]
    return found


def pictures(sheet: Path) -> list[tuple[str, str]]:
    """The plan pictures of a rendered traveler as (name, svg), in sheet order:
    the name is the alt text, `` (picture N)`` appended when the sheet repeats it."""
    found = []
    for tag in _IMG.findall(Path(sheet).read_text(encoding="utf-8")):
        data = _DATA.search(tag)
        if not data:
            continue
        alt = _ALT.search(tag)
        alt = html.unescape(alt.group(1)) if alt else ""
        if alt.startswith(_KEY_ALT):
            continue
        found.append((alt, base64.b64decode(data.group(1)).decode("utf-8")))
    repeated = Counter(alt for alt, _svg in found)
    return [
        (f"{alt} (picture {index})" if repeated[alt] > 1 else alt, svg)
        for index, (alt, svg) in enumerate(found, 1)
    ]


def findings(sheet: Path) -> list[Finding]:
    """Every finding on the plan pictures of a rendered traveler, or of one .svg."""
    sheet = Path(sheet)
    if sheet.suffix == ".svg":
        return svg_findings(sheet.read_text(encoding="utf-8"), sheet.name)
    return [
        finding for name, svg in pictures(sheet) for finding in svg_findings(svg, name)
    ]


def baseline(stem: str, path: Path | None = None) -> Counter[str]:
    """The findings ``stem``'s pictures are known to carry (their keys, each
    as often as listed), from ``path`` or :data:`BASELINE`."""
    with (path or BASELINE).open("rb") as handle:
        plans = tomllib.load(handle).get("plans", {})
    return Counter(plans.get(stem, {}).get("findings", []))


def check(stem: str, sheet: Path, path: Path | None = None) -> list[str]:
    """What fails ``stem``'s render: each finding beyond the times the baseline
    lists its key, and each listed key beyond the times it occurs. Empty when
    it passes."""
    found = findings(sheet)
    allowed = baseline(stem, path)
    new = []
    for finding in found:
        if allowed[finding.key] > 0:
            allowed[finding.key] -= 1
        else:
            new.append(f"new: {finding}")
    return new + [
        f"fixed, so remove it from {(path or BASELINE).name}: {key}"
        for key in sorted(allowed.elements())
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
