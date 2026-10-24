r"""Magnifying-wheel dimensional contract -- the single source of truth shared by
the part build (``build_mg_magnifying_wheel.py``) and its manufacturing drawing
(``draw_mg_magnifying_wheel.py``).

PURE DATA, no SolidWorks/COM imports.  The wheel nominals live in the drawing-
FREE ``mg_magnifying_wheel_geom`` module (the assembly imports the hub
stations); they are re-exported here for the drawing-side consumers and the
offline lockstep test, which asserts the part marks and the drawing keeps
EXACTLY ``DRAWING_DIMENSIONS``.

The walls and the groove seat are proved here, not in the geom: each term
takes the band its dimension PRINTS -- its explicit model band, or the title
block's row for the places ``DRAWING_PRECISION`` gives it -- so the proof and
the sheet have one source.
"""

from __future__ import annotations

import itertools
import math

from _gtol_cylinder import CylinderFace
from _printed_tolerance import angular_band_deg, drilled_oversize_mm, printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from _mg_wheel_rim_geometry import (
    GROOVE_BOTTOM_BAND,
    GROOVE_BOTTOM_DIA,
    GROOVE_R,
    GROOVE_R_BAND,
    PEN_WIRE_DIA,
    RIM_AXIAL,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
)
import sh_vn_music_wire_lever_geom as _lever
from mg_magnifying_wheel_geom import (  # noqa: F401 (re-export)
    BORE_DIA,
    CAST_ROUND_R,
    DRILL_WANDER_DEG,
    HUB_BACK_Z,
    HUB_DIA,
    HUB_FILLET_R,
    HUB_FRONT_Z,
    RIM_FILLET_R,
    SPIGOT_DIA,
    SPIGOT_DIA_MIN,
    SPOKE_AXIAL,
    SPOKE_COUNT,
    SPOKE_ROOT_WIDTH,
    SPOKE_TIP_WIDTH,
    TIE1_CLOCK_DEG,
    TIE1_POSITION_BAND,
    TIE1_R,
    TIE1_R_PLACES,
    TIE1_WANDER,
    TIE2_CLOCK_DEG,
    TIE_HOLE_DIA,
    clock_to_local_deg,
    fillet,
)
from mg_wheel_group import WHEEL_BORE_MAX

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The face view carries the rim, bore, spoke, fillet and tie
# dimensions; SECTION A-A carries the hub profile, the groove and the spoke
# thickness.  The rim's axial width and the rim-bore round's R are added on
# the sheet (A-A cannot import a fillet radius whose arc is the cut). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RimProfile": {"RimOuterDiaDim", "RimInnerDiaDim"},
    "SpokeProfile": {"SpokeRootWidth", "SpokeTipWidth"},
    "Spoke": {"SpokeAxial"},
    "HubProfile": {"HubDia", "SpigotDia", "HubLength", "SpigotLength", "HubFrontZ"},
    "BoreProfile": {"BoreDiaDim"},
    "HubFillets": {"HubFilletR"},
    "RimFillets": {"RimFilletR"},
    "GrooveProfile": {"GrooveR", "GrooveBottomDia"},
    "Tie1Profile": {"Tie1Y", "Tie1HoleDia"},
    "Tie2Profile": {"Tie2HoleDia", "Tie2Angle"},
}
# Decimal places per marked dimension (drawing-guidelines.md rule 3 (decimal places carry the tolerance)): the cast
# shapes at one place, the turned and drilled sizes at two.  The rim's OD
# keeps two: at .X its Ø99.2 floor leaves the groove 0.75 deep under the 0.8
# pen wire (GROOVE_DEPTH_MIN), so its callout says what the band holds.  The
# web's plane prints at .X: the lever wire clears the rim and spokes with
# the web moved the whole row (LEVER_WIRE_WEB_GAP below).  The spigot and the
# bore are matched fits, their two places a reference nominal.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RimProfile": {"RimOuterDiaDim": 2, "RimInnerDiaDim": 1},
    "SpokeProfile": {"SpokeRootWidth": 1, "SpokeTipWidth": 1},
    "Spoke": {"SpokeAxial": 1},
    "HubProfile": {
        "HubDia": 2,
        "SpigotDia": 2,
        "HubLength": 2,
        "SpigotLength": 2,
        "HubFrontZ": 1,
    },
    "BoreProfile": {"BoreDiaDim": 2},
    "HubFillets": {"HubFilletR": 1},
    "RimFillets": {"RimFilletR": 1},
    "GrooveProfile": {"GrooveR": 2, "GrooveBottomDia": 2},
    "Tie1Profile": {"Tie1Y": TIE1_R_PLACES, "Tie1HoleDia": 2},
    "Tie2Profile": {"Tie2HoleDia": 2, "Tie2Angle": 0},
}
# Matched fits (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): the spigot is turned to the stated
# interference in the finished drum's bore and the bore reamed to the stated
# clearance on the finished axle, so each Ø is a reference nominal and its
# callout names the mate and the acceptance.
REFERENCE_DIMENSIONS = frozenset({"SpigotDia", "BoreDiaDim"})
# Places of the sheet-added dimensions (drawing-simplicity-policy.md `How the repository implements the guidelines`: the spec owns them,
# the sheet only passes them through).  The rim-bore round is a single
# limit, R0.8 MAX at one place: TIE2_FACE_WALL takes the R at that limit,
# and a sharp edge falls under the title block's edge break.  The rim's
# axial width takes one, its .X row the coarsest the walls admit.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "rim bore round": 1,
    "rim axial width": 1,
}
ROUND_TEXT_SUFFIX = " MAX"

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the notes say only what no callout can.  The spigot's press fit and
# the bore's running fit print on their own diameter callouts.  The spokes'
# clocking is a 0 deg relation no dimension can show: the seed spoke lies on
# local +X, so two spokes lie on the face view's horizontal centerline, the
# one TIE 2's angle is measured from, and TIE 1 on the vertical one falls
# midway between two (both asserted below).  TIE 1's radius rides the title
# block: the boss is sized so its wall holds at .XX (TIE1_HUB_WALL), and its
# note says why the hole stands off the drum (mg_magnifying_wheel_geom
# TIE1_DRUM_OPENING) without a number.
MIN_WALL = 2.0  # drawing-guidelines.md rule 17 (walls and webs) target
DRAWING_NOTES = "\n".join(
    (
        f"{SPOKE_COUNT} TAPERED SPOKES EQUALLY SPACED, TWO ON THE HORIZONTAL CENTERLINE.",
        "TIE 1: LEVER-WIRE TIE HOLE THRU BOSS, CLEAR OF MG-WHEEL-DRUM.",
        "TIE 2: PEN-WIRE TIE HOLE, GROOVE BOTTOM TO RIM BORE.",
    )
)
# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the bore is a running journal on the axle.  The spigot is
# pressed into the drum and the boss step the drum butts against is a
# register face: neither carries a symbol.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("mg_wheel_bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

# --- walls and the groove seat at the worst PRINTED band (drawing-guidelines.md rule 17 (walls and webs)) -----------------
_PLACES = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}


def _printed(model: float, name: str) -> tuple[float, float]:
    """(min, max) of a dimension that prints the title block's general row."""
    band = printed_band_mm(_PLACES[name])
    return model - band, model + band


_RIM_OD = _printed(RIM_OUTER_DIA, "RimOuterDiaDim")
_RIM_ID = _printed(RIM_INNER_DIA, "RimInnerDiaDim")
_ROOT = _printed(SPOKE_ROOT_WIDTH, "SpokeRootWidth")
_TIP = _printed(SPOKE_TIP_WIDTH, "SpokeTipWidth")
_HUB_FILLET = _printed(HUB_FILLET_R, "HubFilletR")
_RIM_FILLET = _printed(RIM_FILLET_R, "RimFilletR")
_RIM_AXIAL_MIN = RIM_AXIAL - printed_band_mm(
    DRAWING_REFERENCE_PRECISION["rim axial width"]
)
# R0.8 MAX: the R's single limit is its nominal.
_CAST_ROUND_MAX = CAST_ROUND_R
_HUB_DIA = _printed(HUB_DIA, "HubDia")
# The ties are drilled to the title block's DRILLED HOLES row (+0.10/0).
_TIE_R_MAX = (TIE_HOLE_DIA + drilled_oversize_mm()) / 2.0
# TIE 1's axis may stand off its nominal by its printed .XX radius band and
# its drill wander over the boss (mg_magnifying_wheel_geom): a disk about it.
_TIE1_OFFSET_MAX = TIE1_POSITION_BAND + TIE1_WANDER
# TIE 2 drills from the groove bottom into the rim bore; it breaks out at the
# rim ID, where both its walls are judged, after its deepest run.
_TIE2_WANDER = (
    (GROOVE_BOTTOM_DIA + GROOVE_BOTTOM_BAND[0] - _RIM_ID[0]) / 2.0
) * math.tan(math.radians(DRILL_WANDER_DEG))
_SPOKE_PITCH = 360.0 / SPOKE_COUNT
if clock_to_local_deg(0.0) % _SPOKE_PITCH or TIE1_CLOCK_DEG % 180.0 != 90.0:
    raise AssertionError("the spokes no longer lie on the horizontal centerline")

# TIE 1 to the boss OD, every size at the title block's .XX (+/-0.51):
# 13.995 - (10.75 + 0.51 + 0.056) - 0.55 = 2.129.
TIE1_HUB_WALL = _HUB_DIA[0] / 2.0 - (TIE1_R + _TIE1_OFFSET_MAX) - _TIE_R_MAX
# TIE 1 to the nearest hub-fillet foot: the hole sits midway between two
# spokes, at +30 deg from the seed (+X) spoke in its frame.
_TIE1_OFF = math.radians(
    (clock_to_local_deg(TIE1_CLOCK_DEG) % _SPOKE_PITCH) or _SPOKE_PITCH
)
if abs(math.degrees(_TIE1_OFF) - _SPOKE_PITCH / 2.0) > 1e-9:
    raise AssertionError("TIE 1 must sit midway between two spokes")
_TIE1_XY = (TIE1_R * math.cos(_TIE1_OFF), TIE1_R * math.sin(_TIE1_OFF))
TIE1_FILLET_WALL = (
    min(
        math.dist(fillet(hub / 2.0, r, True, root, tip)["on_circle"], _TIE1_XY)
        for hub, r, root, tip in itertools.product(_HUB_DIA, _HUB_FILLET, _ROOT, _TIP)
    )
    - _TIE_R_MAX
    - _TIE1_OFFSET_MAX
)
# TIE 1 to the bore it runs beside, at the largest finished bore.
TIE1_BORE_WALL = TIE1_R - _TIE1_OFFSET_MAX - _TIE_R_MAX - WHEEL_BORE_MAX / 2.0
# TIE 2 to the nearest rim-fillet foot, where the hole breaks out at the rim
# ID: its angle off the nearest spoke, less the printed angular band.
_tie2_local = clock_to_local_deg(TIE2_CLOCK_DEG)
_TIE2_OFF = (
    min(
        abs((_tie2_local - k * _SPOKE_PITCH + 180.0) % 360.0 - 180.0)
        for k in range(SPOKE_COUNT)
    )
    - angular_band_deg()
)


def _tie2_to_foot(rim_id: float, r: float, root: float, tip: float) -> float:
    foot = fillet(rim_id / 2.0, r, False, root, tip)["on_circle"]
    angle = math.radians(_TIE2_OFF) - math.atan2(foot[1], foot[0])
    return rim_id / 2.0 * math.sin(angle)


TIE2_SPOKE_WALL = (
    min(
        _tie2_to_foot(*corner)
        for corner in itertools.product(_RIM_ID, _RIM_FILLET, _ROOT, _TIP)
    )
    - _TIE_R_MAX
    - _TIE2_WANDER
)
# TIE 2 to the rim's side faces: it breaks into the bore at mid-width, where
# the faces end at the rim-bore rounds' tangent line (R0.8 MAX: 3.6 - 0.8 -
# 0.55 - 0.03 = 2.22).
TIE2_FACE_WALL = _RIM_AXIAL_MIN / 2.0 - _CAST_ROUND_MAX - _TIE_R_MAX - _TIE2_WANDER
# Spigot to bore at the smallest finished spigot and the largest finished
# bore, and the groove floor to the rim ID.
SPIGOT_WALL = (SPIGOT_DIA_MIN - WHEEL_BORE_MAX) / 2.0
GROOVE_FLOOR_WALL = (GROOVE_BOTTOM_DIA + GROOVE_BOTTOM_BAND[1] - _RIM_ID[1]) / 2.0

WALLS = {
    "tie1_to_hub_od": TIE1_HUB_WALL,  # 2.129
    "tie1_to_hub_fillet": TIE1_FILLET_WALL,  # 2.335
    "tie1_to_bore": TIE1_BORE_WALL,  # 7.224
    "tie2_to_rim_fillet": TIE2_SPOKE_WALL,  # 2.693
    "tie2_to_rim_faces": TIE2_FACE_WALL,  # 2.222
    "spigot_to_bore": SPIGOT_WALL,  # 4.592
    "groove_floor": GROOVE_FLOOR_WALL,  # 4.350
}
for _name, _wall in WALLS.items():
    if _wall < MIN_WALL - 1e-9:
        raise AssertionError(f"wheel wall {_name} {_wall:.3f} < {MIN_WALL}")

# The web and rim locate off the spigot face at .X (HubFrontZ).  Moved the
# whole row (and the 15.51 printed as 15.5) toward the pen side, the rim's
# and the spokes' pen faces still clear the lever wire's run; the boss, the
# spigot and the drum lane are hub stations the row does not move.  The pen
# wire leaves the groove plumb, so the groove's shift only leans it.
_WEB_PLACES = DRAWING_PRECISION["HubProfile"]["HubFrontZ"]
_WEB_SHIFT_MAX = printed_band_mm(_WEB_PLACES) + abs(
    round(HUB_FRONT_Z, _WEB_PLACES) - HUB_FRONT_Z
)  # 0.81
LEVER_WIRE_WEB_GAP = (
    min(_lever.RUN_GAPS["rim"], _lever.RUN_GAPS["spokes"]) - _WEB_SHIFT_MAX
)  # follows the current fixture hook and drum route
if LEVER_WIRE_WEB_GAP < _lever.CLEARANCE:
    raise AssertionError(
        f"lever wire {LEVER_WIRE_WEB_GAP:.3f} off the shifted web < {_lever.CLEARANCE}"
    )

# The pen wire seats in the groove at every printed corner: the narrowest
# groove is wider than the wire, the shallowest buries it below the rim OD,
# and the round bottom is never deeper than the groove.
GROOVE_WIDTH_MIN = 2.0 * (GROOVE_R + GROOVE_R_BAND[1])  # 1.0
GROOVE_DEPTH_MIN = (
    _RIM_OD[0] - (GROOVE_BOTTOM_DIA + GROOVE_BOTTOM_BAND[0])
) / 2.0  # 0.895
if not GROOVE_WIDTH_MIN > PEN_WIRE_DIA:
    raise AssertionError(f"groove {GROOVE_WIDTH_MIN:.3f} wide pinches the wire")
if not GROOVE_DEPTH_MIN >= PEN_WIRE_DIA:
    raise AssertionError(f"groove {GROOVE_DEPTH_MIN:.3f} deep leaves the wire proud")
if not GROOVE_DEPTH_MIN > GROOVE_R + GROOVE_R_BAND[0]:
    raise AssertionError("the groove's round bottom outgrows its depth")
