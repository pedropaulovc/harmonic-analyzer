"""Measure separation of native datum ink and diameter lines in sheet metres."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def finite_row(row, length):
    if not isinstance(row, (list, tuple)) or len(row) != length:
        return False
    try:
        return all(type(value) in (int, float) and math.isfinite(value) for value in row)
    except OverflowError:
        return False


def cross(p, q, r):
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def triangle_points(row):
    return [tuple(row[index:index + 2]) for index in (0, 3, 6)]


def triangle_contains(point, triangle):
    """Containment includes the boundary and accepts either vertex winding."""
    signs = [cross(start, end, point)
             for start, end in zip(triangle, triangle[1:] + triangle[:1])]
    return all(value >= 0 for value in signs) or all(value <= 0 for value in signs)


def point_distance(point, start, end):
    delta = (end[0] - start[0], end[1] - start[1])
    length2 = sum(value * value for value in delta)
    if length2 == 0:
        return math.dist(point, start)
    fraction = sum((point[index] - start[index]) * delta[index] for index in range(2)) / length2
    fraction = min(1.0, max(0.0, fraction))
    return math.dist(point, [start[index] + fraction * delta[index] for index in range(2)])


def segment_distance(first, second):
    a, b = first
    c, d = second

    # A strict crossing has opposite orientations on both supporting lines.
    if cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0:
        return 0.0
    return min(point_distance(a, c, d), point_distance(b, c, d),
               point_distance(c, a, b), point_distance(d, a, b))


def ink_segments(stage, prefix):
    lines = stage.get(f"{prefix}_lines")
    triangles = stage.get(f"{prefix}_triangles")
    if not lines or (prefix == "datum" and not triangles):
        raise ValueError(f"missing {prefix} ink")
    if not isinstance(lines, (list, tuple)) or not isinstance(triangles, (list, tuple)):
        raise ValueError("invalid native primitive collection")
    offset = 1 if prefix == "datum" else 4
    segments = []
    for row in lines:
        if not finite_row(row, offset + 6):
            raise ValueError("invalid native line primitive")
        segments.append((tuple(row[offset:offset + 2]), tuple(row[offset + 3:offset + 5])))
    for row in triangles:
        if not finite_row(row, 11):
            raise ValueError("invalid native triangle primitive")
        points = triangle_points(row)
        if cross(*points) == 0:
            raise ValueError("degenerate native triangle primitive")
        segments.extend(zip(points, points[1:] + points[:1]))
    if any(not (0 <= value <= limit) for segment in segments for point in segment
           for value, limit in zip(point, (0.4318, 0.2794))):
        raise ValueError("ink is outside the ASME B sheet coordinate domain")
    return segments


def minimum_clearance(stage):
    """Measure only finite primitives consistent with the current datum anchor.

    ``position`` and ``dimension_position`` are native annotation XYZ readbacks.
    The 1e-8 m consistency check is not a placement tolerance: it rejects stale
    datum display primitives before they can supply a clearance measurement.
    Dimension text anchors need not lie on their dimension lines.
    """
    for field in ("position", "dimension_position"):
        if not finite_row(stage.get(field), 3):
            raise ValueError(f"invalid annotation {field}")
    datum = ink_segments(stage, "datum")
    dimension = ink_segments(stage, "dimension")
    endpoints = [tuple(row[offset:offset + 2])
                 for row in stage["datum_lines"] for offset in (1, 4)]
    if min(math.dist(point, stage["position"][:2]) for point in endpoints) > 1e-8:
        raise ValueError("datum primitives do not contain the current annotation anchor")
    # Boundary distances alone miss a segment (or smaller triangle) entirely
    # inside filled triangle ink. Check both directions before edge distances.
    for rows, opposing in ((stage["datum_triangles"], dimension),
                           (stage["dimension_triangles"], datum)):
        for row in rows:
            triangle = triangle_points(row)
            if any(triangle_contains(point, triangle) for segment in opposing for point in segment):
                return 0.0
    return min(segment_distance(first, second) for first in datum for second in dimension)


def assert_clearance(stage, minimum_m=0.001):
    """Require 1 mm between the two ink sets, including the datum triangle/box."""
    if not finite_row([minimum_m], 1) or minimum_m <= 0:
        raise ValueError("clearance must be positive and finite")
    actual = minimum_clearance(stage)
    if actual < minimum_m:
        raise RuntimeError(f"datum/diameter ink clearance {actual:.9g} m < {minimum_m:.9g} m")
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    print(json.dumps({row["stage"]: minimum_clearance(row) for row in receipt["stages"]}, indent=2))


if __name__ == "__main__":
    main()
