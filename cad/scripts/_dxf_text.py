r"""Text -> closed polygons -> minimal DXF, for engraving numerals at build time.

SolidWorks-free. The COM adapter has no sketch-text API, so engraved lettering
follows the nameplate precedent: a vendored DXF of CLOSED loops that
``adapter.import_dxf_dwg`` inserts as one sketch and a cut-extrude engraves as
one feature (``build_nameplate`` / ``cad/references/nameplate-engraving.dxf``).
The nameplate's DXF was traced off a photo; a ruled scale's numerals are plain
type, so this module renders them from a font instead:

* :func:`glyph_polylines` -- a string to a list of closed rings (outer contours
  AND counters, e.g. the hole of a "0") via ``matplotlib.textpath.TextPath`` on
  matplotlib's own bundled DejaVu Sans (pinned by file, not by family name, so
  the output is identical on every seat). Bezier segments are flattened here
  with a FIXED subdivision count rather than ``Path.to_polygons`` (whose density
  varies with the path size), so the rings are deterministic and dense enough
  (~40 points on a "0") to read as curves at a 2 mm engraving.
* :func:`render_dxf` / :func:`write_dxf` -- the rings as a hand-written minimal
  R2000 (AC1015) DXF: millimetre units (``$INSUNITS = 4``), one closed
  ``LWPOLYLINE`` (flag 70 = 1) per ring in modelspace, mirroring the entity
  shape of the vendored nameplate DXF. Written by hand because ``ezdxf`` is not
  a dependency and the file is a few hundred lines. No timestamps, fixed
  ``.6f`` coordinates: the same rings render the same bytes, so the generated
  file can be tracked and its regeneration byte-compared in a test.

Nested rings cut as islands: a cut-extrude of a sketch region whose outer loop
contains an inner loop removes the ring between them, which is exactly how the
nameplate's closed-ribbon letters with counters engrave.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath

Point = tuple[float, float]
Ring = list[Point]

# matplotlib's bundled DejaVu Sans -- the same bytes wherever matplotlib is
# installed at the locked version, unlike a family-name lookup that may resolve
# to a system font.
DEJAVU_SANS = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"

# Segments per Bezier curve when flattening. Fixed, so output is deterministic.
_CURVE_STEPS = 8
# Consecutive points closer than this (mm) collapse to one: a near-zero-length
# LWPOLYLINE segment can defeat SolidWorks' endpoint merge on import (the
# build imports with merge_distance 0.002 mm; 5x that keeps every segment
# unambiguously a segment, and is still ~1/200 of a 2 mm glyph).
_MIN_SEGMENT_MM = 0.01
# The digit whose ink height defines "height_mm": flat top and bottom, so the
# round digits keep their normal ~2% optical overshoot instead of being shrunk.
_HEIGHT_REFERENCE_GLYPH = "1"


def _font(font: Path) -> FontProperties:
    return FontProperties(fname=str(font))


def _flatten_path(path: MplPath) -> list[Ring]:
    """Flatten a matplotlib Path into closed rings (curves subdivided)."""
    rings: list[Ring] = []
    current: Ring = []
    verts = path.vertices
    codes = path.codes
    if codes is None:
        raise ValueError("glyph path without codes")
    i = 0
    n = len(codes)
    while i < n:
        code = codes[i]
        if code == MplPath.MOVETO:
            if current:
                rings.append(current)
            current = [tuple(map(float, verts[i]))]
            i += 1
            continue
        if code == MplPath.LINETO:
            current.append(tuple(map(float, verts[i])))
            i += 1
            continue
        if code == MplPath.CURVE3:
            p0 = current[-1]
            c, p1 = verts[i], verts[i + 1]
            for s in range(1, _CURVE_STEPS + 1):
                t = s / _CURVE_STEPS
                u = 1.0 - t
                x = u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0]
                y = u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1]
                current.append((float(x), float(y)))
            i += 2
            continue
        if code == MplPath.CURVE4:
            p0 = current[-1]
            c1, c2, p1 = verts[i], verts[i + 1], verts[i + 2]
            for s in range(1, _CURVE_STEPS + 1):
                t = s / _CURVE_STEPS
                u = 1.0 - t
                x = u**3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * p1[0]
                y = u**3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * p1[1]
                current.append((float(x), float(y)))
            i += 3
            continue
        if code == MplPath.CLOSEPOLY:
            if current:
                rings.append(current)
            current = []
            i += 1
            continue
        raise ValueError(f"unexpected path code {code}")
    if current:
        rings.append(current)
    return [r for r in rings if len(r) >= 3]


def _dedupe(ring: Ring, min_segment: float) -> Ring:
    """Drop the closing duplicate and any point within ``min_segment`` of its
    predecessor (the closed flag on the LWPOLYLINE supplies the closing edge)."""
    out: Ring = []
    for p in ring:
        if out and math.dist(out[-1], p) < min_segment:
            continue
        out.append(p)
    while len(out) > 1 and math.dist(out[0], out[-1]) < min_segment:
        out.pop()
    return out


def _raw_rings(text: str, font: Path) -> list[Ring]:
    return _flatten_path(TextPath((0.0, 0.0), text, size=1.0, prop=_font(font)))


def digit_height_em(font: Path = DEJAVU_SANS) -> float:
    """Ink height of the reference digit at size 1 (em units)."""
    rings = _raw_rings(_HEIGHT_REFERENCE_GLYPH, font)
    ys = [y for ring in rings for _, y in ring]
    return max(ys) - min(ys)


def glyph_polylines(text: str, height_mm: float, font: Path = DEJAVU_SANS) -> list[Ring]:
    """Closed rings (outer contours and counters) of ``text`` in millimetres.

    Text frame: x runs along the baseline (advance direction), y up; the
    baseline sits at y = 0 and the first glyph's origin at x = 0 (its left ink
    edge is at the font's left side bearing, not at 0 -- callers normalise by
    :func:`bbox`). Scaled so the reference digit ("1") is ``height_mm`` tall;
    round digits overshoot by the font's ~2 % optical correction.
    """
    scale = height_mm / digit_height_em(font)
    rings = []
    for ring in _raw_rings(text, font):
        scaled = [(x * scale, y * scale) for x, y in ring]
        scaled = _dedupe(scaled, _MIN_SEGMENT_MM)
        if len(scaled) >= 3:
            rings.append(scaled)
    return rings


def bbox(rings: list[Ring]) -> tuple[float, float, float, float]:
    xs = [x for ring in rings for x, _ in ring]
    ys = [y for ring in rings for _, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


def signed_area(ring: Ring) -> float:
    """Shoelace area (positive = counter-clockwise)."""
    total = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        total += x0 * y1 - x1 * y0
    return 0.5 * total


def point_in_ring(ring: Ring, point: Point) -> bool:
    """Even-odd ray cast."""
    x, y = point
    inside = False
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            x_cross = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < x_cross:
                inside = not inside
    return inside


def nesting_depth(rings: list[Ring], index: int) -> int:
    """Number of OTHER rings enclosing ring ``index`` (0 = outer contour)."""
    probe = rings[index][0]
    return sum(
        1 for j, other in enumerate(rings) if j != index and point_in_ring(other, probe)
    )


def net_area(rings: list[Ring]) -> float:
    """Filled area: outer contours minus counters (odd nesting depth)."""
    total = 0.0
    for i, ring in enumerate(rings):
        sign = -1.0 if nesting_depth(rings, i) % 2 else 1.0
        total += sign * abs(signed_area(ring))
    return total


# --- DXF writer ---------------------------------------------------------------

_MODEL_SPACE_HANDLE = 0x1F  # *Model_Space BLOCK_RECORD; entities cite it as owner
_FIRST_ENTITY_HANDLE = 0x30  # above every fixed skeleton handle (max 0x21)


def _fmt(value: float) -> str:
    text = f"{value:.6f}"
    return "0.000000" if text == "-0.000000" else text


def _group(code: int, value: object) -> list[str]:
    return [f"{code:3d}", str(value)]


def _skeleton_tables() -> list[str]:
    g = _group
    lines: list[str] = []
    # VPORT / VIEW / UCS -- empty tables (readers expect the table to exist).
    for name, handle in (("VPORT", "8"), ("VIEW", "6"), ("UCS", "7")):
        lines += g(0, "TABLE") + g(2, name) + g(5, handle) + g(330, "0")
        lines += g(100, "AcDbSymbolTable") + g(70, 0) + g(0, "ENDTAB")
    # LTYPE: the three mandatory line types.
    lines += g(0, "TABLE") + g(2, "LTYPE") + g(5, "5") + g(330, "0")
    lines += g(100, "AcDbSymbolTable") + g(70, 3)
    for handle, name in (("14", "ByBlock"), ("15", "ByLayer"), ("16", "Continuous")):
        lines += g(0, "LTYPE") + g(5, handle) + g(330, "5")
        lines += g(100, "AcDbSymbolTableRecord") + g(100, "AcDbLinetypeTableRecord")
        lines += g(2, name) + g(70, 0) + g(3, "") + g(72, 65) + g(73, 0) + g(40, "0.0")
    lines += g(0, "ENDTAB")
    # LAYER 0.
    lines += g(0, "TABLE") + g(2, "LAYER") + g(5, "2") + g(330, "0")
    lines += g(100, "AcDbSymbolTable") + g(70, 1)
    lines += g(0, "LAYER") + g(5, "10") + g(330, "2")
    lines += g(100, "AcDbSymbolTableRecord") + g(100, "AcDbLayerTableRecord")
    lines += g(2, "0") + g(70, 0) + g(62, 7) + g(6, "Continuous") + g(370, -3) + g(390, "F")
    lines += g(0, "ENDTAB")
    # STYLE Standard.
    lines += g(0, "TABLE") + g(2, "STYLE") + g(5, "3") + g(330, "0")
    lines += g(100, "AcDbSymbolTable") + g(70, 1)
    lines += g(0, "STYLE") + g(5, "11") + g(330, "3")
    lines += g(100, "AcDbSymbolTableRecord") + g(100, "AcDbTextStyleTableRecord")
    lines += g(2, "Standard") + g(70, 0) + g(40, "0.0") + g(41, "1.0") + g(50, "0.0")
    lines += g(71, 0) + g(42, "2.5") + g(3, "txt") + g(4, "")
    lines += g(0, "ENDTAB")
    # APPID ACAD.
    lines += g(0, "TABLE") + g(2, "APPID") + g(5, "9") + g(330, "0")
    lines += g(100, "AcDbSymbolTable") + g(70, 1)
    lines += g(0, "APPID") + g(5, "12") + g(330, "9")
    lines += g(100, "AcDbSymbolTableRecord") + g(100, "AcDbRegAppTableRecord")
    lines += g(2, "ACAD") + g(70, 0)
    lines += g(0, "ENDTAB")
    # DIMSTYLE -- empty.
    lines += g(0, "TABLE") + g(2, "DIMSTYLE") + g(5, "A") + g(330, "0")
    lines += g(100, "AcDbSymbolTable") + g(70, 0) + g(100, "AcDbDimStyleTable") + g(71, 0)
    lines += g(0, "ENDTAB")
    # BLOCK_RECORD: modelspace + paperspace.
    lines += g(0, "TABLE") + g(2, "BLOCK_RECORD") + g(5, "1") + g(330, "0")
    lines += g(100, "AcDbSymbolTable") + g(70, 2)
    for handle, name in ((f"{_MODEL_SPACE_HANDLE:X}", "*Model_Space"), ("1B", "*Paper_Space")):
        lines += g(0, "BLOCK_RECORD") + g(5, handle) + g(330, "1")
        lines += g(100, "AcDbSymbolTableRecord") + g(100, "AcDbBlockTableRecord")
        lines += g(2, name) + g(340, "0")
    lines += g(0, "ENDTAB")
    return lines


def _skeleton_blocks() -> list[str]:
    g = _group
    lines: list[str] = []
    for begin, end, owner, name, paper in (
        ("20", "21", f"{_MODEL_SPACE_HANDLE:X}", "*Model_Space", False),
        ("1C", "1D", "1B", "*Paper_Space", True),
    ):
        lines += g(0, "BLOCK") + g(5, begin) + g(330, owner) + g(100, "AcDbEntity") + g(8, "0")
        if paper:
            lines += g(67, 1)
        lines += g(100, "AcDbBlockBegin") + g(2, name) + g(70, 0)
        lines += g(10, "0.0") + g(20, "0.0") + g(30, "0.0") + g(3, name) + g(1, "")
        lines += g(0, "ENDBLK") + g(5, end) + g(330, owner) + g(100, "AcDbEntity") + g(8, "0")
        if paper:
            lines += g(67, 1)
        lines += g(100, "AcDbBlockEnd")
    return lines


def _lwpolyline(handle: int, ring: Ring) -> list[str]:
    g = _group
    lines = g(0, "LWPOLYLINE") + g(5, f"{handle:X}") + g(330, f"{_MODEL_SPACE_HANDLE:X}")
    lines += g(100, "AcDbEntity") + g(8, "0") + g(100, "AcDbPolyline")
    lines += g(90, len(ring)) + g(70, 1)  # 1 = closed
    for x, y in ring:
        lines += g(10, _fmt(x)) + g(20, _fmt(y))
    return lines


def render_dxf(rings: list[Ring]) -> str:
    """The rings as a minimal millimetre-unit R2000 DXF (text, LF newlines)."""
    if not rings:
        raise ValueError("render_dxf: no rings")
    g = _group
    x0, y0, x1, y1 = bbox(rings)
    handseed = _FIRST_ENTITY_HANDLE + len(rings) + 1
    lines: list[str] = []
    lines += g(0, "SECTION") + g(2, "HEADER")
    lines += g(9, "$ACADVER") + g(1, "AC1015")
    lines += g(9, "$HANDSEED") + g(5, f"{handseed:X}")
    lines += g(9, "$INSUNITS") + g(70, 4)  # 4 = millimetres
    lines += g(9, "$MEASUREMENT") + g(70, 1)  # metric
    lines += g(9, "$INSBASE") + g(10, "0.0") + g(20, "0.0") + g(30, "0.0")
    lines += g(9, "$EXTMIN") + g(10, _fmt(x0)) + g(20, _fmt(y0)) + g(30, "0.0")
    lines += g(9, "$EXTMAX") + g(10, _fmt(x1)) + g(20, _fmt(y1)) + g(30, "0.0")
    lines += g(0, "ENDSEC")
    lines += g(0, "SECTION") + g(2, "CLASSES") + g(0, "ENDSEC")
    lines += g(0, "SECTION") + g(2, "TABLES") + _skeleton_tables() + g(0, "ENDSEC")
    lines += g(0, "SECTION") + g(2, "BLOCKS") + _skeleton_blocks() + g(0, "ENDSEC")
    lines += g(0, "SECTION") + g(2, "ENTITIES")
    for i, ring in enumerate(rings):
        lines += _lwpolyline(_FIRST_ENTITY_HANDLE + i, ring)
    lines += g(0, "ENDSEC")
    lines += g(0, "SECTION") + g(2, "OBJECTS")
    lines += g(0, "DICTIONARY") + g(5, "C") + g(330, "0") + g(100, "AcDbDictionary")
    lines += g(281, 1) + g(3, "ACAD_GROUP") + g(350, "D")
    lines += g(0, "DICTIONARY") + g(5, "D") + g(330, "C") + g(100, "AcDbDictionary")
    lines += g(281, 1)
    lines += g(0, "ENDSEC")
    lines += g(0, "EOF")
    return "\n".join(lines) + "\n"


def write_dxf(path: Path, rings: list[Ring]) -> bytes:
    """Write :func:`render_dxf` to ``path`` as LF bytes; returns the bytes.

    Bytes, not text mode, so the platform newline never leaks in (git's
    autocrlf may still check the tracked file out with CRLF -- compare with
    :func:`normalize_newlines`).
    """
    data = render_dxf(rings).encode("ascii")
    path.write_bytes(data)
    return data


def normalize_newlines(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def read_lwpolylines(text: str) -> list[tuple[Ring, bool]]:
    """Minimal DXF reader: every LWPOLYLINE's vertices + closed flag.

    Enough to round-trip :func:`render_dxf` and the vendored nameplate DXF (a
    flat list of LWPOLYLINEs); not a general DXF parser.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    pairs = [
        (lines[i].strip(), lines[i + 1].strip())
        for i in range(0, len(lines) - 1, 2)
    ]
    entities: list[tuple[Ring, bool]] = []
    i = 0
    while i < len(pairs):
        code, value = pairs[i]
        if code == "0" and value == "LWPOLYLINE":
            ring: Ring = []
            closed = False
            x: float | None = None
            i += 1
            while i < len(pairs) and pairs[i][0] != "0":
                c, v = pairs[i]
                if c == "70":
                    closed = bool(int(v) & 1)
                if c == "10":
                    x = float(v)
                if c == "20" and x is not None:
                    ring.append((x, float(v)))
                    x = None
                i += 1
            entities.append((ring, closed))
            continue
        i += 1
    return entities


def header_int(text: str, variable: str) -> int | None:
    """Value of an integer header variable (``$INSUNITS`` -> 4), or None."""
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        if line.strip() == f"${variable}" and i + 2 < len(lines):
            return int(lines[i + 2].strip())
    return None
