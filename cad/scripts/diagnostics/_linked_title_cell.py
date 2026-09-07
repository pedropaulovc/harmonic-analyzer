"""Diagnostic-only title-cell measurement; no selection, setters or font changes.

Native ISheet.GetTemplateSketch supplies the sheet-format line geometry. Curves,
text and construction entities are inventoried, not treated as rectangular rules.
The 1 nm topology bound joins native rule endpoints only; it is never a title
placement, printed-fit or cold-reopen acceptance tolerance.
"""

from __future__ import annotations

import math

from _common import _early_bound

TOPOLOGY_M = 1e-9


def finite(values, length, label):
    result = tuple(float(value) for value in values or ())
    if len(result) != length or not all(math.isfinite(value) for value in result):
        raise RuntimeError(f"{label}: invalid native coordinates {result!r}")
    return result


def required(value, interface):
    if value is None:
        raise RuntimeError(f"title cell: native {interface} is missing")
    return _early_bound(value, interface)


def template_lines(adapter):
    """Read raw sketch and sheet endpoints with documented native math transforms."""
    import pythoncom
    from win32com.client import VARIANT

    ddoc = required(adapter.currentModel, "IDrawingDoc")
    sheet = required(ddoc.GetCurrentSheet(), "ISheet")
    sketch = required(sheet.GetTemplateSketch(), "ISketch")
    transform = required(sketch.ModelToSketchTransform, "IMathTransform")
    inverse = required(transform.Inverse(), "IMathTransform")
    utility = required(adapter.swApp.GetMathUtility(), "IMathUtility")
    segments = tuple(sketch.GetSketchSegments() or ())
    if not segments or len(segments) > 2000:
        raise RuntimeError(
            "title cell: empty or unsupported template segment inventory"
        )
    receipt = {
        "model_to_sketch": finite(transform.ArrayData, 16, "template transform"),
        "sketch_to_model": finite(inverse.ArrayData, 16, "inverse template transform"),
        "segments": [],
    }
    lines, identities = [], set()
    for raw in segments:
        segment = required(raw, "ISketchSegment")
        kind, identity = int(segment.GetType()), tuple(segment.GetID() or ())
        if (
            kind not in range(6)
            or len(identity) != 2
            or any(type(i) is not int for i in identity)
        ):
            raise RuntimeError("title cell: unsupported native segment type/identity")
        key = (kind, *identity)
        if key in identities:
            raise RuntimeError("title cell: duplicated native segment identity")
        identities.add(key)
        role = "construction" if segment.ConstructionGeometry else "drawing"
        row = {"kind": kind, "id": identity, "role": role}
        receipt["segments"].append(row)
        if kind != 0 or role == "construction":
            row["cell_boundary"] = "excluded_non_rule"
            continue
        line = required(segment, "ISketchLine")
        sketch_points, sheet_points = [], []
        for endpoint in (line.GetStartPoint2(), line.GetEndPoint2()):
            point = required(endpoint, "ISketchPoint")
            xyz = finite((point.X, point.Y, point.Z), 3, "template sketch endpoint")
            native = required(
                utility.CreatePoint(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, xyz)),
                "IMathPoint",
            )
            moved = required(native.MultiplyTransform(inverse), "IMathPoint")
            sketch_points.append(xyz)
            sheet_points.append(finite(moved.ArrayData, 3, "template sheet endpoint"))
        row.update(sketch_points=sketch_points, sheet_points=sheet_points)
        lines.append(tuple(sheet_points))
    return lines, receipt


def enclosing_cell(lines, anchor):
    """Nearest four crossing rules must close; never choose a larger fallback box."""
    x, y, z = finite(anchor, 3, "title anchor")
    if abs(z) > TOPOLOGY_M:
        raise RuntimeError("title cell: anchor is outside the sheet plane")
    horizontal, vertical = [], []
    for endpoints in lines:
        if len(endpoints) != 2:
            raise RuntimeError("title cell: incomplete line")
        a, b = (finite(point, 3, "template line") for point in endpoints)
        if abs(a[2]) > TOPOLOGY_M or abs(b[2]) > TOPOLOGY_M:
            raise RuntimeError("title cell: rule is outside the sheet plane")
        if math.dist(a, b) <= TOPOLOGY_M:
            raise RuntimeError("title cell: degenerate rule")
        if abs(a[1] - b[1]) <= TOPOLOGY_M:
            horizontal.append((a[1], min(a[0], b[0]), max(a[0], b[0])))
        elif abs(a[0] - b[0]) <= TOPOLOGY_M:
            vertical.append((a[0], min(a[1], b[1]), max(a[1], b[1])))
        # Diagonal drawing lines are not rectangular cell boundaries.
    crossing_x = [u for u, lo, hi in vertical if lo <= y <= hi]
    crossing_y = [v for v, lo, hi in horizontal if lo <= x <= hi]
    if any(abs(u - x) <= TOPOLOGY_M for u in crossing_x) or any(
        abs(v - y) <= TOPOLOGY_M for v in crossing_y
    ):
        raise RuntimeError("title cell: anchor lies on an ambiguous rule")
    sides = (
        [u for u in crossing_x if u < x],
        [v for v in crossing_y if v < y],
        [u for u in crossing_x if u > x],
        [v for v in crossing_y if v > y],
    )
    if not all(sides):
        raise RuntimeError("title cell: no enclosing closed rectangular cell")
    left, bottom, right, top = (
        max(sides[0]),
        max(sides[1]),
        min(sides[2]),
        min(sides[3]),
    )

    def covered(rules, coordinate, start, stop):
        end = start
        for lo, hi in sorted(
            (lo, hi) for u, lo, hi in rules if abs(u - coordinate) <= TOPOLOGY_M
        ):
            if hi < end:
                continue
            if lo > end + TOPOLOGY_M:
                return False
            end = max(end, hi)
            if end >= stop - TOPOLOGY_M:
                return True
        return False

    if not all(
        (
            covered(vertical, left, bottom, top),
            covered(vertical, right, bottom, top),
            covered(horizontal, bottom, left, right),
            covered(horizontal, top, left, right),
        )
    ):
        raise RuntimeError("title cell: nearest rules do not form a closed cell")
    return left, bottom, right, top


def left_anchor(cell, original, font_height):
    left, bottom, right, top = finite(cell, 4, "title cell")
    _, y, z = finite(original, 3, "title anchor")
    height = float(font_height)
    if (
        not math.isfinite(height)
        or height <= 0
        or not left < right
        or not bottom < y < top
    ):
        raise RuntimeError("title cell: invalid font/cell/vertical anchor")
    x = (
        left + height / 2
    )  # Explicit half-font-height left inset, not reflow compensation.
    if x >= right or abs(z) > TOPOLOGY_M:
        raise RuntimeError("title cell: inset does not fit")
    return x, y, 0.0


def require_box(cell, box, label):
    left, bottom, right, top = finite(cell, 4, "title cell")
    x0, y0, x1, y1 = finite(box, 4, label)
    if not (left <= x0 < x1 <= right and bottom <= y0 < y1 <= top):
        raise RuntimeError(
            f"{label}: title does not fit measured cell: {box} in {cell}"
        )


def require_native_fit(cell, observation):
    extent = finite(observation["extent"], 6, "title extent")
    require_box(
        cell, (extent[0], extent[1], extent[3], extent[4]), "native title extent"
    )


def require_pdf_fit(cell, pdf):
    """PDFium get_charbox and SW sheet coordinates both originate at lower left."""
    width_pt, height_pt = finite(pdf["page_size_pt"], 2, "PDF page")
    if width_pt <= 0 or height_pt <= 0:
        raise RuntimeError("title cell: invalid PDF page")
    factor = 0.0254 / 72
    require_box(
        (0, 0, width_pt * factor, height_pt * factor), cell, "title cell on PDF page"
    )
    if not pdf["characters"]:
        raise RuntimeError("title cell: PDF contains no title glyphs")
    for row in pdf["characters"]:
        x0, y0, x1, y1 = finite(row["box_pt"], 4, "PDF glyph")
        require_box(
            cell,
            (
                x0 * factor,
                y0 * factor,
                x1 * factor,
                y1 * factor,
            ),
            "PDF title glyph",
        )
