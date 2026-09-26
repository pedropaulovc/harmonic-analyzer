r"""Reproduction script: cone swing platform (book ch. 12, p. 18 "pivot").

The wedge-shaped plate the whole cone-gear set rides on. The book's
top-down photo (p. 18) labels the TIP end "pivot": the merged green
column (big-end journal + crank pedestal, ONE casting), the cone shaft
and the tip adjuster-carrier block all stand ON this plate, and the whole unit --
crank, 16T pinion, chain wheel included -- swings horizontally about a
vertical axis near the shaft's thin tip to dis/engage the cone set from
the cylinder set (video 4/4, engage/disengage stills). Swing separation
grows with distance from the pivot, so pivoting at the TIP gives the
big-end gears the largest throw.

Plan shape is the p.18 wedge, ASYMMETRIC about the shaft line: the east
side tapers 16 -> 24 half-width, the west side flares out to 37 so the
run from the swing pivot to the cone-lock-knob is SOLID plate (no lobe
protrusion); the open LOCK NOTCH cuts straight into the west edge.  The
west edge's north end is derived from the tip block's full west reach
(I31).  The
four plan corners are rounded, echoing the hardware each sits beside
(pivot screw head at the north end, the green column at the south-east,
the lock-knob head at the south-west). A native close-clearance Ø6.756 pivot
hole clears the stock Ø6.35 shoulder. A 10.50-wide x 0.25-deep top relief,
round-ended about the pivot and open through the north edge (rule-12 W18),
reduces only the local bearing thickness to 6.10, preserving 0.25 running
axial clearance without lowering the plate or its mounted hardware.

The shortened envelope and paired 1/4-20 post mounts are the direct platform
cascade from ``cone-pivot-post-v2.SLDPRT``.  Its 42.011 mm casting foot is
centred at cone station -39.9014; the post's world-X hole pair is transformed
into this plate's engaged local frame so the two native tapped holes remain
coaxial after Ry(+12.5182 deg) placement.

The asymmetric flare keeps the part CHIRAL; the assembly places it at
Ry(+INCLINE), under which part-local +x tips machine WEST at the engaged
pose -- the west flare and notch are authored at +x (constants note below).

Named refs for the assembly: "swing pivot" (Axis1, vertical through the
origin), the CRANK AXIS (Axis2 -- the machine-z crank line the
crankshaft mates to, built from an angled plane so it swings WITH the
plate), and "PlateTop" (datum plane on the top face -- the riders'
seat mate).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_swing_platform.py
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
import sys
from typing import Any

from _common import (
    PANEL_BLACK,
    SketchDims,
    _early_bound,
    _read_member,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    name_dimensions,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _holes import wizard_holes
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from build_cone_lock_knob import HEAD_DIA as LOCK_HEAD_DIA
from build_cone_lock_knob import STUD_DIA as LOCK_STUD_DIA
from cone_swing_platform_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FEATURE_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    LOCK_STUD_MAJOR,
    NOTCH_ENGAGE_OVERTRAVEL,
    NOTCH_MOUTH_ANGLE_DEG,
    NOTCH_VIEW_NOTE,
    NOTCH_W,
    NOTCH_W_BAND,
    PIVOT_BEARING_RELIEF_DEPTH,
    PIVOT_BEARING_RELIEF_DIAMETER,
    PIVOT_BEARING_THICKNESS,
    PIVOT_HOLE_DIA,
    PIVOT_HOLE_SPEC,
    PIVOT_HEAD_RADIAL_CLEARANCE,  # noqa: F401 -- public verify contract
    PIVOT_RELIEF_FIT_REQUIREMENT,
    POST_MOUNT_ENGAGEMENT_NOTE,
    PLATE_THICKNESS,
    POST_ATTACHMENT_SPACING,
    POST_BLOCK_DIA,
    POST_MOUNT_SPEC,
    POST_MOUNT_TAP_DIA,
    PROFILE_VIEW_NOTE,
    SURFACE_FINISHES,
    TIP_BLOCK_EDGE_MARGIN,
    TIP_BLOCK_NORTH_REACH_Z,
    TIP_BLOCK_WEST_REACH,
    TIP_CBORE_DEPTH,
    TIP_CBORE_W,
    TIP_CBORE_W_BAND,
    TIP_CBORE_W_MAX,
    TIP_SCREW_HALF_TRAVEL,
    TIP_SCREW_LOCAL_Z,
    TIP_SLOT_W,
    TIP_SLOT_W_BAND,
    TITLE_BLOCK_BAND_BY_PLACES,
    assert_notch_stud_stack,
)
from _fit_limits import deviations
from _hole_spec import HoleSpec
from cone_post_dowel_spec import (
    DOWEL_REAM_TOLERANCE_MM,
    PLATE_DOWEL_REAM_DIA,
    POST_DOWEL_PLATE_XZ,
)

PART_NAME = "cone-swing-platform"
MATERIAL = "Plain Carbon Steel"  # black-finished steel plate (p.18 dark wedge)

PLATE_T = PLATE_THICKNESS  # 1/4" plate
HALF_WIDTH_N = 16.0  # north (pivot/tip) half-width, EAST side (the lock-slot
# region keeps its full seat)
EAST_HALF_S = 24.0  # widened for the v2 post's Ø42.011 casting foot
WEST_HALF_S = 37.0  # west half-width at the south end: the flare that makes
# the pivot -> lock-knob line solid plate (covers the notch seat + collar)
NORTH_OVERHANG = 7.0  # pivot -> north edge (plate continues past the pivot)
# Native 1/4-in close-clearance Hole Wizard feature over the stock Ø6.35
# shoulder; cone_swing_platform_spec owns its table identity and diameter.

THROUGH_CUT_DEPTH = 40.0  # mid-plane total (both_directions splits it half per
# side of the sketch plane); must exceed 2x any extent crossed
if abs(PLATE_T - PIVOT_BEARING_RELIEF_DEPTH - PIVOT_BEARING_THICKNESS) > 1e-9:
    raise AssertionError(
        "pivot bearing relief no longer leaves its specified thickness"
    )

INCLINE_DEG = 12.5182  # cone-axis plan incline (the assembly's ROT_Y_INCLINE)
_SIN_I = math.sin(math.radians(INCLINE_DEG))
_COS_I = math.cos(math.radians(INCLINE_DEG))

# --- cone-pivot-post-v2 attachment footprint -------------------------------
# The rederived casting is centred at cone station -39.90136099793 while the
# plate origin/pivot remains station 196.  Its two vertical attachment holes
# are a world-X pair at +/-13.44352 mm.  Undoing the engaged Ry(+INCLINE)
# placement gives this skewed pair in the platform's local (x, z) frame.
POST_STATION = -39.90136099793
PIVOT_STATION = 152.27232594770453
POST_MAIN_DIA = POST_BLOCK_DIA
POST_LOCAL_Z = POST_STATION - PIVOT_STATION
POST_SOUTH_MARGIN = 3.175  # 1/8 in clearance beyond the post's south rim
PLATE_SOUTH_Z = POST_LOCAL_Z - POST_MAIN_DIA / 2.0 - POST_SOUTH_MARGIN
PLATE_LEN = NORTH_OVERHANG - PLATE_SOUTH_Z
# North half-width, WEST side (I31 item 8, Main 2026-09-25: widen the plate,
# do not narrow the block's travel).  The west edge runs straight from here
# to WEST_HALF_S.  At the tip block's northmost station it keeps
# TIP_BLOCK_EDGE_MARGIN outside the block's worst-case west reach (every
# float and location band, cone_swing_platform_spec) with the outline itself
# at the worst of its printed .X bands: both west corners' half-widths
# (NorthWestX, SouthWestX), the north edge's station (NorthEdgeZ) and the
# length to the south edge (PlateLenDim).  Rounded up to the outline's one
# place.  The drive train proves the arbor pedestals and the base clear the
# widened edge over the whole p1 swing.
OUTLINE_BAND = 0.8  # .X title-block band on every outline dimension
_OUTLINE_BAND_CASES = tuple(
    itertools.product((-OUTLINE_BAND, OUTLINE_BAND), repeat=4)
)


def edge_half_width_worst(half_n: float, half_s: float, z_local: float) -> float:
    """Narrowest half-width of one plan side (its north and south corner
    half-widths given) at plate-local z, over the outline's .X bands."""
    worst = math.inf
    for d_xn, d_xs, d_zn, d_len in _OUTLINE_BAND_CASES:
        z_n = NORTH_OVERHANG + d_zn
        z_s = z_n - (PLATE_LEN + d_len)
        run = (z_n - z_local) / (z_n - z_s)
        x_n, x_s = half_n + d_xn, half_s + d_xs
        worst = min(worst, x_n + (x_s - x_n) * run)
    return worst


def west_edge_x_worst(west_half_n: float, z_local: float) -> float:
    """Narrowest west edge at plate-local z over the outline's .X bands."""
    return edge_half_width_worst(west_half_n, WEST_HALF_S, z_local)


def _west_half_n_required(reach: float, z_local: float) -> float:
    required = -math.inf
    for d_xn, d_xs, d_zn, d_len in _OUTLINE_BAND_CASES:
        z_n = NORTH_OVERHANG + d_zn
        z_s = z_n - (PLATE_LEN + d_len)
        run = (z_n - z_local) / (z_n - z_s)
        required = max(
            required, (reach - (WEST_HALF_S + d_xs) * run) / (1.0 - run) - d_xn
        )
    return required


TIP_WEST_EDGE_NEED = TIP_BLOCK_WEST_REACH + TIP_BLOCK_EDGE_MARGIN
_WEST_HALF_N_REQUIRED = _west_half_n_required(TIP_WEST_EDGE_NEED, TIP_BLOCK_NORTH_REACH_Z)
WEST_HALF_N = math.ceil(_WEST_HALF_N_REQUIRED * 10.0 - 1e-6) / 10.0
TIP_WEST_EDGE_MARGIN_WORST = (
    west_edge_x_worst(WEST_HALF_N, TIP_BLOCK_NORTH_REACH_Z) - TIP_BLOCK_WEST_REACH
)
if TIP_WEST_EDGE_MARGIN_WORST < TIP_BLOCK_EDGE_MARGIN - 1e-9:
    raise AssertionError("tip block reaches past the worst-case west edge")
# The 6.5 counterbored slot's webs at the printed worst case (U27: 2.0
# target, 1.5 floor): to both plan edges across the slot's station band, and
# along the axis to the pivot's bearing relief.  The slot's station
# (TipSlotZ) and end centres (TipSlot*Cx) print .XX.
_TIP_XX = 0.51
_CBORE_HALF_Z = TIP_CBORE_W_MAX / 2.0 + _TIP_XX
_CBORE_REACH_X = TIP_SCREW_HALF_TRAVEL + _TIP_XX + TIP_CBORE_W_MAX / 2.0
TIP_CBORE_WEBS = {
    "west edge": min(
        west_edge_x_worst(WEST_HALF_N, TIP_SCREW_LOCAL_Z + dz)
        for dz in (-_CBORE_HALF_Z, _CBORE_HALF_Z)
    )
    - _CBORE_REACH_X,
    "east edge": min(
        edge_half_width_worst(HALF_WIDTH_N, EAST_HALF_S, TIP_SCREW_LOCAL_Z + dz)
        for dz in (-_CBORE_HALF_Z, _CBORE_HALF_Z)
    )
    - _CBORE_REACH_X,
    "pivot relief": -TIP_SCREW_LOCAL_Z
    - _CBORE_HALF_Z
    - (PIVOT_BEARING_RELIEF_DIAMETER / 2.0 + _TIP_XX),
}
for _web_name, _web in TIP_CBORE_WEBS.items():
    if _web < 2.0:
        raise AssertionError(
            f"tip counterbored slot leaves {_web:.3f} to the {_web_name} (< 2.0, U27)"
        )
POST_MOUNT_HALF_PITCH = POST_ATTACHMENT_SPACING / 2.0
POST_MOUNT_X = POST_MOUNT_HALF_PITCH * _COS_I
POST_MOUNT_DZ = POST_MOUNT_HALF_PITCH * _SIN_I
POST_MOUNT_WEST_XZ = (POST_MOUNT_X, POST_LOCAL_Z + POST_MOUNT_DZ)
POST_MOUNT_EAST_XZ = (-POST_MOUNT_X, POST_LOCAL_Z - POST_MOUNT_DZ)

# #917 S1 dowel pair (cone_post_dowel_spec): on the post's crank-axis diameter
# -- the direction Ry(+INCLINE) maps to machine z -- at the screws' pitch
# radius, north then south.  The spec carries the ruled three-place literal;
# it must sit on the post's actual pattern.
POST_DOWEL_PATTERN_ERROR = max(
    abs(literal - exact)
    for (x, z), sign in zip(POST_DOWEL_PLATE_XZ, (1.0, -1.0), strict=True)
    for literal, exact in (
        (x, -sign * POST_MOUNT_HALF_PITCH * _SIN_I),
        (z, POST_LOCAL_Z + sign * POST_MOUNT_HALF_PITCH * _COS_I),
    )
)
if POST_DOWEL_PATTERN_ERROR > 6e-4:
    raise AssertionError(
        f"POST_DOWEL_PLATE_XZ is {POST_DOWEL_PATTERN_ERROR:.4f} off the post's pattern"
    )
# The named reference axis through each ream, for the drive-train's pin mates.
POST_DOWEL_AXES = (
    ("post dowel north", POST_DOWEL_PLATE_XZ[0]),
    ("post dowel south", POST_DOWEL_PLATE_XZ[1]),
)
# Reamed through the plate from underneath, at the reamer's nominal; its
# +.0002/0 band rides the hole feature.
PLATE_DOWEL_HOLE_SPEC = HoleSpec(
    "drilled_fractional",
    "1/8",
    overrides_mm={"HoleDiameter": PLATE_DOWEL_REAM_DIA},
)

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

# The open-ended lock notch cuts from the engaged stud seat straight out
# through the plate's WEST edge. The cone-lock-knob stud is fixed to the base;
# on disengage the plate swings until its edge passes the stud and collar.
# Tightened with no plate under it, the collar fences the mouth and locks the
# plate disengaged; tightened on the plate it clamps the engaged pose.
# The stud runs out along the swing arc's CHORD (sagitta ~0.02 at R~208
# over the 2.76 to the mouth); the notch is cut within half a degree of it,
# at the whole-degree mouth angle below, and the spec's stud stack carries
# both against the O6.35-stud-in-8.0 clearance.
#
# LOCAL-FRAME CONVENTION: the assembly places this part at Ry(+INCLINE)
# (train._plate_local_to_machine), under which local +x maps to machine WEST
# at the engaged pose -- every west-side feature below (the flare, the lock
# notch) is authored at local +x, east-side features at local -x.
SLOT_W = 8.0  # Ø6.35 stud clearance plus chord-vs-arc slack
# The stock O25.4 head must clear both the O42.011 post foot and the nearby
# T120/64T gear row.  The northern solution beside the post clears the post but
# overlaps both gears; use the southern solution and move the stud west until
# the head retains the established 2 mm post gap with useful plate edge stock.
SLOT_E_X = 33.0
LOCK_HEAD_POST_CLEARANCE = 2.0
_LOCK_POST_C2C = LOCK_HEAD_DIA / 2.0 + POST_MAIN_DIA / 2.0 + LOCK_HEAD_POST_CLEARANCE
SLOT_E_Z = POST_LOCAL_Z - math.sqrt(_LOCK_POST_C2C**2 - SLOT_E_X**2)
SLOT_R = math.hypot(SLOT_E_X, SLOT_E_Z)
# The plate swings toward disengage (big end away from the drum), so in PLATE
# coords the fixed stud sweeps the INVERSE rotation: unit direction (-z, x)/R
# at E -- outward toward the west edge (+x), slightly north (+z).
_SLOT_TX, _SLOT_TZ = -SLOT_E_Z / SLOT_R, SLOT_E_X / SLOT_R


def _west_edge_x(z_local: float) -> float:
    """Authored x of the west taper edge at local z (linear WEST_HALF_N -> 37)."""
    return (
        WEST_HALF_N
        + (WEST_HALF_S - WEST_HALF_N) * (NORTH_OVERHANG - z_local) / PLATE_LEN
    )


def _exit_travel(x0: float, z0: float, ux: float, uz: float) -> float:
    """Travel from (x0, z0) along the unit direction (ux, uz) to the west edge."""
    # solve x0 + t*ux = _west_edge_x(z0 + t*uz) for t (both sides linear)
    k = (WEST_HALF_S - WEST_HALF_N) / PLATE_LEN
    return (WEST_HALF_N + k * (NORTH_OVERHANG - z0) - x0) / (ux + k * uz)


def _chord_exit_travel(x0: float, z0: float) -> float:
    """Stud travel from (x0, z0) along the chord to the west taper edge."""
    return _exit_travel(x0, z0, _SLOT_TX, _SLOT_TZ)


# Stud travel from the engaged seat to the mouth. Past this the stud is out of
# the plate; the shared hardware calculation adds the exact collar radius to
# derive the disengaged pose.
NOTCH_EXIT_TRAVEL = _chord_exit_travel(SLOT_E_X, SLOT_E_Z)
# The stud's chord off the plate's east-west line (it climbs north as it
# opens through the west edge).
NOTCH_RUN_DEG = math.degrees(math.atan2(_SLOT_TZ, _SLOT_TX))

# The print sets the notch's run by its angle to the plate's WEST edge at the
# mouth (cone_swing_platform_spec.NOTCH_MOUTH_ANGLE_DEG): both legs are real
# edges, the vertex the mouth's SOUTH corner, whose material wedge -- the
# inward rail against the edge running south -- is the acute one.  The stud's
# chord makes NOTCH_CHORD_MOUTH_DEG (87.38) with it; the spec rounds that to
# the whole degree and the notch is CUT along the rounded angle (direction
# NOTCH_CUT_U), so a protractor on the part reads the printed number.  The
# stud still runs the chord: the rounding offset is a term of the stud stack.
_WEST_EDGE_DX = WEST_HALF_S - WEST_HALF_N
_WEST_EDGE_DZ = -PLATE_LEN
WEST_EDGE_LEN = math.hypot(_WEST_EDGE_DX, _WEST_EDGE_DZ)
_EDGE_SX, _EDGE_SZ = _WEST_EDGE_DX / WEST_EDGE_LEN, _WEST_EDGE_DZ / WEST_EDGE_LEN
NOTCH_CHORD_MOUTH_DEG = math.degrees(
    math.atan2(
        _EDGE_SX * -_SLOT_TZ - _EDGE_SZ * -_SLOT_TX,
        _EDGE_SX * -_SLOT_TX + _EDGE_SZ * -_SLOT_TZ,
    )
)
if round(abs(NOTCH_CHORD_MOUTH_DEG)) != NOTCH_MOUTH_ANGLE_DEG:
    raise AssertionError(
        f"the stud's chord makes {abs(NOTCH_CHORD_MOUTH_DEG):.2f} deg with the west "
        f"edge; the spec prints {NOTCH_MOUTH_ANGLE_DEG:g} -- re-derive it"
    )
NOTCH_MOUTH_ANGLE_OFFSET_DEG = NOTCH_MOUTH_ANGLE_DEG - abs(NOTCH_CHORD_MOUTH_DEG)
_CUT_INWARD = math.atan2(_EDGE_SZ, _EDGE_SX) + math.copysign(
    math.radians(NOTCH_MOUTH_ANGLE_DEG), NOTCH_CHORD_MOUTH_DEG
)
NOTCH_CUT_U = (-math.cos(_CUT_INWARD), -math.sin(_CUT_INWARD))
NOTCH_CUT_DEG = math.degrees(math.atan2(NOTCH_CUT_U[1], NOTCH_CUT_U[0]))
# The reference edge's own direction error: its two ends are located at the
# outline's grade (NorthWestX, SouthWestX), one band each, over its length.
WEST_EDGE_ANGLE_ERROR_DEG = math.degrees(
    math.atan(
        2.0
        * TITLE_BLOCK_BAND_BY_PLACES[
            min(
                DRAWING_PRECISION["PlateProfile"][name]
                for name in ("NorthWestX", "SouthWestX")
            )
        ]
        / WEST_EDGE_LEN
    )
)
_MOUTH_OVERSHOOT = 4.0  # rails run past the edge so the mouth opens clean
# The closed end's full R is centred NOTCH_ENGAGE_OVERTRAVEL deeper than the
# stud's engaged seat, back along the cut (#917 S1): the fit-up may swing the
# platform past the seat.  SLOT_E itself -- where the base stud stands -- and
# the stud's exit travel to the mouth are unchanged.
NOTCH_CAP_E_XZ = (
    SLOT_E_X - NOTCH_ENGAGE_OVERTRAVEL * NOTCH_CUT_U[0],
    SLOT_E_Z - NOTCH_ENGAGE_OVERTRAVEL * NOTCH_CUT_U[1],
)


def notch_cut_points() -> dict[str, tuple[float, float]]:
    """The lock notch's cut outline, local (x, z).

    Closed-end corners either side of the cap centre (NOTCH_CAP_E_XZ), the
    rails' crossings of the west edge (the mouth corners), and the outboard
    ends _MOUTH_OVERSHOOT past the SOUTH crossing, square to the rails.
    """
    ux, uz = NOTCH_CUT_U
    cx, cz = NOTCH_CAP_E_XZ
    px, pz = -uz * SLOT_W / 2.0, ux * SLOT_W / 2.0  # toward the north rail
    closed_s = (cx - px, cz - pz)
    closed_n = (cx + px, cz + pz)
    a_s = _exit_travel(*closed_s, ux, uz)
    a_n = _exit_travel(*closed_n, ux, uz)
    out = a_s + _MOUTH_OVERSHOOT
    return {
        "closed_s": closed_s,
        "mouth_s": (closed_s[0] + a_s * ux, closed_s[1] + a_s * uz),
        "out_s": (closed_s[0] + out * ux, closed_s[1] + out * uz),
        "out_n": (closed_n[0] + out * ux, closed_n[1] + out * uz),
        "mouth_n": (closed_n[0] + a_n * ux, closed_n[1] + a_n * uz),
        "closed_n": closed_n,
    }


NOTCH_CUT_POINTS = notch_cut_points()
# In-material length of the cut on its centreline: the rails cross a straight
# edge symmetrically about it, so the in-plate area is exactly width x this.
NOTCH_CUT_TRAVEL = _exit_travel(*NOTCH_CAP_E_XZ, *NOTCH_CUT_U)
if (
    min(
        math.dist(NOTCH_CUT_POINTS["mouth_n"], NOTCH_CUT_POINTS["out_n"]),
        math.dist(NOTCH_CUT_POINTS["mouth_s"], NOTCH_CUT_POINTS["out_s"]),
    )
    < _MOUTH_OVERSHOOT / 2.0
):
    raise AssertionError("lock notch rails do not run clear past the west edge")

# The cut's width IS the spec's banded notch width, and the stud is the lock
# knob's; the stud must seat and run out at the printed bands.
if SLOT_W != NOTCH_W:
    raise AssertionError(f"SLOT_W {SLOT_W} != spec NOTCH_W {NOTCH_W}")
if abs(LOCK_STUD_MAJOR - LOCK_STUD_DIA) > 1e-9:
    raise AssertionError(
        f"spec LOCK_STUD_MAJOR {LOCK_STUD_MAJOR} != lock knob STUD_DIA {LOCK_STUD_DIA}"
    )
NOTCH_STUD_STACK = assert_notch_stud_stack(
    NOTCH_CUT_DEG,
    NOTCH_EXIT_TRAVEL,
    SLOT_R,
    NOTCH_MOUTH_ANGLE_OFFSET_DEG,
    WEST_EDGE_ANGLE_ERROR_DEG,
)


def _as_construction(adapter: Any, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if _read_member(segment, "ConstructionGeometry") is not True:
        raise RuntimeError(f"{entity_id} did not remain construction geometry")


def notch_mouth_angle_text_point() -> tuple[float, float]:
    """Sketch (x, y) of the angle's text: 3 mm out along the bisector of the
    south mouth corner's material wedge (inward rail vs the edge running
    south).  A Top-plane sketch's y is local -z."""
    vx, vz = NOTCH_CUT_POINTS["mouth_s"]
    bx, bz = _EDGE_SX - NOTCH_CUT_U[0], _EDGE_SZ - NOTCH_CUT_U[1]
    b = math.hypot(bx, bz)
    return (vx + 3.0 * bx / b, -(vz + 3.0 * bz / b))


async def _add_notch_mouth_angle(
    adapter: Any, edge_line: str, rail_line: str, dims: SketchDims
) -> None:
    """Author the notch's DRIVING mouth angle between the west-edge reference
    and the south rail, at their shared mouth corner.

    ``AddSpecificDimension`` picks whichever of the four angle regions holds
    its text point, so the text goes on the material wedge's bisector, with
    sketch y in both the y and the -z slots (a Top-plane sketch's y is model
    -Z).  The value is read back at once, so the obtuse supplement fails the
    build instead of printing 92 degrees; the rotation is still free when the
    angle is added, so it drives the rails.
    """
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    text_x, text_y = (c / 1000.0 for c in notch_mouth_angle_text_point())
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [edge_line, rail_line], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_x,
        text_y,
        -text_y,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"notch mouth angle: AddSpecificDimension failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    expected_rad = math.radians(NOTCH_MOUTH_ANGLE_DEG)
    actual_rad = abs(float(_read_member(dimension, "SystemValue")))
    if abs(actual_rad - expected_rad) > 1e-8:
        raise RuntimeError(
            f"notch mouth angle measured {math.degrees(actual_rad):.6f} deg, "
            f"expected {NOTCH_MOUTH_ANGLE_DEG:.6f} deg"
        )
    driven_state = int(_read_member(dimension, "DrivenState"))
    if driven_state != 2:  # swDimensionDrivenState_e.swDimensionDriving
        raise RuntimeError(
            f"notch mouth angle is not driving (DrivenState {driven_state})"
        )
    dims.record("NotchMouthAngle")


# The tip slot's end centres are dimensioned to a construction centerline on
# the cone axis (sketch x = 0), from the origin to this far past the slot's
# far (south) edge -- not to the origin.  Detail B is centred on the slot,
# 27.7 south of the origin, and a detail view drops every model dimension
# whose reference falls outside its crop circle (farm leaf 7ab69742b:
# "missing model dimensions: ['TipSlotEastCx', 'TipSlotWestCx']"); the
# centerline's end lies inside it.
TIP_SLOT_AXIS_RUNOUT = 2.0

# Each tip-slot sketch dimension (name after the prefix, in creation order)
# and its two sketch references, named as in tip_slot_sketch_points.
TIP_SLOT_DIMENSION_REFERENCES: dict[str, tuple[str, str]] = {
    "AxisLen": ("axis_start", "axis_end"),
    "EastCx": ("east_center", "axis_end"),
    "Z": ("east_center", "origin"),
    "WestCx": ("west_center", "axis_end"),
    "W": ("line_a_start", "line_b_end"),
}


def tip_slot_sketch_points(width: float) -> dict[str, tuple[float, float]]:
    """The tip slot sketch's named points, Top-plane sketch mm (y is part -Z).

    ``axis_start``/``axis_end`` are the cone-axis centerline's ends; the
    builder draws and dimensions from these very coordinates."""
    c, r = TIP_SCREW_HALF_TRAVEL, width / 2.0
    y = -TIP_SCREW_LOCAL_Z  # sketch y -> part -Z
    return {
        "origin": (0.0, 0.0),
        "axis_start": (0.0, 0.0),
        "axis_end": (0.0, y + r + TIP_SLOT_AXIS_RUNOUT),
        "east_center": (-c, y),
        "west_center": (c, y),
        "line_a_start": (-c, y - r),
        "line_b_end": (-c, y + r),
    }


async def _sketch_tip_screw_slot(
    adapter, *, width: float, label: str, prefix: str
) -> SketchDims:
    """Top-plane straight slot across the cone axis at the tip-block station.

    Two lines and two end arcs whose centres sit TIP_SCREW_HALF_TRAVEL either
    side of the pivot's cone-axis line, so the shop sets each end from the
    pivot centre.  That line is a construction centerline on sketch x = 0,
    started at the origin, and each end centre is dimensioned horizontally to
    its far end (TIP_SLOT_AXIS_RUNOUT past the slot), which detail B's crop
    takes in; the station (``Z``) stays dimensioned to the origin for the
    plan.  The width is dimensioned between the two lines (it is the
    end-mill size); tangency makes the arcs full radius."""
    dims = SketchDims()
    c, r = TIP_SCREW_HALF_TRAVEL, width / 2.0
    y = -TIP_SCREW_LOCAL_Z  # sketch y -> part -Z
    points = tip_slot_sketch_points(width)
    check(f"create_sketch {label}", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    line_a = check(f"{label} line a", await adapter.add_line(-c, y - r, c, y - r))
    arc_w = check(
        f"{label} west arc", await adapter.add_arc(c, y, c, y - r, c, y + r)
    )
    line_b = check(f"{label} line b", await adapter.add_line(c, y + r, -c, y + r))
    arc_e = check(
        f"{label} east arc", await adapter.add_arc(-c, y, -c, y + r, -c, y - r)
    )
    # Direct-to-DB like the profile: a vertical line from the origin would
    # otherwise infer the very relations added below and over-define.
    axis = check(
        f"{label} cone-axis centerline",
        await adapter.add_centerline(*points["axis_start"], *points["axis_end"]),
    )
    set_sketch_direct_db(adapter, False)
    refs = {
        "origin": "origin",
        "axis_start": f"{axis}.start",
        "axis_end": f"{axis}.end",
        "east_center": f"{arc_e}.center",
        "west_center": f"{arc_w}.center",
        "line_a_start": f"{line_a}.start",
        "line_b_end": f"{line_b}.end",
    }

    async def dimension(name: str, kind: str, value: float, what: str) -> None:
        first, second = TIP_SLOT_DIMENSION_REFERENCES[name]
        await dimension_between(
            adapter, refs[first], refs[second], kind, value, f"{label} {what}"
        )
        dims.record(f"{prefix}{name}")

    await anchor_point_to_origin(
        adapter, refs["axis_start"], *points["axis_start"], f"{label} axis start"
    )
    check(
        f"{label} axis vertical",
        await adapter.add_sketch_constraint(axis, None, "vertical"),
    )
    await dimension(
        "AxisLen", "vertical_distance", points["axis_end"][1], "axis length"
    )
    await dimension("EastCx", "horizontal_distance", c, "east end")
    await dimension("Z", "vertical_distance", y, "station")
    check(
        f"{label} end centres level",
        await adapter.add_sketch_constraint(
            refs["east_center"], refs["west_center"], "horizontal_points"
        ),
    )
    await dimension("WestCx", "horizontal_distance", c, "west end")
    check(
        f"horizontal {label} line a",
        await adapter.add_sketch_constraint(line_a, None, "horizontal"),
    )
    for junction, e1, e2 in (
        ("a-west", line_a, arc_w),
        ("west-b", arc_w, line_b),
        ("b-east", line_b, arc_e),
        ("east-a", arc_e, line_a),
    ):
        check(
            f"{label} tangent {junction}",
            await adapter.add_sketch_constraint(e1, e2, "tangent"),
        )
    await dimension("W", "vertical_distance", width, "width")
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    return dims


# The top relief's sketch runs this far past the north edge, so its cut
# opens the edge cleanly (the plate stops at NORTH_OVERHANG).
PIVOT_RELIEF_RUNOUT = 3.0
if PIVOT_BEARING_RELIEF_DIAMETER / 2.0 >= NORTH_OVERHANG:
    raise AssertionError("pivot relief no longer runs out through the north edge")


async def _sketch_pivot_relief(adapter, dims: SketchDims) -> None:
    """Top relief: a south half-circle about the pivot plus two lines north.

    Sketched on the plate top.  The arc's centre is the pivot, the two lines
    are vertical and tangent to it, and the closing line lies
    PIVOT_RELIEF_RUNOUT past the north edge, so the cut is one round-ended
    slot open to that edge.  The width between the lines is the relief
    diameter (the end-mill size).
    """
    r = PIVOT_BEARING_RELIEF_DIAMETER / 2.0
    far = -(NORTH_OVERHANG + PIVOT_RELIEF_RUNOUT)  # sketch y -> part -Z
    set_sketch_direct_db(adapter, True)
    arc = check(
        "pivot relief south arc", await adapter.add_arc(0.0, 0.0, r, 0.0, -r, 0.0)
    )
    line_w = check("pivot relief line a", await adapter.add_line(-r, 0.0, -r, far))
    line_n = check("pivot relief runout", await adapter.add_line(-r, far, r, far))
    line_e = check("pivot relief line b", await adapter.add_line(r, far, r, 0.0))
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{arc}.center", 0.0, 0.0, "pivot relief")
    for line, relation in (
        (line_w, "vertical"),
        (line_e, "vertical"),
        (line_n, "horizontal"),
    ):
        check(
            f"pivot relief {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    for junction, e1, e2 in (("a", arc, line_w), ("b", line_e, arc)):
        check(
            f"pivot relief tangent {junction}",
            await adapter.add_sketch_constraint(e1, e2, "tangent"),
        )
    await dimension_between(
        adapter,
        f"{line_w}.end",
        f"{line_e}.start",
        "horizontal_distance",
        2.0 * r,
        "pivot relief width",
    )
    dims.record("PivotBearingReliefDia", '"PivotBearingReliefDia"')
    await dimension_between(
        adapter,
        f"{line_n}.start",
        "origin",
        "vertical_distance",
        -far,
        "pivot relief runout",
    )
    dims.record("PivotReliefRunout")


def _north_fillet_relief_overlap(label: str, r: float) -> float:
    """Plan area of a north corner fillet that lies over the open relief.

    The fillet is cut after the relief, so where its removed wedge overlaps
    the 10.50 slot it takes 0.25 less thickness.  A north corner's first edge
    is the north edge (horizontal), so the fillet circle is tangent to it at
    ``x_t`` and the removed wedge above the arc spans ``x_t`` to the corner.
    """
    idx = [c[0] for c in _CORNERS].index(label)
    x, z = _CORNERS[idx][1], _CORNERS[idx][2]
    if abs(z - NORTH_OVERHANG) > 1e-9:
        return 0.0
    tangent = r / math.tan(_corner_theta(label) / 2.0)
    half = PIVOT_BEARING_RELIEF_DIAMETER / 2.0
    run = half - (abs(x) - tangent)  # slot edge past the tangent point
    if run <= 0.0:
        return 0.0
    run = min(run, r)
    return r * run - (
        0.5 * run * math.sqrt(r * r - run * run) + 0.5 * r * r * math.asin(run / r)
    )


def _slot_area(width: float) -> float:
    return math.pi * (width / 2.0) ** 2 + width * 2.0 * TIP_SCREW_HALF_TRAVEL


STOP_LOCAL_Z = -105.0


@dataclass(frozen=True, slots=True)
class SwingHardwareGeometry:
    """Shared machine-frame stations for the base-fixed lock and travel stop."""

    lock_xz: tuple[float, float]
    disengage_deg: float
    stop_contact_xz: tuple[float, float]
    stop_xz: tuple[float, float]
    stop_engaged_gap: float


# Designed clear air between the lock-knob collar and the notch mouth at the
# disengaged stop, so the collar can be tightened onto bare base to fence the
# mouth.  Sized so the linear worst case keeps >= 2.0 mm (U27) with the plate
# outline at .X (+/-0.8) and the base stop/stud holes at .XX (+/-0.51/axis):
# east edge at the stop 2 x 0.8 (lever 105.6 vs SLOT_R 208.4), west edge at the
# mouth 0.99 x 0.8, stop hole ~1.1, stud hole ~0.59, collar/shank ~0.35 -- 4.41
# in all.  The base derives its swing-stop hole from this function.
DISENGAGE_COLLAR_MARGIN = 6.5


def swing_hardware_geometry(
    pivot_xz: tuple[float, float],
    *,
    lock_collar_dia: float,
    stop_shank_dia: float,
) -> SwingHardwareGeometry:
    """Derive the lock seat and stop contact once from the platform outline."""
    if lock_collar_dia <= 0.0 or stop_shank_dia <= 0.0:
        raise ValueError("swing hardware diameters must be positive")

    def placed(x_local: float, z_local: float, angle_rad: float) -> tuple[float, float]:
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return (
            pivot_xz[0] + x_local * c + z_local * s,
            pivot_xz[1] - x_local * s + z_local * c,
        )

    incline_rad = math.radians(INCLINE_DEG)
    lock_xz = placed(SLOT_E_X, SLOT_E_Z, incline_rad)
    disengage_deg = math.degrees(
        (NOTCH_EXIT_TRAVEL + lock_collar_dia / 2.0 + DISENGAGE_COLLAR_MARGIN) / SLOT_R
    )
    disengaged_rad = incline_rad + math.radians(disengage_deg)

    east_slope = (EAST_HALF_S - HALF_WIDTH_N) / PLATE_LEN
    stop_local_x = -(HALF_WIDTH_N + east_slope * (NORTH_OVERHANG - STOP_LOCAL_Z))
    edge_out_local = (-1.0, east_slope)
    edge_norm = math.hypot(*edge_out_local)
    edge_out_local = (
        edge_out_local[0] / edge_norm,
        edge_out_local[1] / edge_norm,
    )

    contact_xz = placed(stop_local_x, STOP_LOCAL_Z, disengaged_rad)
    c_dis, s_dis = math.cos(disengaged_rad), math.sin(disengaged_rad)
    edge_out_disengaged = (
        edge_out_local[0] * c_dis + edge_out_local[1] * s_dis,
        -edge_out_local[0] * s_dis + edge_out_local[1] * c_dis,
    )
    stop_xz = (
        contact_xz[0] + edge_out_disengaged[0] * stop_shank_dia / 2.0,
        contact_xz[1] + edge_out_disengaged[1] * stop_shank_dia / 2.0,
    )

    engaged_edge_xz = placed(stop_local_x, STOP_LOCAL_Z, incline_rad)
    edge_out_engaged = (
        edge_out_local[0] * _COS_I + edge_out_local[1] * _SIN_I,
        -edge_out_local[0] * _SIN_I + edge_out_local[1] * _COS_I,
    )
    stop_delta = (
        stop_xz[0] - engaged_edge_xz[0],
        stop_xz[1] - engaged_edge_xz[1],
    )
    engaged_gap = (
        stop_delta[0] * edge_out_engaged[0]
        + stop_delta[1] * edge_out_engaged[1]
        - stop_shank_dia / 2.0
    )
    return SwingHardwareGeometry(
        lock_xz=lock_xz,
        disengage_deg=disengage_deg,
        stop_contact_xz=contact_xz,
        stop_xz=stop_xz,
        stop_engaged_gap=engaged_gap,
    )


# --- rounded plan corners (item: they echo the neighbouring hardware) --------
# (authored x, local z, radius): north pair ~ the pivot screw head, south-east
# ~ the green column foot.  The south-west fillet is reduced around the
# relocated lock notch so the corner round and the closed seat do not overlap.
_CORNERS = (
    ("NE", -HALF_WIDTH_N, NORTH_OVERHANG, 10.0),
    ("NW", WEST_HALF_N, NORTH_OVERHANG, 8.0),
    ("SW", WEST_HALF_S, NORTH_OVERHANG - PLATE_LEN, 5.0),
    ("SE", -EAST_HALF_S, NORTH_OVERHANG - PLATE_LEN, 12.0),
)
# The NW round must end on the west edge north of the tip block's reach, so
# the straight edge WEST_HALF_N is derived for is the one beside the block.
_NW_TURN = math.pi / 2.0 + math.atan((WEST_HALF_S - WEST_HALF_N) / PLATE_LEN)
_NW_SETBACK = _CORNERS[1][3] / math.tan(_NW_TURN / 2.0)
NW_ROUND_END_Z = NORTH_OVERHANG - _NW_SETBACK * math.cos(_NW_TURN - math.pi / 2.0)
if NW_ROUND_END_Z - OUTLINE_BAND < TIP_BLOCK_NORTH_REACH_Z:
    raise AssertionError("the NW corner round reaches down beside the tip block")


def _corner_theta(label: str) -> float:
    """Interior angle of the named sharp plan corner, radians."""
    idx = [c[0] for c in _CORNERS].index(label)
    x, z = _CORNERS[idx][1], _CORNERS[idx][2]
    xp, zp = _CORNERS[idx - 1][1], _CORNERS[idx - 1][2]
    xn, zn = _CORNERS[(idx + 1) % 4][1], _CORNERS[(idx + 1) % 4][2]
    v1 = (xp - x, zp - z)
    v2 = (xn - x, zn - z)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    return math.acos(dot / (math.hypot(*v1) * math.hypot(*v2)))


def corner_fillet_center(label: str) -> tuple[float, float]:
    """Plan centre (authored x, local z; mm) of the named corner's fillet.

    On the bisector of the corner's two edges, ``r / sin(theta / 2)`` in from
    the sharp corner, so it is ``r`` from both edges.  The NW corner is not
    square (``_NW_TURN``), so no corner may assume a 90 deg inset."""
    idx = [c[0] for c in _CORNERS].index(label)
    _label, x, z, r = _CORNERS[idx]
    bisector = [0.0, 0.0]
    for neighbour in (_CORNERS[idx - 1], _CORNERS[(idx + 1) % 4]):
        dx, dz = neighbour[1] - x, neighbour[2] - z
        length = math.hypot(dx, dz)
        bisector[0] += dx / length
        bisector[1] += dz / length
    length = math.hypot(*bisector)
    inset = r / math.sin(_corner_theta(label) / 2.0)
    return (x + bisector[0] / length * inset, z + bisector[1] / length * inset)


def _corner_fillet_area(label: str, r: float) -> float:
    """Plan area a radius-r fillet removes at the named sharp corner."""
    theta = _corner_theta(label)
    return r * r * (1.0 / math.tan(theta / 2.0) - (math.pi - theta) / 2.0)


# --- crank axis (the machine-z crank line, carried BY the plate) -------------
# The merged column's crank bore is oblique geometry only; the KINEMATIC
# reference the crankshaft mates to is this named axis, so the crank rig
# swings with the plate. In the part-local frame the axis runs plan
# direction (-sin I, cos I) -- the direction the Ry(+INCLINE) placement maps
# to machine z (cf. cone-pivot-post) -- at height CRANK_AXIS_Y above the
# plate BOTTOM, passing the plan point (-CRANK_AXIS_OFF * cos I,
# -CRANK_AXIS_OFF * sin I) -- CRANK_AXIS_OFF is the distance the crank axis
# sits EAST of the pivot. This part-local separation is invariant under the
# v2 installation translation and is asserted against the live cone geometry
# in the assembly.
CRANK_AXIS_OFF = 41.6536661190548
CRANK_AXIS_Y = 79.05  # Y_CRANK 129.85 - Y_BASE_TOP 50.8 (above plate BOTTOM)
# Construction: a vertical REFERENCE AXIS through the crank axis's plan
# point (the foot of the pivot's perpendicular onto the axis line), built
# as the intersection of two principal-plane offsets -- name-selected and
# view-independent (a coordinate-picked model edge selects at the SCREEN
# projection and grabbed the notch rail's top edge instead of the vertical
# mouth edge, proven live). CrankAxisVert = "Right Plane" rotated INCLINE
# about that axis (so it CONTAINS the crank axis -- no offset step); the
# crank axis = that plane (x) the Top-offset plane at CRANK_AXIS_Y.
# CrankAxisSeat = "Front Plane" rotated the same way about the same axis,
# so it passes through CRANK_SEAT_ANCHOR -- the anchor the assembly's
# axial-distance mates reference (via _plate_local_to_machine; its machine
# point lands ON the crank axis, x = X_CRANK, asserted SolidWorks-free at
# assembly import). The angle's FLIP side is
# the one remaining EMPIRICAL sign -- flip on assembly crankshaft-mate
# verify failure.
CRANK_PLANE_ANGLE = INCLINE_DEG  # sign candidate (flip side)
CRANK_SEAT_ANCHOR = (-CRANK_AXIS_OFF * _COS_I, -CRANK_AXIS_OFF * _SIN_I)
# (part-local plan x, z) = (-49.92, -11.08); machine (-130.82, 103.29)


# The widths the print bands (feature, dimension, (upper, lower)); build()
# sets each through deviations().
BANDED_WIDTHS = (
    ("TipScrewSlotProfile", "TipSlotW", TIP_SLOT_W_BAND),
    ("TipScrewCboreProfile", "TipCboreW", TIP_CBORE_W_BAND),
    ("LockNotchProfile", "NotchW", NOTCH_W_BAND),
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateAxisParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 214 = 214 in).
    await set_global(adapter, "PlateT", f"{PLATE_T}mm")
    await set_global(
        adapter, "PivotBearingReliefDia", f"{PIVOT_BEARING_RELIEF_DIAMETER}mm"
    )
    await set_global(
        adapter, "PivotBearingReliefDepth", f"{PIVOT_BEARING_RELIEF_DEPTH}mm"
    )
    await set_global(adapter, "HalfWidthN", f"{HALF_WIDTH_N}mm")
    await set_global(adapter, "WestHalfN", f"{WEST_HALF_N}mm")
    await set_global(adapter, "EastHalfS", f"{EAST_HALF_S}mm")
    await set_global(adapter, "WestHalfS", f"{WEST_HALF_S}mm")
    await set_global(adapter, "PlateLen", f"{PLATE_LEN}mm")
    await set_global(adapter, "NorthOverhang", f"{NORTH_OVERHANG}mm")
    # The pivot hole remains a native Hole Wizard 1/4 close-clearance feature;
    # its diameter and callout come from the table rather than a model global.
    await set_global(adapter, "SlotW", f"{SLOT_W}mm")
    await set_global(adapter, "PostLocalZ", f"{POST_LOCAL_Z}mm")
    await set_global(adapter, "PostMountX", f"{POST_MOUNT_X}mm")
    await set_global(adapter, "PostMountDZ", f"{POST_MOUNT_DZ}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Asymmetric trapezoid plan on the Top plane (sketch (x, y) -> part
    # (X, -Z)). The tapered side lines are sloped, so direct-to-DB keeps
    # inference from snapping them.  Every lateral corner offset is located
    # from the PIVOT (the sketch origin); the north station and conspicuous
    # overall length establish the two end edges without chaining feature
    # locations around the profile.
    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    plan_pts = [
        (-HALF_WIDTH_N, -NORTH_OVERHANG),  # north-east (anchor)
        (WEST_HALF_N, -NORTH_OVERHANG),  # north-west (authored +x = west;
        # derived from the tip block's west reach, I31)
        (WEST_HALF_S, PLATE_LEN - NORTH_OVERHANG),  # south-west (flare)
        (-EAST_HALF_S, PLATE_LEN - NORTH_OVERHANG),  # south-east
    ]
    lines = await add_line_chain(adapter, plan_pts)
    set_sketch_direct_db(adapter, False)
    north_line, _west_line, south_line, _east_line = lines
    await anchor_point_to_origin(
        adapter, f"{north_line}.start", *plan_pts[0], "plate plan north-east"
    )
    plate.record("NorthEastX", '"HalfWidthN"')
    plate.record("NorthEdgeZ", '"NorthOverhang"')
    check(
        "horizontal plate north edge",
        await adapter.add_sketch_constraint(north_line, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{north_line}.end",
        "origin",
        "horizontal_distance",
        WEST_HALF_N,
        "plate plan north-west",
    )
    plate.record("NorthWestX", '"WestHalfN"')
    check(
        "horizontal plate south edge",
        await adapter.add_sketch_constraint(south_line, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{south_line}.start",
        "origin",
        "horizontal_distance",
        WEST_HALF_S,
        "plate plan south-west",
    )
    plate.record("SouthWestX", '"WestHalfS"')
    await dimension_between(
        adapter,
        f"{north_line}.start",
        f"{south_line}.start",
        "vertical_distance",
        PLATE_LEN,
        "plate overall length",
    )
    plate.record("PlateLenDim", '"PlateLen"')
    await dimension_between(
        adapter,
        f"{south_line}.end",
        "origin",
        "horizontal_distance",
        EAST_HALF_S,
        "plate plan south-east",
    )
    plate.record("SouthEastX", '"EastHalfS"')
    await ensure_fully_defined(adapter, "plate plan")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_T)),
    )
    name_last_feature(adapter, "Plate")
    plate_thk_dim = name_dimensions(adapter, "Plate", ["PlateThk"])
    drive_jobs += [(plate_thk_dim[0], '"PlateT"')]
    v_plate = (
        ((HALF_WIDTH_N + WEST_HALF_N) + (WEST_HALF_S + EAST_HALF_S))
        / 2.0
        * PLATE_LEN
        * PLATE_T
    )
    volume = await volume_check(adapter, "plate", v_plate, 0.005 * v_plate)

    # Pivot screw clearance hole at the origin: preserve the native Hole
    # Wizard 1/4 close-clearance feature used by this occasional setup pivot.
    # There is no measured evidence that its stock shoulder needs a tighter
    # running-bearing fit, so the title block's DRILLED HOLES +0.10/0 row
    # governs it; a per-feature band would only restate that row.
    pivot_dia = PIVOT_HOLE_DIA
    wizard_holes(
        adapter,
        PIVOT_HOLE_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        "pivot screw hole (1/4 clearance)",
        name="PivotHole",
    )
    v_hole = math.pi * (pivot_dia / 2.0) ** 2 * PLATE_T
    volume = await volume_check(
        adapter, "pivot hole", volume - v_hole, 0.01 * v_hole
    )

    # Nominal reconstruction of the shallow top relief. The finished depth is
    # matched to the actual purchased shoulder and plate under the user-approved
    # functional acceptance; 0.25 is reference, not an independent depth limit.
    check(
        "create_plane PivotBearingTop",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=PLATE_T)
        ),
    )
    name_last_feature(adapter, "PivotBearingTop")
    bearing_relief = SketchDims()
    check(
        "create_sketch pivot bearing relief",
        await adapter.create_sketch("PivotBearingTop"),
    )
    await _sketch_pivot_relief(adapter, bearing_relief)
    await ensure_fully_defined(adapter, "pivot bearing relief sketch")
    check("exit_sketch pivot bearing relief", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotBearingReliefProfile")
    drive_jobs += bearing_relief.apply(adapter, "PivotBearingReliefProfile")
    check(
        "cut pivot bearing relief",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PIVOT_BEARING_RELIEF_DEPTH)
        ),
    )
    name_last_feature(adapter, "PivotBearingRelief")
    relief_depth_dim = name_dimensions(
        adapter, "PivotBearingRelief", ["PivotBearingReliefDepth"]
    )
    drive_jobs += [(relief_depth_dim[0], '"PivotBearingReliefDepth"')]
    # The plan corners are still sharp here, so the relief is exactly a
    # half disc plus a 10.50 x NORTH_OVERHANG strip, less the pivot hole.
    relief_r = PIVOT_BEARING_RELIEF_DIAMETER / 2.0
    v_relief = (
        (
            math.pi * relief_r**2 / 2.0
            + 2.0 * relief_r * NORTH_OVERHANG
            - math.pi * (pivot_dia / 2.0) ** 2
        )
        * PIVOT_BEARING_RELIEF_DEPTH
    )
    volume = await volume_check(
        adapter, "pivot bearing relief", volume - v_relief, 0.01 * v_relief
    )

    # The v2 casting's two Fillister-head attachment bores land on matching
    # native 1/4-20 UNC-2B through taps in the platform.  One Hole Wizard
    # feature keeps the pair's thread metadata and 2X drawing callout together.
    post_mount_cut = wizard_holes(
        adapter,
        POST_MOUNT_SPEC,
        [
            [POST_MOUNT_WEST_XZ[0], 0.0, POST_MOUNT_WEST_XZ[1]],
            [POST_MOUNT_EAST_XZ[0], 0.0, POST_MOUNT_EAST_XZ[1]],
        ],
        (0.0, -1.0, 0.0),
        "cone-pivot-post-v2 mounts (1/4-20 tapped through)",
        name="PostMountHoles",
        # Table-derived tap diameters read back as 0.0 on this seat even when
        # the native feature is exact.  The immediately following measured
        # volume gate is the hard proof of the 1/4-20 tap-drill geometry.
        placement_dims=[
            (
                ("PostMountWestX", '"PostMountX"'),
                ("PostMountWestZ", '-"PostLocalZ" - "PostMountDZ"'),
            ),
            (
                # Horizontal-distance dimensions are unsigned; the point's
                # authored side retains the east/west sign.
                ("PostMountEastX", '"PostMountX"'),
                ("PostMountEastZ", '-"PostLocalZ" + "PostMountDZ"'),
            ),
        ],
    )
    drive_jobs += post_mount_cut.placement_drive_jobs
    v_post_mounts = 2.0 * math.pi * (POST_MOUNT_TAP_DIA / 2.0) ** 2 * PLATE_T
    volume = await volume_check(
        adapter, "v2 post mount taps", volume - v_post_mounts, 0.01 * v_post_mounts
    )

    # #917 S1: the MHA-151 dowel pair, reamed through for a press fit and
    # match-drilled into the fitted post at assembly (the print carries no
    # station).  Modelled at nominal from the underside, where the pins go in.
    wizard_holes(
        adapter,
        PLATE_DOWEL_HOLE_SPEC,
        [[x, 0.0, z] for x, z in POST_DOWEL_PLATE_XZ],
        (0.0, -1.0, 0.0),
        "post dowel pair (Ø.1245 ream through)",
        name="PostDowelHoles",
        dia_tolerance_mm=DOWEL_REAM_TOLERANCE_MM,
    )
    v_dowels = 2.0 * math.pi * (PLATE_DOWEL_REAM_DIA / 2.0) ** 2 * PLATE_T
    volume = await volume_check(
        adapter, "post dowel reams", volume - v_dowels, 0.01 * v_dowels
    )

    # I31 tip-block hold-down: a through slot for the #6-32 shank, then a
    # counterbored slot from the underside, one hex width across, that sinks
    # the hex head below the slide face and stops it turning.  Same end
    # centres, so the head bears on a uniform ledge.
    tip_slot = await _sketch_tip_screw_slot(
        adapter, width=TIP_SLOT_W, label="tip screw slot", prefix="TipSlot"
    )
    name_last_feature(adapter, "TipScrewSlotProfile")
    drive_jobs += tip_slot.apply(adapter, "TipScrewSlotProfile")
    check(
        "cut tip screw slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "TipScrewSlot")
    v_tip_slot = _slot_area(TIP_SLOT_W) * PLATE_T
    volume = await volume_check(
        adapter, "tip screw slot", volume - v_tip_slot, 0.01 * v_tip_slot
    )
    tip_cbore = await _sketch_tip_screw_slot(
        adapter, width=TIP_CBORE_W, label="tip screw counterbore", prefix="TipCbore"
    )
    name_last_feature(adapter, "TipScrewCboreProfile")
    drive_jobs += tip_cbore.apply(adapter, "TipScrewCboreProfile")
    # Sketched on the plate underside (Top Plane); the cut runs +Y into the
    # plate, against the default into-the-sketch-normal direction.
    check(
        "cut tip screw counterbore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=TIP_CBORE_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "TipScrewCbore")
    name_dimensions(adapter, "TipScrewCbore", ["TipCboreDepth"])
    v_tip_cbore = (_slot_area(TIP_CBORE_W) - _slot_area(TIP_SLOT_W)) * TIP_CBORE_DEPTH
    volume = await volume_check(
        adapter, "tip screw counterbore", volume - v_tip_cbore, 0.01 * v_tip_cbore
    )

    # Lock notch: open-ended channel = a rectangle cut from the engaged seat
    # out past the west edge, split at the edge so the mouth corners are
    # vertices, plus ONE end-cap circle cut at the closed end.  The sketch
    # carries the print's facts: the width (NotchW, SlotW by equation) and
    # the run as its DRIVING angle to the west edge at the south mouth corner
    # (NotchMouthAngle); the cap sketch carries the closed-end centre.  The
    # west edge is a construction reference located by the plate's own
    # globals, split at the two mouth corners so every join is a shared
    # vertex and both of the angle's legs lie inside detail D's crop.
    pts = NOTCH_CUT_POINTS
    order = ("closed_s", "mouth_s", "out_s", "out_n", "mouth_n", "closed_n")
    slot_pts = [(pts[k][0], -pts[k][1]) for k in order]
    edge_n = (WEST_HALF_N, -NORTH_OVERHANG)
    edge_s = (WEST_HALF_S, PLATE_LEN - NORTH_OVERHANG)
    mouth_s = slot_pts[1]
    mouth_n = slot_pts[4]
    slot = SketchDims()
    check("create_sketch lock notch", await adapter.create_sketch("Top"))
    rail_in_s, rail_out_s, slot_end, rail_out_n, rail_in_n, slot_back = (
        await add_line_chain(adapter, slot_pts)
    )
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(_read_member(sketch_mgr, "AddToDB"))
    sketch_mgr.AddToDB = True
    try:
        edge_to_n = check(
            "add notch west-edge reference (north)",
            await adapter.add_line(*edge_n, *mouth_n),
        )
        edge_mouth = check(
            "add notch west-edge reference (mouth)",
            await adapter.add_line(*mouth_n, *mouth_s),
        )
        edge_to_s = check(
            "add notch west-edge reference (south)",
            await adapter.add_line(*mouth_s, *edge_s),
        )
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    for line in (edge_to_n, edge_mouth, edge_to_s):
        _as_construction(adapter, line)
    for what, first, second in (
        ("north edge -> north mouth corner", f"{edge_to_n}.end", f"{rail_in_n}.start"),
        ("mouth edge -> north mouth corner", f"{edge_mouth}.start", f"{rail_in_n}.start"),
        ("mouth edge -> south mouth corner", f"{edge_mouth}.end", f"{rail_out_s}.start"),
        ("south edge -> south mouth corner", f"{edge_to_s}.start", f"{rail_out_s}.start"),
    ):
        check(
            f"lock notch {what}",
            await adapter.add_sketch_constraint(first, second, "coincident"),
        )
    for what, first, second, relation in (
        ("west edge straight (north)", edge_to_n, edge_mouth, "parallel"),
        ("west edge straight (south)", edge_mouth, edge_to_s, "parallel"),
        ("south rail straight", rail_in_s, rail_out_s, "parallel"),
        ("north rail straight", rail_out_n, rail_in_n, "parallel"),
        ("rails parallel", rail_in_n, rail_in_s, "parallel"),
        ("closed end square", slot_back, rail_in_s, "perpendicular"),
        ("outboard end square", slot_end, rail_in_s, "perpendicular"),
    ):
        check(
            f"lock notch {what}",
            await adapter.add_sketch_constraint(first, second, relation),
        )
    # The edge reference sits where the plate plan puts the west edge.
    await anchor_point_to_origin(
        adapter, f"{edge_to_n}.start", *edge_n, "notch west edge north end"
    )
    slot.record("NotchEdgeNX", '"WestHalfN"')
    slot.record("NotchEdgeNZ", '"NorthOverhang"')
    await anchor_point_to_origin(
        adapter, f"{edge_to_s}.end", *edge_s, "notch west edge south end"
    )
    slot.record("NotchEdgeSX", '"WestHalfS"')
    slot.record("NotchEdgeSZ", '"PlateLen" - "NorthOverhang"')
    await anchor_point_to_origin(
        adapter, f"{rail_in_s}.start", *slot_pts[0], "lock notch closed corner"
    )
    slot.record("SlotAnchorX")
    slot.record("SlotAnchorZ")
    await dimension_between(
        adapter,
        f"{rail_in_s}.start",
        f"{slot_back}.start",
        "distance",
        SLOT_W,
        "lock notch width",
    )
    slot.record("NotchW", '"SlotW"')
    await _add_notch_mouth_angle(adapter, edge_mouth, rail_in_s, slot)
    await dimension_between(
        adapter,
        f"{rail_out_s}.start",
        f"{rail_out_s}.end",
        "distance",
        _MOUTH_OVERSHOOT,
        "lock notch mouth overshoot",
    )
    slot.record("SlotMouthOvershoot")
    await ensure_fully_defined(adapter, "lock notch sketch")
    check("exit_sketch lock notch", await adapter.exit_sketch())
    name_last_feature(adapter, "LockNotchProfile")
    drive_jobs += slot.apply(adapter, "LockNotchProfile")
    check(
        "cut lock notch",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LockNotch")
    v_slot = NOTCH_CUT_TRAVEL * SLOT_W * PLATE_T
    # The moved notch exits almost tangent to the east taper; SolidWorks' tiny
    # open-edge cut carries about 0.4 mm^3 of B-rep tessellation noise, larger
    # than one percent of this unusually small 6.3 mm^3 removal.
    volume = await volume_check(
        adapter, "lock notch", volume - v_slot, max(0.01 * v_slot, 0.5)
    )

    # Closed-end cap, NOTCH_ENGAGE_OVERTRAVEL past the engaged seat (the
    # mouth end is open -- no W cap).
    v_cap = math.pi * (SLOT_W / 2.0) ** 2 / 2.0 * PLATE_T
    cap = SketchDims()
    check("create_sketch notch cap E", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        NOTCH_CAP_E_XZ[0],
        -NOTCH_CAP_E_XZ[1],
        SLOT_W / 2.0,
        "notch cap E",
        dims=cap,
        names=("CapECx", "CapECz", "CapEDia"),
        drives=(None, None, '"SlotW"'),
    )
    await ensure_fully_defined(adapter, "notch cap E sketch")
    check("exit_sketch notch cap E", await adapter.exit_sketch())
    name_last_feature(adapter, "LockNotchCapEProfile")
    drive_jobs += cap.apply(adapter, "LockNotchCapEProfile")
    check(
        "cut notch cap E",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LockNotchCapE")
    volume = await volume_check(adapter, "notch cap E", volume - v_cap, 0.02 * v_cap)

    # Vertical swing axis through the pivot hole -- Axis1 ("swing pivot").
    swing_axis = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot"
    )

    # Crank-axis construction (see the constants block): a vertical anchor
    # AXIS through CRANK_SEAT_ANCHOR (name-selected pivot, view-independent),
    # then the two angled planes rotated about it.
    anchor_axis = await name_bore_axis(
        adapter,
        "Front Plane",
        CRANK_SEAT_ANCHOR[1],
        "Right Plane",
        CRANK_SEAT_ANCHOR[0],
        "crank anchor (vertical)",
    )
    check(
        "create_plane CrankAxisVert (angled about the anchor axis)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="angle",
                base_plane="Right Plane",
                angle=CRANK_PLANE_ANGLE,
                pivot_axis=anchor_axis,
            )
        ),
    )
    name_last_feature(adapter, "CrankAxisVert")
    check(
        "create_plane CrankAxisHigh (Top + crank height)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Top Plane",
                offset=CRANK_AXIS_Y,
            )
        ),
    )
    name_last_feature(adapter, "CrankAxisHigh")
    # Seat plane PERPENDICULAR to the crank axis (Front rotated the same way
    # about the same anchor): the crankshaft/handle axial distance mates
    # reference it, so the crank rig's along-axis position rides the swinging
    # plate instead of a world datum.
    check(
        "create_plane CrankAxisSeat (angled, perpendicular to the axis)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="angle",
                base_plane="Front Plane",
                angle=CRANK_PLANE_ANGLE,
                pivot_axis=anchor_axis,
            )
        ),
    )
    name_last_feature(adapter, "CrankAxisSeat")
    # Crank axis: the machine-z crank line, in plate coordinates.
    check(
        "create_axis crank axis",
        await adapter.create_axis(
            CreateAxisParameters(
                mode="two_planes",
                planes=["CrankAxisVert", "CrankAxisHigh"],
            )
        ),
    )
    name_last_feature(adapter, "crank axis")

    # Semantic axes let the assembly mate the v2 fasteners without depending
    # on feature-tree Axis<N> numbering (which changes as construction grows).
    for axis_name, (mount_x, mount_z) in (
        ("post mount west", POST_MOUNT_WEST_XZ),
        ("post mount east", POST_MOUNT_EAST_XZ),
    ):
        await name_bore_axis(
            adapter, "Front Plane", mount_z, "Right Plane", mount_x, axis_name
        )
        name_last_feature(adapter, axis_name)
    for axis_name, (dowel_x, dowel_z) in POST_DOWEL_AXES:
        await name_bore_axis(
            adapter, "Front Plane", dowel_z, "Right Plane", dowel_x, axis_name
        )
        name_last_feature(adapter, axis_name)

    # Rounded plan corners LAST (they consume the sharp corner edges; the
    # notch-mouth edges and the axis construction are already in place).
    v_fillets = 0.0
    for lbl, cx_a, cz_l, r in _CORNERS:
        check(
            f"fillet corner {lbl}",
            await adapter.add_fillet(r, [[cx_a, PLATE_T / 2.0, cz_l]]),
        )
        name_last_feature(adapter, f"Corner{lbl}")
        name_dimensions(adapter, f"Corner{lbl}", [f"Corner{lbl}R"])
        v_fillets += _corner_fillet_area(lbl, r) * PLATE_T
        v_fillets -= _north_fillet_relief_overlap(lbl, r) * PIVOT_BEARING_RELIEF_DEPTH
    volume = await volume_check(
        adapter, "rounded corners", volume - v_fillets, 0.01 * v_fillets
    )

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    # Decimal places for imported model dimensions live on the PART.  The
    # Hole Wizard owns the pivot-hole precision and native size callout.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for feature_name, dimension_name, band in BANDED_WIDTHS:
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band)
        )
    await volume_check(
        adapter, "driven platform (equations neutral)", volume, 0.01 * v_hole
    )

    # PlateTop datum: a reference plane ON the top face (+PlateT). The column
    # and tip block seat COINCIDENT to it (FootSeat/DeckTop pattern) so the
    # riders' height mates are flip-free and face-pick-free.
    check(
        "create_plane PlateTop (Top Plane, +PLATE_T)",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=PLATE_T)
        ),
    )
    name_last_feature(adapter, "PlateTop")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Profile View Note": PROFILE_VIEW_NOTE,
            "Feature View Note": FEATURE_VIEW_NOTE,
            "Notch View Note": NOTCH_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Pivot Relief Fit": PIVOT_RELIEF_FIT_REQUIREMENT,
            "Post Mount Engagement": POST_MOUNT_ENGAGEMENT_NOTE,
        },
    )
    blank_reference_geometry(
        adapter,
        (
            # Unnamed offset planes created inside name_bore_axis. The named
            # PivotBearingTop plane occupies the first generated plane ordinal.
            ("PivotBearingTop", "PLANE"),
            ("Plane2", "PLANE"),
            ("Plane3", "PLANE"),
            ("CrankAxisVert", "PLANE"),
            ("CrankAxisHigh", "PLANE"),
            ("CrankAxisSeat", "PLANE"),
            ("Plane7", "PLANE"),
            ("Plane8", "PLANE"),
            ("Plane9", "PLANE"),
            ("Plane10", "PLANE"),
            # ... and the two post dowel axes'.
            ("Plane11", "PLANE"),
            ("Plane12", "PLANE"),
            ("Plane13", "PLANE"),
            ("Plane14", "PLANE"),
            ("PlateTop", "PLANE"),
            (swing_axis, "AXIS"),
            (anchor_axis, "AXIS"),
            ("crank axis", "AXIS"),
            ("post mount west", "AXIS"),
            ("post mount east", "AXIS"),
            ("post dowel north", "AXIS"),
            ("post dowel south", "AXIS"),
        ),
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
