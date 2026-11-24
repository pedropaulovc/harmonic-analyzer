r"""MHA-PD-19 transgear-arm-plate: the drawing contract of the made steel plate.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Every number is ``pd_transgear_arm_plate_geometry``'s (the numbers
authority the plate, its screws, the knob-shaft stack and the paper-drive
assembly share); this module adds only what the sheet needs: the printed
places of each marked dimension, the explicit model bands and the printed
callout text.

Part frame (``pd_transgear_arm_plate_geometry``): origin on the press-hole
axis K on face A (the Front Plane, which seats on the MHA-PD-18 arm's rear
face); +X and +Y are the arm's axes, the long axis runs along -Y from the
screws to the end round about K; +Z to the rear.  The flat plate spans
z 0..THICKNESS_OVER_ARM; the MHA-PD-28 bush pressed into the hole on K
carries the knob bearing (#2425).

[INFERENCE] the -X edge's kink station (``KINK``, read off the book's
notch crop) prints as modelled.
"""

from __future__ import annotations

from _gtol_controls import GeometricControl, PartDatum
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
import pd_transgear_arm_plate_geometry as PLATE
from pd_transgear_arm_plate_geometry import (
    BAND_XX,
    BAND_XXX,
    CSK_DIA_BAND,
    PRESS_HOLE_DIA,
    REDUCER_POSITION_DIAMETER,
    REDUCER_POSITION_RADIUS,  # noqa: F401 - the drawing test reads it off the spec
    EDGE_PLUS_X,
    SCREW_HOLE_DIA,
    THICKNESS_OVER_ARM,
    SCREW_HOLES,
)

# The general-tolerance band each printed place count claims (the title-block
# rows, drawing-guidelines.md rule 3 (decimal places carry the tolerance)).
BAND_BY_PLACES: dict[int, float] = {2: BAND_XX, 3: BAND_XXX}

# Places each printed dimension carries (contract §12, decimal inch #290):
# the outline (end radius, both side edges from K, top corners, kinks)
# follows the arm's own outline in mm and prints .XX, judged at its printed
# reach (``pd_transgear_arm_plate_geometry.OUTLINE_BAND``); the thickness
# .XXX for the real cone floor and standard-stock full-thread margin (its
# callout names the screw reach); the press hole is a four-place reamed fit
# under its explicit band; the screw-hole positions are BASIC under the same
# circular position source as the arm taps, relative to the ACTUAL press
# hole and clocking edge; drilled clearance holes print .XXX under the title
# block's drilled-hole row (R9-13).
OUTLINE_PLACES = PLATE.OUTLINE_PLACES
THICKNESS_PLACES = PLATE.THICKNESS_OVER_ARM_PLACES
SCREW_HOLE_PLACES = PLATE.SCREW_HOLE_PLACES
PRESS_HOLE_PLACES = PLATE.PRESS_HOLE_PLACES
HOLE_POSITION_PLACES = 4
CSK_DIA_PLACES = PLATE.CSK_DIA_PLACES

# The places must claim the bands the geometry module's walls and the hanger
# joints were judged at.
for _label, _places, _band in (
    ("thickness over the arm", THICKNESS_PLACES, PLATE.THICKNESS_OVER_ARM_BAND),
    ("countersink", CSK_DIA_PLACES, CSK_DIA_BAND),
):
    if abs(BAND_BY_PLACES[_places] - _band) > 1e-9:
        raise AssertionError(
            f"MHA-PD-19 {_label} prints {_places} places (±{BAND_BY_PLACES[_places]}),"
            f" not the ±{_band} its walls assume"
        )

# ANALYSIS band, (upper, lower) deviations, not a printed limit: what the
# .4385 set reamer is modelled to cut for the MHA-PD-28 bush's press
# (pd_transgear_knob_bush_geometry); the sheet prints the size and no band.
PRESS_HOLE_BAND = PLATE.BUSH.PRESS_HOLE_BAND
BASIC_REDUCER_DIMENSIONS = (
    ("ScrewHoleProfile", "ScrewHoleX1"),
    ("ScrewHoleProfile", "ScrewHoleX2"),
    ("ScrewHoleProfile", "ScrewHoleY"),
)
BASIC_REDUCER_DIMENSIONS += tuple(
    ("LocatorProfile", name) for name in ("LocatorX1", "LocatorY1", "LocatorX2", "LocatorY2")
)
# B is the press hole: the bush pressed in it carries K, and every pattern
# frame is measured from it.
PART_DATUMS = (
    PartDatum("A", PlanarFace((0.0, 0.0, -1.0), 0.0)),
    PartDatum("B", CylinderFace(PRESS_HOLE_DIA)),
    PartDatum(
        "C", PlanarFace(
            (1.0, 0.0, 0.0), EDGE_PLUS_X,
            contains_z_mm=THICKNESS_OVER_ARM / 2.0,
        ),
    ),
)
# The frames print in inches (#290), plain (rule 26 bars the projected-zone
# modifier; fan-out Q2-A and L1, delegated ruling 2026-11-07 (Main), no
# precedent; owner review #2144; pending owner confirmation).  The locating
# dowel reams are a reamed pattern, Ø.004 (the shop row), inside K's setting
# circle the reducer stacks were judged at.  The screw holes print the
# drilled-hole row, Ø.014: the arm's taps are spotted through them at
# assembly, so they are the joint's master
# (pd_transgear_arm_plate_geometry.SCREW_HOLE_POSITION_DIAMETER_MM).  K's
# tilt is the bush bore's own frame (pd_transgear_knob_bush_spec): the bore
# is reamed after pressing, so the press hole carries none.
GEOMETRIC_TOLERANCES_IN = {"locator_position": ".004", "screw_position": ".014"}
GEOMETRIC_TOLERANCES_MM = {key: float(value) * 25.4 for key, value in GEOMETRIC_TOLERANCES_IN.items()}
if (
    GEOMETRIC_TOLERANCES_MM["locator_position"] > REDUCER_POSITION_DIAMETER
    or GEOMETRIC_TOLERANCES_MM["screw_position"] > PLATE.SCREW_HOLE_POSITION_DIAMETER_MM
):
    raise AssertionError("MHA-PD-19 prints a zone wider than its stacks assume")
GEOMETRIC_CONTROLS = tuple(
    GeometricControl(
        f"plate_hole_{index}_position", "position",
        GEOMETRIC_TOLERANCES_IN["screw_position"],
        CylinderFace(
            SCREW_HOLE_DIA, contains_x_mm=x, contains_y_mm=y,
            contains_z_mm=THICKNESS_OVER_ARM / 2.0,
        ),
        ("A", "B", "C"), "diametral",
    )
    for index, (x, y) in enumerate(SCREW_HOLES, 1)
)
# Each countersink is coaxial with its drilled hole (one hole callout on
# the drilled hole carries it) and so rides the hole's frame; it carries no
# position frame of its own.
GEOMETRIC_CONTROLS += tuple(
    GeometricControl(
        f"plate_locator_{index}_position", "position",
        GEOMETRIC_TOLERANCES_IN["locator_position"],
        CylinderFace(
            PLATE.LOCATOR_HOLE_DIA_MM, contains_x_mm=x, contains_y_mm=y,
            contains_z_mm=THICKNESS_OVER_ARM / 2.0,
        ),
        ("A", "B", "C"), "diametral",
    ) for index, (x, y) in enumerate(PLATE.LOCATOR_SITES_MM, 1)
)
# --- Printed text -------------------------------------------------------------
# Mating parts the callouts name (drawing-guidelines.md rule 4: a band
# tighter than the title block names what it fits).
BUSH_NUMBER = "MHA-PD-28"
ARM_NUMBER = "MHA-PD-18"
DOWEL_NUMBER = "MHA-PD-VN-64"

# No face carries a roughness symbol (drawing-guidelines.md rule 6): the
# press hole is a pressed bore, face A a clamp face, and the knob's running
# bore and thrust faces are the MHA-PD-28 bush's.
# The press hole is a fit: REAM is the requirement (drawing-guidelines.md
# rule 12 (hole and slot callouts say what to do)), and its callout names
# the bush and what the press protects (rule 4).  The screw holes are clearance, drilled; both
# countersinks take the oval heads, each coaxial with its drilled hole: the
# seat and wall budgets bound both axes inside the plate by the hole's zone
# and the drill's run-off
# (pd_transgear_arm_plate_geometry.SCREW_AXIS_RADIUS_IN_PLATE_MM).  Every
# hole's callout is ``pd_transgear_arm_plate_notes``'s (their wording is
# sheet-only).
# The countersink's .XXX diameter seats the screw's oval head and bounds the
# walls beside it (pd_transgear_arm_plate_geometry.WALLS), so the screw-hole
# callout names the screw.
SCREW_NUMBER = "MHA-PD-VN-56"
# The thickness bounds the countersink floor and the screw's thread reach
# into the arm (transgear_hanger_joints._PLATE_MIN/_PLATE_MAX): .XXX.  Two
# lines of words (rule 7; #2657), 16 characters at most.
THICKNESS_CALLOUT = f"SETS SCREW REACH\nIN ARM {ARM_NUMBER}"
# The overall width and height, printed as references (drawing-guidelines.md
# rule 10): the side edges and the end round's extreme under the -X top
# corner, at the outline's own .XX places.  They restate the toleranced
# outline, so they carry no band.
OVERALL_WIDTH_MM = EDGE_PLUS_X - PLATE.EDGE_MINUS_X
OVERALL_HEIGHT_MM = PLATE.TOP_LEFT[1] + PLATE.END_R
DRAWING_REFERENCE_PRECISION = {
    "OverallWidth": PLATE.OUTLINE_PLACES,
    "OverallHeight": PLATE.OUTLINE_PLACES,
}

# Two sheets (drawing-guidelines.md rule 15): the rear face's plan with its
# hole callouts and the isometric, then mounting face A's view with every
# frame and datum, and its projected side view with the thickness and
# datum A edge-on.  The face views say which face they show.
SHEET_NAMES = ("REAR FACE", "FACE A")
REAR_VIEW_LABEL = "REAR VIEW"
FRONT_VIEW_LABEL = "FRONT VIEW (FACE A)"

ISO_VIEW_SCALE = (1, 1)
ISOMETRIC_VIEW_NOTE = f"ISOMETRIC VIEW SCALE {ISO_VIEW_SCALE[0]}:{ISO_VIEW_SCALE[1]}"

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the
# guidelines`).  The countersink Ø lives in the blanked
# ``CountersinkReference`` sketch on the rear face (the revolved cuts that
# model the cones are sketched edge-on to the plan).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateOutline": {
        "EndR",
        "EdgeLeftX",
        "EdgeRightX",
        "TopLeftY",
        "TopRightY",
        "KinkY",
        "KinkRightY",
    },
    "Plate": {"ThicknessOverArm"},
    "PressHoleProfile": {"PressHoleDia"},
    "ScrewHoleProfile": {"ScrewHoleX1", "ScrewHoleX2", "ScrewHoleY", "ScrewHoleDia"},
    "CountersinkReference": {"CskDia"},
    "LocatorProfile": {"LocatorX1", "LocatorY1", "LocatorY2", "LocatorDia1"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateOutline": {
        "EndR": OUTLINE_PLACES,
        "EdgeLeftX": OUTLINE_PLACES,
        "EdgeRightX": OUTLINE_PLACES,
        "TopLeftY": OUTLINE_PLACES,
        "TopRightY": OUTLINE_PLACES,
        "KinkY": OUTLINE_PLACES,
        "KinkRightY": OUTLINE_PLACES,
    },
    "Plate": {"ThicknessOverArm": THICKNESS_PLACES},
    "PressHoleProfile": {"PressHoleDia": PRESS_HOLE_PLACES},
    "ScrewHoleProfile": {
        "ScrewHoleX1": HOLE_POSITION_PLACES,
        "ScrewHoleX2": HOLE_POSITION_PLACES,
        "ScrewHoleY": HOLE_POSITION_PLACES,
        "ScrewHoleDia": SCREW_HOLE_PLACES,
    },
    "CountersinkReference": {"CskDia": CSK_DIA_PLACES},
    "LocatorProfile": {
        "LocatorX1": HOLE_POSITION_PLACES, "LocatorY1": HOLE_POSITION_PLACES,
        "LocatorY2": HOLE_POSITION_PLACES, "LocatorDia1": PLATE.LOCATOR_HOLE_PLACES,
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
    raise AssertionError("MHA-PD-19 marked dimensions and authored places disagree")
if len(DRAWING_PRECISION_BY_NAME) != sum(map(len, DRAWING_DIMENSIONS.values())):
    raise AssertionError("MHA-PD-19 marked dimension names must be unique on the sheet")
