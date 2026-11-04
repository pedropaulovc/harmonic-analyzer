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
section spans z 0..THICKNESS_OVER_ARM, the section below the arm reaches
the arm's front face (its stock thickness), the front hub runs from there to
HUB_FACE_TO_MOUNTING and the rear boss to BOSS_FACE_Z.

[INFERENCE] items the sheet prints as they are modelled: the -X edge's kink
station (``KINK``, read off the book's notch crop) and the rear boss
(contract §1.10).
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
    SCREW_HOLES,
    UNIT,
)

# The general-tolerance band each printed place count claims (the title-block
# rows, drawing-guidelines.md rule 3 (decimal places carry the tolerance)).
BAND_BY_PLACES: dict[int, float] = {2: BAND_XX, 3: BAND_XXX}

# Places each printed dimension carries (contract §12, decimal inch #290):
# the outline (end radius, both side edges from K, top corners, kinks) and
# the notch face's corner heights (it only clears the arm's edge) follow the
# arm's own outline in mm and print .XX, judged at their printed reach
# (``pd_transgear_arm_plate_geometry.OUTLINE_BAND``/``NOTCH_BAND``). The boss
# and hub Ø print .XX; the over-arm thickness .XXX for the real cone floor
# and standard-stock full-thread margin (its callout names the screw reach);
# the notch depth .XX (it only wraps the arm's edge); the hub face's station
# from the mounting face is .XXX (the chain plane, contract §13); the
# hub-to-boss length prints .XXX
# under its explicit knob-float band; the bore is a four-place reamed fit
# under its explicit band; the screw-hole positions are BASIC under the same
# circular position source as the arm taps, relative to the ACTUAL running
# bore and clocking edge; drilled clearance holes print .XXX under the title
# block's drilled-hole row (R9-13).
OUTLINE_PLACES = PLATE.OUTLINE_PLACES
BOSS_DIA_PLACES = 2
NOTCH_DEPTH_PLACES = 2
THICKNESS_PLACES = PLATE.THICKNESS_OVER_ARM_PLACES
HUB_DIA_PLACES = 2
NOTCH_PLACES = PLATE.NOTCH_PLACES
SCREW_HOLE_PLACES = PLATE.SCREW_HOLE_PLACES
HUB_TO_BOSS_PLACES = 3
BORE_PLACES = 4
HOLE_POSITION_PLACES = 4
CSK_DIA_PLACES = PLATE.CSK_DIA_PLACES

# The places must claim the bands the geometry module's walls and the hanger
# joints were judged at.
for _label, _places, _band in (
    ("thickness over the arm", THICKNESS_PLACES, PLATE.THICKNESS_OVER_ARM_BAND),
    ("hub", HUB_DIA_PLACES, BAND_XX),
    ("boss", BOSS_DIA_PLACES, BAND_XX),
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
# The frames print in inches (#290), floored to four places so each printed
# zone stays inside the zones the reducer stacks were judged at.
GEOMETRIC_TOLERANCES_IN = {"position": ".0039", "projected_axis": ".0019"}
GEOMETRIC_TOLERANCES_MM = {key: float(value) * 25.4 for key, value in GEOMETRIC_TOLERANCES_IN.items()}
if (
    GEOMETRIC_TOLERANCES_MM["position"] > REDUCER_POSITION_DIAMETER
    or GEOMETRIC_TOLERANCES_MM["projected_axis"] > REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM
):
    raise AssertionError("MHA-PD-19 prints a reducer zone wider than its stacks assume")
GEOMETRIC_CONTROLS = tuple(
    GeometricControl(
        f"plate_hole_{index}_position", "position",
        GEOMETRIC_TOLERANCES_IN["position"],
        CylinderFace(
            SCREW_HOLE_DIA, contains_x_mm=x, contains_y_mm=y,
            contains_z_mm=THICKNESS_OVER_ARM / 2.0,
        ),
        ("A", "B", "C"), "diametral",
        projected_zone_height_mm=PLATE.CLAMP_PLATE_PROJECTED_HEIGHT_MM,
        projection_unit=UNIT,
    )
    for index, (x, y) in enumerate(SCREW_HOLES, 1)
)
# Each countersink is coaxial with its drilled hole (the plan's 2X CSK
# callout on the drilled hole's centre) and so rides the hole's frame; it
# carries no position frame of its own.
GEOMETRIC_CONTROLS += (
    GeometricControl(
        "knob_projected_axis", "perpendicularity",
        GEOMETRIC_TOLERANCES_IN["projected_axis"],
        CylinderFace(BORE_DIA), ("A",), "diametral",
        projected_zone_height_mm=REGISTRATION.K_PROJECTED_HEIGHT_MM,
        projection_unit=UNIT,
    ),
    *(
        GeometricControl(
            f"plate_locator_{index}_position", "position", GEOMETRIC_TOLERANCES_IN["position"],
            CylinderFace(
                PLATE.LOCATOR_HOLE_DIA_MM, contains_x_mm=x, contains_y_mm=y,
                contains_z_mm=THICKNESS_OVER_ARM / 2.0,
            ),
            ("A", "B", "C"), "diametral",
        ) for index, (x, y) in enumerate(PLATE.LOCATOR_SITES_MM, 1)
    ),
)
# --- Printed text -------------------------------------------------------------
# Mating parts the callouts name (drawing-guidelines.md rule 4: a band
# tighter than the title block names what it fits).
KNOB_SHAFT_NUMBER = "MHA-PD-08"
THRUST_RING_NUMBER = "MHA-PD-15"
KNOB_CUP_NUMBER = "MHA-PD-16"
ARM_NUMBER = "MHA-PD-18"
DOWEL_NUMBER = "MHA-PD-VN-64"

# The locating holes: the size, its fit on the dowel, the matched pair and the
# mouth break. The dowel engagement pays the arm's mouth break, which is
# tighter than the title block's edge break (the wall budgets and the full-
# cylinder span in _transgear_arm_plate_locating_interface are judged at it).
# The match-drill pointer names the MHA-PD-00 view whose native S-K dimension
# sets the pair (rule 7: no method notes; #1388 policy: the setting's value
# lives on the assembly sheet, not here); the draw script fills the sheet
# and view, from a module this part-build input must not import.  All of it
# below the size: the layout audit reads an above-callout as one line.
_MOUTH_BREAK_TEXT = f"{LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM / 25.4:.3f}".removeprefix("0")
LOCATOR_CALLOUT = (
    f"2X REAM THRU, SLIP FIT\nON DOWEL {DOWEL_NUMBER};\n"
    f"MATCH-DRILL WITH ARM\n{ARM_NUMBER}, {{assembly}}\n"
    "{view}; BREAK EDGE\n"
    f"{_MOUTH_BREAK_TEXT} MAX, DOWEL CONTACT"
)

# The bore is the knob shaft's running surface (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)): MACHINED, on
# the exact native bore face the part build resolves. The hub face and the
# boss face are the knob stack's running thrust faces (the MHA-PD-15 thrust
# ring and the MHA-PD-16 cup), MACHINED as the crankshaft journals are (R9-13).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "transgear_arm_plate_bore", MACHINED_UM, CylinderFace(BORE_DIA), display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "hub_face", MACHINED_UM, PlanarFace((0.0, 0.0, -1.0), HUB_FACE_TO_MOUNTING),
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "boss_face", MACHINED_UM, PlanarFace((0.0, 0.0, 1.0), BOSS_FACE_Z), display_unit=UNIT,
    ),
)
# What each thrust face's finish serves, captioned at its symbol.
FINISH_CAPTIONS = {
    "hub_face": f"THRUST FACE,\nRING\n{THRUST_RING_NUMBER}",
    "boss_face": f"THRUST FACE,\nCUP\n{KNOB_CUP_NUMBER}",
}

# The bore is a fit: REAM is the requirement (drawing-guidelines.md rule 12
# (hole and slot callouts say what to do)), and the H7 band names the knob
# shaft's g6 journal it runs on.  The screw holes are clearance, drilled;
# both countersinks take the oval heads, each coaxial with its drilled hole:
# the seat and wall budgets bound both axes inside the plate by the hole's
# projected zone, extrapolated from face A
# (pd_transgear_arm_plate_geometry.SCREW_AXIS_RADIUS_IN_PLATE_MM).
BORE_CALLOUT = f"REAM THRU\nRUNNING FIT ON\nKNOB SHAFT\n{KNOB_SHAFT_NUMBER}"
SCREW_HOLE_CALLOUT = "DRILL THRU"
# Size-independent: the callout is fixed text on the native countersink
# dimension, so a printed hole size here would not follow a unit change of
# the drill callout's own native value (codjiflo review of fad938fc9).  The
# .XXX diameter seats the screw's oval head and bounds the walls beside it
# (pd_transgear_arm_plate_geometry.WALLS), so the callout names the screw.
SCREW_NUMBER = "MHA-PD-VN-56"
CSK_CALLOUT = (
    f"{CSK_ANGLE_DEG:.0f}\u00b0 CSK, HEAD\nSEAT FOR {SCREW_NUMBER}\n"
    "COAXIAL WITH\nDRILLED HOLE"
)
HOLE_COUNT_CALLOUT = f"{len(SCREW_HOLES)}X"
# The hub face's station from mounting face A sets the knob shaft's 12T plane
# through the thrust ring (the chain plane and the disc-to-platen air,
# contract §13) and, as the disc cluster's printed stack's first term, the
# collar's air to the disc (#2038: its ±0.02 is that stack's band); the
# hub-to-boss band sets the cup's station on the shaft and so the cup pin's
# end wall (pd_transgear_knob_shaft_spec.CUP_FACE_STATION_BAND).  Short
# lines, between the dimension's own witness lines.
HUB_STATION_CALLOUT = f"SETS 12T PLANE\nAND COLLAR AIR\nOF {KNOB_SHAFT_NUMBER}"
HUB_TO_BOSS_CALLOUT = f"SETS CUP {KNOB_CUP_NUMBER}\nON SHAFT {KNOB_SHAFT_NUMBER}"
# The over-arm thickness bounds the countersink floor and the screw's thread
# reach into the arm (transgear_hanger_joints._PLATE_MIN/_PLATE_MAX): .XXX.
# Three short lines (12 characters at most), so the block stands clear of
# the hub-to-boss dimension's boss-face witness line.
THICKNESS_CALLOUT = f"SETS SCREW\nREACH IN ARM\n{ARM_NUMBER}"

# Two sheets (drawing-guidelines.md rule 15): the rear face's plan with the
# isometric and section D-D through the screw holes, then mounting face A's
# view with every frame and datum and section A-A on the knob bore. The face
# views say which face they show; each projected zone is a chain line from
# face A with its height (ASME Y14.5-2018 §6.4.7), the knob bore's toward the
# hub and each screw hole's out of face A into the mating arm MHA-PD-18
# (coordinator ruling 2026-10-27, #2017).
SHEET_NAMES = ("REAR FACE", "FACE A")
REAR_VIEW_LABEL = "REAR VIEW"
FRONT_VIEW_LABEL = "FRONT VIEW (FACE A)"
KNOB_ZONE_HEIGHT = REGISTRATION.K_PROJECTED_HEIGHT_MM
SCREW_ZONE_HEIGHT = PLATE.CLAMP_PLATE_PROJECTED_HEIGHT_MM
# The chain lines' heights print as references at the frames' .001 grid
# (Ⓟ .276 and Ⓟ 1.587), each frame stating its zone.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"KnobZone": 3, "ScrewZone": 3}

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
