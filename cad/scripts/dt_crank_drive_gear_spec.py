r"""Pure-data dimensional contract shared by the crank-drive gear and its drawing.

The dark steel 64T gear at the cone set's large end; it carries the crossed-axis
helical accommodation for its straight 16T crank pinion mate (4:1 crank-to-cone
reduction).

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The five blank,
bore and entry sizes -- outside diameter, face width, round bore, D-bore
across-flat and south bore chamfer -- are NATIVE model dimensions carrying
their own decimal places and bands; the tooth system a cut-gear print cannot
express as dimensions stays in the gear-data block rule 6 allows, with every
generating number marked REF.

PURE DATA, no SolidWorks/COM imports: ``build_dt_crank_drive_gear`` marks and
tolerances exactly ``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model,
``draw_dt_crank_drive_gear`` keeps exactly the same names, and the offline test
(``test_dt_crank_drive_gear_drawing.py``) fails the moment one side drifts.
"""

from __future__ import annotations

import math

import _config
import cone_line
import cone_shaft_land_bands
import gear_seat_fit
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 64

# The crossed-axis accommodation: the 64T rides the cone shaft, inclined in
# plan against a crank pinion that spins about machine z, so the gear is cut as
# a true helix at the shaft angle (a crossed-helical pair, pinion straight) with
# a transverse tooth thinning that opens the mesh's side clearance. Both live in
# gear_train.yaml, shared with the assembly that meshes them.
HELIX_ANGLE_DEG = _config.machine("gear_train", "crank_drive_helix_deg")
BACKLASH_MM = _config.machine("gear_train", "crank_drive_backlash_mm")

# Face width.  The v36 MHA-DT-005 casting is restored: its crank boss's north
# face is the collar's tangent plane again, so the 64T's SOUTH face -- seated
# on MHA-DT-004's thrust collar -- stays where the #1126 ruling put it, 1.5 north
# of the 8.0 face the 19.9 station was laid out on (crank_boss_rim holds every
# MHA-DT-005 north feature off it).  The cone set is a solid stack (user ruling
# 2026-09-28, dt_cone_gear_stack): the 64T grows NORTH until it bears on T120's
# grown south face, so its face is the gap between the collar and T120,
# floored to the four places it prints.  dt_cone_gear_stack pins the two faces
# together.  The band is the cone gears' +/-0.025.
LAYOUT_FACE_WIDTH = 8.0
SOUTH_FACE_SHIFT_NORTH = 1.5
FACE_WIDTH = round(14.1 - math.floor(cone_line.SEAT_PITCH * 1e4) / 1e4, 4)
FACE_WIDTH_BAND = (0.025, -0.025)
# The centre sits CENTRE_SHIFT_NORTH north of the 19.9 layout station.
CENTRE_SHIFT_NORTH = SOUTH_FACE_SHIFT_NORTH + (FACE_WIDTH - LAYOUT_FACE_WIDTH) / 2.0
if not LAYOUT_FACE_WIDTH - SOUTH_FACE_SHIFT_NORTH < FACE_WIDTH < LAYOUT_FACE_WIDTH:
    raise AssertionError(
        f"64T face {FACE_WIDTH} must grow past the #1126 6.5 face "
        f"and stay inside the {LAYOUT_FACE_WIDTH} layout face"
    )

# ONE cutter cuts both gears of the pair (#906, Main 2026-09-26). A crossed
# helical pair meshes in the NORMAL plane, so this gear is cut normal-defined:
# the cutter, set over at the helix angle, cuts its own DP, pressure angle and
# depth in the normal section, and the straight 16T takes the same cutter
# square. The TRANSVERSE DP stays the frame's (gear_train.yaml): it places the
# pitch circle the fixed post was laid out for, and the transverse pressure
# angle follows from the normal one.
DIAMETRAL_PITCH = _config.machine("gear_train", "crank_drive_diametral_pitch")  # transverse
_COS_HELIX = math.cos(math.radians(HELIX_ANGLE_DEG))
CUTTER_DIAMETRAL_PITCH = DIAMETRAL_PITCH / _COS_HELIX  # normal: 26.306
CUTTER_PRESSURE_ANGLE_DEG = 14.5  # normal
PRESSURE_ANGLE_DEG = math.degrees(  # transverse: 14.81
    math.atan(math.tan(math.radians(CUTTER_PRESSURE_ANGLE_DEG)) / _COS_HELIX)
)
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH  # transverse
NORMAL_MODULE_MM = MM_PER_IN / CUTTER_DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
# The cutter's depth below the pitch circle: a standard dedendum of the NORMAL
# module, whatever plane the profile is read in.  The blank is turned
# LONG_ADDENDUM_MM over the cutter's standard addendum (R9-56, 2026-09-30) so
# the 16T's turned band keeps contact over the 64T row at every printed
# corner (build_dt_drive_train_assembly.crank_row_engagement); the cutter, sunk
# to its own depth below the pitch circle, leaves the root where it was.
LONG_ADDENDUM_MM = 0.05
OUTSIDE_DIA = PITCH_DIA + 2.0 * (NORMAL_MODULE_MM + LONG_ADDENDUM_MM)
WHOLE_DEPTH = 2.157 * NORMAL_MODULE_MM + LONG_ADDENDUM_MM
# The gap floor is a root arc one standard dedendum below the pitch circle
# (``_gear.build_fixed_gear(root_relief=True)``, required by the helix path):
# the cutter's depth of cut produces it, so it is REF on the print.
ROOT_DIA = PITCH_DIA - 2.0 * 1.157 * NORMAL_MODULE_MM

# Hand: the tooth azimuth advances counter-clockwise about +z as z increases
# (``_gear._TWIST_CCW``), which is a RIGHT-hand helix. It is the one tooth-system
# fact a mirrored part would get wrong and no view can settle, so the data block
# states it in words.
HELIX_HAND = "RIGHT HAND"
TRANSVERSE_CIRCULAR_TOOTH_THICKNESS = math.pi * MODULE_MM / 2.0 - BACKLASH_MM
# What a gear-tooth caliper set square to the helix reads.
NORMAL_CIRCULAR_TOOTH_THICKNESS = TRANSVERSE_CIRCULAR_TOOTH_THICKNESS * _COS_HELIX

# The blank's outside diameter is the one tooth-system number the turner sets
# before a cutter touches the part, so it prints as a NATIVE dimension instead
# of as text in the data block.  The user ruled +/-0.10 on both gears' tips
# (2026-09-26, #906), held with a micrometer before cutting, as on the cone
# gears' blanks.  The mesh runs at a fixed centre with no adjustment (user
# ruling 2026-09-28): ``crank_mesh_stack`` books this band as the tip-to-root
# term of its closing corner (TIP_ROOT_BAND_RADIAL), and crank_boss_rim grows
# the tip by half of it toward MHA-DT-005.
OUTSIDE_DIA_TOLERANCE_MM = 0.10

# The Ø9.525 round portion of MHA-DT-004's Sec1 gear seat. The round-bore
# clearance is paired with the published shaft diameter band in the part
# builder. This shared spec owns the nominal and D-flat AF band without
# pulling a fit-class config read into assembly rebuild dependencies.
BORE_DIA = 0.375 * MM_PER_IN  # 9.525

# One D-flat on local +X, paired with MHA-DT-004 Sec1. Across-flat is measured
# from this plane to the opposite circular wall, not from the gear centre.
BORE_AF = cone_shaft_land_bands.SECTION_FLAT_AF[1]
BORE_AF_BAND = gear_seat_fit.flat_bore_af_band(cone_shaft_land_bands.FLAT_AF_BAND)
if BORE_AF is None:
    raise AssertionError("the 64T needs the flatted Sec1 gear seat")

# The MHA-DT-004 Sec1 flat stops square against its collar. A flat milled with
# an end mill of at least Ø8 leaves an axial crescent at the chord corners.
# At offset y from the flat midpoint its horn height above the flat is
# sqrt(Rshaft²-y²)-flat_offset, and the cutter's axial runout is
# Rcutter-sqrt(Rcutter²-y²). Their SUM must fit inside the 45° bore-entry
# chamfer, not merely the cutter runout alone. With Rcutter < Rshaft that
# sum increases monotonically from the flat midpoint to a chord corner;
# using the upper shaft diameter and lower shaft AF is print-worst.
MIN_FLAT_CUTTER_RADIUS = 4.0  # ≥Ø8 end mill
BORE_SOUTH_CHAMFER = 1.00
# The south entry is functional: .X's general band could accept a chamfer
# smaller than the cutter crescent. A native +0.10/-0.00 leg band preserves
# the full 1.00-mm minimum without constraining the harmless upper end.
BORE_SOUTH_CHAMFER_BAND = (0.10, 0.00)
# The shaft's nominal Sec1 Ø is BORE_DIA; the drawing contract tests it
# against dt_cone_gear_shaft_spec.SECTION_DIAS[1] without a circular import.
_SHAFT_MAX_R = (BORE_DIA + cone_shaft_land_bands.SECTION_DIA_BANDS[1][0]) / 2.0
_SHAFT_MIN_AF = BORE_AF + cone_shaft_land_bands.FLAT_AF_BAND[1]
_FLAT_OFFSET = _SHAFT_MIN_AF - _SHAFT_MAX_R
_HALF_CHORD = math.sqrt(_SHAFT_MAX_R**2 - _FLAT_OFFSET**2)
_MAX_HORN = _SHAFT_MAX_R - _FLAT_OFFSET
_MAX_CUTTER_RUNOUT = MIN_FLAT_CUTTER_RADIUS - math.sqrt(
    MIN_FLAT_CUTTER_RADIUS**2 - _HALF_CHORD**2
)
MAX_FLAT_CRESCENT = max(_MAX_HORN, _MAX_CUTTER_RUNOUT)
if MAX_FLAT_CRESCENT >= BORE_SOUTH_CHAMFER + BORE_SOUTH_CHAMFER_BAND[1]:
    raise AssertionError(
        f"Sec1 end-mill horn + runout {MAX_FLAT_CRESCENT:.4f} reaches "
        f"the south bore chamfer {BORE_SOUTH_CHAMFER + BORE_SOUTH_CHAMFER_BAND[1]:.4f}"
    )

# Even at the collar's supplied 5/8-in stock lower bound and the bore/chamfer
# upper bounds, the mouth ends before the collar's outer bearing annulus.
# Mirror the stock class here: dt_cone_gear_shaft_spec imports this gear's face
# width, so importing its COLLAR_DIA here would form an import cycle. The
# offline drawing test cross-checks these numbers against the shaft spec.
_COLLAR_MIN_R = (0.625 * MM_PER_IN - 0.002 * MM_PER_IN) / 2.0
_BORE_MAX_R = (
    BORE_DIA + gear_seat_fit.seat_bore_band(cone_shaft_land_bands.GEAR_SEAT_BAND)[0]
) / 2.0
COLLAR_BEARING_ANNULUS = _COLLAR_MIN_R - (
    _BORE_MAX_R + BORE_SOUTH_CHAMFER + BORE_SOUTH_CHAMFER_BAND[0]
)
if COLLAR_BEARING_ANNULUS <= 0:
    raise AssertionError("the chamfer reaches the collar's bearing outer rim")
FLAT_ENGAGEMENT_MIN = FACE_WIDTH + FACE_WIDTH_BAND[1] - (
    BORE_SOUTH_CHAMFER + BORE_SOUTH_CHAMFER_BAND[0]
)

# One roughness, on the one surface whose function depends on it: the bore is a
# size-toleranced fit onto the cone shaft's land, and a fit lives on the peaks
# as much as on the limits, so the bore carries the project's general machined
# grade. Nothing runs on the teeth or the end faces -- they are as the title
# block's process row states (drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("crank_drive_gear_bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_dt_crank_drive_gear`` marks exactly these;
# ``draw_dt_crank_drive_gear`` keeps exactly their union across its per-view
# ``keep`` maps. ---
#
# ``OutsideDiaReference`` is a construction-geometry sketch whose single driving
# dimension IS the tip circle: the helix recipe grows the teeth off a ROOT
# cylinder blank, so no solid feature owns the diameter the turner sets, and
# rule 2 says model it rather than type it into the data block.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OutsideDiaReference": {"OutsideDia"},
    "GearBlank": {"FaceWidth"},
    "BoreProfile": {"BoreDia", "BoreAF"},
    "BoreSouthChamfer": {"BoreSouthChamferSize"},
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2: the places a dimension prints are part of the tolerance it
# claims, and the model owns both. ``build_dt_crank_drive_gear`` applies this table
# natively (``_drawing_marks.apply_drawing_precision``) right after the drawing
# marks, so ``draw_dt_crank_drive_gear`` imports each dimension verbatim and only
# reads ``GetPrimaryPrecision2()`` back off the sheet.
#
# The round and D-flat bore sizes carry their own fit bands at three places.
# The outside diameter prints two with +/-0.10. The face width is the four-place
# ±0.025 member of the solid gear stack; its south face seats on the collar
# and the tolerance only shifts the north face. The south chamfer leg prints
# two places with its explicitly unilateral functional band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OutsideDiaReference": {"OutsideDia": 2},
    "GearBlank": {"FaceWidth": 4},
    "BoreProfile": {"BoreDia": 3, "BoreAF": 3},
    "BoreSouthChamfer": {"BoreSouthChamferSize": 2},
}

# The drawing reads this flat view back off the sheet: a dimension name is
# unique across the features that expose one, and a marked dimension nobody
# authored places for would otherwise print SolidWorks' template default.
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"{_feature}: precision authored for unmarked dimensions {_unmarked}"
        )
