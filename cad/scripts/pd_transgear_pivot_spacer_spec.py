r"""Transgear pivot spacer (MHA-PD-20) dimensional contract.

PURE DATA, no SolidWorks/COM imports.  A turned brass ring on the MHA-PD-VN-57
shoulder screw between the MHA-PD-07 support bar's back face and the MHA-PD-18
arm's front face (contract §3.4).  Its length sets the MHA-PD-VN-63 spring's
room with the arm's spot-face floor and the screw's shoulder, so it prints
±.002; it is fitted as made, never faced (R9-6).  It is a light press on
the shoulder, pressed flush with the shoulder's end, so screw and spacer
seat on the bar as one body and the ring cannot index its wedge; the
screw's one MHA-PD-VN-63 curved disc spring preloads the arm onto the rear
face.  The hanger's out-of-plane tilt is then both faces' perpendicularity
to the bore (datum A) over the face the arm seats on: the sheet carries
those two frames.  The sheet is in inches (#290).

Local frame: lathe axis +Z, origin on the axis at the face that bears on the
bar (the FRONT face, machine z -129.4); the rear face (on the arm) at
z = LENGTH.  Front Plane (z = 0) and the RearFace plane (z = LENGTH) are the
mating planes, Axis1 the bore axis.
"""

from __future__ import annotations

import _config
import _mcmaster_90325a174 as SCREW
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
    printed_deviations,
)
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl

UNIT = drawing_unit(
    "parts/pd-transgear-pivot-spacer", _config.parts("pd-transgear-pivot-spacer")
)

# Ø.44 at .XX (owner ruling 2026-10-27 on #1380, option D: no stack reads the
# O.D.'s band), so the outside profile takes a loose title-block row
# (rule 4) and the wall reaches the .080 target at the full worst case below.
# 7/16 in 360 brass rod lies inside the band as supplied: McMaster 8953K162
# series, Ø7/16 in -0.003/+0.003 in (.4345..4405), H02, ASTM B16 (read live
# 2026-10-27), against Ø.43..45.
OD = 11.176  # .44
OD_PLACES = 2
OD_BAND = printed_band_mm(OD_PLACES, unit=UNIT)
# The bore is a light press on the .1875 -.0010/0 shoulder, so it is a
# reamed fit bore (drawing-guidelines.md rule 12 (hole and slot callouts say
# what to do): the callout states the process) under an explicit band on the
# model dimension: .185 +.0010/+.0005 (#290, fit class F7).  A standard hole,
# it is fully defined by its callout on the end view, where it is a circle.
BORE_DIA = 4.699  # .185
BORE_DIA_PLACES = 4
BORE_DIA_BAND = (0.0254, 0.0127)  # (upper, lower) deviations, reamed
BORE_DIA_MAX = round(BORE_DIA + BORE_DIA_BAND[0], 6)
BORE_DIA_MIN = round(BORE_DIA + BORE_DIA_BAND[1], 6)
BORE_CALLOUT = "REAM THRU"
# 5.0: the bar grew 0.5 rearward under the arm (user ruling 2026-10-15), so
# the ring gives it up and the hanger stays put.  It keeps 5.0 (#290: it
# sets the arm's Z, the chain plane's datum) and prints .197 ±.002 on the
# .001 grid (machinist review: a fourth place was a soft-converted 5 mm); the
# spring room (transgear_hanger_joints) is judged at that print's reach.
LENGTH = 5.0
LENGTH_PLACES = 3
LENGTH_TOLERANCE = 0.0508  # ±.002
LENGTH_BAND = max(
    abs(deviation)
    for deviation in printed_deviations(
        LENGTH, LENGTH_PLACES, (-LENGTH_TOLERANCE, LENGTH_TOLERANCE), unit=UNIT
    )
)
# (loosest, tightest): the smallest shoulder in the largest ream, and the
# reverse.
_SHOULDER_DIA_MIN = SCREW.SHOULDER_DIA + SCREW.SHOULDER_DIA_LIMITS[0]
_SHOULDER_DIA_MAX = SCREW.SHOULDER_DIA + SCREW.SHOULDER_DIA_LIMITS[1]
PRESS_INTERFERENCE = (
    round(_SHOULDER_DIA_MIN - BORE_DIA_MAX, 6),
    round(_SHOULDER_DIA_MAX - BORE_DIA_MIN, 6),
)  # .0005, .0020
if not 0.0 < PRESS_INTERFERENCE[0] <= PRESS_INTERFERENCE[1]:
    raise AssertionError(
        f"MHA-PD-20 bore leaves the shoulder press: {PRESS_INTERFERENCE}"
    )

# --- geometric control --------------------------------------------------------
# Pressed on the shoulder, the ring's bore is the screw's axis (datum A).  The
# front face seats on the bar and the arm seats on the rear face, so the arm
# tilts off the axis by the sum of both faces' perpendicularity to A over the
# smallest flat the arm seats on (FACE_PERPENDICULARITY_ZONE_DIA); the
# assembly's hanger-tilt stack reads all three.  The O.D.'s circular runout
# to A bounds the bore's offset in the bar the shop may chuck as supplied
# (coordinator ruling, #2014): it is what the wall below charges.
BORE_DATUM = "A"
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "rear face perpendicularity to bore": ".0004",
    "front face perpendicularity to bore": ".0004",
    "o.d. circular runout to bore": ".016",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * 25.4 for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
OD_RUNOUT = GEOMETRIC_TOLERANCES_MM["o.d. circular runout to bore"]

# Rule 17 at the full worst case: the smallest O.D. over the largest ream,
# offset by the bore's eccentricity to the O.D., less the title block's edge
# break on both rims of an end face (the bore's and the O.D.'s; the round or
# the chamfer, whichever sets back further).  No drill run-off: the bore is
# drilled and reamed in the chucking that holds the O.D.; that chucking's
# coaxiality is the printed O.D. runout, whose full indicator movement is
# twice the axes' offset.
WALL_TARGET = WALL_TARGET_MM
EDGE_BREAK = max(edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT))
BORE_ECCENTRICITY = OD_RUNOUT / 2.0
WALL_NOMINAL = (OD - BORE_DIA) / 2.0
WALL_WORST = (OD - OD_BAND - BORE_DIA_MAX) / 2.0 - BORE_ECCENTRICITY - 2.0 * EDGE_BREAK
if WALL_WORST < WALL_TARGET:
    raise AssertionError(
        f"MHA-PD-20 wall {WALL_WORST:.3f} < the {WALL_TARGET} target at the worst case"
    )
REAR_FACE_PERPENDICULARITY = GEOMETRIC_TOLERANCES_MM[
    "rear face perpendicularity to bore"
]
FRONT_FACE_PERPENDICULARITY = GEOMETRIC_TOLERANCES_MM[
    "front face perpendicularity to bore"
]
# The arm seats on the face's flat: the smallest O.D. less the title block's
# break on its rim (the same break the wall charges above).
FACE_PERPENDICULARITY_ZONE_DIA = OD - OD_BAND - 2.0 * EDGE_BREAK

# The wall holds the target, so the sheet states no shortfall and carries no
# notes: the length and bore bands ride their dimensions as model tolerances
# (drawing-simplicity-policy.md `How the repository implements the guidelines`).

# Marked model dimensions and the places the part authors on them (policy
# drawing-simplicity-policy.md `How the repository implements the guidelines`).
# The O.D. prints at .XX under the title block's row; the length
# (LENGTH_TOLERANCE) at three places and the bore (BORE_DIA_BAND) at four,
# under their own model bands.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"RingOd", "BoreDia"},
    "Ring": {"RingLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"RingOd": OD_PLACES, "BoreDia": BORE_DIA_PLACES},
    "Ring": {"RingLength": LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-PD-20 dimension needs authored places")

ISOMETRIC_VIEW_SCALE = (4, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)

# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs,
# slides or locates): the arm swings on the shoulder against the rear face, so
# the rear face runs (MACHINED, labelled as the arm's bearing face on the
# sheet); the front face is the one static seat that locates the ring on the
# bar (SEAT).  Resolved on the exact native faces by outward normal and offset
# in the part frame.  The pressed bore carries no symbol.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "front_face", SEAT_UM, PlanarFace((0.0, 0.0, -1.0), 0.0), display_unit=UNIT
    ),
    SurfaceFinishControl(
        "rear_face",
        MACHINED_UM,
        PlanarFace((0.0, 0.0, 1.0), LENGTH),
        production_method="BEARING FACE",
        display_unit=UNIT,
    ),
)
