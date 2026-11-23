r"""MHA-PD-28 transgear-knob-bush: the drawing contract of the turned steel bush.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Every number is ``pd_transgear_knob_bush_geometry``'s (the numbers
authority the bush, the plate it is pressed in, the knob-shaft stack and the
paper-drive assembly share); this module adds only what the sheet needs: the
printed places, the datum and the bore's frame, the finishes and the
printed callout text.

Datum A is the shoulder face (it seats on MHA-PD-19's face A); the bore
carries no datum, since no frame references one (rule 5).  The bore's
perpendicularity to A (RV-02) moved here from the plate with the bore
(owner ruling 2026-11-20 (Pedro), #2425).

Part frame (``pd_transgear_knob_bush_geometry``): axis local +Y, hub face
y = 0, shoulder y = HUB_LENGTH, rear face y = LENGTH.
"""

from __future__ import annotations

import math

import _config
import paper_drive_arm_registration as REGISTRATION
import pd_transgear_knob_bush_geometry as BUSH
from _gtol_controls import GeometricControl, PartDatum
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

UNIT = BUSH.UNIT

# The H7 running bore's model band, (upper, lower), on the knob shaft's g6
# journal.
BORE_BAND = (max(BUSH.BORE_DIA_LIMITS), min(BUSH.BORE_DIA_LIMITS))


# --- Datum and the bore's frame -----------------------------------------------
PART_DATUMS = (PartDatum("A", PlanarFace((0.0, 1.0, 0.0), BUSH.HUB_LENGTH)),)
# The frame prints in inches (#290), plain (rule 26 bars the projected-zone
# modifier; owner ruling 2026-11-08 (Pedro), #2144 item 4.1).  The bore's
# tilt to A, carried to K's projected height
# (paper_drive_arm_registration.K_PROJECTED_HEIGHT_MM), stays inside the
# reducer axes' tilt budget (AXIS_PROJECTED_ZONE_DIAMETER_MM) that the collar
# and platen air stacks charge (pd_cluster_air).  ⊥ Ø.002 is a plain inch
# step no tighter than the shop row (.001 per inch over the bore, never
# under .001).
GEOMETRIC_TOLERANCES_IN = {"bore_perpendicularity": ".002"}
GEOMETRIC_TOLERANCES_MM = {
    key: float(value) * 25.4 for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
SHOP_PERPENDICULARITY_MM = max(0.0254, 0.001 * (BUSH.LENGTH + BUSH.LENGTH_BAND))
if GEOMETRIC_TOLERANCES_MM["bore_perpendicularity"] < SHOP_PERPENDICULARITY_MM:
    raise AssertionError(
        "MHA-PD-28 prints a perpendicularity tighter than the shop row"
    )
BORE_AXIS_ZONE_AT_PROJECTED_HEIGHT_MM = (
    GEOMETRIC_TOLERANCES_MM["bore_perpendicularity"]
    * REGISTRATION.K_PROJECTED_HEIGHT_MM
    / BUSH.KNOB_BORE_LENGTH_MIN_MM
)
if BORE_AXIS_ZONE_AT_PROJECTED_HEIGHT_MM > REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM:
    raise AssertionError("MHA-PD-28 prints a zone wider than its stacks assume")
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "bore_perpendicularity",
        "perpendicularity",
        GEOMETRIC_TOLERANCES_IN["bore_perpendicularity"],
        CylinderFace(BUSH.BORE_DIA),
        ("A",),
        "diametral",
    ),
)

# --- Mates the callouts name (drawing-guidelines.md rule 4) -------------------
PLATE_NUMBER = _config.parts("pd-transgear-arm-plate")["number"]
KNOB_SHAFT_NUMBER = _config.parts("pd-transgear-knob-shaft")["number"]
THRUST_RING_NUMBER = _config.parts("pd-transgear-knob-thrust-ring")["number"]
KNOB_CUP_NUMBER = _config.parts("pd-transgear-knob-cup")["number"]
SPROCKET_NUMBER = _config.parts("pd-transgear-removable")["number"]


def _inch(value_mm: float, places: int, rounding) -> str:
    """``value_mm`` rounded by ``rounding`` onto the ``places`` inch grid, as
    print text without the leading zero (``.0005``)."""
    scaled = rounding(round(value_mm / 25.4 * 10**places, 6)) / 10**places
    return f"{scaled:.{places}f}".removeprefix("0")


# --- Finishes -----------------------------------------------------------------
# The bore is the knob shaft's running surface (rule 6); the hub face and the
# rear face are the knob stack's running thrust faces (the MHA-PD-15 thrust
# ring and the MHA-PD-16 cup), MACHINED as the plate's hub and boss faces
# were (R9-13).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bore",
        MACHINED_UM,
        CylinderFace(BUSH.BORE_DIA),
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "hub_face",
        MACHINED_UM,
        PlanarFace((0.0, -1.0, 0.0), 0.0),
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "rear_face",
        MACHINED_UM,
        PlanarFace((0.0, 1.0, 0.0), BUSH.LENGTH),
        display_unit=UNIT,
    ),
)
# What each thrust face's finish serves, captioned at its symbol: two lines
# of words (rule 7; #2657).
FINISH_CAPTIONS = {
    "hub_face": f"THRUST FACE,\nRING {THRUST_RING_NUMBER}",
    "rear_face": f"THRUST FACE,\nCUP {KNOB_CUP_NUMBER}",
}

# --- Callouts -----------------------------------------------------------------
# The bore is a fit reamed in place (rule 12 process, rule 4 route): REAM
# after pressing, the H7 band naming the knob shaft's g6 journal it runs on,
# and the press section's wall, under the .080 target, stated as a plain fact
# (rule 20).  The B pre-drill is the process's, not the sheet's.
WALL_TEXT = f"WALL {_inch(BUSH.WALL_STATED_MIN, 3, math.floor)} MIN"
BORE_CALLOUT = (
    f"REAM THRU AFTER PRESSING IN {PLATE_NUMBER}\n"
    f"RUNNING FIT ON KNOB SHAFT {KNOB_SHAFT_NUMBER}\n"
    f"{WALL_TEXT}"
)
# Made to fit (rule 4, form 2): the press step is turned last to MHA-PD-19's
# hole as measured, so its size prints REF and the interference range
# (.0011 wide) is the requirement, with what the press protects: it alone
# holds knob axis K in the plate (the MHA-CH-12 press land's form,
# ch_rocker_hub_notes.LAND_CALLOUT).
PRESS_CALLOUT = (
    f"PRESS FIT IN {PLATE_NUMBER}, HOLDS KNOB AXIS\n"
    "TURN TO MEASURED HOLE (INTERFERENCE "
    f"{_inch(BUSH.PRESS_INTERFERENCE[0], 4, math.floor)}-"
    f"{_inch(BUSH.PRESS_INTERFERENCE[1], 4, math.ceil)})"
)
# The press Ø prints as a reference, in parentheses (the MHA-PD-23 press
# land's form, pd_transgear_pin_callouts.DIMENSION_TEXT).
PRESS_DIA_TEXT_PREFIX = "(<MOD-DIAM>"
PRESS_DIA_TEXT_SUFFIX = ")"
# The hub face's station from the shoulder (face A) sets the knob shaft (its
# integral 15T meshing the reducer disc) and, through the drive collar on
# the 15T's front face, the removable chain sprocket's plane
# (paper_drive_arm_registration.KNOB_F_MACHINE_Z_MM,
# transgear_cluster_fit.F_CHAIN): it names both by drawing number, as the
# plate's hub station did.
HUB_LENGTH_CALLOUT = f"SETS {KNOB_SHAFT_NUMBER}\nAND {SPROCKET_NUMBER}"
# The hub-to-rear-face length places the bush's rear face on the knob shaft,
# so its ±.002 is a term of the journal's stand-out behind it
# (pd_transgear_knob_shaft_spec.JOURNAL_STANDOUT_BAND), the range the
# MHA-PD-16 cup's supplied pilot absorbs by facing at fit-up
# (pd_transgear_knob_cup_spec.FACING_REMOVAL, never negative).
LENGTH_CALLOUT = f"SETS FACING RANGE\nOF CUP {KNOB_CUP_NUMBER}"
# Below-text the part build authors on its source dimensions; the drawing
# imports and reads it back (text set from the drawing writes through to the
# built part, fleet issue #1942).
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "BoreSketch": {"BoreDia": BORE_CALLOUT},
    "BushProfile": {
        "PressDia": PRESS_CALLOUT,
        "HubLength": HUB_LENGTH_CALLOUT,
        "BushLength": LENGTH_CALLOUT,
    },
}
# The shoulder root, a sketch arc in the turned profile so its radius imports
# into the axial section (a fillet feature's does not: farm r3), prints as
# the single limit R.005 MAX: no native band, " MAX" its suffix
# (build_dt_cone_gear_tl_keyed_arbor's shoulder root).
SHOULDER_ROOT_TOL_TYPE = 0  # swTolType_e.swTolNONE
SHOULDER_ROOT_SUFFIX = " MAX"

# --- Marked dimensions and places ---------------------------------------------
# The turned profile carries both diameters, both lengths from the hub face
# and the shoulder root's radius, so all print on the axial section (rule
# 11).  The stub (shoulder to rear face) follows from the two lengths and is
# not printed.  The reamed bore is its own Top-plane circle, so its Ø and
# callout print on the face view, where the bore is a circle (rule 12; the
# MHA-PD-25 bushing's end view): in A-A its dimension line, nested inside
# the hub Ø's extension lines, had to cross one to reach its block (farm r6).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreSketch": {"BoreDia"},
    "BushProfile": {
        "HubDia",
        "PressDia",
        "HubLength",
        "BushLength",
        "ShoulderR",
    },
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BoreSketch": {"BoreDia": BUSH.BORE_PLACES},
    "BushProfile": {
        "HubDia": BUSH.HUB_DIA_PLACES,
        "PressDia": BUSH.PRESS_DIA_PLACES,
        "HubLength": BUSH.HUB_LENGTH_PLACES,
        "BushLength": BUSH.LENGTH_PLACES,
        "ShoulderR": BUSH.SHOULDER_ROOT_R_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if {
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
} != {
    (feature, name) for feature, names in DRAWING_DIMENSIONS.items() for name in names
}:
    raise AssertionError("MHA-PD-28 marked dimensions and authored places disagree")
for _feature, _callouts in DIMENSION_CALLOUTS.items():
    if not set(_callouts) <= DRAWING_DIMENSIONS[_feature]:
        raise AssertionError(f"MHA-PD-28 {_feature} callout on an unmarked dimension")
