"""MHA-CH-06-TL-30: removable steel positive-capture cap, two off.

Model frame: aperture/pocket axis at local X=Y=0, +Z up, block seating face
Z=0 and cap top Z=HEIGHT. The assembly seats this face on the original block
TOP, not on either bearing. The flange pocket is on the UNDERSIDE. Its
nominal depth is only a machining reference: actual flange thickness and
local face variation govern the fitted stop chamber, with the screws fully
seated. Bearing axial behavior is not part of this acceptance.

Two integral underside registers locate the cap in the block's flat-bottom
receivers. Their real 45-degree free-end chamfers use the title-block edge-break
maximum; the roots remain unrelieved for straight locating engagement.

The four circular counterbores are fitted to the actual installed screw heads;
their nominal depth is reference-only. Their FULL width and depth open to the
nearest X edge, with the actual whole floor and mouths retained. Separate,
shallower channels carry the doubled wire and tails between X pairs. No head
or installed wire may project above the cap plane. Physical acceptance of the
whole installed wire/tail route belongs to assembly C3C, not this bare cap.
The representative normal wire route is only a diagnostic. The separate
whole-route capture proof is conditional on actual continuous-route acceptance
and fixed heads; it gives no wire/contact stop, structural, universal
head-clocking or elastic credit.
Each screw has one cylindrical through bore below its head counterbore.
That same bore clears the sourced underhead fillet; there is no intermediate
entry shelf and no preload/load-capacity certification.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
import ch_rocker_arm_tl_vn_oblique_pivot_lock_wire_spec as lock_wire
import ch_rocker_arm_tl_oblique_cap_wire_clearance as wire_capture
from _gtol_planar import PlanarFace
from _printed_tolerance import printed_band_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl

WIDTH = retention.CAP_WIDTH
LENGTH = retention.CAP_LENGTH
HEIGHT = retention.CAP_HEIGHT
POCKET_DIA = retention.CAP_POCKET_DIAMETER
POCKET_DEPTH = retention.CAP_POCKET_DEPTH
POCKET_CORNER_RADIUS_MAX = retention.CAP_POCKET_CORNER_RADIUS_MAX
APERTURE_DIA = retention.CAP_APERTURE_DIAMETER
BOLT_POINTS = retention.CAP_BOLT_CENTERS
HOLE_DIA = retention.CAP_BOLT_CLEARANCE_DIAMETER
COUNTERBORE_DIA = retention.CAP_COUNTERBORE_DIAMETER
COUNTERBORE_DEPTH = retention.CAP_COUNTERBORE_DEPTH
HEAD_RECESS_MIN = retention.CAP_HEAD_RECESS_MIN
HEAD_RECESS_MAX = retention.CAP_HEAD_RECESS_MAX
COUNTERBORE_FLOOR_MIN = retention.CAP_COUNTERBORE_FLOOR_MIN
CHANNEL_WIDTH = retention.CAP_WIRE_CHANNEL_WIDTH
CHANNEL_DEPTH = retention.CAP_WIRE_CHANNEL_DEPTH
REGISTER_POINTS = retention.CAP_REGISTER_CENTERS
REGISTER_DIA = retention.CAP_REGISTER_DIAMETER
REGISTER_BAND = retention.CAP_REGISTER_DIAMETER_BAND
REGISTER_PROJECTION = retention.CAP_REGISTER_PROJECTION
REGISTER_LOCATION_PLACES = retention.CAP_REGISTER_LOCATION_PLACES
REGISTER_PROJECTION_PLACES = retention.CAP_REGISTER_PROJECTION_PLACES
REGISTER_END_CHAMFER_MAX = retention.CAP_REGISTER_END_CHAMFER_MAX
TOTAL_HEIGHT = HEIGHT + REGISTER_PROJECTION
APERTURE_BAND = retention.CAP_APERTURE_BAND
# Existing blank authority: cad/config/parts/ch-rocker-arm-tl-oblique-pivot-cap.yaml,
# material_specification and process (including the minimum supplied length).
STOCK_THICKNESS = 0.625 * 25.4
STOCK_WIDTH = 2.5 * 25.4
POCKET_BAND = retention.CAP_POCKET_DIAMETER_BAND
DRILLED_BAND = retention.CAP_BOLT_CLEARANCE_BAND
STOCK_LENGTH_MIN = 3.5 * 25.4
SCREW_MAJOR_LIMITS = (hardware.SCREW_MAJOR_DIA_MIN, hardware.SCREW_MAJOR_DIA_MAX)
SCREW_THREAD_SOURCE_URL = hardware.SCREW_THREAD_SOURCE_URL
SCREW_SKU = hardware.SCREW_SKU
HEAD_DIAMETER_MAX = hardware.SCREW_HEAD_DIA_MAX
HEAD_BEARING_DIAMETER_MIN = retention.CAP_BOLT_HEAD_BEARING_DIAMETER_MIN
WIRE_DIAMETER = hardware.WIRE_DIA
if HOLE_DIA < SCREW_MAJOR_LIMITS[1]:
    raise AssertionError("the minimum cap clearance hole will not pass the sourced screw")

HEIGHT_PLACES = retention.CAP_HEIGHT_PLACES
OUTLINE_PLACES = retention.CAP_OUTLINE_PLACES
CENTER_LOCATION_PLACES = retention.CAP_CENTER_LOCATION_PLACES
CENTER_LOCATION_NOTE = "CENTRE X FROM COMMON -X STOCK EDGE; Y FROM COMMON -Y STOCK EDGE"
POSITION_PLACES = retention.CAP_BOLT_LOCATION_PLACES
COUNTERBORE_DIAMETER_PLACES = retention.CAP_COUNTERBORE_DIAMETER_PLACES
CHANNEL_PLACES = retention.CAP_WIRE_CHANNEL_PLACES
POSITION_TOLERANCE = printed_band_mm(POSITION_PLACES)
HEIGHT_TOLERANCE = printed_band_mm(HEIGHT_PLACES)
CHAMBER_EXCESS_MIN, CHAMBER_EXCESS_MAX = retention.CAP_CHAMBER_EXCESS
FITTED_POCKET_DEPTH_MAX = (
    retention.PIN_FLANGE_THICK
    + printed_band_mm(retention.PIN_FLANGE_THICK_PLACES)
    + CHAMBER_EXCESS_MAX
)

AXIS_NAME = "CaptureAxis"
BOTTOM_PLANE = "Front Plane"
TOP_PLANE = "CapTop"
BOLT_AXES = tuple(f"CapBoltAxis{index}" for index in range(1, 5))
SECTION_PLANE = "CapSectionPlane"
SECTION_REFERENCE = "CapSectionReference"
REFERENCE_SKETCHES = (SECTION_REFERENCE,)


def fitted_counterbore_acceptance(
    *, head_recess: float, whole_floor_min: float, forced_fit: bool = False,
) -> dict[str, float]:
    """Accept measured NORMAL highest-head recess and the actual whole floor.

    Recess is normal to the actual top with the identified screws seated.
    The minimum floor includes every full-width outward mouth. These are
    actual matched-hardware limits, not a tolerance on the REF model depth.
    An incompatible head/floor slope cannot be accepted by forcing the fit.
    """
    if not all(math.isfinite(value) for value in (head_recess, whole_floor_min)):
        raise ValueError("fitted counterbore measurements must be finite")
    if forced_fit:
        raise ValueError("fitted counterbore cannot require a forced fit")
    # Picometre-scale equality absorbs subtraction roundoff at an exact
    # limit; it is not an extra manufacturing allowance.
    below = head_recess < HEAD_RECESS_MIN and not math.isclose(head_recess, HEAD_RECESS_MIN, rel_tol=0.0, abs_tol=1e-12)
    above = head_recess > HEAD_RECESS_MAX and not math.isclose(head_recess, HEAD_RECESS_MAX, rel_tol=0.0, abs_tol=1e-12)
    if below or above:
        raise ValueError("fitted counterbore actual head recess is outside acceptance")
    if whole_floor_min < COUNTERBORE_FLOOR_MIN:
        raise ValueError("fitted counterbore whole floor/mouth is below acceptance")
    return {"head_recess": head_recess, "whole_floor_min": whole_floor_min}


def require_fitted_counterbore_geometry(
    *, height: float = HEIGHT, counterbore_depth: float = COUNTERBORE_DEPTH,
    actual_floor_min: float = COUNTERBORE_FLOOR_MIN,
) -> dict[str, float]:
    """Keep the representative native cut inside a constructive fitted window.

    The native mean-height head is normal and seated. Its cut must meet the
    actual recess acceptance and leave material even in a minimum-height cap.
    Separately, the shared helper proves a parallel-floor machining window
    for the full hardware/angular envelope; it does not waive actual fit-up.
    """
    if not all(math.isfinite(value) for value in (height, counterbore_depth, actual_floor_min)):
        raise ValueError("fitted counterbore geometry must be finite")
    if counterbore_depth <= 0.0:
        raise ValueError("fitted counterbore nominal depth must be positive")
    bounds = retention.fitted_counterbore_bounds(height=height)
    nominal_floor = height - HEIGHT_TOLERANCE - counterbore_depth
    accepted = fitted_counterbore_acceptance(
        head_recess=counterbore_depth - hardware.SCREW_HEAD_HEIGHT,
        whole_floor_min=min(actual_floor_min, nominal_floor),
    )
    if not bounds.depth_at_head_min <= counterbore_depth <= bounds.depth_at_head_max:
        raise ValueError("fitted counterbore nominal cut is outside the constructive fit window")
    return {
        "nominal_head_recess": accepted["head_recess"],
        "nominal_floor": nominal_floor,
        "parallel_cut_floor": bounds.parallel_cut_floor_min,
    }


def clearance_geometry(
    *, width: float = WIDTH, length: float = LENGTH, height: float = HEIGHT,
    counterbore_depth: float = COUNTERBORE_DEPTH,
    counterbore_dia: float = COUNTERBORE_DIA, pocket_dia: float = POCKET_DIA,
    hole_dia: float = HOLE_DIA, channel_width: float = CHANNEL_WIDTH,
    channel_depth: float = CHANNEL_DEPTH, points: tuple = BOLT_POINTS,
    fitted_pocket_depth_max: float = FITTED_POCKET_DEPTH_MAX,
    actual_floor_min: float = COUNTERBORE_FLOOR_MIN,
) -> dict[str, float]:
    """Source-only worst-case material margins; never a load certificate.

    Bolt positions are independent X/Y three-place limits from the actual
    pocket axis. Pocket/aperture centres are two-place coordinates from the
    common -X/-Y stock corner. The opposite edge can be a full outline band
    nearer that corner, independently of the centre error. Shared pocket
    location cancels from pocket-to-bolt/channel margins. Mouths open at X;
    no fictitious outside-X wall is counted. The actual whole-floor acceptance
    governs fitted recesses; the representative nominal cut is also checked
    for breakthrough, never assigned an invented depth tolerance.
    """
    cb_r = (counterbore_dia + printed_band_mm(COUNTERBORE_DIAMETER_PLACES)) / 2.0
    pocket_r = (pocket_dia + POCKET_BAND[0]) / 2.0
    hole_r = (hole_dia + DRILLED_BAND[0]) / 2.0
    channel_half = (channel_width + printed_band_mm(CHANNEL_PLACES)) / 2.0
    outline_band = printed_band_mm(OUTLINE_PLACES)
    center_band = printed_band_mm(CENTER_LOCATION_PLACES)
    near = tuple((abs(x) - POSITION_TOLERANCE, abs(y) - POSITION_TOLERANCE) for x, y in points)
    return {
        "counterbore_floor": min(actual_floor_min, height - HEIGHT_TOLERANCE - counterbore_depth),
        "channel_floor": height - HEIGHT_TOLERANCE - channel_depth - printed_band_mm(CHANNEL_PLACES),
        "chamber_roof": height - HEIGHT_TOLERANCE - fitted_pocket_depth_max,
        "counterbore_to_chamber": min(math.hypot(x, y) - cb_r - pocket_r for x, y in near),
        "hole_to_chamber": min(math.hypot(x, y) - hole_r - pocket_r for x, y in near),
        "mouth_to_chamber": min(math.hypot(x, max(y - cb_r, 0.0)) - pocket_r for x, y in near),
        "channel_to_chamber": min(y - channel_half - pocket_r for _, y in near),
        "counterbore_to_y_edge": length / 2.0 - outline_band - center_band - max(abs(y) for _, y in points) - POSITION_TOLERANCE - cb_r,
        "pocket_to_x_edge": width / 2.0 - outline_band - center_band - pocket_r,
    }


def require_clearance_geometry(**changes: float) -> dict[str, float]:
    require_fitted_counterbore_geometry(**{
        name: changes[name] for name in ("height", "counterbore_depth", "actual_floor_min")
        if name in changes
    })
    margins = clearance_geometry(**changes)
    for name, value in margins.items():
        if not math.isfinite(value) or value < 2.0:
            raise ValueError(f"cap {name}: {value:.4f} mm is below the 2 mm material target")
    return margins


def register_clearance_geometry(
    *, register_points: tuple = REGISTER_POINTS, register_dia: float = REGISTER_DIA,
    points: tuple = BOLT_POINTS, hole_dia: float = HOLE_DIA,
    pocket_dia: float = POCKET_DIA, aperture_dia: float = APERTURE_DIA,
    width: float = WIDTH, length: float = LENGTH, height: float = HEIGHT,
    counterbore_depth: float = COUNTERBORE_DEPTH, channel_depth: float = CHANNEL_DEPTH,
    actual_floor_min: float = COUNTERBORE_FLOOR_MIN,
) -> dict[str, float]:
    """Conservative register-root material, including vertically separate voids.

    Boss and bolt coordinates vary independently from the actual pocket axis.
    Head pockets, their full-depth outward mouths and wire channels are ABOVE
    the uncut seating plane; their XY silhouettes need not be disjoint from a
    register. Their surviving floor is the real separation, not an invented
    planar clearance.
    """
    radius = (register_dia + REGISTER_BAND[0]) / 2.0
    location = printed_band_mm(REGISTER_LOCATION_PLACES)
    relative = location + POSITION_TOLERANCE
    edge_error = printed_band_mm(OUTLINE_PLACES) + printed_band_mm(CENTER_LOCATION_PLACES) + location
    nearest_axis = min(math.hypot(max(abs(x) - location, 0.0), max(abs(y) - location, 0.0)) for x, y in register_points)
    return {
        "register_to_through_hole": min(
            math.hypot(max(abs(x - bx) - relative, 0.0), max(abs(y - by) - relative, 0.0))
            - radius - (hole_dia + DRILLED_BAND[0]) / 2.0
            for x, y in register_points for bx, by in points
        ),
        "register_to_pocket": nearest_axis - radius - (pocket_dia + POCKET_BAND[0]) / 2.0,
        "register_to_aperture": nearest_axis - radius - (aperture_dia + APERTURE_BAND[0]) / 2.0,
        "register_to_x_edge": width / 2.0 - edge_error - max(abs(x) for x, _ in register_points) - radius,
        "register_to_y_edge": length / 2.0 - edge_error - max(abs(y) for _, y in register_points) - radius,
        "register_to_head_void_floor": min(actual_floor_min, height - HEIGHT_TOLERANCE - counterbore_depth),
        "register_to_wire_void_floor": height - HEIGHT_TOLERANCE - channel_depth - printed_band_mm(CHANNEL_PLACES),
    }


def require_register_geometry(**changes: float) -> dict[str, float]:
    require_fitted_counterbore_geometry(**{
        name: changes[name] for name in ("height", "counterbore_depth", "actual_floor_min")
        if name in changes
    })
    margins = register_clearance_geometry(**changes)
    for name, value in margins.items():
        if not math.isfinite(value) or value < 2.0:
            raise ValueError(f"cap {name}: {value:.4f} mm is below the 2 mm material target")
    return margins


def require_fitted_head_capture(*, bounds: retention.CaptureBounds | None = None) -> float:
    """Use the actual fitted-head/captured proof, not an axial REF-depth stack."""
    if bounds is None:
        bounds = retention.capture_bounds()
    clearance = bounds.cap_head_running_clearance
    if not math.isfinite(clearance) or clearance <= 0.0:
        raise ValueError("cap fitted head loses captured running clearance")
    return clearance


def wire_clearance_geometry(
    *, wire_bounds: tuple[float, float] | None = None,
    counterbore_depth: float = COUNTERBORE_DEPTH,
    channel_depth: float = CHANNEL_DEPTH,
    head_seating_gap_max: float = retention.CAP_HEAD_SEATING_GAP_MAX,
) -> dict[str, float]:
    """Representative hand-formed side route in the NORMAL nominal cap pose.

    The unchanged provider includes its hardware-height/hole endpoints. The
    allowed underhead gap raises the head and route together; the shallowest
    channel includes its own ordinary depth band. The head-seat depth is the
    representative nominal cut, NOT a manufacturing depth interval.

    Positive values show this normal route's vertical feasibility only.
    They prove neither all accepted floor/head slopes nor contact-free cap
    motion, wire flexibility, channel stops or structural retention.
    """
    wire_low, wire_high = wire_bounds if wire_bounds is not None else lock_wire.swept_wire_z_bounds(hardware_limits=True)
    return {
        "formed_wire_below_cap": counterbore_depth - wire_high - head_seating_gap_max,
        "formed_wire_above_channel_floor": wire_low - (counterbore_depth - channel_depth + printed_band_mm(CHANNEL_PLACES)),
    }


def require_wire_clearance_geometry(**changes) -> dict[str, float]:
    """Guard the representative NORMAL source route, not captured motion."""
    margins = wire_clearance_geometry(**changes)
    for name, value in margins.items():
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"cap {name}: {value:.4f} mm fails representative NORMAL wire feasibility")
    return margins


def nominal_register_volume_mm3() -> float:
    """Two external cylinders, less the real 45-degree free-end chamfers."""
    radius, chamfer = REGISTER_DIA / 2.0, REGISTER_END_CHAMFER_MAX
    return len(REGISTER_POINTS) * math.pi * (
        radius**2 * REGISTER_PROJECTION - radius * chamfer**2 + chamfer**3 / 3.0
    )


def fitted_chamber_excess(pocket_depth: float, flange_thickness: float) -> float:
    """Actual opposing-face separation minus actual flange thickness."""
    excess = pocket_depth - flange_thickness
    if not CHAMBER_EXCESS_MIN - 1e-9 <= excess <= CHAMBER_EXCESS_MAX + 1e-9:
        raise ValueError("fitted chamber excess is outside its measured acceptance")
    return excess


def nominal_volume_mm3() -> float:
    """Exact stock/void union plus the integral, end-chamfered registers."""
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
    return total + nominal_register_volume_mm3()


GEOMETRY_MARGINS = require_clearance_geometry()
REGISTER_GEOMETRY_MARGINS = require_register_geometry()
FITTED_COUNTERBORE_GEOMETRY = require_fitted_counterbore_geometry()
FITTED_HEAD_RUNNING_CLEARANCE = require_fitted_head_capture()
WIRE_GEOMETRY_MARGINS = require_wire_clearance_geometry()
WIRE_CAPTURE_BOUNDS = wire_capture.require_wire_capture_geometry()
VOLUME_MM3 = nominal_volume_mm3()
DRAWING_DIMENSIONS = {
    "CapProfile": {"CapWidth", "CapLength"},
    "PocketProfile": {"PocketCenterX", "PocketCenterY", "PocketDia"},
    "ApertureProfile": {"ApertureCenterX", "ApertureCenterY", "ApertureDia"},
    "BoltProfile": {"BoltHoleDia", *(f"Bolt{index}{axis}" for index in range(1, 5) for axis in ("X", "Y"))},
    "HeadProfile": {"CounterboreDia"},
    "HeadRecesses": {"CounterboreDepth"},
    "WireProfile1": {"WireWidth"},
    "WireChannels1": {"WireDepth"},
    SECTION_REFERENCE: {"CapHeight", "PocketDepth"},
    "RegisterProfile": {"RegisterDia", *(f"Register{index}{axis}" for index in range(1, 3) for axis in ("X", "Y"))},
    "Registers": {"RegisterProjection"},
}
DRAWING_PRECISION = {
    "CapProfile": {"CapWidth": OUTLINE_PLACES, "CapLength": OUTLINE_PLACES},
    "PocketProfile": {"PocketCenterX": CENTER_LOCATION_PLACES, "PocketCenterY": CENTER_LOCATION_PLACES, "PocketDia": 2},
    "ApertureProfile": {"ApertureCenterX": CENTER_LOCATION_PLACES, "ApertureCenterY": CENTER_LOCATION_PLACES, "ApertureDia": 2},
    "BoltProfile": {"BoltHoleDia": 2, **{f"Bolt{index}{axis}": POSITION_PLACES for index in range(1, 5) for axis in ("X", "Y")}},
    "HeadProfile": {"CounterboreDia": COUNTERBORE_DIAMETER_PLACES},
    "HeadRecesses": {"CounterboreDepth": 2},
    "WireProfile1": {"WireWidth": CHANNEL_PLACES},
    "WireChannels1": {"WireDepth": CHANNEL_PLACES},
    SECTION_REFERENCE: {"CapHeight": HEIGHT_PLACES, "PocketDepth": 2},
    "RegisterProfile": {"RegisterDia": 2, **{f"Register{index}{axis}": REGISTER_LOCATION_PLACES for index in range(1, 3) for axis in ("X", "Y")}},
    "Registers": {"RegisterProjection": REGISTER_PROJECTION_PLACES},
}
DRAWING_PRECISION_BY_NAME = {name: places for row in DRAWING_PRECISION.values() for name, places in row.items()}
DIMENSION_CALLOUTS = {
    "PocketDia": (
        "RUNNING CHAMBER FOR\nMHA-CH-06-TL-23 FLANGE\n"
        f"FLOOR/WALL CORNER R{POCKET_CORNER_RADIUS_MAX:.2f} MAX"
    ),
    "PocketDepth": (
        "REF; DEPTH = ACTUAL MHA-CH-06-TL-23\n"
        f"FLANGE THK +{CHAMBER_EXCESS_MIN:.2f}/+{CHAMBER_EXCESS_MAX:.2f}, INCLUDING\n"
        "LOCAL FACE VARIATION; SCREWS SEATED;\n"
        "NO BEARING PRELOAD"
    ),
    "ApertureDia": "BORE THRU; CLEARS TL-23 CARRIER SEAT",
    "BoltHoleDia": f"4X DRILL THRU; {SCREW_SKU}",
    "CounterboreDia": (
        "4X COAXIAL WITH CLEARANCE HOLES;\n"
        "FULL WIDTH OPEN TO NEAREST X EDGE\n"
        f"WHOLE FLOOR THICKNESS {COUNTERBORE_FLOOR_MIN:.2f} MIN\n"
        "UNDER COUNTERBORE INCLUDING\n"
        "FULL-WIDTH EDGE OPENINGS"
    ),
    "CounterboreDepth": (
        f"4X REF; FIT SEATED {SCREW_SKU}\n"
        "HIGHEST HEAD RECESS NORMAL\n"
        "TO ACTUAL CAP TOP FACE\n"
        f"ACTUAL {HEAD_RECESS_MIN:.2f} TO {HEAD_RECESS_MAX:.2f}\n"
        "UPPER LIMIT SETS FIXED\n"
        "HEAD/WIRE HEIGHT FOR\n"
        "MHA-CH-06-TL-VN-76\n"
        "GROOVE CLEARANCE"
    ),
    "WireWidth": "2X X-PAIR WIRE GROOVE;\nCENTRED ON CAP-SCREW ROW;\nMHA-CH-06-TL-VN-76",
    "WireDepth": "2X NORMAL TO\nACTUAL CAP TOP FACE;\nDEPTH LIMITS OVER\nWHOLE GROOVE FLOOR",
    **{f"Bolt{index}{axis}": "FROM POCKET AXIS;\nLOCATES TL-22 CAP SCREW" for index in range(1, 5) for axis in ("X", "Y")},
    "RegisterDia": "2X INTEGRAL; LOCATES IN TL-22 RECEIVERS",
    "RegisterProjection": "2X BELOW BLOCK SEATING FACE;\nLOCATES IN TL-22 RECEIVERS;\nNO ROOT UNDERCUT",
    **{f"Register{index}{axis}": "FROM ACTUAL POCKET AXIS;\nLOCATES IN TL-22 RECEIVER" for index in range(1, 3) for axis in ("X", "Y")},
}
SURFACE_FINISHES = (SurfaceFinishControl("block_seat", SEAT_UM, PlanarFace((0.0, 0.0, -1.0), 0.0)),)
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
