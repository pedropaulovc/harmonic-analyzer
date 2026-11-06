"""Bandsaw preform in carrier XY; pure geometry, no native CAD calls.

The retained material is the region between two symmetric chord chains,
clipped to the purchased 350 x 38.1 flat. Chord vertices lie on the cutter
CENTRE circles, not the finished edges. The raw rolled edges remain wherever
an extrapolated chord leaves the bar. This matters at both blank ends: a
38.1-wide bar cannot contain both complete circles over +/-175.

``proof()`` evaluates continuous domains, not a sampling grid: half-plane
clipping limits each boundary to the relevant angular wedge, and the exact
line-segment projection and endpoints give every radial extremum. Entry air
is the exact disk/polygon intersection area (line integrals of triangles and
circular sectors). Both stops are checked, including all polygon corners.
The kerf margin is to the SCRAP-facing edge of the swept cutter annulus:
no strip can survive between the bandsawn edge and that edge of the kerf.
The 4 mm finishing stock requirement applies to the finished tip-ray domain,
not to the sacrificial run-out tails.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import ch_rocker_arm_tl_oblique_trammel_spec as trammel

Point = tuple[float, float]
BLANK_HALF_LENGTH = trammel.BLANK_LENGTH / 2.0
RAW_Y_MIN = trammel.STRAP_SPAN_Y[0] - trammel.BLANK_EDGE_WASTE
RAW_Y_MAX = RAW_Y_MIN + trammel.BLANK_WIDTH
# Four inner and seven outer full-edge cuts. Extra cuts avoid demanding a
# precision bandsaw result: the retained saw edge has a +/-0.5 normal strip.
# The end segments continue through their circle anchor to the blank ends.
INNER_STATIONS = (0.0, 75.0, 148.0)
OUTER_STATIONS = (20.0, 60.0, 100.0, 140.0)
SAW_EDGE_TOLERANCE = 0.5  # inspected normal edge corridor, NOT machine accuracy
SLIVER_MARGIN_MIN = 3.0
FINISH_STOCK_MIN = 4.0


def _vertices(radius: float, stations: tuple[float, ...]) -> tuple[Point, ...]:
    xs = tuple(-x for x in reversed(stations) if x > 0.0) + stations
    return tuple((x, math.sqrt(radius * radius - x * x) - trammel.H1) for x in xs)


INNER_ANCHORS = _vertices(trammel.R_C1, INNER_STATIONS)
OUTER_ANCHORS = _vertices(trammel.R_C2, OUTER_STATIONS)


def _extend(anchors: tuple[Point, ...]) -> tuple[Point, ...]:
    a, b = anchors[-2:]
    end_y = b[1] + (b[1] - a[1]) / (b[0] - a[0]) * (BLANK_HALF_LENGTH - b[0])
    return ((-BLANK_HALF_LENGTH, end_y),) + anchors + ((BLANK_HALF_LENGTH, end_y),)


INNER_VERTICES = _extend(INNER_ANCHORS)
OUTER_VERTICES = _extend(OUTER_ANCHORS)


def _clip(points: tuple[Point, ...], a: float, b: float, c: float) -> tuple[Point, ...]:
    """Retain a*x+b*y+c >= 0; preserve polygon winding."""
    result: list[Point] = []
    for p, q in zip(points, points[1:] + points[:1]):
        fp, fq = a * p[0] + b * p[1] + c, a * q[0] + b * q[1] + c
        if fp >= 0.0:
            result.append(p)
        if (fp < 0.0) != (fq < 0.0):
            t = fp / (fp - fq)
            result.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return tuple(result)


# Inner runs left->right, outer right->left: counterclockwise retained polygon.
BLANK_OUTLINE = _clip(
    _clip(INNER_VERTICES + tuple(reversed(OUTER_VERTICES)), 0.0, 1.0, -RAW_Y_MIN),
    0.0, -1.0, RAW_Y_MAX,
)


def _edge_chain(vertices: tuple[Point, ...], lower: float, upper: float) -> tuple[Point, ...]:
    """Clip a chain to the raw Y interval, inserting exact intersections."""
    result: list[Point] = []
    for p, q in zip(vertices, vertices[1:]):
        cuts = [0.0, 1.0]
        if q[1] != p[1]:
            cuts += [t for y in (lower, upper) if 0.0 < (t := (y - p[1]) / (q[1] - p[1])) < 1.0]
        for t in sorted(cuts):
            x, y = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
            point = (x, min(upper, max(lower, y)))
            if not result or point != result[-1]:
                result.append(point)
    return tuple(result)


INNER_EDGE = _edge_chain(INNER_VERTICES, RAW_Y_MIN, RAW_Y_MAX)
OUTER_EDGE = _edge_chain(OUTER_VERTICES, RAW_Y_MIN, RAW_Y_MAX)


def _radial_bounds(chain: tuple[Point, ...], half_angle: float) -> tuple[float, float]:
    """Exact radius extrema on a chain within the two tip/sweep rays."""
    radii: list[float] = []
    tangent = math.tan(half_angle)
    for p, q in zip(chain, chain[1:]):
        # Clip the segment parameter to +/-x <= (y+H1)*tan(angle).
        lo, hi = 0.0, 1.0
        for sign in (-1.0, 1.0):
            f = tangent * (p[1] + trammel.H1) + sign * p[0]
            slope = tangent * (q[1] - p[1]) + sign * (q[0] - p[0])
            if slope > 0.0:
                lo = max(lo, -f / slope)
            elif slope < 0.0:
                hi = min(hi, -f / slope)
            elif f < 0.0:
                hi = -1.0
        if lo > hi:
            continue
        px, py = p[0], p[1] + trammel.H1
        dx, dy = q[0] - p[0], q[1] - p[1]
        norm = dx * dx + dy * dy
        projection = max(lo, min(hi, -(px * dx + py * dy) / norm)) if norm else lo
        radii.extend(math.hypot(px + t * dx, py + t * dy) for t in (lo, projection, hi))
    return min(radii), max(radii)


def disk_material_area(centre: Point, radius: float, polygon: tuple[Point, ...] = BLANK_OUTLINE) -> float:
    """Exact area inside a disk and a simple CCW polygon (mm squared)."""
    area = 0.0
    for p, q in zip(polygon, polygon[1:] + polygon[:1]):
        px, py = p[0] - centre[0], p[1] - centre[1]
        dx, dy = q[0] - p[0], q[1] - p[1]
        aa = dx * dx + dy * dy
        if aa == 0.0:
            continue
        bb = 2.0 * (px * dx + py * dy)
        cc = px * px + py * py - radius * radius
        discriminant = bb * bb - 4.0 * aa * cc
        cuts = [0.0, 1.0]
        if discriminant > 0.0:
            root = math.sqrt(discriminant)
            cuts += [t for t in ((-bb - root) / (2.0 * aa), (-bb + root) / (2.0 * aa)) if 0.0 < t < 1.0]
        cuts.sort()
        for lo, hi in zip(cuts, cuts[1:]):
            ax, ay = px + lo * dx, py + lo * dy
            bx, by = px + hi * dx, py + hi * dy
            mx, my = px + (lo + hi) / 2.0 * dx, py + (lo + hi) / 2.0 * dy
            cross = ax * by - ay * bx
            if mx * mx + my * my <= radius * radius:
                area += cross / 2.0
            else:
                area += radius * radius * math.atan2(cross, ax * bx + ay * by) / 2.0
    return area


@dataclass(frozen=True)
class PassProof:
    finished_radius_bounds: tuple[float, float]
    swept_radius_bounds: tuple[float, float]
    sliver_margin: float
    finish_stock: float
    accepted_sliver_margin: float
    accepted_finish_stock: float
    entry_air_fraction: tuple[float, float]


def proof() -> dict[str, PassProof]:
    """Continuous nominal bounds and conservative accepted-edge bounds.

    Only the sawn line has a +/-SAW_EDGE_TOLERANCE normal corridor, including
    radius-0.5 corner caps; rolled edges are unchanged. A corridor point's
    radius differs from its nearest nominal point by at most 0.5 (the norm
    is 1-Lipschitz). Expand the angular domain by the maximum possible ray
    shift too, so nearest points across a tip/stop ray are not omitted.
    Bound the FULL untrimmed chord chains before clipping to stock: this
    covers moving intersections with rolled edges. An accepted edge is
    unchanged raw stock or in that corridor, so take the lesser bound.
    Entry fractions describe the final faced blank at each stop before feed.
    The mill is lowered in the already-open scrap side before traversing into
    this engagement, never plunged at a stop or through solid bar.
    """
    result = {}
    cutter = trammel.PART_CUTTER_DIA / 2.0
    for name, chain in (("inner", INNER_EDGE), ("outer", OUTER_EDGE)):
        radius, sweep = trammel.PASS_RADIUS[name], trammel.SWEEP[name]
        finished = _radial_bounds(chain, trammel.TIP_ANGLE)
        swept = _radial_bounds(chain, sweep)
        margin = swept[0] - (radius - cutter) if name == "inner" else radius + cutter - swept[1]
        stock = trammel.R_INNER - finished[1] if name == "inner" else finished[0] - trammel.R_OUTER
        full_chain = INNER_VERTICES if name == "inner" else OUTER_VERTICES
        minimum_radius = _radial_bounds(full_chain, math.pi / 4.0)[0]
        angular_guard = math.asin(SAW_EDGE_TOLERANCE / minimum_radius)
        full_finished = _radial_bounds(full_chain, trammel.TIP_ANGLE + angular_guard)
        full_swept = _radial_bounds(full_chain, sweep + angular_guard)
        sawn_margin = full_swept[0] - (radius - cutter) if name == "inner" else radius + cutter - full_swept[1]
        sawn_stock = trammel.R_INNER - full_finished[1] if name == "inner" else full_finished[0] - trammel.R_OUTER
        accepted_margin = min(margin, sawn_margin - SAW_EDGE_TOLERANCE)
        accepted_stock = min(stock, sawn_stock - SAW_EDGE_TOLERANCE)
        air = tuple(
            1.0 - disk_material_area((sign * radius * math.sin(sweep), radius * math.cos(sweep) - trammel.H1), cutter) / (math.pi * cutter * cutter)
            for sign in (-1.0, 1.0)
        )
        result[name] = PassProof(finished, swept, margin, stock, accepted_margin, accepted_stock, air)
    return result
