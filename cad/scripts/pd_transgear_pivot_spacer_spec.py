r"""Transgear pivot spacer (MHA-PD-20) dimensional contract.

PURE DATA, no SolidWorks/COM imports.  A turned brass ring on the MHA-PD-VN-57
shoulder screw between the MHA-PD-07 support bar's back face and the MHA-PD-18
arm's front face (contract §3.4).  Its length sets the MHA-PD-VN-63 spring's
room with the arm's spot-face floor and the screw's shoulder, and the
spread of its limits is all that bounds its two faces' taper, which tilts
the hanger, so it prints ±.001; it is fitted as made, never faced (R9-6).
It is a bonded slip fit
(LOCTITE 638) on the shoulder, a #12 drilled hole, cured with its front face
and the shoulder's end down together on a flat plate, so screw and spacer
seat on the bar as one body and the ring cannot index its wedge; the
screw's one MHA-PD-VN-63 curved disc spring preloads the arm onto the rear
face.  The hanger's out-of-plane tilt is then the rear face's parallelism
to the front face over the face the arm seats on; the sheet carries no
frame for it (rule 5).  The sheet is in inches (#290).

Local frame: lathe axis +Z, origin on the axis at the face that bears on the
bar (the FRONT face, machine z -129.4); the rear face (on the arm) at
z = LENGTH.  Front Plane (z = 0) and the RearFace plane (z = LENGTH) are the
mating planes, Axis1 the bore axis.
"""

from __future__ import annotations

import math

import _config
import _mcmaster_90325a174 as SCREW
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
    printed_deviations,
)
from _surface_finish import MACHINED_UM, SurfaceFinishControl

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
# The bore is a bonded slip fit on the .1875 -.0010/0 shoulder (owner ruling
# 2026-11-24, fit audit question 6, which reverses R9-71's press and #2144
# item 4.4's mandrel facing): a #12 drill at the title block's DRILLED HOLES row,
# LOCTITE 638 in the gap.  Nothing reads its size but the bond's gap and the
# wall, so it prints the drill and no band; BORE_DIA_BAND is the ANALYSIS
# band of what the drill cuts (the DRILLED HOLES row), not a printed limit.
# A standard hole, it is fully defined by its callout on the end view, where
# it is a circle.
BORE_DRILL = "#12"
BORE_DIA = 4.8006  # .189
BORE_DIA_PLACES = 3
BORE_DIA_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)  # (upper, lower), drilled
BORE_DIA_MAX = round(BORE_DIA + BORE_DIA_BAND[0], 6)
BORE_DIA_MIN = round(BORE_DIA + BORE_DIA_BAND[1], 6)
BORE_CALLOUT = f"{BORE_DRILL} DRILL THRU"
# 5.0: the bar grew 0.5 rearward under the arm (user ruling 2026-10-15), so
# the ring gives it up and the hanger stays put.  It keeps 5.0 (#290: it
# sets the arm's Z, the chain plane's datum) and prints .197 on the
# .001 grid (machinist review: a fourth place was a soft-converted 5 mm); the
# spring room (transgear_hanger_joints) is judged at that print's reach.
# ±.001 (it was ±.002 under a parallelism frame): with no frame (below) the
# band's whole spread is the faces' taper, and at ±.002 that taper closes
# the MHA-PD-06 disc's statistical air to the platen under its floor
# (build_pd_paper_drive_assembly PLATEN_AIR; test_pd_transgear_pivot_spacer_drawing
# computes both).  ±.001 is the shop's row for a turned length.
# It follows owner ruling 2026-11-24, fit audit question 6 (the spacer
# drilled and bonded, so no mandrel facing holds a parallelism frame).
LENGTH = 5.0
LENGTH_PLACES = 3
LENGTH_TOLERANCE = 0.0254  # ±.001
LENGTH_BAND = max(
    abs(deviation)
    for deviation in printed_deviations(
        LENGTH, LENGTH_PLACES, (-LENGTH_TOLERANCE, LENGTH_TOLERANCE), unit=UNIT
    )
)
# The bond's diametral gap (least, greatest): the largest shoulder in the
# smallest hole, and the reverse.  It must be a slip fit at both limits and
# stay inside the 638 TDS gap limit (the limit dt_pinion_arbor_geometry,
# sm_gooseneck_spring_joint and cone_tip_cluster hold their 638 joints to).
LOCTITE_638_GAP_MAX = 0.25
_SHOULDER_DIA_MIN = SCREW.SHOULDER_DIA + SCREW.SHOULDER_DIA_LIMITS[0]
_SHOULDER_DIA_MAX = SCREW.SHOULDER_DIA + SCREW.SHOULDER_DIA_LIMITS[1]
BOND_GAP = (
    round(BORE_DIA_MIN - _SHOULDER_DIA_MAX, 6),
    round(BORE_DIA_MAX - _SHOULDER_DIA_MIN, 6),
)  # .0015, .0065
if not 0.0 < BOND_GAP[0] <= BOND_GAP[1] <= LOCTITE_638_GAP_MAX:
    raise AssertionError(
        f"MHA-PD-20 bore leaves the LOCTITE 638 bond gap on the shoulder: {BOND_GAP}"
    )
# The ring may cure off the screw's axis by half the greatest gap: the
# assembly's sweep places its O.D. that much further out.
SEAT_OFFSET_MAX = BOND_GAP[1] / 2.0

# --- geometric control --------------------------------------------------------
# The ring is bonded on the shoulder with its front face and the shoulder's
# end down together on a flat plate (MHA-PD-00), so the front face lies in
# the plane that seats on the bar and the bore plays no part in the arm's
# attitude.  That needs the bore square enough to the front face for the
# ring to tilt that much inside its tightest bond gap (BOND_GAP[0] over
# BOND_LAND_MIN): the sheet holds the drilled bore only at the angular
# row, so MHA-PD-00's dry trial (15C: the spacer, as made, shows no
# daylight on the plate with the screw held down on it) is its acceptance,
# and test_pd_transgear_pivot_spacer_drawing ties the tailstock drill's
# run-off to that tilt (Codjiflo r2 on #3487).  The arm, seated on the rear
# face, tilts to the bar by the rear
# face's parallelism to the front over the smallest flat it seats on
# (FACE_PARALLELISM_ZONE_DIA).  No frame prints it (machinist review
# 20261124T013305458Z, rule 5: a face-to-face frame on a spacer is
# over-specification; with owner ruling 2026-11-24, fit audit question 6,
# it replaced #2144 item 4.4's mandrel facing): the
# length's printed limits hold at every place round the rim, so the faces
# cannot be out of parallel by more than the band's whole spread
# (REAR_FACE_PARALLELISM below), and every hanger-tilt stack is judged at
# that.  The O.D.'s circular runout to the
# bore (datum A) bounds the bore's offset in the bar the shop may chuck as
# supplied (coordinator ruling, #2014): it is what the wall below charges.
BORE_DATUM = "A"
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "o.d. circular runout to bore": ".016",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * 25.4 for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
OD_RUNOUT = GEOMETRIC_TOLERANCES_MM["o.d. circular runout to bore"]

# Rule 17 at the full worst case: the smallest O.D. over the largest drilled
# hole, offset by the bore's eccentricity to the O.D., less the title block's
# edge break on both rims of an end face (the bore's and the O.D.'s; the
# round or the chamfer, whichever sets back further).  The printed O.D.
# runout holds at every section of the length, so it encloses the drill's
# run-off with the chucking's coaxiality; its full indicator movement is
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
# The faces' greatest out-of-parallel: the printed length's high limit at
# one place of the rim and its low limit opposite.
REAR_FACE_PARALLELISM = 2.0 * LENGTH_TOLERANCE
# The arm seats on the face's flat: the smallest O.D. less the title block's
# break on its rim (the same break the wall charges above).
FACE_PARALLELISM_ZONE_DIA = OD - OD_BAND - 2.0 * EDGE_BREAK
# The seated arm's greatest tilt to the bar's back face, rad.
SEATED_FACE_TILT = math.atan(REAR_FACE_PARALLELISM / FACE_PARALLELISM_ZONE_DIA)
# The bond's shortest land: the shortest ring less the bore's break at each
# mouth.
BOND_LAND_MIN = LENGTH - LENGTH_BAND - 2.0 * EDGE_BREAK

# The wall holds the target, so the sheet states no shortfall and carries no
# notes: the length's band rides its dimension as a model tolerance
# (drawing-simplicity-policy.md `How the repository implements the guidelines`).

# Marked model dimensions and the places the part authors on them (policy
# drawing-simplicity-policy.md `How the repository implements the guidelines`).
# The O.D. prints at .XX under the title block's row; the length
# (LENGTH_TOLERANCE) at three places under its own model band; the bore at
# three, the drill's size under the DRILLED HOLES row.
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
# sheet).  The front face seats on the bar under the screw's clamp and
# carries no symbol (machinist review 20261124T013305458Z): a turned face
# serves.  Resolved on the exact native face by outward normal and offset
# in the part frame.  The bonded bore carries no symbol.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "rear_face",
        MACHINED_UM,
        PlanarFace((0.0, 0.0, 1.0), LENGTH),
        production_method="BEARING FACE",
        display_unit=UNIT,
    ),
)
