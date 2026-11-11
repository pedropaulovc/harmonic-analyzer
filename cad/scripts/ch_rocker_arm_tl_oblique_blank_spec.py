"""Bandsaw preform in carrier XY; pure geometry, no native CAD calls.

The retained material lies between five inner and two outer straight chords,
clipped to the procured 350 x 38.1 flat at its existing raw-edge datum.
Roughing anchors use R795.080/R821.210 rather than the cutter-centre circles
R795.2375/R820.7625. This roughing-layout bias preserves 4 mm stock to R800,
0.30 mm stock to R816 and 3 mm scrap-side overlap after ordinary setup.
Neither finished product radius nor its hub interface changes.

``proof()`` evaluates continuous domains, not a sampling grid: half-plane
clipping limits each boundary to the relevant angular wedge, and the exact
line-segment projection and endpoints give every radial extremum. Entry air
is the exact disk/polygon intersection area (line integrals of triangles and
circular sectors). Both stops are checked, including all polygon corners.
The kerf margin is to the SCRAP-facing edge of the swept cutter annulus:
no strip can survive between the bandsawn edge and that edge of the kerf.
The 4 mm finishing-stock floor applies to R800 inside the finished tip rays;
R816 requires 0.30 mm skim stock. Sacrificial run-out tails need neither floor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_oblique_riser_spec as riser
from _printed_tolerance import printed_band_mm

Point = tuple[float, float]
BLANK_HALF_LENGTH = trammel.BLANK_LENGTH / 2.0
BLANK_WIDTH = riser.STRAP_STOCK_WIDTH
RAW_Y_MIN = riser.STRAP_RAW_Y_MIN
RAW_Y_MAX = RAW_Y_MIN + BLANK_WIDTH
# Five inner and two outer full-edge straight cuts. Extend end segments to
# the square ends; rolled-edge portions are not additional cuts.
INNER_STATIONS = (30.0, 90.0, 150.0)
OUTER_STATIONS = (0.0, 160.0)
INNER_ANCHOR_RADIUS = 795.080
OUTER_ANCHOR_RADIUS = 821.210
# TOTAL layout-plus-saw corridor relative to the PRINTED chord, not .5 mm
# added to independently toleranced layout marks. Inch .XXX coordinate
# rounding is charged separately against the exact design geometry.
SAW_EDGE_TOLERANCE = 0.5
LAYOUT_PLACES = 3
LAYOUT_ROUNDING_ERROR = math.sqrt(2.0) * 0.0005 * trammel.INCH
ACCEPTED_EDGE_CORRIDOR = SAW_EDGE_TOLERANCE + LAYOUT_ROUNDING_ERROR
LONGITUDINAL_SETUP_ERROR = 0.5
_STOP_SPAN_MIN = (
    riser.STOP_PIN_CARRIER_POINTS[1][0] - riser.STOP_PIN_CARRIER_POINTS[0][0]
    - 2.0 * printed_band_mm(riser.STATION_PLACES, unit=riser.UNIT)
)
YAW_SLOPE_MAX = (riser.STOP_RAW_Y_LIMITS[1] - riser.STOP_RAW_Y_LIMITS[0]) / _STOP_SPAN_MIN
LONGITUDINAL_ERROR = LONGITUDINAL_SETUP_ERROR + BLANK_WIDTH * YAW_SLOPE_MAX
_YAW_Y_ERROR = BLANK_WIDTH * (1.0 - math.cos(math.atan(YAW_SLOPE_MAX)))
REGISTRATION_Y_ERROR = (
    riser.STOP_RAW_Y_LIMITS[0] - RAW_Y_MIN - _YAW_Y_ERROR,
    riser.STOP_RAW_Y_LIMITS[1] - RAW_Y_MIN + _YAW_Y_ERROR,
)
SLIVER_MARGIN_MIN = 3.0
FINISH_STOCK_MIN = 4.0  # inner R800 only
FINISH_STOCK_MIN_BY_PASS = {"inner": FINISH_STOCK_MIN, "outer": 0.30}

# Transfer from the ACTUAL carrier taps after edge registration: a pilot run
# up through each tap from below, opened from above in place (TL-00 steps
# 19F-19J; #2443). Predrilling nominal stations from a separately displaced
# raw blank would add an invalid stack.
CLAMP_TRANSFER_POINTS = (trammel.CL, trammel.CR)
CLAMP_TRANSFER_BAND = printed_band_mm(2, unit=riser.UNIT)
CLAMP_DRILL = "7/32"
CLAMP_DRILL_DIA = 7.0 / 32.0 * trammel.INCH
CLAMP_HOLE_DIA = 0.218 * trammel.INCH
CLAMP_HOLE_LIMITS = (CLAMP_HOLE_DIA, CLAMP_HOLE_DIA + riser.DRILLED_BAND[0])
if not CLAMP_HOLE_LIMITS[0] <= CLAMP_DRILL_DIA <= CLAMP_HOLE_LIMITS[1]:
    raise AssertionError("the end-clamp drill leaves its printed hole limits")


def _vertices(radius: float, stations: tuple[float, ...]) -> tuple[Point, ...]:
    xs = tuple(-x for x in reversed(stations) if x > 0.0) + stations
    return tuple((x, math.sqrt(radius * radius - x * x) - trammel.H1) for x in xs)


INNER_ANCHORS = _vertices(INNER_ANCHOR_RADIUS, INNER_STATIONS)
OUTER_ANCHORS = _vertices(OUTER_ANCHOR_RADIUS, OUTER_STATIONS)
# Layout from the blank's end midpoint X0 and registered raw edge Y0, not
# from a pre-existing HUB hole. Values stay physical mm; the plan prints
# these exact rounded coordinates as .XXX inch reference stations.
LAYOUT_DATUM = (0.0, RAW_Y_MIN)
LAYOUT_MARKS = {
    name: tuple(
        (round(x / trammel.INCH, LAYOUT_PLACES) * trammel.INCH,
         round((y - RAW_Y_MIN) / trammel.INCH, LAYOUT_PLACES) * trammel.INCH)
        for x, y in anchors
    )
    for name, anchors in (("inner", INNER_ANCHORS), ("outer", OUTER_ANCHORS))
}


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


def _convex_hull(points: tuple[Point, ...]) -> tuple[Point, ...]:
    """Boundary of a segment translated over the rectangular setup corridor."""
    ordered = sorted(set(points))

    def cross(a: Point, b: Point, c: Point) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    lower: list[Point] = []
    upper: list[Point] = []
    for sequence, half in ((ordered, lower), (reversed(ordered), upper)):
        for point in sequence:
            while len(half) > 1 and cross(half[-2], half[-1], point) <= 0.0:
                half.pop()
            half.append(point)
    return tuple(lower[:-1] + upper[:-1])


def directional_radial_bounds(chain: tuple[Point, ...], half_angle: float) -> tuple[float, float]:
    """Continuous extrema including every directional placement, not samples.

    Each edge plus the X/Y setup rectangle is a convex polygon. Clip that
    polygon to the actual angular domain, then inspect every vertex and exact
    line projection. Convexity puts a maximum at a vertex; a minimum is a
    projected edge point (the arc centre is outside these material polygons).
    """
    extrema: list[tuple[float, float]] = []
    tangent = math.tan(half_angle)
    for a, b in zip(chain, chain[1:]):
        polygon = _convex_hull(tuple(
            (p[0] + dx, p[1] + dy)
            for p in (a, b)
            for dx in (-LONGITUDINAL_ERROR, LONGITUDINAL_ERROR)
            for dy in REGISTRATION_Y_ERROR
        ))
        polygon = _clip(_clip(polygon, 1.0, tangent, tangent * trammel.H1),
                        -1.0, tangent, tangent * trammel.H1)
        if polygon:
            extrema.append(_radial_bounds(polygon + (polygon[0],), half_angle))
    if not extrema:
        raise ValueError("the edge has no material inside the requested angular domain")
    return min(lo for lo, _hi in extrema), max(hi for _lo, hi in extrema)


def proof() -> dict[str, PassProof]:
    """Continuous nominal and accepted envelopes with no pre-made hub datum.

    Exact directional setup rectangles include stop play/tilt, ordinary
    longitudinal placement and two-stop yaw. Only the layout/saw corridor
    and coordinate rounding use a radial Lipschitz bound; expand the angular
    domain too, so no tip/stop-ray caps are missed. Raw edges translate with
    the blank but have neither a saw corridor nor coordinate-rounding error.
    Entry fractions describe nominal side engagement, not a plunge route.
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
        minimum_radius = directional_radial_bounds(full_chain, math.pi / 4.0)[0]
        angular_guard = math.asin(ACCEPTED_EDGE_CORRIDOR / minimum_radius)
        full_finished = directional_radial_bounds(full_chain, trammel.TIP_ANGLE + angular_guard)
        full_swept = directional_radial_bounds(full_chain, sweep + angular_guard)
        raw_y = RAW_Y_MIN if name == "inner" else RAW_Y_MAX
        raw_chain = ((-BLANK_HALF_LENGTH, raw_y), (BLANK_HALF_LENGTH, raw_y))
        raw_finished = directional_radial_bounds(raw_chain, trammel.TIP_ANGLE)
        if name == "inner":
            accepted_stock = trammel.R_INNER - max(
                full_finished[1] + ACCEPTED_EDGE_CORRIDOR, raw_finished[1])
            # Clipping the lower saw edge upward to raw stock cannot reduce
            # its scrap-side clearance.
            accepted_margin = full_swept[0] - ACCEPTED_EDGE_CORRIDOR - (radius - cutter)
        else:
            accepted_stock = min(full_finished[0] - ACCEPTED_EDGE_CORRIDOR,
                                 raw_finished[0]) - trammel.R_OUTER
            accepted_margin = radius + cutter - (full_swept[1] + ACCEPTED_EDGE_CORRIDOR)
        air = tuple(
            1.0 - disk_material_area((sign * radius * math.sin(sweep), radius * math.cos(sweep) - trammel.H1), cutter) / (math.pi * cutter * cutter)
            for sign in (-1.0, 1.0)
        )
        result[name] = PassProof(finished, swept, margin, stock, accepted_margin, accepted_stock, air)
    return result
