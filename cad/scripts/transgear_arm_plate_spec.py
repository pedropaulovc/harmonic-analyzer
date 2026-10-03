r"""MHA-165 transgear-arm-plate: the drawing contract of the made steel plate.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Every number is ``transgear_arm_plate_geometry``'s (the numbers
authority the plate, its screws, the knob-shaft stack and the paper-drive
assembly share); this module adds only what the sheet needs: the printed
places of each marked dimension, the explicit model bands, the bore's and
the thrust faces' finish and the printed callout text.

Part frame (``transgear_arm_plate_geometry``): origin on the knob-shaft bore
axis K on the MOUNTING face (the Front Plane, which seats on the MHA-164
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

from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from transgear_arm_plate_geometry import (
    BAND_X,
    BAND_XX,
    BAND_XXX,
    BORE_DIA,
    BORE_DIA_LIMITS,
    BOSS_FACE_Z,
    CSK_ANGLE_DEG,
    CSK_DIA_BAND,
    HOLE_POSITION_BAND,
    HUB_FACE_TO_MOUNTING,
    HUB_TO_BOSS_BAND,
    NOTCH_BAND,
    SCREW_HOLES,
)

# The general-tolerance band each printed place count claims (the title-block
# rows the geometry module hard-codes, policy rule 12).
BAND_BY_PLACES: dict[int, float] = {1: BAND_X, 2: BAND_XX, 3: BAND_XXX}

# Places each printed dimension carries (contract §12):
# the outline (end radius, bar width, top corners, kink), the boss Ø, the
# notch face's corner heights (it only clears the arm's edge) and the
# countersink Ø (the cut-to-fit screw's seat, CSK_DIA_BAND) are routine .X;
# the thickness over the arm is .XX (at .X the shortest stock MHA-166 no
# longer stands past its cut and the land under the cone thins below the
# wall target), as is the hub Ø (wall) and the notch's depth, the arm's stock
# thickness it takes (7.94; R9-26; at .X the lower section's front face
# enters the guide-lock screw heads' sweep); the hub face's station from the
# mounting face is .XXX (the chain plane, contract §13: the disc-to-platen air
# closes at .XX); the hub-to-boss length prints .XXX under its explicit
# knob-float band; the bore is a .XXX running fit under its explicit band;
# the screw-hole positions are .XXX under the explicit ±HOLE_POSITION_BAND the
# arm's taps share (the two shanks' float over the plate-to-arm pitch); the
# drilled clearance holes print .X under the title block's drilled-hole row
# (R9-13).
OUTLINE_PLACES = 1
BOSS_DIA_PLACES = 1
NOTCH_DEPTH_PLACES = 2
THICKNESS_PLACES = 2
HUB_DIA_PLACES = 2
NOTCH_PLACES = 1
SCREW_HOLE_PLACES = 1
HUB_STATION_PLACES = 3
HUB_TO_BOSS_PLACES = 3
BORE_PLACES = 3
HOLE_POSITION_PLACES = 3
CSK_DIA_PLACES = 1

# The places must claim the bands the geometry module's walls and the hanger
# joints were judged at.
for _label, _places, _band in (
    ("thickness over the arm", THICKNESS_PLACES, BAND_XX),
    ("hub", HUB_DIA_PLACES, BAND_XX),
    ("notch face", NOTCH_PLACES, NOTCH_BAND),
    ("boss", BOSS_DIA_PLACES, BAND_X),
    ("outline", OUTLINE_PLACES, BAND_X),
    ("countersink", CSK_DIA_PLACES, CSK_DIA_BAND),
):
    if abs(BAND_BY_PLACES[_places] - _band) > 1e-9:
        raise AssertionError(
            f"MHA-165 {_label} prints {_places} places (±{BAND_BY_PLACES[_places]}),"
            f" not the ±{_band} its walls assume"
        )

# Explicit model bands, (upper, lower) deviations where one-sided.
# The running bore on the knob shaft's Ø8.5 journal.
BORE_BAND = (BORE_DIA_LIMITS[1], BORE_DIA_LIMITS[0])
# The knob's end float between the thrust ring on the hub face and the cup
# behind the boss face.
HUB_TO_BOSS_TOLERANCE = HUB_TO_BOSS_BAND
# The screw-hole positions from the bore, the band the arm's taps carry.
HOLE_POSITION_TOLERANCE = HOLE_POSITION_BAND

# The bore is the knob shaft's running surface (policy rule 5): MACHINED, on
# the exact native Ø8.5 face the part build resolves.  The hub face and the
# boss face are the knob stack's running thrust faces (the MHA-156 thrust
# ring and the MHA-157 cup), MACHINED as the crankshaft journals are (R9-13).
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
# The bore is a fit: REAM is the requirement (policy rule 7).  The screw
# holes are clearance, drilled; both countersinks take the oval heads.
BORE_CALLOUT = "REAM THRU"
SCREW_HOLE_CALLOUT = "DRILL THRU"
CSK_CALLOUT = f"{CSK_ANGLE_DEG:.0f}\u00b0 CSK"
HOLE_COUNT_CALLOUT = f"{len(SCREW_HOLES)}X"

ISO_VIEW_SCALE = (1, 1)
ISOMETRIC_VIEW_NOTE = f"ISOMETRIC VIEW SCALE {ISO_VIEW_SCALE[0]}:{ISO_VIEW_SCALE[1]}"

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).  The bearing profile is the revolved
# hub and boss, sketched in the section plane; the countersink Ø lives in the
# blanked ``CountersinkReference`` sketch on the rear face (the revolved cuts
# that model the cones are sketched edge-on to the plan).  The boss height is
# not marked: the thickness over the arm, the hub station and the hub-to-boss
# length already fix the boss face.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateOutline": {"EndR", "Width", "TopLeftY", "TopRightY", "KinkY"},
    "Plate": {"ThicknessOverArm"},
    "LowerOutline": {"NotchLeftY", "NotchRightY"},
    "LowerSection": {"NotchDepth"},
    "BearingProfile": {"HubDia", "BossDia", "HubFaceToMounting", "HubToBoss"},
    "BoreProfile": {"BoreDia"},
    "ScrewHoleProfile": {"ScrewHoleX1", "ScrewHoleX2", "ScrewHoleY", "ScrewHoleDia"},
    "CountersinkReference": {"CskDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateOutline": {
        "EndR": OUTLINE_PLACES,
        "Width": OUTLINE_PLACES,
        "TopLeftY": OUTLINE_PLACES,
        "TopRightY": OUTLINE_PLACES,
        "KinkY": OUTLINE_PLACES,
    },
    "Plate": {"ThicknessOverArm": THICKNESS_PLACES},
    "LowerOutline": {"NotchLeftY": NOTCH_PLACES, "NotchRightY": NOTCH_PLACES},
    "LowerSection": {"NotchDepth": NOTCH_DEPTH_PLACES},
    "BearingProfile": {
        "HubDia": HUB_DIA_PLACES,
        "BossDia": BOSS_DIA_PLACES,
        "HubFaceToMounting": HUB_STATION_PLACES,
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
    raise AssertionError("MHA-165 marked dimensions and authored places disagree")
if len(DRAWING_PRECISION_BY_NAME) != sum(map(len, DRAWING_DIMENSIONS.values())):
    raise AssertionError("MHA-165 marked dimension names must be unique on the sheet")
