r"""Pure-data dimensional contract shared by the crank-drive gear and its drawing.

The dark steel 64T gear at the cone set's large end; it carries the crossed-axis
helical accommodation for its straight 16T crank pinion mate (4:1 crank-to-cone
reduction).

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The three sizes a
machinist turns and bores -- outside diameter, face width, bore -- are NATIVE
model dimensions carrying their own decimal places and bands (rules 1, 2, 4);
the tooth system a cut-gear print cannot express as dimensions stays in the
gear-data block rule 6 allows, with every generating number marked REF; and
nothing here restates the title block.

PURE DATA, no SolidWorks/COM imports: ``build_crank_drive_gear`` marks and
tolerances exactly ``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model,
``draw_crank_drive_gear`` keeps exactly the same names, and the offline test
(``test_crank_drive_gear_drawing.py``) fails the moment one side drifts.
"""

from __future__ import annotations

import math

import _config
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 64
DIAMETRAL_PITCH = _config.machine("gear_train", "crank_drive_diametral_pitch")
PRESSURE_ANGLE_DEG = 14.5  # transverse
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN
# The gap floor is a root arc one standard dedendum below the pitch circle
# (``_gear.build_fixed_gear(root_relief=True)``, required by the helix path):
# the cutter's depth of cut produces it, so it is REF on the print.
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN

# The crossed-axis accommodation: the 64T rides the cone shaft, inclined in
# plan against a crank pinion that spins about machine z, so the gear is cut as
# a true helix at the shaft angle (a crossed-helical pair, pinion straight) with
# a transverse tooth thinning that opens the mesh's side clearance. Both live in
# gear_train.yaml, shared with the assembly that meshes them.
HELIX_ANGLE_DEG = _config.machine("gear_train", "crank_drive_helix_deg")
BACKLASH_MM = _config.machine("gear_train", "crank_drive_backlash_mm")
FACE_WIDTH = 8.0

# Hand: the tooth azimuth advances counter-clockwise about +z as z increases
# (``_gear._TWIST_CCW``), which is a RIGHT-hand helix. It is the one tooth-system
# fact a mirrored part would get wrong and no view can settle, so the data block
# states it in words.
HELIX_HAND = "RIGHT HAND"
TOTAL_TWIST_DEG = math.degrees(
    FACE_WIDTH * math.tan(math.radians(HELIX_ANGLE_DEG)) / (PITCH_DIA / 2.0)
)
TRANSVERSE_CIRCULAR_TOOTH_THICKNESS = math.pi * MODULE_MM / 2.0 - BACKLASH_MM

# The blank's outside diameter is the one tooth-system number the turner sets
# before a cutter touches the part, so it prints as a NATIVE dimension instead
# of as text in the data block -- but at the title block's general .XX grade,
# with no band of its own. The crossed 16T:64T mesh is built with
# ``fits.crank_mesh.c2c_slack_mm`` 0.25 mm of centre-distance slack on top of
# the tooth system's own tip clearance below, so the tip circle has 0.405 mm of
# radial room: the general +/-0.51 diametral is +/-0.255 radial, inside it. A
# tighter band here would be a habit, not a requirement
# (cad/docs/tolerance-policy.md, "Fit classes" and the one-sided-load bullets).
TIP_CLEARANCE_MM = 0.157 / DIAMETRAL_PITCH * MM_PER_IN

# The cone shaft's 3/8" gear land. The bore over it is the part's one critical
# fit and the only reason anything on the print carries a third decimal -- but
# its BAND is derived in ``build_crank_drive_gear`` from the named fit class and
# the shaft land's own published limits, because a fit-class read
# (``_config.fit`` -> tolerances.yaml) inside THIS module would land in the
# import closure of every assembly that imports OUTSIDE_DIA and make fit classes
# a rebuild dependency of the frame (test_dodo_recipe's fine-grained-config
# contract). The drawing needs the size and the places; only the part needs the
# limits.
BORE_DIA = 0.375 * MM_PER_IN  # 9.525

# One roughness, on the one surface whose function depends on it: the bore is a
# size-toleranced fit onto the cone shaft's land, and a fit lives on the peaks
# as much as on the limits, so the bore carries the project's general machined
# grade. Nothing runs on the teeth or the end faces -- they are as the title
# block's process row states (drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("crank_drive_gear_bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_crank_drive_gear`` marks exactly these;
# ``draw_crank_drive_gear`` keeps exactly their union across its per-view
# ``keep`` maps. ---
#
# ``OutsideDiaReference`` is a construction-geometry sketch whose single driving
# dimension IS the tip circle: the helix recipe grows the teeth off a ROOT
# cylinder blank, so no solid feature owns the diameter the turner sets, and
# rule 2 says model it rather than type it into the data block.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OutsideDiaReference": {"OutsideDia"},
    "GearBlank": {"FaceWidth"},
    "BoreProfile": {"BoreDia"},
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2: the places a dimension prints are part of the tolerance it
# claims, and the model owns both. ``build_crank_drive_gear`` applies this table
# natively (``_drawing_marks.apply_drawing_precision``) right after the drawing
# marks, so ``draw_crank_drive_gear`` imports each dimension verbatim and only
# reads ``GetPrimaryPrecision2()`` back off the sheet.
#
# The bore is the only fit on the part and prints three places with its own
# band. The outside diameter prints two with none. The face width is a free
# length between two turned faces: one place, so the title block's .X +/-0.8 is
# the band it claims -- and that is the band it needs, the mating 16T's face
# being 2.8 mm wider than this one at every allowed axial position.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OutsideDiaReference": {"OutsideDia": 2},
    "GearBlank": {"FaceWidth": 1},
    "BoreProfile": {"BoreDia": 3},
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
