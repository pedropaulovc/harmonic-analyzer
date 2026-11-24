r"""Pen carriage layout + balance -- PURE DATA and math, no SolidWorks/COM.

The single place the pen carriage's machine layout is derived, shared by
``build_pn_pen_assembly`` (component placement), ``sh_vn_music_wire_pen_geom`` (the wire's
bottom end), the hanger's engagement test and ``test_pn_pen_carriage_geom``.

The carriage hangs from the rod (engineerguy 4/4, 9:15-10:34; design brief
option C): the rod's square shoulder rests on the v-block top and its turned
pivot end drops into the block's pivot bore, locked by the v-block set screw.
The Sharpie Fine Point's grip lies in the block's V-groove, yawed PEN_BLOCK_YAW_DEG
to the paper, held by the stirrup frame at the PAPER end of the block and its
thumb screw. On the rod top, the adjuster stud + jam nut carry the wire eye.

Two coupled solves fix the layout:

* Paper: the nib stands PEN_PAPER_CLEARANCE_MM off the paper; every carriage
  corner stands 2 x CLEARANCE off as modelled, and clear of the paper with
  every printed band at its worst (``paper_side_points_printed_worst``).
* Balance: the carriage's plan CG (v-block + marker + stirrup + thumb screw +
  rod set screw; the rod, stud and nut sit on the axis) lands on the rod axis.
  The v-block's length is the knob (``pn_pen_v_block_spec.BLOCK_LENGTH``);
  ``plan_cg_residual_mm`` is the analytic check (brass 8.5, AISI 304 8.0,
  alloy steel 7.7 g/cc; the marker's published mass at its envelope CG).

Block-local frame (``build_pn_pen_v_block``): x along the length (0 = paper
end), y up (0 = bottom face), z across the depth (0 = the neck's front face;
the body runs BODY_Z0..BODY_Z1, both centred on DEPTH_MID_Z). The block's
local +X points forward-and-east at the yaw: machine (+sin, 0, -cos).
"""

from __future__ import annotations

import math
from types import ModuleType

import _mcmaster_99607a213 as thumb
import pn_pen_adjust_screw_spec as stud
import pn_pen_frame_spec as frame
import pn_pen_rod_groove_spec as groove
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as vb
import pn_vn_pen_marker_spec as marker
import sh_vn_arbor_set_screw_spec as rod_set_screw
from _hole_spec import TAP_DRILL_MM
from _printed_tolerance import printed_deviations
from _recording_geometry import (
    PAPER_FRONT_Z,
    PEN_BLOCK_YAW_DEG,
    PEN_PAPER_CLEARANCE_MM,
    PEN_ROD_X,
    PEN_Z_MID,
)

CLEARANCE = 0.25  # interference-gate margin convention
# output.yaml pen_trace_half_mm: the pen's travel about its rest (build) pose.
# Literal here so the pen assembly recipe does not read machine/output.yaml
# (test_buildgraph.test_pen_assembly_free_of_pen_driver_closure);
# test_pn_pen_carriage_geom pins it to pen_driver.stroke_half_mm().
PEN_TRAVEL_HALF_MM = 25.0
# Recording paper y 324.5..405 (build_pd_paper_drive_assembly): the marker
# axis rests at mid-height so the trace stays on the sheet.
PAPER_MID_Y = 364.75

BRASS_G_PER_MM3 = 8.5e-3
AISI_304_G_PER_MM3 = 8.0e-3
ALLOY_STEEL_G_PER_MM3 = 7.7e-3  # SOLIDWORKS "Alloy Steel"
# The rod set screw's mass: the McMaster 91375A106 vendor solid's volume
# (diagnostics/diag_build_91375A106.VENDOR_VOLUME_MM3).
ROD_SET_SCREW_MASS_G = 25.8601 * ALLOY_STEEL_G_PER_MM3

_C = math.cos(math.radians(PEN_BLOCK_YAW_DEG))
_S = math.sin(math.radians(PEN_BLOCK_YAW_DEG))
# Images of the block's local axes (rows convention of place_component). Rows
# only: the Euler angles are the assembly's business (_transforms is an
# assembly helper, and sh_vn_music_wire_pen_geom -- a leaf part's recipe -- imports this).
BLOCK_ROWS = [[_S, 0.0, -_C], [0.0, 1.0, 0.0], [_C, 0.0, _S]]
BORE_LOCAL = (vb.PIVOT_BORE_X, vb.DEPTH_MID_Z)  # (x, z) of the rod axis

# --- vertical stack -------------------------------------------------------------
BLOCK_BOTTOM_Y = round(PAPER_MID_Y - vb.MARKER_AXIS_Y, 1)
BLOCK_TOP_Y = BLOCK_BOTTOM_Y + vb.BLOCK_HEIGHT
VBLOCK_POS = (
    PEN_ROD_X - BORE_LOCAL[0] * _S - BORE_LOCAL[1] * _C,
    BLOCK_BOTTOM_Y,
    PEN_Z_MID + BORE_LOCAL[0] * _C - BORE_LOCAL[1] * _S,
)


def block_to_machine(local: tuple[float, float, float]) -> tuple[float, float, float]:
    """Machine point of a v-block-local point."""
    x, y, z = local
    return (
        VBLOCK_POS[0] + x * BLOCK_ROWS[0][0] + z * BLOCK_ROWS[2][0],
        VBLOCK_POS[1] + y,
        VBLOCK_POS[2] + x * BLOCK_ROWS[0][2] + z * BLOCK_ROWS[2][2],
    )


# Rod: part origin = the shoulder centre, resting on the block top.
ROD_POS = (PEN_ROD_X, BLOCK_TOP_Y, PEN_Z_MID)
ROD_SQUARE_TOP_REST_Y = BLOCK_TOP_Y + rod.SQUARE_LENGTH
ROD_PIVOT_END_LOCAL_Y = vb.BLOCK_HEIGHT - rod.PIVOT_LENGTH
# Adjuster stud: part origin = its threaded end, STUD_ENGAGEMENT down the tap.
STUD_POS = (PEN_ROD_X, ROD_SQUARE_TOP_REST_Y - rod.STUD_ENGAGEMENT, PEN_Z_MID)
STUD_HEAD_TOP_REST_Y = STUD_POS[1] + stud.OVERALL_LENGTH
# Jam nut: part axis +Z turned to machine +Y, bearing face on the rod top.
NUT_ROWS = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
NUT_POS = (PEN_ROD_X, ROD_SQUARE_TOP_REST_Y, PEN_Z_MID)

# --- marker in the V-groove ----------------------------------------------------------
# Marker local +Y (nib -> back end) -> block local +X, local +X -> block -Y.
MARKER_ROWS = [[-v for v in BLOCK_ROWS[1]], list(BLOCK_ROWS[0]), list(BLOCK_ROWS[2])]
# Nib on the paper: machine z of local (x, ., D/2) is VBLOCK_POS.z - x*cos + D/2*sin.
# The yawed nib reaches the paper on its rounded flank, not its axial tip: a
# profile station (y, r) sits r*sin - y*cos paper-ward of the tip (piecewise
# linear, so a station is the extreme). The paper-most station stands
# PEN_PAPER_CLEARANCE_MM off the paper.
MARKER_NIB_REACH = max(r * _S - y * _C for y, r in marker.PROFILE)
MARKER_NIB_LOCAL_X = (
    -(
        (PAPER_FRONT_Z - PEN_PAPER_CLEARANCE_MM - MARKER_NIB_REACH)
        - VBLOCK_POS[2]
        - vb.DEPTH_MID_Z * _S
    )
    / _C
)
MARKER_POS = block_to_machine((MARKER_NIB_LOCAL_X, vb.MARKER_AXIS_Y, vb.DEPTH_MID_Z))
MARKER_GRIP_LOCAL_X = (
    MARKER_NIB_LOCAL_X + marker.BARREL_START_Y,
    MARKER_NIB_LOCAL_X + marker.BARREL_END_Y,
)

# --- stirrup frame + thumb screw --------------------------------------------------------
# Frame-local (pn_pen_frame_spec): width X, height Y, depth Z. Placed with its
# plane across the block length: frame X -> block Z, frame Y -> up, frame Z ->
# block -X. Placed flush with the paper end face; the window straddles the
# block section, its top rail FRAME_TOP_GAP above the block top.
FRAME_TOP_GAP = 0.1
FRAME_X0_LOCAL = 0.0  # the frame's paper-side face, flush with the block end
# The stirrup's setting along the neck (#3467): nothing but the thumb
# screw's clamp locates it there, so MHA-PN-00 sets it as that screw clamps
# it (step 5A) and checks it (5C).  Its rear (rod-side) face stands
# STIRRUP_REAR_FACE_LIMITS from the block's paper-end face, read with
# calipers over the two faces, the setting VIEW C prints natively
# (pn_pen_assembly_spec), and its paper-side face stands no more than
# STIRRUP_PROUD_MAX proud of that end face, checked with a square's blade
# laid on the end face across the stirrup (calipers over a proud stirrup
# read only its own depth).  The near limit is the model's flush stirrup;
# the far limit is the deepest stirrup flush plus .005: there its far
# window corners still clear the neck breaks' run-out
# (window_corner_ride_max); STIRRUP_REAR_FACE_LIMIT is how far they may go.
_FRAME_DEPTH_UPPER = printed_deviations(
    frame.FRAME_DEPTH, frame.DRAWING_PRECISION_BY_NAME["Depth"], unit=frame.UNIT
)[1]
STIRRUP_REAR_FACE_LIMITS = (
    FRAME_X0_LOCAL + frame.FRAME_DEPTH,  # .310
    FRAME_X0_LOCAL + frame.FRAME_DEPTH + _FRAME_DEPTH_UPPER + 0.127,  # .325
)
STIRRUP_PROUD_MAX = 0.0
FRAME_X_CENTER_LOCAL = FRAME_X0_LOCAL + frame.FRAME_DEPTH / 2.0
FRAME_ORIGIN_LOCAL = (
    FRAME_X0_LOCAL + frame.FRAME_DEPTH,  # frame z 0 is the face nearer the rod
    vb.BLOCK_HEIGHT + FRAME_TOP_GAP + frame.RAIL_END - frame.OUTER_HEIGHT,
    vb.DEPTH_MID_Z - frame.OUTER_WIDTH / 2.0,
)
FRAME_POS = block_to_machine(FRAME_ORIGIN_LOCAL)
FRAME_ROWS = [[_C, 0.0, _S], [0.0, 1.0, 0.0], [-_S, 0.0, _C]]
FRAME_TOP_LOCAL_Y = vb.BLOCK_HEIGHT + FRAME_TOP_GAP + frame.RAIL_END
FRAME_WINDOW_BOTTOM_LOCAL_Y = FRAME_ORIGIN_LOCAL[1] + frame.RAIL_END
ROD_HALF_DIAGONAL = rod.ROD_SECTION / math.sqrt(
    2.0
)  # the square spans its diagonal along the yawed block
FRAME_ROD_GAP = BORE_LOCAL[0] - ROD_HALF_DIAGONAL - (FRAME_X0_LOCAL + frame.FRAME_DEPTH)
# Thumb screw: stock local +X (head -> tip) turned up the frame's screw axis;
# its tip is tangent to the underside of the grip.
THUMB_SCREW_ROWS = [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
MARKER_BOTTOM_LOCAL_Y = vb.MARKER_AXIS_Y - marker.BARREL_DIA / 2.0
THUMB_SCREW_REACH = thumb.HEAD_STACK_LEN + thumb.SHANK_LEN
THUMB_SCREW_POS = block_to_machine(
    (
        FRAME_X_CENTER_LOCAL,
        MARKER_BOTTOM_LOCAL_Y - THUMB_SCREW_REACH,
        vb.DEPTH_MID_Z,
    )
)

# --- rod set screw -------------------------------------------------------------
# Stock local +Y (cup -> socket) points out of the front face (block -Z); the cup
# sits on the floor of the pivot's relief groove (#2439), .010 inside the
# pivot-bore wall.
ROD_SET_SCREW_CUP_LOCAL_Z = vb.DEPTH_MID_Z - groove.GROOVE_DIA / 2.0
ROD_SET_SCREW_ROWS = [
    [BLOCK_ROWS[0][0], BLOCK_ROWS[0][1], BLOCK_ROWS[0][2]],
    [-BLOCK_ROWS[2][0], -BLOCK_ROWS[2][1], -BLOCK_ROWS[2][2]],
    [BLOCK_ROWS[1][0], BLOCK_ROWS[1][1], BLOCK_ROWS[1][2]],
]

ROD_SET_SCREW_POS = block_to_machine(
    (vb.PIVOT_BORE_X, vb.SET_SCREW_Y, ROD_SET_SCREW_CUP_LOCAL_Z)
)

# --- travel envelope (published for the hanger's U-guide engagement test) -----
ROD_SECTION = rod.ROD_SECTION
ROD_SQUARE_BOTTOM_Y = (
    BLOCK_TOP_Y - PEN_TRAVEL_HALF_MM,
    BLOCK_TOP_Y + PEN_TRAVEL_HALF_MM,
)
ROD_SQUARE_TOP_Y = (
    ROD_SQUARE_TOP_REST_Y - PEN_TRAVEL_HALF_MM,
    ROD_SQUARE_TOP_REST_Y + PEN_TRAVEL_HALF_MM,
)
CARRIAGE_TOP_Y = (
    BLOCK_BOTTOM_Y + FRAME_TOP_LOCAL_Y - PEN_TRAVEL_HALF_MM,
    BLOCK_BOTTOM_Y + FRAME_TOP_LOCAL_Y + PEN_TRAVEL_HALF_MM,
)
STUD_HEAD_TOP_Y = (
    STUD_HEAD_TOP_REST_Y - PEN_TRAVEL_HALF_MM,
    STUD_HEAD_TOP_REST_Y + PEN_TRAVEL_HALF_MM,
)


# --- paper clearance -------------------------------------------------------------
def machine_z(local_x: float, local_z: float) -> float:
    return block_to_machine((local_x, 0.0, local_z))[2]


def paper_side_points() -> dict[str, float]:
    """Machine z of each carriage feature's paper-most point (the nib excepted)."""
    frame_z_paper = vb.DEPTH_MID_Z + frame.OUTER_WIDTH / 2.0
    points = {
        "v-block neck paper-end corner": machine_z(0.0, vb.NECK_DEPTH),
        "v-block body paper-side corner": machine_z(vb.RELIEF_X0, vb.BODY_Z1),
        "stirrup paper-side corner": machine_z(FRAME_X0_LOCAL, frame_z_paper),
        "thumb-screw head rim": machine_z(FRAME_X_CENTER_LOCAL, vb.DEPTH_MID_Z)
        + thumb.HEAD_DIA / 2.0,
    }
    # Marker envelope: a profile station (y, r) reaches its paper-most point on
    # the generatrix facing the paper (block +z), r*sin off the axis.
    for y, r in marker.PROFILE:
        if y < marker.NIB_LENGTH:
            continue  # the nib itself is placed by the paper solve
        x = MARKER_NIB_LOCAL_X + y
        points[f"marker at y={y:g}"] = machine_z(x, vb.DEPTH_MID_Z) + r * _S
    return points


# --- paper clearance at the printed extremes (drawing-guidelines.md rule 19) ---
# paper_side_points() reads the model as placed, the stirrup centred on the
# neck and flush on its end.  No fit-up setting moves the block off the paper
# (the nib preset slides only the marker, which the final machine sets from
# the paper by its nib), and the stirrup's setting holds its paper face no
# more than STIRRUP_PROUD_MAX proud of the end, so the two prints' loose
# bands must hold the rigid carriage off it at their worst case together.  About the
# rod axis (the pivot bore): the block prints its length-wise stations from
# the paper end and its depth-wise ones from the body's front face, all .XX.
# The stirrup sits anywhere across the neck its window lets it: neither its
# window corner radii nor the thumb screw's tip on the round grip stops it,
# so at worst its window's front wall lies on the neck's front face.  The
# narrow window and thin rails (pn_pen_frame_spec) are what keep its
# paper-side corner off the paper.
def _printed_limits(spec: ModuleType, name: str, model: float) -> tuple[float, float]:
    """``(min, max)`` mm of ``spec``'s printed dimension ``name`` (model value
    ``model``) at the title block's limits for its places."""
    low, high = printed_deviations(
        model, spec.DRAWING_PRECISION_BY_NAME[name], unit=spec.UNIT
    )
    return model + low, model + high


def paper_side_points_printed_worst() -> dict[str, float]:
    """Machine z of each rigid carriage feature's paper-most point, every
    printed band it reads at its paper-ward limit."""
    pivot_x = _printed_limits(vb, "PivotX", vb.PIVOT_BORE_X)[1]
    pivot_z = _printed_limits(vb, "PivotZ", vb.depth_station(vb.DEPTH_MID_Z))[0]

    def z_at(x: float, z: float) -> float:
        """Machine z of block (x from the paper end, z from the body's front
        face) with the rod axis at the printed pivot."""
        return PEN_Z_MID + (pivot_x - x) * _C + (z - pivot_z) * _S

    neck_front = _printed_limits(vb, "NeckZ0", vb.depth_station(0.0))[1]
    neck_back = _printed_limits(vb, "NeckZ1", vb.depth_station(vb.NECK_DEPTH))[1]
    step = _printed_limits(vb, "ReliefX0", vb.RELIEF_X0)[0]
    body_back = _printed_limits(vb, "Depth", vb.BODY_DEPTH)[1]
    # The stirrup's outer faces with its window's front wall on the neck, its
    # paper-side face as proud of the block's end as its setting lets it be.
    frame_x0 = -STIRRUP_PROUD_MAX
    frame_front = neck_front - _printed_limits(frame, "LeftWall", frame.RAIL_SIDE)[0]
    frame_paper = (
        frame_front + _printed_limits(frame, "OuterSpanX", frame.OUTER_WIDTH)[1]
    )
    # The thumb screw's axis: ScrewZ from the stirrup's rod-side face, which
    # the setting holds at least its near limit from the end face.
    screw_x = (
        STIRRUP_REAR_FACE_LIMITS[0]
        - _printed_limits(frame, "ScrewZ", frame.FRAME_DEPTH / 2.0)[1]
    )
    screw_z = frame_front + _printed_limits(frame, "ScrewX", frame.OUTER_WIDTH / 2.0)[1]
    return {
        "v-block neck paper-end corner": z_at(0.0, neck_back),
        "v-block body paper-side corner": z_at(step, body_back),
        "stirrup paper-side corner": z_at(frame_x0, frame_paper),
        "thumb-screw head rim": z_at(screw_x, screw_z) + thumb.HEAD_DIA / 2.0,
    }


# --- the stirrup's window corners on the neck's broken top edges ----------------
# Each break runs full from the paper end to NECK_BREAK_FULL_X, where the
# chamfer mill is fed up (pn_pen_v_block_spec).  That stop is VB06's CNC
# program number, not a printed band: the cut lands within the PM-30MV's
# positioning repeatability, ±0.02 mm (cad/config/shop-equipment/cnc.toml
# cnc.pm-30mv, owner value).
MILL_REPEATABILITY = 0.02
NECK_BREAK_STOP_MIN = vb.NECK_BREAK_FULL_X - MILL_REPEATABILITY


def window_corner_ride(far_x: float, corner_r: float, leg: float, stop: float) -> float:
    """How far window corners of radius ``corner_r`` lift the stirrup's top
    rail off the block top, the window's side wall on the neck's face and the
    stirrup's far (rod-side) face ``far_x`` from the paper end, on 45 deg
    neck breaks of ``leg`` run full to ``stop``.

    A corner's metal lies between its arc and the rail's and the wall's
    faces: measured down from the top (t) and in from the neck's face (z),
    no point of it has z + t over ``corner_r``.  The full break removes every
    point with z + t up to ``leg``, so it leaves the corner nothing to ride
    while ``leg >= corner_r``.  Past the stop the mill's 90 deg cone, its
    point ``leg`` under the top on the neck face's line, was fed straight
    up: ``d`` past the stop it has removed the points with
    sqrt(d^2 + z^2) + t up to ``leg``.  Over the corner's metal that sum is
    greatest where the arc leaves the wall (z 0, t ``corner_r``): elsewhere
    sqrt(d^2 + z^2) <= d + z and the arc stands at least z under that point.
    So the far corners ride the cone's run-out by d + ``corner_r`` - ``leg``
    once d passes ``leg`` - ``corner_r``."""
    past = max(0.0, far_x - stop)
    return max(0.0, past + corner_r - leg)


def window_corner_ride_max(rear_face_max: float) -> float:
    """How far the stirrup's window corners, at their printed R.065's
    greatest (R.070; owner ruling 2026-11-23, tool audit Q9), can lift its
    top rail off the block top by riding the neck's broken top edges (owner
    seat ruling 2026-11-23: .080 X 45, .075-.085), the stirrup's rear (far)
    face set at most ``rear_face_max`` mm from the paper end.

    Nothing centres the stirrup across the neck (paper_side_points_printed_
    worst), so one side wall can lie on the neck's face, the window and the
    neck at their printed limits; its far corners then meet the breaks'
    shortest leg and the stop's nearest landing (``window_corner_ride``)."""
    window = _printed_limits(frame, "WindowWidth", frame.WINDOW_WIDTH)[0]
    neck = (
        _printed_limits(vb, "NeckZ1", vb.depth_station(vb.NECK_DEPTH))[1]
        - _printed_limits(vb, "NeckZ0", vb.depth_station(0.0))[0]
    )
    if window <= neck:
        raise AssertionError("the stirrup window must pass the neck at both prints")
    return window_corner_ride(
        rear_face_max,
        frame.WINDOW_CORNER_R_MAX,
        vb.NECK_EDGE_BREAK_MIN,
        NECK_BREAK_STOP_MIN,
    )


# The furthest the stirrup's rear face may stand from the paper end with its
# window corners still off the run-out at the printed worst case: the stop's
# nearest landing plus the run-out's free reach (shortest leg less greatest
# radius).
STIRRUP_REAR_FACE_LIMIT = (
    NECK_BREAK_STOP_MIN + vb.NECK_EDGE_BREAK_MIN - frame.WINDOW_CORNER_R_MAX
)


def stirrup_setting_ride(rear_face_max: float) -> float:
    """The window corners' ride with the stirrup's rear face set at most
    ``rear_face_max`` from the block's paper end; refuses a setting whose
    corners ride the breaks' run-out.  The module guards below run it on the
    printed setting at import, before any SolidWorks leaf: the assembly's
    interference gate cannot see the ride (the model carries the nominal
    R.065 and .080 leg, its stirrup centred and its rail held FRAME_TOP_GAP
    off the top)."""
    ride = window_corner_ride_max(rear_face_max)
    if ride > 0.0 or rear_face_max > STIRRUP_REAR_FACE_LIMIT:
        raise AssertionError(
            f"the stirrup's rear face set {rear_face_max:.3f} mm from the paper "
            f"end rides the neck breaks' run-out by {ride:.3f} mm (limit "
            f"{STIRRUP_REAR_FACE_LIMIT:.3f})"
        )
    return ride


def stirrup_placement_check(frame_x0: float, depth: float) -> float:
    """The window corners' ride with a stirrup ``depth`` deep placed with its
    paper-side face ``frame_x0`` from the block's paper end (positive toward
    the step); refuses it either way out of its setting.  Proud of the end
    past STIRRUP_PROUD_MAX its paper-side corner leaves the paper clearance
    paper_side_points_printed_worst() proves; its rear face past
    STIRRUP_REAR_FACE_LIMIT its far corners ride the breaks' run-out."""
    if frame_x0 < -STIRRUP_PROUD_MAX:
        raise AssertionError(
            f"the stirrup stands {-frame_x0:.3f} mm proud of the paper end "
            f"(limit {STIRRUP_PROUD_MAX:.3f}): its paper-side corner crowds "
            "the paper"
        )
    return stirrup_setting_ride(frame_x0 + depth)


# --- plan balance ---------------------------------------------------------------
def _cyl(r: float, h: float) -> float:
    return math.pi * r * r * h


def plan_mass_items() -> list[tuple[str, float, float, float]]:
    """(name, mass g, block-local x, block-local z) of every off-axis mass."""
    L, H, X0 = vb.BLOCK_LENGTH, vb.BLOCK_HEIGHT, vb.RELIEF_X0
    zc = vb.DEPTH_MID_Z
    tap_r = TAP_DRILL_MM[vb.SET_SCREW_TAP_SPEC.size] / 2.0
    pivot_r = vb.PIVOT_BORE_DIA / 2.0
    block = [
        ("neck stock", X0 * H * vb.NECK_DEPTH, X0 / 2.0, zc),
        ("body stock", (L - X0) * H * vb.BODY_DEPTH, (X0 + L) / 2.0, zc),
        # The V's section (its triangle less the tip the apex flat leaves)
        # over the seat length.
        (
            "V-groove",
            -vb.V_GROOVE_SECTION * vb.RELIEF_X0,
            vb.RELIEF_X0 / 2.0,
            zc,
        ),
        (
            "relief slot",
            -vb.RELIEF_WIDTH * vb.RELIEF_HEIGHT * (L - vb.RELIEF_X0),
            (vb.RELIEF_X0 + L) / 2.0,
            zc,
        ),
        # The slot's two step corners stand R x R less the quarter disc over
        # its height (R.065, owner ruling 2026-11-23, tool audit Q9), their
        # centroids R (10 - 3 pi) / (12 - 3 pi) off the step, symmetric in z.
        (
            "relief step corners",
            2.0 * (1.0 - math.pi / 4.0) * vb.RELIEF_CORNER_R**2 * vb.RELIEF_HEIGHT,
            vb.RELIEF_X0
            + vb.RELIEF_CORNER_R * (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi),
            zc,
        ),
        # The neck's two top-edge breaks (owner seat ruling 2026-11-23),
        # symmetric in z: each its triangle from the paper end to the stop,
        # then its run-out into the step.
        (
            "neck edge breaks",
            -2.0 * vb.NECK_BREAK_VOLUME,
            vb.NECK_BREAK_FULL_X / 2.0,
            zc,
        ),
        (
            "neck break run-outs",
            -2.0 * vb.NECK_BREAK_RUNOUT_VOLUME,
            vb.NECK_BREAK_RUNOUT_X,
            zc,
        ),
        ("pivot bore", -_cyl(pivot_r, H - vb.RELIEF_HEIGHT), vb.PIVOT_BORE_X, zc),
        (
            "set-screw tap",
            -_cyl(tap_r, vb.SET_SCREW_TAP_LENGTH),
            vb.PIVOT_BORE_X,
            vb.BODY_Z0 + vb.SET_SCREW_TAP_LENGTH / 2.0,
        ),
    ]
    items = [(f"v-block {n}", v * BRASS_G_PER_MM3, x, z) for n, v, x, z in block]

    # The ring less its window, the window's four R.065 corners (owner
    # ruling 2026-11-23, tool audit Q9) giving back R x R less the quarter
    # disc each, symmetric about the ring's centre, and the tap's drill.
    ring = (
        frame.OUTER_WIDTH * frame.OUTER_HEIGHT
        - frame.WINDOW_WIDTH * frame.WINDOW_HEIGHT
        + 4.0 * (1.0 - math.pi / 4.0) * frame.WINDOW_CORNER_R**2
    ) * frame.FRAME_DEPTH - _cyl(frame.SET_SCREW_TAP_DRILL_DIA / 2.0, frame.RAIL_END)
    items.append(("stirrup frame", ring * BRASS_G_PER_MM3, FRAME_X_CENTER_LOCAL, zc))
    thumb_v = (
        _cyl(thumb.TS_HEAD_R, thumb.TS_HEAD_H)
        + _cyl(thumb.TS_SH_R, thumb.TS_SH_H)
        + _cyl(thumb.TS_MAJOR_R, thumb.TS_LEN)
    )
    items.append(
        ("thumb screw", thumb_v * AISI_304_G_PER_MM3, FRAME_X_CENTER_LOCAL, zc)
    )
    items.append(
        (
            "rod set screw",
            ROD_SET_SCREW_MASS_G,
            vb.PIVOT_BORE_X,
            ROD_SET_SCREW_CUP_LOCAL_Z - rod_set_screw.LENGTH / 2.0,
        )
    )
    items.append(("marker", marker.MASS_G, MARKER_NIB_LOCAL_X + marker.CG_Y, zc))
    return items


def plan_cg_local() -> tuple[float, float, float]:
    """(total mass g, CG block-local x, CG block-local z) of the off-axis carriage."""
    items = plan_mass_items()
    m = sum(i[1] for i in items)
    return (
        m,
        sum(i[1] * i[2] for i in items) / m,
        sum(i[1] * i[3] for i in items) / m,
    )


def plan_cg_residual_mm() -> float:
    """Plan distance from the carriage CG to the rod axis."""
    _, x, z = plan_cg_local()
    return math.hypot(x - BORE_LOCAL[0], z - BORE_LOCAL[1])


# --- module-level layout guards (fail loud at import, like the assembly did) ---
if not (
    MARKER_GRIP_LOCAL_X[0] <= 0.0 and MARKER_GRIP_LOCAL_X[1] >= vb.RELIEF_X0 + CLEARANCE
):
    raise AssertionError("the marker grip must span the whole V-groove seat")
if FRAME_ROD_GAP < CLEARANCE:
    raise AssertionError(f"stirrup crowds the rod: gap {FRAME_ROD_GAP:.2f}")
if frame.WINDOW_WIDTH < vb.NECK_DEPTH + 4.0 * CLEARANCE:
    raise AssertionError("stirrup window must pass the neck with 2 x CLEARANCE a side")
if FRAME_X0_LOCAL + frame.FRAME_DEPTH + 4.0 * CLEARANCE > vb.RELIEF_X0:
    raise AssertionError("the stirrup must slide on the neck clear of the body's step")
# The stirrup as placed sits inside its setting, and at the setting's far
# limit its window corners ride nothing (#3467).  The thumb screw keeps its
# throw with the stirrup lifted by its window corners at that worst.
if not (
    STIRRUP_REAR_FACE_LIMITS[0]
    <= FRAME_X0_LOCAL + frame.FRAME_DEPTH
    <= STIRRUP_REAR_FACE_LIMITS[1]
):
    raise AssertionError("the stirrup as placed stands outside its setting")
stirrup_placement_check(FRAME_X0_LOCAL, frame.FRAME_DEPTH)
WINDOW_CORNER_RIDE_MAX = stirrup_setting_ride(STIRRUP_REAR_FACE_LIMITS[1])
if FRAME_WINDOW_BOTTOM_LOCAL_Y + WINDOW_CORNER_RIDE_MAX > MARKER_BOTTOM_LOCAL_Y - 1.0:
    raise AssertionError("stirrup window leaves the thumb screw under 1.0 of throw")
if MARKER_BOTTOM_LOCAL_Y - thumb.SHANK_LEN >= FRAME_ORIGIN_LOCAL[1]:
    raise AssertionError("the thumb screw knob must stand below the stirrup")
if ROD_PIVOT_END_LOCAL_Y - vb.RELIEF_HEIGHT < 0.5:
    raise AssertionError("rod pivot end must stop above the relief roof")
if not ROD_PIVOT_END_LOCAL_Y + 1.5 < vb.SET_SCREW_Y < vb.BLOCK_HEIGHT - 1.5:
    raise AssertionError("rod set screw must bear on the pivot end")
if max(paper_side_points().values()) > (PAPER_FRONT_Z - 2.0 * CLEARANCE):
    raise AssertionError("a pen-carriage corner crowds the recording paper")
if max(paper_side_points_printed_worst().values()) >= PAPER_FRONT_Z:
    raise AssertionError("at the printed worst case the carriage reaches the paper")


# --- the set screw in the pivot's relief groove (#2439) ---------------------------
def groove_landing_spare() -> tuple[float, float]:
    """``(shoulder side, end side)`` mm of groove wall left beyond the set
    screw's point with the axial stack at its printed worst case and the
    diameters nominal.  The screw's axis stands the block height less
    SetScrewY below the shoulder (both .XX on the v-block sheet); the walls
    are .XXX from the shoulder on the rod sheet.  The point is the vendor's
    45 deg x one-pitch cup-end chamfer, taken where it crosses the pivot-bore
    wall, .011 above the cup on the floor in the nominal #30 bore (owner
    ruling 2026-11-24, fit audit question 20): wider than the cup's rim, so
    that is what must pass between the walls.  The deepest printed floor in
    the largest drilled bore lifts that crossing to .01575 and costs about
    .0045 a side; test_pn_pen_carriage_geom proves the spare at that full
    worst case too."""
    height = _printed_limits(vb, "Height", vb.BLOCK_HEIGHT)
    screw_y = _printed_limits(vb, "SetScrewY", vb.SET_SCREW_Y)
    axis_min, axis_max = height[0] - screw_y[1], height[1] - screw_y[0]
    rise = (vb.PIVOT_BORE_DIA - groove.GROOVE_DIA) / 2.0
    point_half = (
        rod_set_screw.MAJOR_DIA - 2.0 * (rod_set_screw.POINT_LENGTH - rise)
    ) / 2.0
    near_low, near_high = printed_deviations(
        groove.GROOVE_NEAR_STATION, groove.GROOVE_PLACES, unit=rod.UNIT
    )
    far_low, far_high = printed_deviations(
        groove.GROOVE_FAR_STATION, groove.GROOVE_PLACES, unit=rod.UNIT
    )
    return (
        axis_min - point_half - (groove.GROOVE_NEAR_STATION + near_high),
        groove.GROOVE_FAR_STATION + far_low - (axis_max + point_half),
    )


if min(groove_landing_spare()) <= 0.0:
    raise AssertionError("the rod set screw's point can land on a groove wall")
# The cup sits .010 inside the bore wall, the chamfered point there, so the
# first full thread stays in the tap (rule 18 counts it wholly engaged).
if rod_set_screw.POINT_LENGTH <= (vb.PIVOT_BORE_DIA - groove.GROOVE_DIA) / 2.0:
    raise AssertionError("the rod set screw's full thread leaves the tap")
