r"""MHA-PD-19 transgear-arm-plate: the drawing contract of the made steel plate.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Every number is ``pd_transgear_arm_plate_geometry``'s (the numbers
authority the plate, its screws, the knob-shaft stack and the paper-drive
assembly share); this module adds only what the sheet needs: the printed
places of each marked dimension, the explicit model bands, the bore's and
the thrust faces' finish and the printed callout text.

Part frame (``pd_transgear_arm_plate_geometry``): origin on the knob-shaft bore
axis K on the MOUNTING face (the Front Plane, which seats on the MHA-PD-18
arm's rear face); +X and +Y are the arm's axes, the long axis runs along -Y
from the screws to the end round about K; +Z to the rear.  The over-arm
section spans z 0..5, the section below the arm z -7.9375..5 (the arm's
stock thickness), the front hub z -20.5375..-7.9375 and the rear boss
z 5..8.5.

[INFERENCE] items the sheet prints as they are modelled: the -X edge's kink
station (``KINK``, read off the book's notch crop) and the rear boss
(Ø20 x 3.5, contract §1.10).
"""

from __future__ import annotations

from _gtol_controls import GeometricControl, PartDatum
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
import pd_transgear_arm_plate_geometry as PLATE
import _transgear_arm_plate_locating_interface as LOCATING_PIN
import paper_drive_arm_registration as REGISTRATION
from pd_transgear_arm_plate_geometry import (
    BAND_X,
    BAND_XX,
    BAND_XXX,
    BORE_DIA,
    BORE_DIA_LIMITS,
    BOSS_FACE_Z,
    CSK_ANGLE_DEG,
    CSK_DIA_BAND,
    REDUCER_POSITION_DIAMETER,
    REDUCER_POSITION_RADIUS,  # noqa: F401 - the drawing test reads it off the spec
    EDGE_PLUS_X,
    SCREW_HOLE_DIA,
    THICKNESS_OVER_ARM,
    HUB_FACE_TO_MOUNTING,
    HUB_TO_BOSS_BAND,
    NOTCH_BAND,
    SCREW_HOLES,
)

# The general-tolerance band each printed place count claims (the title-block
# rows the geometry module hard-codes, drawing-guidelines.md rule 3 (decimal places carry the tolerance)).
BAND_BY_PLACES: dict[int, float] = {1: BAND_X, 2: BAND_XX, 3: BAND_XXX}

# Places each printed dimension carries (contract §12):
# the outline (end radius, both side edges from K, top corners, kinks), the
# boss Ø, the notch face's corner heights (it only clears the arm's edge) are
# routine .X. The over-arm thickness retains .XX for the real cone floor and
# standard-stock full-thread margin. The enlarged clearance permits an
# ordinary .X CSK. The hub Ø and notch depth retain .XX; the arm's stock
# thickness it takes (7.94; R9-26; at .X the lower section's front face
# enters the guide-lock screw heads' sweep); the hub face's station from the
# mounting face is .XXX (the chain plane, contract §13: the disc-to-platen air
# closes at .XX); the hub-to-boss length prints .XXX under its explicit
# knob-float band; the bore is a .XXX running fit under its explicit band;
# the screw-hole positions are BASIC under the same circular position source
# as the arm taps, relative to the ACTUAL running bore and clocking edge;
# drilled clearance holes print .X under the title block's drilled-hole row
# (R9-13).
OUTLINE_PLACES = 1
BOSS_DIA_PLACES = 1
NOTCH_DEPTH_PLACES = 2
THICKNESS_PLACES = PLATE.THICKNESS_OVER_ARM_PLACES
HUB_DIA_PLACES = 2
NOTCH_PLACES = 1
SCREW_HOLE_PLACES = 1
HUB_TO_BOSS_PLACES = 3
BORE_PLACES = 3
HOLE_POSITION_PLACES = 3
CSK_DIA_PLACES = PLATE.CSK_DIA_PLACES

# The places must claim the bands the geometry module's walls and the hanger
# joints were judged at.
for _label, _places, _band in (
    ("thickness over the arm", THICKNESS_PLACES, PLATE.THICKNESS_OVER_ARM_BAND),
    ("hub", HUB_DIA_PLACES, BAND_XX),
    ("notch face", NOTCH_PLACES, NOTCH_BAND),
    ("boss", BOSS_DIA_PLACES, BAND_X),
    ("outline", OUTLINE_PLACES, BAND_X),
    ("countersink", CSK_DIA_PLACES, CSK_DIA_BAND),
):
    if abs(BAND_BY_PLACES[_places] - _band) > 1e-9:
        raise AssertionError(
            f"MHA-PD-19 {_label} prints {_places} places (±{BAND_BY_PLACES[_places]}),"
            f" not the ±{_band} its walls assume"
        )

# Explicit model bands, (upper, lower) deviations where one-sided.
# The H7 running bore on the knob shaft's sourced g6 journal.
BORE_BAND = (BORE_DIA_LIMITS[1], BORE_DIA_LIMITS[0])
# The knob's end float between the thrust ring on the hub face and the cup
# behind the boss face.
HUB_TO_BOSS_TOLERANCE = HUB_TO_BOSS_BAND
BASIC_REDUCER_DIMENSIONS = (
    ("ScrewHoleProfile", "ScrewHoleX1"),
    ("ScrewHoleProfile", "ScrewHoleX2"),
    ("ScrewHoleProfile", "ScrewHoleY"),
)
BASIC_REDUCER_DIMENSIONS += tuple(
    ("LocatorProfile", name) for name in ("LocatorX1", "LocatorY1", "LocatorX2", "LocatorY2")
)
PART_DATUMS = (
    PartDatum("A", PlanarFace((0.0, 0.0, -1.0), 0.0)),
    PartDatum("B", CylinderFace(BORE_DIA)),
    PartDatum(
        "C", PlanarFace(
            (1.0, 0.0, 0.0), EDGE_PLUS_X,
            contains_z_mm=THICKNESS_OVER_ARM / 2.0,
        ),
    ),
)
GEOMETRIC_CONTROLS = tuple(
    GeometricControl(
        f"plate_hole_{index}_position", "position",
        f"{REDUCER_POSITION_DIAMETER:.3f}",
        CylinderFace(
            SCREW_HOLE_DIA, contains_x_mm=x, contains_y_mm=y,
            contains_z_mm=THICKNESS_OVER_ARM / 2.0,
        ),
        ("A", "B", "C"), "diametral",
        projected_zone_height_mm=PLATE.CLAMP_PLATE_PROJECTED_HEIGHT_MM,
    )
    for index, (x, y) in enumerate(SCREW_HOLES, 1)
)
# Each countersink is coaxial with its drilled hole (sheet note 3) and so
# rides the hole's frame; it carries no position frame of its own.
GEOMETRIC_CONTROLS += (
    GeometricControl(
        "knob_projected_axis", "perpendicularity",
        f"{REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM:.3f}",
        CylinderFace(BORE_DIA), ("A",), "diametral",
        projected_zone_height_mm=REGISTRATION.K_PROJECTED_HEIGHT_MM,
    ),
    *(
        GeometricControl(
            f"plate_locator_{index}_position", "position", f"{REDUCER_POSITION_DIAMETER:.3f}",
            CylinderFace(
                PLATE.LOCATOR_HOLE_DIA_MM, contains_x_mm=x, contains_y_mm=y,
                contains_z_mm=THICKNESS_OVER_ARM / 2.0,
            ),
            ("A", "B", "C"), "diametral",
        ) for index, (x, y) in enumerate(PLATE.LOCATOR_SITES_MM, 1)
    ),
)
# The stock locating dowels are a slip fit in the plate and a press fit in
# the arm. Keep the paid mouth-break limit: it preserves cylindrical grip,
# rather than silently falling back to the title block's larger edge break.
LOCATOR_CALLOUT = (
    "2X REAM THRU\nSLIP FIT ON\nMHA-PD-VN-64\nLOCATING DOWELS\n"
    f"BREAK EDGE {LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM:.2f} MAX\n"
    "MATCHED SET: SHEET 2"
)

# The bore is the knob shaft's running surface (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)): MACHINED, on
# the exact native bore face the part build resolves. The hub face and the
# boss face are the knob stack's running thrust faces (the MHA-PD-15 thrust
# ring and the MHA-PD-16 cup), MACHINED as the crankshaft journals are (R9-13).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "transgear_arm_plate_bore", MACHINED_UM, CylinderFace(BORE_DIA)
    ),
    SurfaceFinishControl(
        "hub_face", MACHINED_UM, PlanarFace((0.0, 0.0, -1.0), HUB_FACE_TO_MOUNTING)
    ),
    SurfaceFinishControl(
        "boss_face", MACHINED_UM, PlanarFace((0.0, 0.0, 1.0), BOSS_FACE_Z)
    ),
)

# --- Printed text -------------------------------------------------------------
# The journal is the actual Ø6 g6 running mate, not a generic clearance hole.
BORE_CALLOUT = "REAM THRU\nRUNNING FIT: MHA-PD-08\nKNOB SHAFT JOURNAL"
HUB_STATION_CALLOUT = "CHAIN PLANE: MHA-PD-08 KNOB SHAFT"
HUB_TO_BOSS_CALLOUT = (
    "SETS KNOB FLOAT BETWEEN\n"
    "MHA-PD-15 THRUST RING /\nMHA-PD-16 KNOB CUP"
)
SCREW_HOLE_CALLOUT = "DRILL THRU"
CSK_CALLOUT = f"{CSK_ANGLE_DEG:.0f}\u00b0 CSK\nCOAXIAL WITH DRILLED HOLE"
HOLE_COUNT_CALLOUT = f"{len(SCREW_HOLES)}X"
# Side-on graphics on sheet 2 make these source extents visible without
# overlaying a chain on a face-on bore. The native model FCFs remain the
# governing controls; no height or tolerance is created by the drawing.
SCREW_PROJECTED_ZONE_CALLOUT = "\n".join((
    "2X SCREW-BORE PROJECTED ZONE",
    "START: MOUNTING FACE A",
    f"{PLATE.CLAMP_PLATE_PROJECTED_HEIGHT_MM:.1f} TOWARD THE REAR FACE",
    "GOVERNING CONTROLS ON SHEET 1",
))
KNOB_PROJECTED_ZONE_CALLOUT = "\n".join((
    "KNOB-BORE PROJECTED ZONE",
    "START: MOUNTING FACE A",
    f"{REGISTRATION.K_PROJECTED_HEIGHT_MM:.1f} TOWARD THE HUB",
    "GOVERNING CONTROL ON SHEET 1",
))

ISO_VIEW_SCALE = (1, 1)
ISOMETRIC_VIEW_NOTE = f"ISOMETRIC VIEW SCALE {ISO_VIEW_SCALE[0]}:{ISO_VIEW_SCALE[1]}"

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the guidelines`).  The bearing profile is the revolved
# hub and boss, sketched in the section plane; the countersink Ø lives in the
# blanked ``CountersinkReference`` sketch on the rear face (the revolved cuts
# that model the cones are sketched edge-on to the plan).  The boss height is
# not marked: the thickness over the arm, the hub station and the hub-to-boss
# length already fix the boss face.
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
    "LowerOutline": {"NotchLeftY", "NotchRightY"},
    "LowerSection": {"NotchDepth"},
    "BearingProfile": {"HubDia", "BossDia", "HubFaceToMounting", "HubToBoss"},
    "BoreProfile": {"BoreDia"},
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
    "LowerOutline": {"NotchLeftY": NOTCH_PLACES, "NotchRightY": NOTCH_PLACES},
    "LowerSection": {"NotchDepth": NOTCH_DEPTH_PLACES},
    "BearingProfile": {
        "HubDia": HUB_DIA_PLACES,
        "BossDia": BOSS_DIA_PLACES,
        "HubFaceToMounting": PLATE.HUB_STATION_PLACES,
        "HubToBoss": HUB_TO_BOSS_PLACES,
    },
    "BoreProfile": {"BoreDia": BORE_PLACES},
    "ScrewHoleProfile": {
        "ScrewHoleX1": HOLE_POSITION_PLACES,
        "ScrewHoleX2": HOLE_POSITION_PLACES,
        "ScrewHoleY": HOLE_POSITION_PLACES,
        "ScrewHoleDia": SCREW_HOLE_PLACES,
    },
    "CountersinkReference": {"CskDia": CSK_DIA_PLACES},
    "LocatorProfile": {
        "LocatorX1": 3, "LocatorY1": 3, "LocatorY2": 3, "LocatorDia1": 3,
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
