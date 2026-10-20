"""MHA-CH-06-TL-30: removable steel positive-capture cap, two off.

Model frame: aperture/pocket axis at local X=Y=0, +Z up, block seating face
Z=0 and cap top Z=HEIGHT. The assembly seats this face on the original block
TOP, not on either bearing. The flange pocket is on the UNDERSIDE. Its
nominal depth is only a machining reference: actual flange thickness and
local face variation govern the fitted stop chamber, with the screws fully
seated. Bearing axial behavior is not part of this acceptance.

The four circular counterbores are open to their nearest X edge over their
FULL width and depth. Separate, shallower channels carry the doubled wire
and tails between X pairs. No screw head, single wire, twist or tail may
project above the cap plane. Safety-wire workmanship is accepted installed;
these voids alone do not prove tightening-direction routing or bump strength.
"""

from __future__ import annotations

import math

from _gtol_controls import GeometricControl, PartDatum
from _gtol_cylinder import CylinderFace
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
from _gtol_planar import PlanarFace
from _printed_tolerance import printed_band_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl

WIDTH = retention.CAP_WIDTH
LENGTH = retention.CAP_LENGTH
HEIGHT = retention.CAP_HEIGHT
POCKET_DIA = retention.CAP_POCKET_DIAMETER
POCKET_DEPTH = retention.CAP_POCKET_DEPTH
APERTURE_DIA = retention.CAP_APERTURE_DIAMETER
BOLT_POINTS = retention.CAP_BOLT_CENTERS
HOLE_DIA = retention.CAP_BOLT_CLEARANCE_DIAMETER
COUNTERBORE_DIA = retention.CAP_COUNTERBORE_DIAMETER
COUNTERBORE_DEPTH = retention.CAP_COUNTERBORE_DEPTH
CHANNEL_WIDTH = retention.CAP_WIRE_CHANNEL_WIDTH
CHANNEL_DEPTH = retention.CAP_WIRE_CHANNEL_DEPTH
STOCK_THICKNESS = 0.5 * 25.4
STOCK_WIDTH = 2.0 * 25.4
POCKET_BAND = retention.CAP_POCKET_DIAMETER_BAND
DRILLED_BAND = retention.CAP_BOLT_CLEARANCE_BAND
STOCK_LENGTH_MIN = 3.0 * 25.4
SCREW_MAJOR_LIMITS = (hardware.SCREW_MAJOR_DIA_MIN, hardware.SCREW_MAJOR_DIA_MAX)
SCREW_THREAD_SOURCE_URL = hardware.SCREW_THREAD_SOURCE_URL
HEAD_DIAMETER_MAX = hardware.SCREW_HEAD_DIA_MAX
HEAD_HEIGHT_MAX = hardware.SCREW_HEAD_HEIGHT_MAX
WIRE_DIAMETER = hardware.WIRE_DIA
if HOLE_DIA < SCREW_MAJOR_LIMITS[1]:
    raise AssertionError("the minimum cap clearance hole will not pass the sourced screw")

HEIGHT_PLACES = 2
OUTLINE_PLACES = 1
POSITION_PLACES = 3
COUNTERBORE_DEPTH_PLACES = 3
COUNTERBORE_DIAMETER_PLACES = retention.CAP_COUNTERBORE_DIAMETER_PLACES
CHANNEL_PLACES = 2
POSITION_TOLERANCE = printed_band_mm(POSITION_PLACES)
HEIGHT_TOLERANCE = printed_band_mm(HEIGHT_PLACES)
CHAMBER_EXCESS_MIN, CHAMBER_EXCESS_MAX = retention.CAP_CHAMBER_EXCESS
LOWER_GAP_MIN, LOWER_GAP_MAX = retention.PIN_LOWER_GAP
FITTED_POCKET_DEPTH_MAX = (
    retention.PIN_FLANGE_THICK
    + printed_band_mm(retention.PIN_FLANGE_THICK_PLACES)
    + CHAMBER_EXCESS_MAX
)
APERTURE_POSITION_DIAMETER = retention.CAP_APERTURE_POSITION_DIAMETER
PART_DATUMS = (PartDatum("A", CylinderFace(POCKET_DIA)),)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "aperture_position", "position", f"{APERTURE_POSITION_DIAMETER:.2f}",
        CylinderFace(APERTURE_DIA), ("A",), "diametral",
    ),
)
COUNTERBORE_DEPTH_TOLERANCE = printed_band_mm(COUNTERBORE_DEPTH_PLACES)

AXIS_NAME = "CaptureAxis"
BOTTOM_PLANE = "Front Plane"
TOP_PLANE = "CapTop"
BOLT_AXES = tuple(f"CapBoltAxis{index}" for index in range(1, 5))
BOLT_SEAT_PLANE = "CapBoltSeats"
SECTION_PLANE = "CapSectionPlane"
SECTION_REFERENCE = "CapSectionReference"
REFERENCE_SKETCHES = (SECTION_REFERENCE,)


def clearance_geometry(
    *, height: float = HEIGHT, counterbore_depth: float = COUNTERBORE_DEPTH,
    counterbore_dia: float = COUNTERBORE_DIA, pocket_dia: float = POCKET_DIA,
    hole_dia: float = HOLE_DIA, channel_width: float = CHANNEL_WIDTH,
    channel_depth: float = CHANNEL_DEPTH, points: tuple = BOLT_POINTS,
    fitted_pocket_depth_max: float = FITTED_POCKET_DEPTH_MAX,
) -> dict[str, float]:
    """Source-only worst-case material margins; never a load certificate.

    Positions are independent X/Y three-place limits relative to the actual
    pocket axis. Mouths open deliberately at X, so no fictitious
    outside-X wall is counted. All other walls are real remaining material.
    """
    cb_r = (counterbore_dia + printed_band_mm(COUNTERBORE_DIAMETER_PLACES)) / 2.0
    pocket_r = (pocket_dia + POCKET_BAND[0]) / 2.0
    hole_r = (hole_dia + DRILLED_BAND[0]) / 2.0
    channel_half = (channel_width + printed_band_mm(CHANNEL_PLACES)) / 2.0
    near = tuple((abs(x) - POSITION_TOLERANCE, abs(y) - POSITION_TOLERANCE) for x, y in points)
    return {
        "counterbore_floor": height - HEIGHT_TOLERANCE - counterbore_depth - COUNTERBORE_DEPTH_TOLERANCE,
        "channel_floor": height - HEIGHT_TOLERANCE - channel_depth - printed_band_mm(CHANNEL_PLACES),
        "chamber_roof": height - HEIGHT_TOLERANCE - fitted_pocket_depth_max,
        "counterbore_to_chamber": min(math.hypot(x, y) - cb_r - pocket_r for x, y in near),
        "hole_to_chamber": min(math.hypot(x, y) - hole_r - pocket_r for x, y in near),
        "mouth_to_chamber": min(math.hypot(x, max(y - cb_r, 0.0)) - pocket_r for x, y in near),
        "channel_to_chamber": min(y - channel_half - pocket_r for _, y in near),
        "counterbore_to_y_edge": LENGTH / 2.0 - printed_band_mm(OUTLINE_PLACES) / 2.0 - max(abs(y) for _, y in points) - POSITION_TOLERANCE - cb_r,
        "pocket_to_x_edge": WIDTH / 2.0 - printed_band_mm(OUTLINE_PLACES) / 2.0 - pocket_r,
    }


def require_clearance_geometry(**changes: float) -> dict[str, float]:
    margins = clearance_geometry(**changes)
    for name, value in margins.items():
        if value < 2.0:
            raise ValueError(f"cap {name}: {value:.4f} mm is below the 2 mm material target")
    return margins


def fitted_chamber_excess(pocket_depth: float, flange_thickness: float) -> float:
    """Actual opposing-face separation minus actual flange thickness."""
    excess = pocket_depth - flange_thickness
    if not CHAMBER_EXCESS_MIN - 1e-9 <= excess <= CHAMBER_EXCESS_MAX + 1e-9:
        raise ValueError("fitted chamber excess is outside its measured acceptance")
    return excess


def nominal_volume_mm3() -> float:
    """Exact union of pocket, holes, full-width mouths and connecting channels."""
    cb_r, hole_r = COUNTERBORE_DIA / 2.0, HOLE_DIA / 2.0
    total = WIDTH * LENGTH * HEIGHT
    total -= math.pi * (POCKET_DIA / 2.0) ** 2 * POCKET_DEPTH
    total -= math.pi * (APERTURE_DIA / 2.0) ** 2 * (HEIGHT - POCKET_DEPTH)
    total -= len(BOLT_POINTS) * math.pi * hole_r**2 * HEIGHT
    for x, _y in BOLT_POINTS:
        # Circular head recess plus its rectangular outward half-mouth;
        # the shank hole is already removed at this level.
        area = math.pi * cb_r**2 / 2.0 + COUNTERBORE_DIA * (WIDTH / 2.0 - abs(x))
        total -= (area - math.pi * hole_r**2) * COUNTERBORE_DEPTH
    half = CHANNEL_WIDTH / 2.0
    half_strip = half * math.sqrt(cb_r**2 - half**2) + cb_r**2 * math.asin(half / cb_r)
    pair_span = max(x for x, _ in BOLT_POINTS) - min(x for x, _ in BOLT_POINTS)
    row_count = len({y for _, y in BOLT_POINTS})
    total -= row_count * (pair_span * CHANNEL_WIDTH - 2.0 * half_strip) * CHANNEL_DEPTH
    return total


GEOMETRY_MARGINS = require_clearance_geometry()
VOLUME_MM3 = nominal_volume_mm3()
DRAWING_DIMENSIONS = {
    "CapProfile": {"CapWidth", "CapLength"},
    "PocketProfile": {"PocketDia"},
    "ApertureProfile": {"ApertureDia"},
    "BoltProfile": {"BoltHoleDia", *(f"Bolt{index}{axis}" for index in range(1, 5) for axis in ("X", "Y"))},
    "HeadProfile": {"CounterboreDia"},
    "HeadRecesses": {"CounterboreDepth"},
    "WireProfile1": {"WireWidth"},
    "WireChannels1": {"WireDepth"},
    SECTION_REFERENCE: {"CapHeight", "PocketDepth"},
}
DRAWING_PRECISION = {
    "CapProfile": {"CapWidth": OUTLINE_PLACES, "CapLength": OUTLINE_PLACES},
    "PocketProfile": {"PocketDia": 2},
    "ApertureProfile": {"ApertureDia": 2},
    "BoltProfile": {"BoltHoleDia": 2, **{f"Bolt{index}{axis}": POSITION_PLACES for index in range(1, 5) for axis in ("X", "Y")}},
    "HeadProfile": {"CounterboreDia": COUNTERBORE_DIAMETER_PLACES},
    "HeadRecesses": {"CounterboreDepth": COUNTERBORE_DEPTH_PLACES},
    "WireProfile1": {"WireWidth": CHANNEL_PLACES},
    "WireChannels1": {"WireDepth": CHANNEL_PLACES},
    SECTION_REFERENCE: {"CapHeight": HEIGHT_PLACES, "PocketDepth": 2},
}
DRAWING_PRECISION_BY_NAME = {name: places for row in DRAWING_PRECISION.values() for name, places in row.items()}
DIMENSION_CALLOUTS = {
    "PocketDia": "RUNNING CHAMBER FOR\nMHA-CH-06-TL-23 FLANGE",
    "PocketDepth": (
        "REF; FIT TO ACTUAL TL-23 FLANGE\n"
        f"TOTAL CHAMBER EXCESS {CHAMBER_EXCESS_MIN:.2f}-{CHAMBER_EXCESS_MAX:.2f}\n"
        "INCLUDING LOCAL FACE VARIATION;\nSCREWS FULLY SEATED AND LOCKED\n"
        f"NORMAL LOWER GAP {LOWER_GAP_MIN:.2f}-{LOWER_GAP_MAX:.2f}; NO BEARING PRELOAD"
    ),
    "ApertureDia": "THRU; CLEARS TL-23 CARRIER SEAT",
    "BoltHoleDia": "4X DRILL THRU; NAS1352N4H12",
    "CounterboreDia": "4X COAXIAL WITH CLEARANCE HOLES;\nFULL WIDTH OPEN TO NEAREST X EDGE",
    "CounterboreDepth": "4X FROM TOP; RECESSES\nNAS1352N4H12 HEADS AND SINGLE WIRE",
    "WireWidth": "2X X-PAIR CHANNEL; TWIST AND TAIL\nALL WIRE BELOW CAP PLANE",
    "WireDepth": "2X FROM TOP",
    **{f"Bolt{index}{axis}": "FROM POCKET AXIS;\nLOCATES TL-22 CAP SCREW" for index in range(1, 5) for axis in ("X", "Y")},
}
SURFACE_FINISHES = (SurfaceFinishControl("block_seat", SEAT_UM, PlanarFace((0.0, 0.0, -1.0), 0.0)),)
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
