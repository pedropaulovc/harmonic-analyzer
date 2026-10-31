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
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import angular_band_deg, drilled_oversize_mm
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
    CAST_TOL,
    DRILL_WANDER_DEG,
    HUB_BACK_Z,
    HUB_DIA,
    HUB_FILLET_R,
    HUB_FRONT_Z,
    HUB_LEN_PLACES,
    RIM_FILLET_R,
    SPIGOT_DIA,
    SPIGOT_DIA_MIN,
    SPIGOT_LEN_PLACES,
    SPOKE_AXIAL,
    SPOKE_COUNT,
    SPOKE_ROOT_WIDTH,
    SPOKE_TIP_WIDTH,
    TIE1_CLOCK_DEG,
    TIE1_OFFSET_MAX,
    TIE1_PLACES,
    TIE1_R,
    TIE1_X,
    TIE1_Y,
    TIE2_CLOCK_DEG,
    TIE_HOLE_DIA,
    UNIT,
    clock_to_local_deg,
    fillet,
    printed_limits,
)
from mg_wheel_group import WHEEL_BORE_MAX

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The face view carries the bore, spoke, fillet and tie
# dimensions; SECTION A-A carries the hub profile, the groove, the spoke
# thickness and the rim's two diameters (DIAMETER_REFERENCE: turned sizes on
# the side view, drawing-guidelines.md rule 11 (turned parts read like the
# lathe)).  The rim's axial width and the rim-bore round's R are added on
# the sheet (A-A cannot import a fillet radius whose arc is the cut). ---
#
# The rim's Ø are Front-plane circles, which no side view can import, so
# they are restated as diametric dimensions on a hidden reference sketch in
# A-A's cutting plane (SECTION_PLANE, coincident with the Right plane), each
# driven from the same global as its circle.  Each one's witness is a short
# construction line REFERENCE_WITNESS_LEN long on its surface, starting at
# the rim's back face (the OD) or at the back rim-bore round's tangent (the
# rim bore), so its extension lines leave the part there.
#
# The spoke pattern's pitch prints on the face view between two spoke
# centrelines, the 60 and 120 deg spokes', on a hidden Front-plane sketch
# (SPOKE_REFERENCE): each centreline is a construction stub through the rim
# (SPOKE_STUB_R), and the angle between them is a DRIVEN reference (the
# Tie2Angle precedent) printed "6X 60°".  The seed spoke lies on local +X,
# so two spokes lie on the face view's horizontal centerline, which the
# angle's callout states.
SECTION_PLANE = "SectionAPlane"
DIAMETER_REFERENCE = "DiameterReference"
SPOKE_REFERENCE = "SpokeReference"
REFERENCE_SKETCHES = (DIAMETER_REFERENCE, SPOKE_REFERENCE)
REFERENCE_WITNESS_LEN = 1.0
SPOKE_PITCH_DEG = 360.0 / SPOKE_COUNT
SPOKE_PITCH_SPOKES = (1, 2)
SPOKE_STUB_R = (RIM_INNER_DIA / 2.0 - 4.0, RIM_OUTER_DIA / 2.0 + 3.0)
SPOKE_PITCH_PREFIX = f"{SPOKE_COUNT}X "
SPOKE_PITCH_CALLOUT = "TWO ON THE HORIZONTAL CENTERLINE"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    DIAMETER_REFERENCE: {"RimOuterDiaDim", "RimInnerDiaDim"},
    SPOKE_REFERENCE: {"SpokePitch"},
    "SpokeProfile": {"SpokeRootWidth", "SpokeTipWidth"},
    "Spoke": {"SpokeAxial"},
    "HubProfile": {"HubDia", "SpigotDia", "HubLength", "SpigotLength", "HubFrontZ"},
    "BoreProfile": {"BoreDiaDim"},
    "HubFillets": {"HubFilletR"},
    "RimFillets": {"RimFilletR"},
    "GrooveProfile": {"GrooveR", "GrooveBottomDia"},
    "Tie1Profile": {"Tie1X", "Tie1Y", "Tie1HoleDia"},
    "Tie2Profile": {"Tie2HoleDia", "Tie2Angle"},
}
# Each fillet feature's R imports onto its FIRST picked edge
# (build_mg_wheel_axle: the drawing's inserted radius lands on the first
# pick's edge), so the builder picks the edge the face view prints first:
# (spoke index from the seed on +X, side of that spoke in its own frame).
# The R3.0's leader rises from the seed spoke's -Y hub fillet through the
# spoke and the 0-60 window; the R4.0's leaves the 180 deg spoke's -Y (sheet
# +Y) rim fillet out through the rim to the left.  Neither crosses the
# spoke widths' dimension lines on the seed spoke.
HUB_FILLET_PRINTED = (0, -1)
RIM_FILLET_PRINTED = (3, -1)
# Decimal places per marked dimension (drawing-guidelines.md rule 3 (decimal places carry the tolerance)), in inches:
# every size a wall, the groove seat or the lever-wire run reads prints at
# .XX or finer (the inch .X row, +/-.1, would swallow the walls), the banded
# hub lengths and groove at three, the #60 ties at their drill's three.  The
# rim's OD at .XX keeps the groove deeper than the pen wire
# (GROOVE_DEPTH_MIN), so its callout says what the band holds.  The web's
# plane at .XX: the lever wire clears the rim and spokes with the web moved
# the whole row (LEVER_WIRE_WEB_GAP below).  The spigot and the bore are
# matched fits, a reference nominal at the places their reamers carry.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    DIAMETER_REFERENCE: {"RimOuterDiaDim": 2, "RimInnerDiaDim": 2},
    SPOKE_REFERENCE: {"SpokePitch": 0},
    "SpokeProfile": {"SpokeRootWidth": 2, "SpokeTipWidth": 2},
    "Spoke": {"SpokeAxial": 2},
    "HubProfile": {
        "HubDia": 2,
        "SpigotDia": 3,
        "HubLength": HUB_LEN_PLACES,
        "SpigotLength": SPIGOT_LEN_PLACES,
        "HubFrontZ": 2,
    },
    "BoreProfile": {"BoreDiaDim": 4},
    "HubFillets": {"HubFilletR": 2},
    "RimFillets": {"RimFilletR": 2},
    "GrooveProfile": {"GrooveR": 3, "GrooveBottomDia": 3},
    "Tie1Profile": {"Tie1X": TIE1_PLACES, "Tie1Y": TIE1_PLACES, "Tie1HoleDia": 3},
    "Tie2Profile": {"Tie2HoleDia": 3, "Tie2Angle": 0},
}
# Matched fits (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): the spigot is turned to the stated
# interference in the finished drum's bore and the bore reamed to the stated
# clearance on the finished axle, so each Ø is a reference nominal and its
# callout names the mate and the acceptance.
REFERENCE_DIMENSIONS = frozenset({"SpigotDia", "BoreDiaDim"})
# The as-cast sizes carry the explicit +/-.03 casting band (CAST_TOL) at
# .XX; the turned and drilled ones take the title block.
CAST_DIMENSIONS: dict[str, set[str]] = {
    DIAMETER_REFERENCE: {"RimInnerDiaDim"},
    "SpokeProfile": {"SpokeRootWidth", "SpokeTipWidth"},
    "Spoke": {"SpokeAxial"},
    "HubProfile": {"HubFrontZ"},
    "HubFillets": {"HubFilletR"},
    "RimFillets": {"RimFilletR"},
}
_CAST_NAMES = set().union(*CAST_DIMENSIONS.values())
# Places of the sheet-added dimensions (drawing-simplicity-policy.md `How the repository implements the guidelines`: the spec owns them,
# the sheet only passes them through).  The rim-bore round is a single
# limit, R.03 MAX: TIE2_FACE_WALL takes the R at that limit, and a sharp
# edge falls under the title block's edge break.  The rim's axial width
# takes .XX: at .X its +/-.1 eats TIE 2's ligament to the rim faces.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "rim bore round": 2,
    "rim axial width": 2,
}
ROUND_TEXT_SUFFIX = " MAX"

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the notes say only what no callout can.  The spigot's press fit and
# the bore's running fit print on their own diameter callouts, and the
# spokes' count, pitch and clocking on their own angle (SPOKE_REFERENCE).
# TIE 1's two coordinates ride the title
# block: the boss is sized so its wall holds at .XX (TIE1_HUB_WALL), and its
# note says why the hole stands off the drum (mg_magnifying_wheel_geom
# TIE1_DRUM_OPENING) without a number.
MIN_WALL = WALL_TARGET_MM  # drawing-guidelines.md rule 17 (walls and webs) target
DRAWING_NOTES = "\n".join(
    (
        "TIE 1: LEVER-WIRE TIE HOLE THRU BOSS, CLEAR OF MG-WHEEL-DRUM.",
        "TIE 2: PEN-WIRE TIE HOLE, GROOVE BOTTOM TO RIM BORE.",
    )
)
# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the bore is a running journal on the axle.  The spigot is
# pressed into the drum and the boss step the drum butts against is a
# register face: neither carries a symbol.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl(
        "mg_wheel_bore", MACHINED_UM, CylinderFace(BORE_DIA), display_unit=UNIT
    ),
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

# --- walls and the groove seat at the worst PRINTED band (drawing-guidelines.md rule 17 (walls and webs)) -----------------
_PLACES = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}


def _printed(model: float, name: str) -> tuple[float, float]:
    """(min, max) of a dimension: the casting band or the title block's row."""
    band = (CAST_TOL, -CAST_TOL) if name in _CAST_NAMES else None
    return printed_limits(model, _PLACES[name], band)


_RIM_OD = _printed(RIM_OUTER_DIA, "RimOuterDiaDim")
_RIM_ID = _printed(RIM_INNER_DIA, "RimInnerDiaDim")
_ROOT = _printed(SPOKE_ROOT_WIDTH, "SpokeRootWidth")
_TIP = _printed(SPOKE_TIP_WIDTH, "SpokeTipWidth")
_HUB_FILLET = _printed(HUB_FILLET_R, "HubFilletR")
_RIM_FILLET = _printed(RIM_FILLET_R, "RimFilletR")
_RIM_AXIAL_MIN = printed_limits(
    RIM_AXIAL, DRAWING_REFERENCE_PRECISION["rim axial width"]
)[0]
_GROOVE_BOTTOM = printed_limits(
    GROOVE_BOTTOM_DIA, _PLACES["GrooveBottomDia"], GROOVE_BOTTOM_BAND
)
_GROOVE_R = printed_limits(GROOVE_R, _PLACES["GrooveR"], GROOVE_R_BAND)
# R.03 MAX: the R's single limit is its nominal.
_CAST_ROUND_MAX = CAST_ROUND_R
_HUB_DIA = _printed(HUB_DIA, "HubDia")
# The ties are drilled to the title block's DRILLED HOLES row (+.004/0).
_TIE_R_MAX = (TIE_HOLE_DIA + drilled_oversize_mm(unit=UNIT)) / 2.0
# TIE 2 drills from the groove bottom into the rim bore; it breaks out at the
# rim ID, where both its walls are judged, after its deepest run.
_TIE2_WANDER = ((_GROOVE_BOTTOM[1] - _RIM_ID[0]) / 2.0) * math.tan(
    math.radians(DRILL_WANDER_DEG)
)
_SPOKE_PITCH = SPOKE_PITCH_DEG
if clock_to_local_deg(0.0) % _SPOKE_PITCH:
    raise AssertionError("the spokes no longer lie on the horizontal centerline")

# TIE 1 to the boss OD, every size at the title block's .XX (+/-.01), its
# axis anywhere in TIE1_OFFSET_MAX: 14.859 - (11.153 + 0.602) - 0.559 = 2.545.
TIE1_HUB_WALL = _HUB_DIA[0] / 2.0 - (TIE1_R + TIE1_OFFSET_MAX) - _TIE_R_MAX
# TIE 1 to the hub-fillet feet of the two spokes either side: its angle off
# the lower one, and off the upper one mirrored onto the seed spoke's +Y side.
_TIE1_OFF = math.radians(math.degrees(math.atan2(TIE1_Y, TIE1_X)) % _SPOKE_PITCH)
_TIE1_XY = tuple(
    (TIE1_R * math.cos(off), TIE1_R * math.sin(off))
    for off in (_TIE1_OFF, math.radians(_SPOKE_PITCH) - _TIE1_OFF)
)
TIE1_FILLET_WALL = (
    min(
        math.dist(fillet(hub / 2.0, r, True, root, tip)["on_circle"], xy)
        for hub, r, root, tip in itertools.product(_HUB_DIA, _HUB_FILLET, _ROOT, _TIP)
        for xy in _TIE1_XY
    )
    - _TIE_R_MAX
    - TIE1_OFFSET_MAX
)
# TIE 1 to the bore it runs beside, at the largest finished bore.
TIE1_BORE_WALL = TIE1_R - TIE1_OFFSET_MAX - _TIE_R_MAX - WHEEL_BORE_MAX / 2.0
# TIE 2 to the nearest rim-fillet foot, where the hole breaks out at the rim
# ID: its angle off the nearest spoke, less the printed angular band.
_tie2_local = clock_to_local_deg(TIE2_CLOCK_DEG)
_TIE2_OFF = min(
    abs((_tie2_local - k * _SPOKE_PITCH + 180.0) % 360.0 - 180.0)
    for k in range(SPOKE_COUNT)
) - angular_band_deg(unit=UNIT)


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
# the faces end at the rim-bore rounds' tangent line (R.03 MAX: 3.810 - 0.762
# - 0.559 - 0.028 = 2.462).
TIE2_FACE_WALL = _RIM_AXIAL_MIN / 2.0 - _CAST_ROUND_MAX - _TIE_R_MAX - _TIE2_WANDER
# Spigot to bore at the smallest finished spigot and the largest finished
# bore, and the groove floor to the rim ID.
SPIGOT_WALL = (SPIGOT_DIA_MIN - WHEEL_BORE_MAX) / 2.0
GROOVE_FLOOR_WALL = (_GROOVE_BOTTOM[0] - _RIM_ID[1]) / 2.0

WALLS = {
    "tie1_to_hub_od": TIE1_HUB_WALL,
    "tie1_to_hub_fillet": TIE1_FILLET_WALL,
    "tie1_to_bore": TIE1_BORE_WALL,
    "tie2_to_rim_fillet": TIE2_SPOKE_WALL,
    "tie2_to_rim_faces": TIE2_FACE_WALL,
    "spigot_to_bore": SPIGOT_WALL,
    "groove_floor": GROOVE_FLOOR_WALL,
}
for _name, _wall in WALLS.items():
    if _wall < MIN_WALL - 1e-9:
        raise AssertionError(f"wheel wall {_name} {_wall:.3f} < {MIN_WALL}")

# The web and rim locate off the spigot face at .XX +/-.03 (HubFrontZ).  Moved the
# whole row (and the 15.51 printed as .61) toward the pen side, the rim's
# and the spokes' pen faces still clear the lever wire's run; the boss, the
# spigot and the drum lane are hub stations the row does not move.  The pen
# wire leaves the groove plumb, so the groove's shift only leans it.
_WEB_SHIFT_MAX = max(
    abs(limit - HUB_FRONT_Z) for limit in _printed(HUB_FRONT_Z, "HubFrontZ")
)  # 0.778
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
GROOVE_WIDTH_MIN = 2.0 * _GROOVE_R[0]  # 1.016
GROOVE_DEPTH_MIN = (_RIM_OD[0] - _GROOVE_BOTTOM[1]) / 2.0  # 1.054
if not GROOVE_WIDTH_MIN > PEN_WIRE_DIA:
    raise AssertionError(f"groove {GROOVE_WIDTH_MIN:.3f} wide pinches the wire")
if not GROOVE_DEPTH_MIN >= PEN_WIRE_DIA:
    raise AssertionError(f"groove {GROOVE_DEPTH_MIN:.3f} deep leaves the wire proud")
if not GROOVE_DEPTH_MIN > _GROOVE_R[1]:
    raise AssertionError("the groove's round bottom outgrows its depth")
