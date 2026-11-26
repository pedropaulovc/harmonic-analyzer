r"""Crank-arm dimensional contract -- the single source of truth shared by the
part build (``build_dt_crank_arm.py``) and its manufacturing drawing
(``draw_dt_crank_arm.py``).

REFERENCE for the ``<part>_spec.py`` split. PURE DATA, no SolidWorks/COM imports:
the nominal geometry (the "editable knobs"), the derived spans the drawing needs
for its view math, and the marked-dimension -> kept-dimension NAME map. Keeping
this in ONE module means a rename or a nominal change is a single edit that reaches
both scripts, so the part-side ``mark_dimensions_for_drawing`` set and the
drawing-side ``keep`` maps cannot silently drift apart.

Build-graph consequence (intended): both ``build_dt_crank_arm`` and ``draw_dt_crank_arm``
``from dt_crank_arm_spec import ...``, so ``module_deps_of`` folds THIS file into BOTH
recipe digests -- an edit here rebuilds the part AND the drawing (the coupling you
want). But the drawing no longer imports ``build_dt_crank_arm``, so a pure build-logic
edit that leaves this spec (and the .SLDPRT geometry) untouched does NOT force a
drawing rebuild; a geometry change still re-renders the drawing via its .SLDPRT
``file_dep``. The correct asymmetry -- part change => drawing rebuilds; drawing
change =/> part rebuilds -- falls straight out of the DAG.

The offline lockstep test (``test_dt_crank_arm_drawing.py``) asserts the part marks
and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS`` -- the drift alarm, run
without SolidWorks in ~1 s.
"""

from __future__ import annotations

import math

import _config
import _mcmaster_3603t354 as jack_chain
import dt_crank_hub_geometry
from _hole_spec import THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_deviations
from _surface_finish import SurfaceFinishControl
from dt_crank_handle_pivot_screw_spec import THREAD_SIZE as PIVOT_SCREW_THREAD_SIZE
from dt_crank_hub_geometry import (
    ARM_THICKNESS,
    ARM_WIDTH,
    ARM_WIDTH_STOCK_MINUS,
    AXIAL_PIN_DIA,  # noqa: F401 -- re-exported to the build and drawing
    AXIAL_PIN_RADIUS_FROM_AXIS,
    FIDUCIAL_MODEL_DEPTH,  # noqa: F401 -- re-exported to the build
    FIDUCIAL_MODEL_DIA,  # noqa: F401 -- re-exported to the build and drawing
    HUB_SEAT_DIA,
    SEAM_DEPTH,  # noqa: F401 -- re-exported to the build
)

# Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  Lengths
# stay physical millimetres, each arm-owned nominal the exact decimal of its
# printed inch value.
UNIT = drawing_unit("parts/dt-crank-arm", _config.parts("dt-crank-arm"))
if UNIT != dt_crank_hub_geometry.UNIT:
    raise AssertionError("the matched arm and hub print in different units")
EDGE_BREAK_MAX_MM = edge_break_chamfer_mm(unit=UNIT)


# --- Nominal geometry -------------------------------------------------------
ARM_C2C = 74.93  # 2.95
# User ruling 2026-09-29 (ch11 p.14 photo re-check): the handle end is a full
# semicircle concentric with the handle pivot, the same R.50 as the hub end.
END_RADIUS = ARM_WIDTH / 2.0
# U33: the MHA-DT-32 slotted shoulder screw threads through the arm and carries
# the handle.  The end arc shares the pivot's centre, so its tapped web to the
# end is judged at the printed worst case of the end radius alone (U27).
HANDLE_PIVOT_HOLE_SPEC = HoleSpec("tapped", PIVOT_SCREW_THREAD_SIZE)
_PIVOT_THREAD_R = THREAD_MAJOR_MM[HANDLE_PIVOT_HOLE_SPEC.size] / 2.0
_END_RADIUS_LOWER, _END_RADIUS_UPPER = printed_deviations(END_RADIUS, 2, unit=UNIT)
PIVOT_END_WEB_NOMINAL = END_RADIUS - _PIVOT_THREAD_R
PIVOT_END_WEB_WORST = PIVOT_END_WEB_NOMINAL + _END_RADIUS_LOWER
if PIVOT_END_WEB_WORST < WALL_TARGET_MM:
    raise AssertionError(
        f"handle-pivot thread leaves {PIVOT_END_WEB_WORST:.2f} mm to the arm end"
    )

# The axial MHA-DT-VN-59 groove is match-drilled in the assembled arm/hub.  Its
# centre rides the hub-seat interface at six o'clock (toward the hanging handle);
# its length is shared as exactly half the arm thickness.
AXIAL_PIN_X = AXIAL_PIN_RADIUS_FROM_AXIS
AXIAL_PIN_Y = 0.0

# The arm owns one shallow punched alignment witness; the matching mark is on
# the crankshaft (MHA-DT-11) dome, and the drive-train assembly lines the two up
# before the taper ream.  Its diameter and depth are a visual representation,
# never printed; its centre prints as two ordinates from the hub-seat axis.
#
# The centre must land on the flat outboard face at every accepted part
# (codjiflo P2 on #2005: the first band was checked against the nominal bore).
# That face's worst-case annulus runs from the seat bore's printed upper limit
# plus its edge break out to the boss end's printed lower limit less its break.
FIDUCIAL_FACE_RADII = (
    (HUB_SEAT_DIA + printed_deviations(HUB_SEAT_DIA, 2, unit=UNIT)[1]) / 2.0
    + EDGE_BREAK_MAX_MM,
    END_RADIUS + _END_RADIUS_LOWER - EDGE_BREAK_MAX_MM,
)
# The mark stands at 135 degrees near that annulus's mid-radius, each ordinate
# .31 at the title block's .XX: anywhere in that square band the centre stays
# on the face.
_FIDUCIAL_AXIS = 7.874  # .31
FIDUCIAL_X = -_FIDUCIAL_AXIS
FIDUCIAL_Y = _FIDUCIAL_AXIS
FIDUCIAL_RADIAL_LIMITS = tuple(
    2.0**0.5 * (_FIDUCIAL_AXIS + deviation)
    for deviation in printed_deviations(_FIDUCIAL_AXIS, 2, unit=UNIT)
)
if not (
    FIDUCIAL_FACE_RADII[0]
    < FIDUCIAL_RADIAL_LIMITS[0]
    < FIDUCIAL_RADIAL_LIMITS[1]
    < FIDUCIAL_FACE_RADII[1]
):
    raise AssertionError(
        f"punch witness band reaches {FIDUCIAL_RADIAL_LIMITS} from the hub-seat axis, "
        f"off the worst-case flat face {FIDUCIAL_FACE_RADII}"
    )

# Keeper-chain anchor (ch11 p.14; owner ruling 2026-11-08, #2144 item 9.2): a
# #2-56 brass binding-head screw (MHA-DT-VN-70) clamps the end link of the
# MHA-DT-VN-65 jack chain flat on the outboard face through the link's eye.
# Tapped THRU the 5/16 bar (drawing-guidelines.md rule 17 (walls and webs),
# audit W7): through, the screw has the whole bar of thread and nothing to
# bottom on.  The screw stands .11 from the arm's +Y edge (the crank frame's
# -X edge), so the link's standing eye hangs past that edge instead of
# cutting into the face.
ANCHOR_SCREW_X = 20.066  # .79
ANCHOR_SCREW_Y = 9.906  # .39
ANCHOR_HOLE_SPEC = HoleSpec("tapped", "#2-56")

# MHA-DT-31 is a light press in MHA-DT-06 and pinned; nothing runs in this part.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Derived spans.
ARM_END_X = ARM_C2C + END_RADIUS
HALF_WIDTH = ARM_WIDTH / 2.0
# The bore and pivot axis from the top long edge: a machinist sets the bore
# from an edge, not from a drawn centreline (fan-out round 5, rule 10;
# Main 2026-11-07).  Half the as-rolled width at the title block's .XX: a
# ±.002 band named no mate (fan-out round 6, rule 4), so it loosens to the
# row (L2, Owner ruling 2026-11-08 (Pedro), #2144 item 6.3) once the one stack it feeds passes.  That stack is the cheek round
# the hub seat: the hub's ARM_CHEEK_WORST_MM assumes a centred bore in the
# thinnest bar, so the near side loses the .XX offset plus half the mill's
# width band.  Its construction line stands two thirds of the way from the
# anchor tap to the pivot, in the arm's only empty span above the top edge.
AXIS_FROM_EDGE_STATION_X = (ANCHOR_SCREW_X + 2.0 * ARM_C2C) / 3.0
ARM_CHEEK_OFF_CENTRE_WORST_MM = (
    dt_crank_hub_geometry.ARM_CHEEK_WORST_MM
    - dt_crank_hub_geometry.GENERAL_2PL_TOL_MM
    - ARM_WIDTH_STOCK_MINUS / 2.0
)
if ARM_CHEEK_OFF_CENTRE_WORST_MM < WALL_TARGET_MM:
    raise AssertionError(
        f"hub-seat cheek {ARM_CHEEK_OFF_CENTRE_WORST_MM:.3f} mm with the axis at"
        " .XX from the top edge is under the .080 in target"
    )

# The anchor is located from its near edge (AnchorOffset), printed .XXX: at
# .XX its band takes the tap wall under the rule 17 floor (drawing-guidelines.md
# "a size or location whose .XX band would take a wall below the rule 17
# target takes .XXX and states the wall it holds").  Read from the centreline
# instead, the bar's mill minus takes ARM_WIDTH_STOCK_MINUS / 2 off the edge
# distance; the wall is judged at the lesser of the two readings.
ANCHOR_OFFSET_PLACES = 3
ANCHOR_EDGE_DIST = HALF_WIDTH - ANCHOR_SCREW_Y  # 2.794 (.110)
_ANCHOR_OFFSET_DEV = printed_deviations(ANCHOR_EDGE_DIST, ANCHOR_OFFSET_PLACES, unit=UNIT)
ANCHOR_EDGE_DIST_MIN = ANCHOR_EDGE_DIST + min(
    _ANCHOR_OFFSET_DEV[0], -ARM_WIDTH_STOCK_MINUS / 2.0
)  # 2.667 (.105)
ANCHOR_EDGE_DIST_MAX = ANCHOR_EDGE_DIST + _ANCHOR_OFFSET_DEV[1]  # 2.921 (.115)
# Owner ruling 2026-11-08 (#2144 item 9.2; Main: the edge move and its wall
# are "minor, within the #989 band"): the #2-56 major's wall to the edge holds
# the .060 floor, under the .080 target, so the tap states it (rule 20).
ANCHOR_TAP_WALL_MIN = (
    ANCHOR_EDGE_DIST_MIN - THREAD_MAJOR_MM[ANCHOR_HOLE_SPEC.size] / 2.0
)  # 1.575 (.062)
if ANCHOR_TAP_WALL_MIN < WALL_FLOOR_MM:
    raise AssertionError(
        f"keeper-chain anchor tap leaves {ANCHOR_TAP_WALL_MIN:.3f} mm to the arm edge, "
        f"under the {WALL_FLOOR_MM} mm floor"
    )
# The modelled end link (owner ruling 2026-11-08): its screw eye lies flat
# round the screw, its standing eye c = A - ID along the link toward the edge.
# The screw eye's outer radius stays on the face at the nearest printed edge;
# the standing eye's wire meets the face plane past the edge at the farthest.
# Measured in the face plane, the wire centre stands off it at least w/2 (the
# assembly adds air, which only moves it further past), so the eye's reach
# toward the screw at the face is sqrt(R^2 - (w/2)^2), R = ID/2 + w.


def standing_eye_face_reach(eye_id: float) -> float:
    """How far from the screw axis the standing eye's wire meets the face plane."""
    outer_r = eye_id / 2.0 + jack_chain.WIRE_DIA
    return jack_chain.eye_centre_spacing(eye_id) - (
        outer_r**2 - (jack_chain.WIRE_DIA / 2.0) ** 2
    ) ** 0.5


ANCHOR_EYE_OUTER_R = jack_chain.EYE_ID / 2.0 + jack_chain.WIRE_DIA  # 2.654 (.1045)
if ANCHOR_EYE_OUTER_R > ANCHOR_EDGE_DIST_MIN:
    raise AssertionError("the keeper chain's screw eye overhangs the arm edge")
ANCHOR_STANDING_EYE_AIR = standing_eye_face_reach(jack_chain.EYE_ID) - ANCHOR_EDGE_DIST_MAX
if ANCHOR_STANDING_EYE_AIR <= 0.0:
    raise AssertionError("the keeper chain's standing eye reaches the arm face")
# At the largest published eye (EYE_ID_MAX, .1535) the screw eye overhangs
# the nearest edge by about .019 (harmless: it is clamped on the face inside
# it) and the standing eye just meets the face plane at the farthest edge
# (0.0000 in, before the assembly's air under the link).
ANCHOR_EYE_MAX_OVERHANG = (
    jack_chain.EYE_ID_MAX / 2.0 + jack_chain.WIRE_DIA - ANCHOR_EDGE_DIST_MIN
)
ANCHOR_STANDING_EYE_AIR_AT_EYE_MAX = (
    standing_eye_face_reach(jack_chain.EYE_ID_MAX) - ANCHOR_EDGE_DIST_MAX
)
if ANCHOR_STANDING_EYE_AIR_AT_EYE_MAX < 0.0:
    raise AssertionError(
        "at the largest published eye the keeper chain's standing eye reaches the arm face"
    )

# Width and thickness are the bar's as rolled, printed as the supplier's
# fractions under the stock line's "AS SUPPLIED": the mill tolerance governs
# them, not a title-block band, which would accept a thinner arm and a short
# MHA-DT-32 engagement (Codex #892; the U41 platform precedent).  The width
# is the imported reference-sketch dimension; the thickness is dimensioned
# across the side view's faces on the sheet (an imported extrusion depth has
# no attachment a native reference can be proven on).
STOCK_FRACTION_DENOMINATOR = 16
STOCK_FRACTION_DIMENSIONS = {"Width": ARM_WIDTH, "Thickness": ARM_THICKNESS}

# Marked dimensions imported by the drawing.  The axial seam groove is an
# assembly-match feature, so its representation geometry carries no
# independent size or location dimension; the punch witness prints only its
# location from the hub-seat axis.
# The two end radii are concentric with the hub seat and the handle pivot, so
# they locate both on the arm's mid-width axis.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmOutline": {"BossRadius", "EndRadius"},
    "FiducialProfile": {"FiducialX", "FiducialY"},
    "HubSeatProfile": {"HubSeatDia"},
    "StationReference": {
        "PivotStation",
        "AnchorStation",
        "AnchorOffset",
        "AxisFromEdge",
        "Width",
    },
}

# Decimal places are authored on the model: every arm dimension takes the
# title block's .XX but the anchor's offset from its edge, .XXX for the tap
# wall (above).  The hub seat bore is made first at that band, and MHA-DT-31
# is turned to suit it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: dict.fromkeys(names, 2) for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION["StationReference"]["AnchorOffset"] = ANCHOR_OFFSET_PLACES
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}

# The sheet-derived reference dimensions: the parenthesised extreme-to-extreme
# overall, a read-only sum of the two end radii and the pivot station, and the
# MHA-DT-VN-59 seam's station from the bore axis (the seat radius), neither
# with a model dimension to import.  Their places are still specification,
# so the sheet reads them here instead of typing a literal
# (drawing-simplicity-policy.md `How the repository implements the guidelines`).
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "overall length reference": 2,
    "seam station reference": 2,
}

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): one
# short line.  The section line is a requirement, not a convenience: the U29
# cheek around the hub seat reaches its wall only at the mill's width
# tolerance.  The fiducial and the pivot tap's mouth limit are flagged at
# their features (dt_crank_arm_notes).
STOCK_NOTE = "1. WIDTH AND THICKNESS: CF FLAT BAR AS SUPPLIED."
# The hub seat's bonded slip fit, flagged from the seat callout (SEE NOTE 2):
# the callout's two word rows name the fit and its mate, and its width is
# bounded by the border and the seam leader.  Owner ruling 2026-11-24, fit
# audit question 21: the bore is made first and MHA-DT-31's seat is turned
# to it, the joint bonded with LOCTITE 638 (no press); the acceptance (the
# arm slides on by hand) prints once, on the hub, the member made last.
SEAT_PRESS_NOTE = (
    "2. HUB SEAT: MHA-DT-31 IS TURNED TO THIS BORE;"
    " BONDED WITH LOCTITE 638."
)
# The MHA-DT-VN-59 pin hole across the bore/hub joint, flagged from its drill
# callout (SEE NOTE 3): the callout keeps size, process and depth; the
# assembly-made hole, its pin, bond and clearance, and the owner's permanent
# pair (rulings 2026-11-01, as the hub's sheet prints it) are too many rows
# for the callout (rule 7).  Drilled 5/32 and the pin bonded (fit audit
# 2026-11-23, MHA-DT-06_DT-31.seam_pin; the .1562 reamer is retired).  Plain
# words, not the private "seam" (rule 26, fan-out round 3).  The rows stay
# short of the title block (x 0.216 at the render's 2.67 mm per character).
#
# The bond's diametral clearance prints in the note (machinist review r1,
# farm run 20261124T110807008Z: rule 23, a bonded seat prints its clearance
# on the part sheet).  The 98381A487 pin is 5/32 +.0001/+.0003 as supplied;
# the hole is the 5/32 drill at DRILLED HOLES +.004/0.  The range runs from
# the largest pin in a hole on its drill's size (.0003 tight: a light tap
# home, the compound still wetting the pin, as MHA-DT-VN-69's drilled bond
# takes it) to the smallest pin in the largest hole, which stays inside
# LOCTITE 638's largest gap.
_SEAM_PIN_DIA_BAND_IN = (0.0001, 0.0003)  # 98381A487 catalogue
_seam_pin_limits = tuple(AXIAL_PIN_DIA + band * 25.4 for band in _SEAM_PIN_DIA_BAND_IN)
SEAM_BOND_CLEARANCE_MM = (
    AXIAL_PIN_DIA - max(_seam_pin_limits),
    dt_crank_hub_geometry.SEAM_HOLE_DIA_MAX - min(_seam_pin_limits),
)  # (-.0003, .0039) in
# LOCTITE 638's largest gap, as dt_crank_hub_geometry restates it (already in
# this module's closure; cone_tip_cluster would widen the crank's recipes).
if SEAM_BOND_CLEARANCE_MM[1] > dt_crank_hub_geometry._LOCTITE_638_MAX_GAP_MM:
    raise AssertionError("MHA-DT-VN-59's bond gap passes LOCTITE 638's largest")
if SEAM_BOND_CLEARANCE_MM[1] - SEAM_BOND_CLEARANCE_MM[0] < 0.0254 - 1e-9:
    raise AssertionError("MHA-DT-VN-59's bond range is under .001 wide (rule 4)")
# Printed outward: the tight end floored to .0001, the loose end ceiled to
# .001.  The tight end is a real interference (the largest pin, .15655, in a
# hole on the drill's .15625), so the fit prints as interference to
# clearance, never a negative clearance (drawing-guidelines rule 4, form 1
# and rule 23; pin 98381A487 in the 5/32 drill +.004/0).  The arm's note 3
# and the hub's seam callout print this one text.
_SEAM_BOND_MIN_IN = math.floor(round(SEAM_BOND_CLEARANCE_MM[0] / 25.4 * 1e4, 6)) / 1e4
_SEAM_BOND_MAX_IN = math.ceil(round(SEAM_BOND_CLEARANCE_MM[1] / 25.4 * 1e3, 6)) / 1e3
if not _SEAM_BOND_MIN_IN < 0.0 < _SEAM_BOND_MAX_IN:
    raise AssertionError("MHA-DT-VN-59's fit no longer runs interference to clearance")
_SEAM_BOND_LOW_TEXT = f"{-_SEAM_BOND_MIN_IN:.4f}".removeprefix("0")
_SEAM_BOND_HIGH_TEXT = f"{_SEAM_BOND_MAX_IN:.3f}".removeprefix("0")
SEAM_BOND_CLEARANCE_TEXT = (
    f"{_SEAM_BOND_LOW_TEXT} INTERFERENCE TO {_SEAM_BOND_HIGH_TEXT} CLEARANCE"
)
SEAM_NOTE = (
    "3. DRILL ACROSS BORE/HUB JOINT WITH MHA-DT-31 AT ASSEMBLY; PERMANENT PAIR.\n"
    f"   PIN MHA-DT-VN-59, LOCTITE 638 BOND: {SEAM_BOND_CLEARANCE_TEXT}."
)
DRAWING_NOTES = "\n".join((STOCK_NOTE, SEAT_PRESS_NOTE, SEAM_NOTE))
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
