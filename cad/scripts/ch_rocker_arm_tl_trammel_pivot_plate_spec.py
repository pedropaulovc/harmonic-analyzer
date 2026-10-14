r"""Pure-data contract for the rocker template trammel's pivot plate (MHA-CH-006-TL-19).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). Trial route
``rocker-template-route.md`` section 2.1: "a 1018 offcut from the block bar,
about 50 x 38 x 19, with a #2 centre-drilled 60 degree cone in its middle. Screw
it to the board." The plate is screwed to the MDF scribing board
(inventory ``fixtures.trammel-board-mdf``) and the trammel's 60 degree pivot
point (MHA-CH-006-TL-18) runs in its cone while R800/R816 are scribed. The
plate is an offcut of the blocks' 3/4 x 1-1/2 in bar (``kit.BLOCK_WIDTH`` x
``kit.BLOCK_HEIGHT``), sawn to the blocks' length; the stock sizes stay as
bought.

The seat is a 5/64 in pilot drilled blind and the No. 2 centre drill's 60
degree countersink (inventory ``tools.center-drills-lms-4859`` member "2")
opening it to the printed mouth. The pilot runs deeper than the centre drill's
own 1.98 pilot so no pivot tip, at any printed seat, reaches its floor. Two #8
flat-head wood screws hold the plate down through countersunk clearance holes
either side of the seat, on the same centre line.

Frame (SolidWorks model, and the ``PRECHIPS_SOLIDS`` frame): origin at the
plate's left end, bottom (the face on the board) and back long side; +X along
the 50 length, +Y up through the 19.05 stock height (the seat face is
Y = PLATE_HEIGHT), the 38.1 stock width along -Z (Z 0 to -PLATE_WIDTH). Every
hole axis is vertical (+Y) on the mid-width line Z = -HOLE_Y.
"""

from __future__ import annotations

import math
from typing import Any

import ch_rocker_arm_tl_trammel_spec as kit
from _printed_tolerance import angular_band_deg, drilled_oversize_mm, printed_band_mm

INCH = kit.INCH
_X = printed_band_mm(1)
_XX = printed_band_mm(2)
# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(), 0.0)
# The cones print their face-to-flank angle at the title block's general
# angular band; each flank moving by it moves the included angle twice as much.
INCLUDED_ANGLE_TOL_DEG = 2.0 * angular_band_deg()

# --- Plate: the blocks' bar offcut (stock width and height as bought) --------
PLATE_LENGTH = kit.BLOCK_LENGTH  # 50.0, sawn and faced
PLATE_WIDTH = kit.BLOCK_WIDTH  # 38.1, 1-1/2 in stock
PLATE_HEIGHT = kit.BLOCK_HEIGHT  # 19.05, 3/4 in stock

# --- Pivot seat: blind pilot plus the centre drill's 60 degree cone -----------
SEAT_X = kit.PIVOT_HOLE_L  # 25.0: the plate's middle, as the pivot block's hole
HOLE_Y = PLATE_WIDTH / 2.0  # 19.05 from the back long side: the mid-width line
# Model and export both use the printed two-place size (one fact).
PILOT_DIA = round(kit.CENTER_DRILL_PILOT_DIA, 2)  # 1.98, a 5/64 in drill
PILOT_DEPTH = 6.0  # full-diameter depth below the seat face
SEAT_DIA = 4.0  # the cone's mouth on the seat face
SEAT_ANGLE = kit.CENTER_DRILL_ANGLE  # 60 degrees included
# Printed as the angle from the seat face to the cone flank (the sketch's
# mouth-line-to-flank dimension): 90 - 30 = 60, which equals the included
# angle. The setting bar's H0 seat prints the same dimension.
SEAT_FLANK_ANGLE = 90.0 - SEAT_ANGLE / 2.0
# The sharpest printed cone: each flank at its band edge.
_SEAT_HALF_MIN = math.radians((SEAT_ANGLE - INCLUDED_ANGLE_TOL_DEG) / 2.0)
_SEAT_R_MIN = (SEAT_DIA - _XX) / 2.0
_SEAT_R_MAX = (SEAT_DIA + _XX) / 2.0
_PILOT_R_MAX = (PILOT_DIA + DRILLED_BAND[0]) / 2.0
# A flank exists at every printed seat: the smallest mouth stays outside the
# largest pilot, so the pivot point bears on the cone, not on a pilot edge
# alone.
SEAT_FLANK_MIN = _SEAT_R_MIN - _PILOT_R_MAX
if SEAT_FLANK_MIN <= 0.0:
    raise AssertionError("pivot plate seat mouth does not clear the pilot")
# A sharp tip in the largest, sharpest printed cone reaches that cone's
# apex; the shallowest printed pilot floor must stay below it.
SEAT_APEX_DEPTH_MAX = _SEAT_R_MAX / math.tan(_SEAT_HALF_MIN)
PILOT_FLOOR_ROOM = (PILOT_DEPTH - _X) - SEAT_APEX_DEPTH_MAX
if PILOT_FLOOR_ROOM <= 0.0:
    raise AssertionError("pivot point can bottom in the pivot plate's pilot")

# --- Screws: two #8 flat-head wood screws x 1-1/4 in into the MDF board ------
# ASME B18.6.1 #8 wood screw: body 0.164 in, flat head 0.332 in max, 82 deg.
SCREW_SIZE = "#8"
SCREW_BODY_DIA = 0.164 * INCH
SCREW_HEAD_DIA_MAX = 0.332 * INCH
SCREW_HEAD_ANGLE = 82.0
SCREW_LENGTH = 1.25 * INCH  # overall, head top to point
# A gimlet point is not full thread: allow one body diameter for it.
SCREW_POINT_ALLOWANCE = SCREW_BODY_DIA
SCREW_X = (10.0, 40.0)  # from the plate's left end, either side of the seat
HOLE_DIA = 4.5  # #16 drill (0.1770 in): #8 body clearance
# The shop's countersinks are 90 degree (inventory tools.countersinks); under
# the 82 degree head the head bears at its root, on the hole edge's cone.
CSK_ANGLE = 90.0
CSK_FLANK_ANGLE = 90.0 - CSK_ANGLE / 2.0  # face to flank, printed
CSK_DIA = 9.6
_CSK_HALF = math.radians(CSK_ANGLE / 2.0)
_CSK_R_MIN = (CSK_DIA - _XX) / 2.0
_CSK_R_MAX = (CSK_DIA + _XX) / 2.0
if HOLE_DIA <= SCREW_BODY_DIA:
    raise AssertionError("pivot plate screw hole does not clear the #8 body")
# The head root (body radius) seats on the 90 degree cone; the head top then
# sits HEAD_TOP_DEPTH below the face. The smallest countersink must still sink
# the head (no head proud of the seat face to foul the trammel's swing).
_HEAD_CONE = (
    (SCREW_HEAD_DIA_MAX - SCREW_BODY_DIA)
    / 2.0
    / math.tan(math.radians(SCREW_HEAD_ANGLE / 2.0))
)
_ROOT_DEPTH_MIN = (_CSK_R_MIN - SCREW_BODY_DIA / 2.0) / math.tan(_CSK_HALF)
_ROOT_DEPTH_MAX = (_CSK_R_MAX - SCREW_BODY_DIA / 2.0) / math.tan(_CSK_HALF)
HEAD_TOP_DEPTH_MIN = _ROOT_DEPTH_MIN - _HEAD_CONE
HEAD_TOP_DEPTH_MAX = _ROOT_DEPTH_MAX - _HEAD_CONE
if HEAD_TOP_DEPTH_MIN < 0.0:
    raise AssertionError("#8 flat head stands proud of the pivot plate face")
# The 90 degree cone narrows faster than the 82 degree head, so the head rim
# clears the countersink wall above the root.
if _CSK_R_MIN - HEAD_TOP_DEPTH_MIN * math.tan(_CSK_HALF) < SCREW_HEAD_DIA_MAX / 2.0:
    raise AssertionError("#8 head rim binds in the pivot plate countersink")

# drawing-guidelines.md rule 17 (walls and webs) at worst case: every station at
# its printed band edge, the largest countersink and mouth, the shortest and
# narrowest stock.
_POSITION = _X  # the screw and seat stations print one place
_HOLE_Y_BAND = _XX  # the mid-width stations print two places
_LENGTH_MIN = PLATE_LENGTH - _X
_WIDTH_MIN = PLATE_WIDTH - _X
_HEIGHT_MIN = PLATE_HEIGHT - _XX
_HEIGHT_MAX = PLATE_HEIGHT + _XX
WALLS_MM: dict[str, float] = {
    "left countersink to left end": SCREW_X[0] - _POSITION - _CSK_R_MAX,
    "right countersink to right end": _LENGTH_MIN
    - (SCREW_X[1] + _POSITION)
    - _CSK_R_MAX,
    "left countersink to seat": (SEAT_X - _POSITION - _SEAT_R_MAX)
    - (SCREW_X[0] + _POSITION + _CSK_R_MAX),
    "seat to right countersink": (SCREW_X[1] - _POSITION - _CSK_R_MAX)
    - (SEAT_X + _POSITION + _SEAT_R_MAX),
    "countersink to back side": HOLE_Y - _HOLE_Y_BAND - _CSK_R_MAX,
    "countersink to front side": _WIDTH_MIN - (HOLE_Y + _HOLE_Y_BAND) - _CSK_R_MAX,
    "seat to front side": _WIDTH_MIN - (HOLE_Y + _HOLE_Y_BAND) - _SEAT_R_MAX,
    "pilot floor to bottom": _HEIGHT_MIN - (PILOT_DEPTH + _X),
}
for _wall, _mm in WALLS_MM.items():
    if _mm < 2.0:
        raise AssertionError(
            f"pivot plate {_wall} wall {_mm:.3f} under drawing-guidelines.md rule 17 (walls and webs)"
        )

# drawing-guidelines.md rule 18 (thread engagement) at worst case: the tallest
# plate and the shallowest-sunk head leave the least screw in the board; less
# its gimlet point, the full thread must still reach one and a half body
# diameters. The deepest screw must stay inside the 3/4 in board.
BOARD_THICKNESS = 0.75 * INCH  # fixtures.trammel-board-mdf
SCREW_IN_BOARD_MIN = SCREW_LENGTH + HEAD_TOP_DEPTH_MIN - _HEIGHT_MAX
SCREW_FULL_THREAD_MIN = SCREW_IN_BOARD_MIN - SCREW_POINT_ALLOWANCE
if SCREW_FULL_THREAD_MIN < 1.5 * SCREW_BODY_DIA:
    raise AssertionError(
        "#8 wood screw engages the board under one and a half diameters"
    )
SCREW_IN_BOARD_MAX = SCREW_LENGTH + HEAD_TOP_DEPTH_MAX - _HEIGHT_MIN
if SCREW_IN_BOARD_MAX >= BOARD_THICKNESS:
    raise AssertionError("#8 wood screw breaks through the scribing board")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateLength", "PlateWidth"},
    "Plate": {"PlateHeight"},
    "ScrewHoleProfile": {"HoleLeftX", "HoleRightX", "HoleY", "HoleDia"},
    "PilotProfile": {"PilotX", "PilotY", "PilotDia"},
    "Pilot": {"PilotDepth"},
    "SeatProfile": {"SeatDia", "SeatFlankAngle"},
    "CountersinkProfile1": {"CskDia", "CskFlankAngle"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {"PlateLength": 1, "PlateWidth": 1},
    "Plate": {"PlateHeight": 2},
    "ScrewHoleProfile": {"HoleLeftX": 1, "HoleRightX": 1, "HoleY": 2, "HoleDia": 2},
    "PilotProfile": {"PilotX": 1, "PilotY": 2, "PilotDia": 2},
    "Pilot": {"PilotDepth": 1},
    "SeatProfile": {"SeatDia": 2, "SeatFlankAngle": 0},
    "CountersinkProfile1": {"CskDia": 2, "CskFlankAngle": 0},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked pivot plate dimension needs authored places")
# The printed values are the model values (no hidden rounding).
for _name, _value in (
    ("PlateLength", PLATE_LENGTH),
    ("PlateWidth", PLATE_WIDTH),
    ("PlateHeight", PLATE_HEIGHT),
    ("HoleLeftX", SCREW_X[0]),
    ("HoleRightX", SCREW_X[1]),
    ("HoleY", HOLE_Y),
    ("HoleDia", HOLE_DIA),
    ("PilotX", SEAT_X),
    ("PilotY", HOLE_Y),
    ("PilotDia", PILOT_DIA),
    ("PilotDepth", PILOT_DEPTH),
    ("SeatDia", SEAT_DIA),
    ("SeatFlankAngle", SEAT_FLANK_ANGLE),
    ("CskDia", CSK_DIA),
    ("CskFlankAngle", CSK_FLANK_ANGLE),
):
    if abs(_value - round(_value, DRAWING_PRECISION_BY_NAME[_name])) > 1e-9:
        raise AssertionError(f"pivot plate {_name} {_value} does not print as modelled")
# (feature, dimension) native bands; every other size is the title block's
# general band for its places.
DRILLED_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("ScrewHoleProfile", "HoleDia"),
    ("PilotProfile", "PilotDia"),
)

# Sheet callouts (the draw imports them; tolerance text never lives there).
PIVOT_POINT_NUMBER = "MHA-CH-006-TL-18"
# HoleY locates both screw holes (the right one is driven equal).
CALLOUTS_ABOVE = {"HoleY": "2X", "HoleDia": "2X", "CskDia": "2X", "CskFlankAngle": "2X"}
CALLOUTS_BELOW = {
    "HoleDia": "THRU",
    "CskDia": f"FOR {SCREW_SIZE} FLAT HEAD WOOD SCREW",
    "SeatDia": f"SEAT FOR {PIVOT_POINT_NUMBER} PIVOT POINT",
}

SURFACE_FINISHES = ()
DRAWING_NOTES = "PIVOT POINT SEAT: NO BURR AT THE MOUTH."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"


def _hole(name: str, x: float, dia: float, y0: float, length: float) -> dict[str, Any]:
    return {
        "name": name,
        "shape": "cylinder",
        "at_mm": [x, y0, -HOLE_Y],
        "axis": [0.0, 1.0, 0.0],
        "dia_mm": dia,
        "length_mm": length,
        "void": True,
        "cuts": ["pivot plate"],
    }


# The plate as made, in the model frame above. The cones (seat and
# countersinks) are left to the CAD part; the solids carry their bores.
PRECHIPS_SOLIDS: list[dict[str, Any]] = [
    {
        "name": "pivot plate",
        "shape": "box",
        "at_mm": [0.0, 0.0, -PLATE_WIDTH],
        "size_mm": [PLATE_LENGTH, PLATE_HEIGHT, PLATE_WIDTH],
        "note": (
            "MHA-CH-006-TL-19, 1018 3/4 x 1-1/2 bar offcut; No. 2 centre-drilled "
            "60 degree seat on the top face for the pivot point (MHA-CH-006-TL-18)"
        ),
    },
    _hole("seat pilot", SEAT_X, PILOT_DIA, PLATE_HEIGHT - PILOT_DEPTH, PILOT_DEPTH),
    *(
        _hole(f"screw hole {index}", x, HOLE_DIA, 0.0, PLATE_HEIGHT)
        for index, x in enumerate(SCREW_X, start=1)
    ),
]
