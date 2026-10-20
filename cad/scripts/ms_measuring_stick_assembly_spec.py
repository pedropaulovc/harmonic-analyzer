"""Pure placement and fitting contract for ms-measuring-stick.SLDASM (MHA-MS-00).

The ch16 measuring stick and its clamped stop (user-approved re-derivation,
2026-10-09): the graduated bar, the brass block, its cover plate, the two
MHA-MS-VN-51 plate screws and one MHA-MS-VN-50 knurled thumbscrew. The assembly
frame IS the stop frame of ``ms_stop_spec`` (X along the stick, Y from the
thumbscrew face up to the roof, Z from the cover into the block), so the
block and plate sit at the identity and every other pose below is derived
from the part contracts -- the builder, the top-level park pose and the
fitter drawing all read these values; none of them restates a dimension.

Builder data only: everything here reaches the saved .SLDASM (poses, the
clamped-setting sketch and its tolerance/precision, the top-level park
envelope). The explode lives in ``ms_measuring_stick_explode_spec``; the
fitter drawing's BOM, captions and text in ``ms_measuring_stick_assembly_sheet``.

Clamped state: the stick rides the window against the roof, graduations up,
with the thumbscrew's tip on its underside and the block centred on the
STOP_MARK division. Rotation rows follow ``_transforms``: ``rows[i]`` is the
assembly-frame image of the part's local axis ``i``. No SolidWorks imports.
"""

from __future__ import annotations

import ms_stick_spec as stick
import ms_stop_spec as stop
import _mcmaster_90114a124 as plate_screw
import _mcmaster_91882a221 as thumb

ASM_NAME = "ms-measuring-stick"

STICK = "ms-stick"
BLOCK = "ms-stop-block"
PLATE = "ms-stop-plate"
PLATE_SCREW = "ms-vn-stop-plate-screw"
THUMB_SCREW = "ms-vn-thumb-screw"

# Every component family and its count: the builder places, the explode moves
# and the drawing's BOM proves exactly this inventory.
QUANTITIES = {STICK: 1, BLOCK: 1, PLATE: 1, PLATE_SCREW: 2, THUMB_SCREW: 1}

Rows = tuple[tuple[float, float, float], ...]
IDENTITY_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

# --- Stick ------------------------------------------------------------------
# ms-stick's frame: X along the 200 bar, Y across its 8 width (the ticks hang
# from the y=8 edge), Z through its 3 thickness from the graduated z=0 face
# (outward normal -Z). Graduations up against the roof: part -Z -> +Y, i.e.
# part Z -> -Y; part X stays along the stop; part Y runs across into +Z.
STICK_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
STICK_MARK_X = stick.SCALE_START_X + stop.STOP_MARK * stick.DIVISION_SPACING
STICK_TOP_Y = stop.WINDOW_Y_MAX  # the graduated face bears on the roof
STICK_BOTTOM_Y = STICK_TOP_Y - stick.BODY_THICKNESS
STICK_SIDE_CLEARANCE = (stop.WINDOW_WIDTH - stick.BODY_WIDTH) / 2.0
STICK_Z_MIN = stop.WINDOW_Z_MIN + STICK_SIDE_CLEARANCE
STICK_Z_MAX = STICK_Z_MIN + stick.BODY_WIDTH
# The STOP_MARK division sits on the thumbscrew axis (the block's centre).
STICK_ORIGIN = (stop.THUMB_AXIS_X - STICK_MARK_X, STICK_TOP_Y, STICK_Z_MIN)
STICK_X_MIN = STICK_ORIGIN[0]
STICK_X_MAX = STICK_X_MIN + stick.BODY_LENGTH
# Under the clamped bar, down to the window floor.
STICK_FLOOR_GAP = STICK_BOTTOM_Y - stop.WINDOW_Y_MIN

# --- Block and cover plate --------------------------------------------------
BLOCK_ORIGIN = (0.0, 0.0, 0.0)
PLATE_ORIGIN = (0.0, 0.0, 0.0)

# --- Thumbscrew -------------------------------------------------------------
# ms-vn-thumb-screw's frame: outer head face at X=0, axis +X, collar bearing face
# at HEAD_STACK_LEN, tip at OVERALL_LEN. Axis up the tapped wall: part X -> +Y.
THUMB_ROWS: Rows = ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
THUMB_TIP_Y = STICK_BOTTOM_Y  # the tip clamps the bar's underside
THUMB_HEAD_FACE_Y = THUMB_TIP_Y - thumb.OVERALL_LEN  # the stop's lowest point
THUMB_COLLAR_FACE_Y = THUMB_HEAD_FACE_Y + thumb.HEAD_STACK_LEN
THUMB_ORIGIN = (stop.THUMB_AXIS_X, THUMB_HEAD_FACE_Y, stop.THUMB_AXIS_Z)
THUMB_EXPOSED_THREAD = 0.0 - THUMB_COLLAR_FACE_Y  # collar to the block's face
THUMB_ENGAGED_THREAD = stop.FLOOR_THICKNESS  # the whole tapped wall

# --- Plate screws -----------------------------------------------------------
# ms-vn-stop-plate-screw's frame: head +Y, thread -Y, bearing plane Y=0. The
# thread runs +Z into the block (part -Y -> +Z, part Y -> -Z); the bearing
# plane sits on the plate's outer face.
PLATE_SCREW_ROWS: Rows = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))
PLATE_SCREW_ORIGINS = tuple(
    (x, stop.PLATE_HOLE_Y, stop.PLATE_Z_MIN) for x in stop.PLATE_HOLE_XS
)
PLATE_SCREW_TIP_Z = stop.PLATE_Z_MIN + plate_screw.LENGTH
PLATE_SCREW_HEAD_Z = stop.PLATE_Z_MIN - plate_screw.HEAD_H
PLATE_SCREW_ENGAGED = PLATE_SCREW_TIP_Z - stop.PLATE_Z_MAX
PLATE_SCREW_TAP_RESERVE = stop.PLATE_TAP_THREAD_DEPTH - PLATE_SCREW_ENGAGED

# --- Envelope in the assembly frame (the park pose reads it) ------------------
EXTENT_MIN = (
    min(STICK_X_MIN, 0.0),
    THUMB_HEAD_FACE_Y,
    min(PLATE_SCREW_HEAD_Z, stop.THUMB_AXIS_Z - thumb.HEAD_DIA / 2.0),
)
EXTENT_MAX = (
    max(STICK_X_MAX, stop.BLOCK_LENGTH),
    stop.BLOCK_HEIGHT,
    max(stop.BLOCK_DEPTH, stop.THUMB_AXIS_Z + thumb.HEAD_DIA / 2.0),
)

# --- Clamped setting (a construction sketch in the .SLDASM) ------------------
# Assembly acceptance measured between real faces; no component size is changed.
# The builder applies its tolerance and both precisions to the model dimension.
SETTING_TOLERANCE_MM = 0.10
SETTING_NEAR_FACE_MM = BLOCK_ORIGIN[0] - STICK_X_MIN
SETTING_PRECISION = 1
SETTING_TOLERANCE_PRECISION = 2
SETTING_FEATURE = "ClampedSetting"
SETTING_DIMENSION = "NearFaceFromStickEnd"
DRAWING_PRECISION = {SETTING_FEATURE: {SETTING_DIMENSION: SETTING_PRECISION}}
SETTING_CHORD = (
    (STICK_X_MIN, STICK_TOP_Y),
    (BLOCK_ORIGIN[0], STICK_TOP_Y),
)

assert STICK_SIDE_CLEARANCE > 0.0, STICK_SIDE_CLEARANCE
assert STICK_FLOOR_GAP > 0.0, STICK_FLOOR_GAP
assert STICK_Z_MAX < stop.WINDOW_Z_MAX, STICK_Z_MAX
assert STICK_X_MIN < 0.0 and STICK_X_MAX > stop.BLOCK_LENGTH, (STICK_X_MIN, STICK_X_MAX)
assert THUMB_EXPOSED_THREAD > 0.0, THUMB_EXPOSED_THREAD
assert abs(
    THUMB_EXPOSED_THREAD + THUMB_ENGAGED_THREAD + STICK_FLOOR_GAP - thumb.SHANK_LEN
) < 1e-9
assert 0.0 < PLATE_SCREW_ENGAGED < stop.PLATE_TAP_THREAD_DEPTH, PLATE_SCREW_ENGAGED
