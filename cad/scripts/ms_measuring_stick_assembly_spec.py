"""Pure placement and fitting contract for ms-measuring-stick.SLDASM (MHA-MS-000).

The ch16 measuring stick and its clamped stop (user-approved re-derivation,
2026-10-09): the graduated bar, the brass block, its cover plate, the two
MHA-VN-054 plate screws and one MHA-VN-011 knurled thumbscrew. The assembly
frame IS the stop frame of ``ms_stop_spec`` (X along the stick, Y from the
thumbscrew face up to the roof, Z from the cover into the block), so the
block and plate sit at the identity and every other pose below is derived
from the part contracts -- the builder, the top-level park pose and the
fitter drawing all read these values; none of them restates a dimension.

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
DRAWING_NUMBER = "MHA-MS-000"

STICK = "ms-stick"
BLOCK = "ms-stop-block"
PLATE = "ms-stop-plate"
PLATE_SCREW = "vn-ms-stop-plate-screw"
THUMB_SCREW = "vn-thumb-screw"

# Every component family and its count: the builder places, the explode moves
# and the drawing's BOM proves exactly this inventory.
QUANTITIES = {STICK: 1, BLOCK: 1, PLATE: 1, PLATE_SCREW: 2, THUMB_SCREW: 1}
BOM_ORDER = (STICK, BLOCK, PLATE, PLATE_SCREW, THUMB_SCREW)

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
# vn-thumb-screw's frame: outer head face at X=0, axis +X, collar bearing face
# at HEAD_STACK_LEN, tip at OVERALL_LEN. Axis up the tapped wall: part X -> +Y.
THUMB_ROWS: Rows = ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
THUMB_TIP_Y = STICK_BOTTOM_Y  # the tip clamps the bar's underside
THUMB_HEAD_FACE_Y = THUMB_TIP_Y - thumb.OVERALL_LEN  # the stop's lowest point
THUMB_COLLAR_FACE_Y = THUMB_HEAD_FACE_Y + thumb.HEAD_STACK_LEN
THUMB_ORIGIN = (stop.THUMB_AXIS_X, THUMB_HEAD_FACE_Y, stop.THUMB_AXIS_Z)
THUMB_EXPOSED_THREAD = 0.0 - THUMB_COLLAR_FACE_Y  # collar to the block's face
THUMB_ENGAGED_THREAD = stop.FLOOR_THICKNESS  # the whole tapped wall

# --- Plate screws -----------------------------------------------------------
# vn-ms-stop-plate-screw's frame: head +Y, thread -Y, bearing plane Y=0. The
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

# BOM DESCRIPTION cells (the parts carry no Description property); the steps
# below name the parts the same way.
BOM_DESCRIPTIONS = {
    STICK: "GRADUATED STICK",
    BLOCK: "STOP BLOCK",
    PLATE: "STOP COVER PLATE",
    PLATE_SCREW: f"{plate_screw.THREAD} X 1/4 BRASS FILLISTER SCREW",
    THUMB_SCREW: f"{thumb.THREAD} X 7/16 KNURLED THUMBSCREW",
}

# --- Native explode (MS_EXPLODED) --------------------------------------------
# The disassembly order, ASSEMBLY_STEPS read back to front: the cover and its
# screws off the open side, the screws clear of the cover, the bar out of the
# opened window, then the thumbscrew down its axis. (label, families, axis,
# signed distance mm), all along the assembly's global axes. The distances are
# sized for the drawing's *Isometric (it looks from +X+Y+Z, the closed side):
# each further -Z step slides a part up and right on the sheet, so the screws
# withdraw far enough to clear the cover's outline instead of hiding behind
# it, and the thumbscrew drops clear of the block.
EXPLODED_VIEW_NAME = "MS_EXPLODED"
SOURCE_CONFIGURATION = "Default"
EXPLODE_STEPS = (
    ("cover comes off", (PLATE, PLATE_SCREW), "z", -24.0),
    ("plate screws withdraw", (PLATE_SCREW,), "z", -26.0),
    ("stick leaves window", (STICK,), "z", -12.0),
    ("thumbscrew backs out", (THUMB_SCREW,), "y", -22.0),
)

# --- Fitter package text ------------------------------------------------------
EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEET 3"
# Components own material and finish; no assembly coating operation is required.
# The fitter's order; the explode above runs steps 2-5 backwards. Each line
# names the parts as the BOM's DESCRIPTION column does. The block and its
# cover are a match-drilled pair (step 1): neither is interchangeable.
ASSEMBLY_STEPS = (
    "1. MATCH-DRILL THE PAIR: CLAMP THE STOP COVER PLATE ON THE STOP BLOCK, "
    f"OUTLINES ALIGNED; PILOT BOTH SCREW HOLES DIA {stop.PLATE_TAP_DRILL_DIA:.2f} "
    "THROUGH PLATE INTO BLOCK IN ONE PASS. REMOVE THE PLATE; OPEN ITS HOLES TO "
    f"DIA {stop.PLATE_CLEARANCE_DIA:.1f}; BOTTOMING-TAP THE BLOCK HOLES "
    f"{plate_screw.THREAD}. MARK BLOCK AND PLATE AS A PAIR.",
    f"2. START THE {thumb.THREAD} KNURLED THUMBSCREW UP INTO THE STOP BLOCK FROM "
    "ITS UNDERSIDE; KEEP THE TIP BELOW THE WINDOW FLOOR.",
    "3. LAY THE GRADUATED STICK, GRADUATED FACE UP, INTO THE BLOCK WINDOW FROM "
    "ITS OPEN SIDE.",
    "4. FIT ITS OWN STOP COVER PLATE OVER THE WINDOW, PAIR MARKS TOGETHER; DRIVE "
    f"BOTH {plate_screw.THREAD} BRASS FILLISTER SCREWS UNTIL THE HEADS SEAT.",
    "5. LOCATE THE STOP BLOCK'S NEAR FACE FROM THE LEFT STICK END USING THE "
    "LOCATION REFERENCE ON SHEET 1; THEN TURN THE THUMBSCREW IN BY HAND UNTIL "
    "ITS TIP CLAMPS THE STICK AGAINST THE ROOF.",
)
ASSEMBLY_CHECKS = (
    "CHECK: WITH THE THUMBSCREW BACKED OFF THE STICK SLIDES FREELY IN THE WINDOW.",
    "CHECK: CLAMPED, THE STOP DOES NOT MOVE ALONG THE STICK.",
    "CHECK: BOTH SCREW HEADS SEAT ON THE COVER AND THE COVER LIES FLAT ON THE BLOCK.",
)
CLAMPED_SETUP_NOTE = (
    "CLAMPED SETUP: LOCATE THE BLOCK'S NEAR FACE FROM THE LEFT STICK END "
    "USING THE LOCATION REFERENCE ABOVE; THEN CLAMP. GRADUATED FACE AGAINST "
    "THE ROOF; THUMBSCREW TIP ON THE STICK UNDERSIDE."
)

# --- Reference dimensions (sheet 1, front view) -------------------------------
# Parenthesized REFERENCE values only: the stick and stop drawings own every
# size and its tolerance. OVERALL is the stick end to end; the STOP POSITION
# is the stop's near (X=0) face from the stick's scale-start end (part x=0)
# with the STOP_MARK division on the thumbscrew axis -- the mark less half
# the block.
REFERENCE_OVERALL_LENGTH = STICK_X_MAX - STICK_X_MIN
REFERENCE_STOP_FACE = BLOCK_ORIGIN[0] - STICK_X_MIN
STOP_POSITION_CALLOUT = f"STOP AT {stop.STOP_MARK:.1f} MARK"
DRAWING_REFERENCE_PRECISION = 1

assert STICK_SIDE_CLEARANCE > 0.0, STICK_SIDE_CLEARANCE
assert STICK_FLOOR_GAP > 0.0, STICK_FLOOR_GAP
assert STICK_Z_MAX < stop.WINDOW_Z_MAX, STICK_Z_MAX
assert STICK_X_MIN < 0.0 and STICK_X_MAX > stop.BLOCK_LENGTH, (STICK_X_MIN, STICK_X_MAX)
assert THUMB_EXPOSED_THREAD > 0.0, THUMB_EXPOSED_THREAD
assert abs(
    THUMB_EXPOSED_THREAD + THUMB_ENGAGED_THREAD + STICK_FLOOR_GAP - thumb.SHANK_LEN
) < 1e-9
assert 0.0 < PLATE_SCREW_ENGAGED < stop.PLATE_TAP_THREAD_DEPTH, PLATE_SCREW_ENGAGED
assert sorted(QUANTITIES) == sorted(BOM_ORDER)
