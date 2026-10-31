"""Spec-dependent mounting, web and manufactured-stop checks for the platform.

The shared outline and base-fixed hardware placement stay in
``dt_cone_swing_platform_geometry`` without importing the post/shaft/tip specs.
Part and assembly owners consume these checks separately.
"""

from __future__ import annotations

import math

import _config
import dt_vn_cone_pivot_screw_spec as pivot_stock
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
import dt_swing_stop_screw_spec as stop_stock
from cone_pitch import COS_I as _COS_I, INCLINE_DEG, SIN_I as _SIN_I
from dt_cone_swing_platform_geometry import (
    EAST_HALF_S,
    HALF_WIDTH_N,
    NORTH_OVERHANG,
    NOTCH_EXIT_TRAVEL,
    PLATE_CORNERS,
    PLATE_LEN,
    PLATE_T,
    POST_LOCAL_Z,
    POST_MAIN_DIA,
    SLOT_E_X,
    SLOT_E_Z,
    SLOT_TX,
    SLOT_TZ,
    SLOT_W,
    WEST_HALF_N,
    WEST_HALF_S,
    _MOUTH_OVERSHOOT,
    swing_hardware_geometry,
)
from dt_cone_swing_platform_spec import (
    HOLDDOWN_CBORE_DIA,
    HOLDDOWN_CLEARANCE_DIA,
    HOLDDOWN_LOCAL_X,
    HOLDDOWN_LOCAL_Z,
    HOLDDOWN_STATION_TOL_MM,
    PIVOT_BEARING_RELIEF_DEPTH,
    PIVOT_BEARING_RELIEF_DIAMETER,
    PIVOT_BEARING_THICKNESS,
    POST_ATTACHMENT_SPACING,
    POST_MOUNT_STATION_TOL_MM,
    POST_MOUNT_TAP_DIA,
    POST_MOUNT_THREAD_DIA,
    UNIT,
)
from dt_cone_swing_platform_pivot_spec import PIVOT_HOLE_DIA
from dt_vn_cone_lock_knob_spec import HEAD_DIA as LOCK_HEAD_DIA

if abs(PLATE_T - PIVOT_BEARING_RELIEF_DEPTH - PIVOT_BEARING_THICKNESS) > 1e-9:
    raise AssertionError(
        "pivot bearing relief no longer leaves its specified thickness"
    )

# The post's vertical attachment holes are a world-X pair at +/-POST_MOUNT_HALF_PITCH.
# Undoing the engaged Ry(+INCLINE) placement gives the skewed pair in the
# platform's local (x, z), without a frozen former pivot station.
POST_MOUNT_HALF_PITCH = POST_ATTACHMENT_SPACING / 2.0
POST_MOUNT_X = POST_MOUNT_HALF_PITCH * _COS_I
POST_MOUNT_DZ = POST_MOUNT_HALF_PITCH * _SIN_I
POST_MOUNT_WEST_XZ = (POST_MOUNT_X, POST_LOCAL_Z + POST_MOUNT_DZ)
POST_MOUNT_EAST_XZ = (-POST_MOUNT_X, POST_LOCAL_Z - POST_MOUNT_DZ)

# Fail before COM if the v2 foot ever drifts off the tapered plate.  Distance
# is normal to each straight boundary, not merely an axis-aligned half-width.
_POST_R = POST_MAIN_DIA / 2.0
_POST_SOUTH_CLEAR = POST_LOCAL_Z - (NORTH_OVERHANG - PLATE_LEN)
_POST_FRAC = (NORTH_OVERHANG - POST_LOCAL_Z) / PLATE_LEN
_POST_EAST_HALF = HALF_WIDTH_N + (EAST_HALF_S - HALF_WIDTH_N) * _POST_FRAC
_POST_WEST_HALF = WEST_HALF_N + (WEST_HALF_S - WEST_HALF_N) * _POST_FRAC
_POST_EAST_NORMAL_CLEAR = _POST_EAST_HALF / math.hypot(
    1.0, (EAST_HALF_S - HALF_WIDTH_N) / PLATE_LEN
)
_POST_WEST_NORMAL_CLEAR = _POST_WEST_HALF / math.hypot(
    1.0, (WEST_HALF_S - WEST_HALF_N) / PLATE_LEN
)
POST_FOOT_CONTAINMENT = (
    min(_POST_SOUTH_CLEAR, _POST_EAST_NORMAL_CLEAR, _POST_WEST_NORMAL_CLEAR) - _POST_R
)
if POST_FOOT_CONTAINMENT < 0.25:
    raise AssertionError(
        f"v2 post foot has only {POST_FOOT_CONTAINMENT:.3f} mm platform containment"
    )
if POST_MOUNT_HALF_PITCH + POST_MOUNT_TAP_DIA / 2.0 > _POST_R:
    raise AssertionError("v2 post mount taps fall outside the casting foot")

# drawing-guidelines.md rule 17 (walls and webs) webs round the tip-block hold-down hole (user ruling 2026-09-29), at
# print worst: the outline and relief at .XX, the counterbore at its
# callout's .XXX, drilled holes at the DRILLED HOLES row, the hole's two
# stations (HoldDownX, HoldDownZ) at their explicit bands; the post taps at
# their explicit bands, judged at the thread major.
# The relief is on the TOP face only (there the hole is the drilled
# clearance), the counterbore on the UNDERSIDE only (there the pivot is the
# bare drilled bore); each web is judged on the face both share.  The plan
# corner rounds sweep toward their own corners, away from this hole, so the
# straight edges bound the outline web.
_XX_MM = printed_band_mm(2, unit=UNIT)
# MHA-FR-01 locates the stop and pivot taps on its own sheet.
_BASE_XX_MM = printed_band_mm(
    2, unit=drawing_unit("parts/fr-harmonic-base", _config.parts("fr-harmonic-base"))
)
_DRILL_OVERSIZE_MM = drilled_oversize_mm(unit=UNIT)
_HOLDDOWN_SHIFT = math.hypot(HOLDDOWN_STATION_TOL_MM, HOLDDOWN_STATION_TOL_MM)
_HOLDDOWN_THRU_R = (HOLDDOWN_CLEARANCE_DIA + _DRILL_OVERSIZE_MM) / 2.0
_HOLDDOWN_CBORE_R = (HOLDDOWN_CBORE_DIA + printed_band_mm(3, unit=UNIT)) / 2.0
_HOLDDOWN_PIVOT_DIST = math.hypot(HOLDDOWN_LOCAL_X, HOLDDOWN_LOCAL_Z)


def _edge_normal_distance(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Distance from ``point`` to the infinite line through plan points a, b."""
    (px, pz), (ax, az), (bx, bz) = point, a, b
    return abs((bx - ax) * (az - pz) - (ax - px) * (bz - az)) / math.hypot(
        bx - ax, bz - az
    )


_HOLDDOWN_XZ = (HOLDDOWN_LOCAL_X, HOLDDOWN_LOCAL_Z)
_SOUTH_Z = NORTH_OVERHANG - PLATE_LEN
HOLDDOWN_WEBS = {
    "pivot relief (top)": _HOLDDOWN_PIVOT_DIST
    - _HOLDDOWN_SHIFT
    - _HOLDDOWN_THRU_R
    - (PIVOT_BEARING_RELIEF_DIAMETER + _XX_MM) / 2.0,
    "pivot bore (underside)": _HOLDDOWN_PIVOT_DIST
    - _HOLDDOWN_SHIFT
    - _HOLDDOWN_CBORE_R
    - (PIVOT_HOLE_DIA + _DRILL_OVERSIZE_MM) / 2.0,
    **{
        f"post tap {side}": math.dist(_HOLDDOWN_XZ, tap)
        - _HOLDDOWN_SHIFT
        - math.hypot(POST_MOUNT_STATION_TOL_MM, POST_MOUNT_STATION_TOL_MM)
        - _HOLDDOWN_CBORE_R
        - POST_MOUNT_THREAD_DIA / 2.0
        for side, tap in (("west", POST_MOUNT_WEST_XZ), ("east", POST_MOUNT_EAST_XZ))
    },
    "north edge": NORTH_OVERHANG - HOLDDOWN_LOCAL_Z,
    "east edge": _edge_normal_distance(
        _HOLDDOWN_XZ, (-HALF_WIDTH_N, NORTH_OVERHANG), (-EAST_HALF_S, _SOUTH_Z)
    ),
    "west edge": _edge_normal_distance(
        _HOLDDOWN_XZ, (WEST_HALF_N, NORTH_OVERHANG), (WEST_HALF_S, _SOUTH_Z)
    ),
}
for _edge in ("north edge", "east edge", "west edge"):
    HOLDDOWN_WEBS[_edge] -= _HOLDDOWN_SHIFT + _HOLDDOWN_CBORE_R + _XX_MM
if min(HOLDDOWN_WEBS.values()) < WALL_TARGET_MM:
    raise AssertionError(
        f"tip-block hold-down leaves a web under the .080 in wall target: {HOLDDOWN_WEBS}"
    )


# ASME B1.1 class-2B receiver limits, not a title-row coordinate tolerance.
# https://itpbolt.com/wp-content/uploads/2015/08/Class-2B-Internal-Threads.pdf
RECEIVER_THREAD_LIMITS_SOURCE = (
    "https://itpbolt.com/wp-content/uploads/2015/08/Class-2B-Internal-Threads.pdf"
)
PIVOT_INTERNAL_PITCH_MAX_MM = 0.1672 * 25.4  # #10-24 UNC-2B
STOP_INTERNAL_PITCH_MAX_MM = 0.0991 * 25.4  # #4-40 UNC-2B


def seated_pivot_axis_offset_terms_mm() -> dict[str, float]:
    """Shoulder centre relative to the printed base tap, without coaxiality.

    The connected thread/shoulder bodies must intersect at their junction;
    their centres can be at most the sum of their outside radii apart.
    Full-form engagement bounds thread cock; use the whole supplied tail
    as an extrapolation lever rather than presuming runout at the shoulder.
    This is deliberately loose, not an invented supplier concentricity grade.
    """
    clearance = PIVOT_INTERNAL_PITCH_MAX_MM - pivot_stock.EXTERNAL_PITCH_DIA_MIN_MM
    return {
        "pivot thread radial fit": clearance / 2.0,
        "pivot thread extrapolation": (
            pivot_stock.THREAD_TAIL_LEN
            * clearance
            / pivot_stock.MIN_USEFUL_ENGAGEMENT_MM
        ),
        "connected shoulder/thread offset": (
            pivot_stock.SHOULDER_DIA + pivot_stock.THREAD_MAJOR_MAX_MM
        )
        / 2.0,
    }


def manufactured_p1_stop_enclosure() -> dict:
    """Finite seated P1 fence, conditional on the installed-joint inspections.

    At the returned angle a positive unslotted head disk lies strictly inside
    guaranteed, unbroken plate material for EVERY booked source corner.
    A continuously rotated, base-seated plate cannot reach that overlapping
    pose: its first physical stop occurs earlier. This is an upper enclosure,
    not the nominal mating angle or a claim that stock was inspected.

    No head/thread or shoulder/thread coaxiality is assumed. Full seating
    supplies the bearing plane; connected material supplies only a very loose
    centre offset. Lifting the plate is expressly outside this functional state.
    """
    from dt_cone_swing_platform_spec import PLATE_STOCK_BAND

    edge_break = max(edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT))
    core_height = stop_stock.UNSLOTTED_HEAD_HEIGHT_MIN_MM
    contact_height = (edge_break + core_height) / 2.0
    if (
        not edge_break
        < contact_height
        < min(
            core_height,
            PLATE_T - PLATE_STOCK_BAND - edge_break,
        )
    ):
        raise ValueError("seated stop has no positive unbroken plate/head height")
    # Half of the guaranteed underside bearing radius is safely within the
    # unslotted cylindrical side, leaving positive material in every direction.
    core_radius = stop_stock.HEAD_BEARING_RADIUS_MIN_MM / 2.0
    clearance = STOP_INTERNAL_PITCH_MAX_MM - stop_stock.EXTERNAL_PITCH_DIA_MIN_MM
    pivot_fit = (
        PIVOT_HOLE_DIA
        + _DRILL_OVERSIZE_MM
        - pivot_stock.SHOULDER_DIA
        - pivot_stock.SHOULDER_DIA_BAND[1]
    ) / 2.0
    terms = {
        "base stop and pivot coordinate errors": 2.0 * math.sqrt(2.0) * _BASE_XX_MM,
        "platform shoulder radial fit": pivot_fit,
        **seated_pivot_axis_offset_terms_mm(),
        "stop thread radial fit": clearance / 2.0,
        "stop thread extrapolation": (
            stop_stock.LENGTH_MAX_MM * clearance / stop_stock.MIN_USEFUL_ENGAGEMENT_MM
        ),
        "connected head/thread offset": (
            stop_stock.HEAD_DIA_MAX_MM + stop_stock.THREAD_MAJOR_MAX_MM
        )
        / 2.0,
    }
    uncertainty = sum(terms.values())
    hardware = swing_hardware_geometry(
        (0.0, 0.0),
        lock_head_dia=LOCK_HEAD_DIA,
        stop_contact_dia=stop_stock.CONTACT_DIA,
    )
    # Vertices have X +/-g, north Z +/-g, and south Z +/-2g because
    # PlateLenDim is measured from NorthEdgeZ. This Euclidean Hausdorff
    # erosion contains every straight-edge manufacturing corner.
    outline_erosion = math.sqrt(5.0) * _XX_MM
    corners = tuple((x, z) for _, x, z, _ in PLATE_CORNERS)

    def fence_margins(angle: float) -> dict[str, float]:
        theta = math.radians(INCLINE_DEG + angle)
        c, s = math.cos(theta), math.sin(theta)
        x, z = hardware.stop_xz
        point = (c * x - s * z, s * x + c * z)
        reach = uncertainty + core_radius
        margins = {}
        for i, a in enumerate(corners):
            b = corners[(i + 1) % len(corners)]
            cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (
                point[0] - a[0]
            )
            # The authored order is clockwise in (x,z).
            margins[f"edge {i}"] = -cross / math.dist(a, b) - reach - outline_erosion
        for i, (label, x, z, radius) in enumerate(PLATE_CORNERS):
            # Bound the rounded-corner cut by its corner-centred disk. For
            # every actual vertex (within the erosion radius), the smallest
            # possible interior angle follows from both perturbed edge rays.
            a, b = corners[i - 1], corners[(i + 1) % len(corners)]
            va, vb = (a[0] - x, a[1] - z), (b[0] - x, b[1] - z)
            theta = math.acos(
                sum(u * v for u, v in zip(va, vb)) / (math.hypot(*va) * math.hypot(*vb))
            )
            theta -= sum(
                math.asin(min(1.0, 2.0 * outline_erosion / math.hypot(*v)))
                for v in (va, vb)
            )
            if theta <= 0.0:
                raise ValueError("manufactured corner can collapse")
            cut_reach = (radius + _XX_MM) / math.tan(theta / 2.0)
            margins[f"corner {label}"] = (
                math.dist(point, (x, z)) - reach - outline_erosion - cut_reach
            )
        # Bound even openings on the other face: conservative, never credit
        # a through-fence where a hole, relief or lock notch removes it.
        holes = (
            (
                "pivot/relief",
                (0.0, 0.0),
                (PIVOT_BEARING_RELIEF_DIAMETER + _XX_MM) / 2.0,
                0.0,
            ),
            ("tip hold-down", _HOLDDOWN_XZ, _HOLDDOWN_CBORE_R, _HOLDDOWN_SHIFT),
            (
                "west post tap",
                POST_MOUNT_WEST_XZ,
                POST_MOUNT_THREAD_DIA / 2.0,
                math.sqrt(2.0) * POST_MOUNT_STATION_TOL_MM,
            ),
            (
                "east post tap",
                POST_MOUNT_EAST_XZ,
                POST_MOUNT_THREAD_DIA / 2.0,
                math.sqrt(2.0) * POST_MOUNT_STATION_TOL_MM,
            ),
        )
        for name, centre, radius, shift in holes:
            margins[name] = (
                math.dist(point, centre) - reach - radius - shift - edge_break
            )
        # The relief opens north; the notch's whole chord is a capsule.
        margins["open north relief"] = -point[1] - reach - _XX_MM
        notch_delta = (point[0] - SLOT_E_X, point[1] - SLOT_E_Z)
        along = max(
            0.0,
            min(
                NOTCH_EXIT_TRAVEL + _MOUTH_OVERSHOOT,
                notch_delta[0] * SLOT_TX + notch_delta[1] * SLOT_TZ,
            ),
        )
        margins["lock notch"] = (
            math.hypot(
                notch_delta[0] - along * SLOT_TX,
                notch_delta[1] - along * SLOT_TZ,
            )
            - reach
            - (SLOT_W + _XX_MM) / 2.0
            - math.sqrt(2.0) * _XX_MM
            - edge_break
        )
        return margins

    # Finding ANY strict, source-enclosed collision barrier suffices. The
    # 0.01-degree lattice is rounded outward, not a sampled clearance proof:
    # each tested pose itself encloses ALL manufacturing corners.
    for hundredths in range(math.ceil(hardware.disengage_deg * 100.0), 9000):
        upper = hundredths / 100.0
        margins = fence_margins(upper)
        if min(margins.values()) > 0.0:
            return {
                "angle_interval_deg": (0.0, upper),
                "nominal_disengage_deg": hardware.disengage_deg,
                "contact_height_mm": contact_height,
                "positive_head_core_radius_mm": core_radius,
                "source_offset_terms_mm": terms,
                "unbroken_fence_margins_mm": margins,
                "qualification": (
                    "conditional installed-joint enclosure: pivot full-form "
                    f"engagement >= {pivot_stock.MIN_USEFUL_ENGAGEMENT_MM:.2f} mm, "
                    "shoulder fully seated; stop full-form engagement >= "
                    f"{stop_stock.MIN_USEFUL_ENGAGEMENT_MM:.2f} mm, head fully "
                    "seated; platform remains seated throughout P1; not stock inspection evidence"
                ),
            }
    raise ValueError(
        "positive sourced stop material has no certified unbroken plate fence"
    )
