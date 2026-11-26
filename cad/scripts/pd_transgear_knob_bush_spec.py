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
import textwrap

import _config
import paper_drive_arm_registration as REGISTRATION
import pd_transgear_knob_bush_geometry as BUSH
from _gtol_controls import GeometricControl, PartDatum
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

UNIT = BUSH.UNIT

# The reamed running bore's ANALYSIS band, (upper, lower): what the reamer
# is taken to cut.  Not a printed limit (the sheet prints the reamer's size
# and no band); the feature declaration and the stacks read it.
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
DRIVE_COLLAR_NUMBER = _config.parts("pd-transgear-drive-collar")["number"]


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
# after pressing, at the reamer's size with no band, then the pointer to the
# sheet's one numbered note and the press section's wall, under the .080
# target, stated as a plain fact (rule 20).  Under the size and process a
# callout carries at most two lines of words (rule 7), so the fit statement
# stands in the note: the knob shaft is turned to this bore (guidelines v2:
# the acceptance prints once, on the sheet of the member made last,
# MHA-PD-08's note 1; a bare fit name here was r1's blocker).  What the fit
# protects is in the necessity register
# (cad/config/necessity/pd-transgear-knob-bush.yaml N-01; owner ruling
# 2026-11-24: the sheet prints no reason).  No line of the callout is longer
# than its process line: at 59 characters the block ran out through the left
# border and its leader through the bore finish's text (r1).  The B
# pre-drill is the process's, not the sheet's.
WALL_TEXT = f"WALL {_inch(BUSH.WALL_STATED_MIN, 3, math.floor)} MIN"
BORE_NOTE_NUMBER = 1
BORE_NOTE_WIDTH = 40
BORE_NOTE = "\n".join(
    textwrap.wrap(
        f"{BORE_NOTE_NUMBER}. KNOB SHAFT {KNOB_SHAFT_NUMBER} IS TURNED TO THIS BORE.",
        width=BORE_NOTE_WIDTH,
        subsequent_indent="   ",
        break_on_hyphens=False,
    )
)
BORE_CALLOUT = (
    f"REAM THRU AFTER PRESSING IN {PLATE_NUMBER}\n"
    f"SEE NOTE {BORE_NOTE_NUMBER}\n"
    f"{WALL_TEXT}"
)
# Made to fit (rule 4, form 2): the press step is turned last to MHA-PD-19's
# hole as measured, so its size prints REF and the interference range
# (.0011 wide) is the requirement (the MHA-CH-12 press land's form,
# ch_rocker_hub_notes.LAND_CALLOUT).  What the press protects is in the
# necessity register (N-04).  The press itself, where rule 4 would take a
# bonded slip fit, is the registry row's RV-04.  The fitted mate is named
# with its number, as the shaft, ring and cup are (rule 4; machinist review
# of 2fd8267613).  Neither line is longer than the 48 characters the
# block's place was set for.
PRESS_CALLOUT = (
    f"PRESS FIT IN ARM PLATE {PLATE_NUMBER}\n"
    "TURN TO MEASURED HOLE (INTERFERENCE "
    f"{_inch(BUSH.PRESS_INTERFERENCE[0], 4, math.floor)}-"
    f"{_inch(BUSH.PRESS_INTERFERENCE[1], 4, math.ceil)})"
)
# The press Ø prints as a reference, in parentheses (the MHA-PD-23 press
# land's form, pd_transgear_pin_callouts.DIMENSION_TEXT).
PRESS_DIA_TEXT_PREFIX = "(<MOD-DIAM>"
PRESS_DIA_TEXT_SUFFIX = ")"
# The hub face's station from the shoulder (face A) is the first term of
# the disc cluster's stack (F, transgear_cluster_fit), and the stack's air
# between the MHA-PD-22 drive collar and the MHA-PD-06 disc is what closes
# when it is loose: at the title block's ±.005 the statistical air falls to
# 0.0972 mm under its 0.1016 floor (pd_cluster_air.require_air; the
# MHA-PD-17 spigot length at the title block, delegated ruling D21).
# The hub-to-rear-face length places the bush's rear face on the knob shaft,
# so its ±.002 is a term of the journal's stand-out behind it
# (pd_transgear_knob_shaft_spec.JOURNAL_STANDOUT_BAND), which the
# MHA-PD-16 cup's supplied pilot must cover for the knob's end float to be
# set by facing the cup (pd_transgear_knob_cup_spec.FACING_REMOVAL, never
# negative: .001 is left at ±.002, none at ±.003, and at the title block's
# ±.005 the float cannot be set).  Neither band has a mate to try, so
# neither prints a label (rule 4: a band with no mate to try names none);
# the station stands on machinist exception RV-05 and the length on the
# necessity register (N-03).
# Below-text the part build authors on its source dimensions; the drawing
# imports and reads it back (text set from the drawing writes through to the
# built part, fleet issue #1942).
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "BoreSketch": {"BoreDia": BORE_CALLOUT},
    "BushProfile": {
        "PressDia": PRESS_CALLOUT,
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
