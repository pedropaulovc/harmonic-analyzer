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
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as vb
import pn_vn_pen_marker_spec as marker
import pn_vn_pen_rod_set_screw_spec as rod_set_screw
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
PEN_TRAVEL_HALF_MM = 15.0
# Recording paper y 324.5..405 (build_pd_paper_drive_assembly): the marker
# axis rests at mid-height so the trace stays on the sheet.
PAPER_MID_Y = 364.75

BRASS_G_PER_MM3 = 8.5e-3
AISI_304_G_PER_MM3 = 8.0e-3

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
# block -X. Flush with the paper end face; the window straddles the block section,
# its top rail FRAME_TOP_GAP above the block top.
FRAME_TOP_GAP = 0.1
FRAME_X0_LOCAL = 0.0  # the frame's paper-side face, flush with the block end
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
# sits on the pivot-bore wall.
ROD_SET_SCREW_CUP_LOCAL_Z = vb.DEPTH_MID_Z - vb.PIVOT_BORE_DIA / 2.0
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
    edge_r = frame.EDGE_ROUND_R
    points = {
        "v-block neck paper-end corner": machine_z(0.0, vb.NECK_DEPTH),
        "v-block body paper-side corner": machine_z(vb.RELIEF_X0, vb.BODY_Z1),
        # The paper's normal lies inside the round's quarter (block -x .. +z),
        # so its paper-most point stands edge_r off its axis toward the paper.
        "stirrup paper-side round": machine_z(
            FRAME_X0_LOCAL + edge_r, frame_z_paper - edge_r
        )
        + edge_r,
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
# neck.  No fit-up setting moves the block or the stirrup off the paper (the
# nib preset slides only the marker, which the final machine sets from the
# paper by its nib), so the two prints' loose bands must hold the rigid
# carriage off it at their worst case together.  About the rod axis (the
# pivot bore): the block prints its length-wise stations from the paper end
# and its depth-wise ones from the body's front face, all .XX.  The stirrup
# seats flush on the paper end (assembly step 3) and sits anywhere across the
# neck its window lets it: neither its window corner radii nor the thumb
# screw's tip on the round grip stops it, so at worst its window's front wall
# lies on the neck's front face.  Its paper-side edge round
# (pn_pen_frame_spec.EDGE_ROUND_R), at its printed minimum, keeps it off.
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
    # The stirrup's outer faces with its window's front wall on the neck.
    frame_front = neck_front - _printed_limits(frame, "LeftWall", frame.RAIL_SIDE)[0]
    frame_paper = (
        frame_front + _printed_limits(frame, "OuterSpanX", frame.OUTER_WIDTH)[1]
    )
    r = _printed_limits(frame, "EdgeRoundR", frame.EDGE_ROUND_R)[0]
    # The thumb screw's axis: ScrewZ from the stirrup's rod-side face, so from
    # the paper end it stands the depth less ScrewZ.
    screw_x = (
        _printed_limits(frame, "Depth", frame.FRAME_DEPTH)[0]
        - _printed_limits(frame, "ScrewZ", frame.FRAME_DEPTH / 2.0)[1]
    )
    screw_z = frame_front + _printed_limits(frame, "ScrewX", frame.OUTER_WIDTH / 2.0)[1]
    return {
        "v-block neck paper-end corner": z_at(0.0, neck_back),
        "v-block body paper-side corner": z_at(step, body_back),
        "stirrup paper-side round": z_at(r, frame_paper - r) + r,
        "thumb-screw head rim": z_at(screw_x, screw_z) + thumb.HEAD_DIA / 2.0,
    }


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
        ("pivot bore", -_cyl(pivot_r, H - vb.RELIEF_HEIGHT), vb.PIVOT_BORE_X, zc),
        (
            "set-screw tap",
            -_cyl(tap_r, vb.SET_SCREW_TAP_LENGTH),
            vb.PIVOT_BORE_X,
            vb.BODY_Z0 + vb.SET_SCREW_TAP_LENGTH / 2.0,
        ),
    ]
    items = [(f"v-block {n}", v * BRASS_G_PER_MM3, x, z) for n, v, x, z in block]

    ring = (
        frame.OUTER_WIDTH * frame.OUTER_HEIGHT
        - frame.WINDOW_WIDTH * frame.WINDOW_HEIGHT
    ) * frame.FRAME_DEPTH - _cyl(frame.SET_SCREW_TAP_DRILL_DIA / 2.0, frame.RAIL_END)
    # The two diagonal edge rounds: a pair about the ring's centre.
    ring -= 2.0 * (1.0 - math.pi / 4.0) * frame.EDGE_ROUND_R**2 * frame.OUTER_HEIGHT
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
            rod_set_screw.MASS_G,
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
if frame.WINDOW_WIDTH < vb.NECK_DEPTH + 2.0:
    raise AssertionError("stirrup window must pass the neck with 1.0 a side")
if FRAME_X0_LOCAL + frame.FRAME_DEPTH + 4.0 * CLEARANCE > vb.RELIEF_X0:
    raise AssertionError("the stirrup must slide on the neck clear of the body's step")
if FRAME_WINDOW_BOTTOM_LOCAL_Y > MARKER_BOTTOM_LOCAL_Y - 1.0:
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
