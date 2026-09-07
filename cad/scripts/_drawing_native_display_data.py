"""Exact native display-data witness, not a rendered or estimated bounding box.

Used by blank-template SF preservation. Numeric arrays stay in native order,
including XYZ, normals, style/color fields and documented unused slots. Nothing
is projected, rounded, tessellated, font-calibrated or interpreted as ink extents.
Unsupported primitive/leader forms fail instead of returning a partial witness.
"""

import math

from _common import _early_bound
from _drawing_annotation_bounds import _native_counts


def _finite_array(value, sizes, label):
    if value is None:
        raise ValueError(f"missing native {label} array")
    raw = list(value)
    if sizes is not None and len(raw) not in sizes:
        raise ValueError(f"unsupported native {label} array length: {len(raw)}")
    if any(type(item) not in (int, float) or not math.isfinite(item) for item in raw):
        raise ValueError(f"non-finite or nonnumeric native {label} array")
    return raw


def _count(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid native {label} count: {value}")
    return value


def _native_text(data, index):
    plane = data.GetTextPlaneAtIndex(index)
    row = {
        "value": data.GetTextAtIndex(index),
        "position": _finite_array(data.GetTextPositionAtIndex(index), {3}, "text XYZ"),
        "height_m": data.GetTextHeightAtIndex(index),
        "font": data.GetTextFontAtIndex(index),
        "angle_rad": data.GetTextAngleAtIndex(index),
        "reference": data.GetTextRefPositionAtIndex(index),
        "inverted": data.GetTextInvertAtIndex(index),
        # Drawing controls expose no plane; retain null/empty as observed,
        # or every element of the documented nine-double rotation matrix.
        "plane": None if plane is None else _finite_array(plane, {0, 9}, "text plane"),
        "line_spacing": data.GetTextLineSpacingAtIndex(index),
    }
    if row["value"] is not None and not isinstance(row["value"], str):
        raise ValueError("native displayed text must be a string or null")
    if not isinstance(row["font"], str) or not row["font"]:
        raise ValueError("native displayed text has no font name")
    for name in ("height_m", "angle_rad", "line_spacing"):
        value = row[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"invalid native displayed text {name}")
    if row["height_m"] <= 0:
        raise ValueError("native displayed text height must be positive")
    if type(row["reference"]) is not int or row["reference"] not in range(6):
        raise ValueError("unsupported native text reference position")
    if type(row["inverted"]) is not int:
        raise ValueError("native text invert flag must be integral")
    return row


def _point_array(data, kind, index):
    if kind == "PolyLine":
        raw = _finite_array(data.GetPolylineAtIndex2(index), None, "polyline")
        size = _count(data.GetPolylineSizeAtIndex2(index), "polyline size")
        if len(raw) < 7 or raw[0] not in {0, 1}:
            raise ValueError("unsupported native polyline geometry form")
        if raw[1] < 0 or int(raw[1]) != raw[1] or (raw[0] == 0 and raw[1] != 0):
            raise ValueError("unsupported native polyline data-size field")
        header, minimum = 7, 2
    else:
        raw = _finite_array(data.GetPolygonAtIndex(index), None, "polygon")
        size = _count(data.GetPolygonSizeAtIndex(index), "polygon size")
        header, minimum = 5, 3
    if len(raw) < header:
        raise ValueError(f"unsupported native {kind} header")
    points = raw[header - 1]
    if points < minimum or int(points) != points:
        raise ValueError(f"invalid native {kind} point count")
    if len(raw) != size or size != header + 3 * int(points):
        raise ValueError(f"native {kind} array/point/size count mismatch")
    return raw


def native_display_data(annotation):
    """Read supported native primitives and leaders without calculating bounds."""
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    if data is None:
        raise ValueError("native annotation has no display data")
    counts = _native_counts(
        data,
        (
            "Text",
            "Line",
            "Arc",
            "PolyLine",
            "Triangle",
            "ArrowHead",
            "Polygon",
            "Ellipse",
            "Parabola",
            "Point",
        ),
    )
    primitives = {}
    for kind, method, size in (
        ("Line", "GetLineAtIndex3", 10),
        ("Arc", "GetArcAtIndex2", 17),
        ("Triangle", "GetTriangleAtIndex", 11),
        ("ArrowHead", "GetArrowHeadAtIndex2", 12),
    ):
        primitives[kind] = [
            _finite_array(getattr(data, method)(index), {size}, kind)
            for index in range(counts[kind])
        ]
    for kind in ("PolyLine", "Polygon"):
        primitives[kind] = [
            _point_array(data, kind, index) for index in range(counts[kind])
        ]
    multi_jog_count = _count(annotation.GetMultiJogLeaderCount(), "multi-jog leader")
    if multi_jog_count:
        raise ValueError("unsupported native multi-jog leaders")
    leader_count = _count(annotation.GetLeaderCount(), "leader")
    style = annotation.GetLeaderStyle()
    leader_sizes = {0: 0, 1: 6, 2: 9, 3: 6}  # swLeaderStyle_e
    if type(style) is not int or style not in leader_sizes:
        raise ValueError(f"unsupported native leader style: {style}")
    if style == 0 and leader_count:
        raise ValueError("native no-leader style has nonzero leader count")
    return {
        "counts": counts,
        "texts": [_native_text(data, index) for index in range(counts["Text"])],
        "primitives": primitives,
        "leader_count": leader_count,
        "multi_jog_leader_count": multi_jog_count,
        "leader_style": style,
        "leaders": [
            _finite_array(
                annotation.GetLeaderPointsAtIndex(index),
                {leader_sizes[style]},
                "leader XYZ",
            )
            for index in range(leader_count)
        ],
    }
