"""Pure placement and fitting contract for ms-measuring-stick.SLDASM (MHA-MS-00).

The ch16 measuring stick and its clamped stop (user-approved re-derivation,
2026-10-09): the graduated bar, the brass block, its cover plate, the two
MHA-MS-VN-51 plate screws and one MHA-SH-VN-55 knurled thumbscrew. The assembly
frame turns ``ms_stop_spec`` half a turn about the stick's X axis: the
thumbscrew is above the stick (+Y), the block below it, and the cover faces
+Z. The builder, the top-level park pose and the fitter drawing all read
these values; none of them restates a dimension.

Builder data only: everything here reaches the saved .SLDASM (poses, the
clamped-setting reference sketch and its precision, the top-level park
envelope). The explode lives in ``ms_measuring_stick_explode_spec``; the
fitter drawing's BOM, captions and text in ``ms_measuring_stick_assembly_sheet``.

Clamped state: the graduated face still bears on the window wall opposite
the thumbscrew, with the tip on the plain face and the block centred on the
STOP_MARK division. The 2026-10-20 user ruling puts the screw above, so the
graduations face down; no part or mating relationship changes. Rotation rows
are the assembly-frame images of the part's local axes. No SolidWorks imports.
"""

from __future__ import annotations

import ms_stick_spec as stick
import ms_stop_spec as stop
import _mcmaster_90114a124 as plate_screw
import sh_vn_thumb_screw_spec as thumb

ASM_NAME = "ms-measuring-stick"

STICK = "ms-stick"
BLOCK = "ms-stop-block"
PLATE = "ms-stop-plate"
PLATE_SCREW = "ms-vn-stop-plate-screw"
THUMB_SCREW = "sh-vn-thumb-screw"

# Every component family and its count: the builder places, the explode moves
# and the drawing's BOM proves exactly this inventory.
QUANTITIES = {STICK: 1, BLOCK: 1, PLATE: 1, PLATE_SCREW: 2, THUMB_SCREW: 1}

Rows = tuple[tuple[float, float, float], ...]
WORKING_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))

# Only the graduated-underside inspection follows the old stop frame.
# The exploded camera looks down from -X+Y+Z, keeping the thumbscrew above.
DRAWING_UNDERSIDE_VIEW = "MS GRADUATED UNDERSIDE"
DRAWING_STANDARD_VIEWS = {DRAWING_UNDERSIDE_VIEW: 5}
DRAWING_EXPLODED_VIEW = "ISO FRONT-TOP-LEFT"
DRAWING_EXPLODED_OCTANTS = {"FRONT-TOP-LEFT": (-1, 1, 1)}

# --- Stick ------------------------------------------------------------------
# ms-stick's frame: X along the bar (BODY_LENGTH), Y across its BODY_WIDTH (the
# ticks hang from the y=BODY_WIDTH edge), Z through its BODY_THICKNESS from the
# graduated z=0 face
# (outward normal -Z). The same fit, turned screw-up: part -Z -> -Y,
# part X stays along the stop, and part Y runs across into -Z.
STICK_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))
STICK_MARK_X = stick.SCALE_START_X + stop.STOP_MARK * stick.DIVISION_SPACING
STICK_BOTTOM_Y = -stop.WINDOW_Y_MAX  # the graduated face bears on the fixed wall
STICK_TOP_Y = STICK_BOTTOM_Y + stick.BODY_THICKNESS
STICK_SIDE_CLEARANCE = (stop.WINDOW_WIDTH - stick.BODY_WIDTH) / 2.0
STICK_Z_MAX = -stop.WINDOW_Z_MIN - STICK_SIDE_CLEARANCE
STICK_Z_MIN = STICK_Z_MAX - stick.BODY_WIDTH
# The STOP_MARK division sits on the thumbscrew axis (the block's centre).
STICK_ORIGIN = (stop.THUMB_AXIS_X - STICK_MARK_X, STICK_BOTTOM_Y, STICK_Z_MAX)
STICK_X_MIN = STICK_ORIGIN[0]
STICK_X_MAX = STICK_X_MIN + stick.BODY_LENGTH
# From the clamped bar's plain face to the tapped wall above it.
STICK_TAPPED_WALL_GAP = -stop.WINDOW_Y_MIN - STICK_TOP_Y

# --- Block and cover plate --------------------------------------------------
BLOCK_ORIGIN = (0.0, 0.0, 0.0)
PLATE_ORIGIN = (0.0, 0.0, 0.0)
BLOCK_ROWS = WORKING_ROWS
PLATE_ROWS = WORKING_ROWS

# --- Thumbscrew -------------------------------------------------------------
# sh-vn-thumb-screw's frame: outer head face at X=0, axis +X, collar bearing face
# at HEAD_STACK_LEN, tip at OVERALL_LEN. The screw points down: part X -> -Y.
THUMB_ROWS: Rows = ((0.0, -1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, -1.0))
THUMB_TIP_Y = STICK_TOP_Y  # the tip clamps the bar's plain face
THUMB_HEAD_FACE_Y = THUMB_TIP_Y + thumb.OVERALL_LEN  # the assembly's highest point
THUMB_COLLAR_FACE_Y = THUMB_HEAD_FACE_Y - thumb.HEAD_STACK_LEN
THUMB_ORIGIN = (stop.THUMB_AXIS_X, THUMB_HEAD_FACE_Y, -stop.THUMB_AXIS_Z)
THUMB_EXPOSED_THREAD = THUMB_COLLAR_FACE_Y  # collar above the block's tapped face
THUMB_ENGAGED_THREAD = stop.FLOOR_THICKNESS  # the whole tapped wall

# --- Plate screws -----------------------------------------------------------
# ms-vn-stop-plate-screw's frame: head +Y, thread -Y, bearing plane Y=0. The
# thread runs -Z into the block (part -Y -> -Z, part Y -> +Z); the bearing
# plane sits on the plate's outer face.
PLATE_SCREW_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
PLATE_SCREW_ORIGINS = tuple(
    (x, -stop.PLATE_HOLE_Y, -stop.PLATE_Z_MIN) for x in stop.PLATE_HOLE_XS
)
PLATE_SCREW_TIP_Z = -stop.PLATE_Z_MIN - plate_screw.LENGTH
PLATE_SCREW_HEAD_Z = -stop.PLATE_Z_MIN + plate_screw.HEAD_H
PLATE_SCREW_ENGAGED = -stop.PLATE_Z_MAX - PLATE_SCREW_TIP_Z
PLATE_SCREW_TAP_RESERVE = stop.PLATE_TAP_THREAD_DEPTH - PLATE_SCREW_ENGAGED

# --- Envelope in the assembly frame (the park pose reads it) ------------------
EXTENT_MIN = (
    min(STICK_X_MIN, 0.0),
    -stop.BLOCK_HEIGHT,
    min(-stop.BLOCK_DEPTH, -stop.THUMB_AXIS_Z - thumb.HEAD_DIA / 2.0),
)
EXTENT_MAX = (
    max(STICK_X_MAX, stop.BLOCK_LENGTH),
    THUMB_HEAD_FACE_Y,
    max(PLATE_SCREW_HEAD_Z, -stop.THUMB_AXIS_Z + thumb.HEAD_DIA / 2.0),
)

# --- Clamped setting (a construction sketch in the .SLDASM) ------------------
# A reference to the saved pose, not an acceptance band: STOP_MARK places the
# block on a calibrated graduation and no fit consumes this span. It prints
# parenthesized, at three decimal-inch places.
SETTING_NEAR_FACE_MM = BLOCK_ORIGIN[0] - STICK_X_MIN
SETTING_PRECISION = 3
SETTING_FEATURE = "ClampedSetting"
SETTING_DIMENSION = "NearFaceFromStickEnd"
DRAWING_PRECISION = {SETTING_FEATURE: {SETTING_DIMENSION: SETTING_PRECISION}}
SETTING_CHORD = (
    (STICK_X_MIN, STICK_BOTTOM_Y),
    (BLOCK_ORIGIN[0], STICK_BOTTOM_Y),
)

assert STICK_SIDE_CLEARANCE > 0.0, STICK_SIDE_CLEARANCE
assert STICK_TAPPED_WALL_GAP > 0.0, STICK_TAPPED_WALL_GAP
assert STICK_Z_MIN > -stop.WINDOW_Z_MAX, STICK_Z_MIN
assert STICK_X_MIN < 0.0 and STICK_X_MAX > stop.BLOCK_LENGTH, (STICK_X_MIN, STICK_X_MAX)
assert THUMB_EXPOSED_THREAD > 0.0, THUMB_EXPOSED_THREAD
assert abs(
    THUMB_EXPOSED_THREAD + THUMB_ENGAGED_THREAD + STICK_TAPPED_WALL_GAP - thumb.SHANK_LEN
) < 1e-9
assert 0.0 < PLATE_SCREW_ENGAGED < stop.PLATE_TAP_THREAD_DEPTH, PLATE_SCREW_ENGAGED


def assert_thumbscrew_up(axis: tuple[float, ...], *, label: str) -> None:
    """The live screw's head-to-tip axis must point down, not just look upright."""
    if len(axis) != 3 or not all(
        abs(actual - expected) < 1e-6
        for actual, expected in zip(axis, (0.0, -1.0, 0.0), strict=True)
    ):
        raise RuntimeError(f"{label}: thumbscrew head must be above the stick; axis {axis!r}")
