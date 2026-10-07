r"""Pure-data contract for the rocker arm's rod-hole diamond pin (MHA-CH-006-TL-03).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). Fitted
permanently in the rocker profile fixture plate (MHA-CH-006-TL-02), the pin's
two round lands enter the rocker arm's rod-pin hole and orient the part about
datum A in S3/S4; it is the positive tangential stop for the S4 closing profile
pass only, never datum C, a clamp or a lift. One is made.

Built up (shop-additions section 3, binding route): the lands are a bought
Vermont Gage Class X 0.0782 in plus gauge pin (1.9863-1.9873, certified), its
two flats stoned to 1.76 across, bonded with Loctite 638 into a reamed bore of
a turned 4140 HT body. The model is the finished state: the body and the pin
are two solids, the pin standing LAND_HEIGHT proud of the neck face.

Frame (the inventory's fixture frame, rocker-inv rocker-rod-diamond-pin):
origin on the pin axis at the neck face, +Z DOWN into the plate (axis model
+Z), +X radial from the rocker pivot to the rod hole. The flats face +-X, so
the round lands bear tangentially (+-Y). S3/S4 pose this frame at frame-A
[133.0674, 8.4561, -4.77825], x = [0.997988, 0.063419, 0], z = [0, 0, -1].
"""

from __future__ import annotations

import math

import _hole_spec
from _printed_tolerance import printed_band_mm
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_profile_fixture_spec as plate
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace

BUILT_UP_PERMISSION_NOTE = "LANDS ARE A BOUGHT GAUGE PIN BONDED INTO THE REAMED BORE."

# --- Lands: the bought gauge pin (Class X 0.0782 in plus: +0.000040 in). ---
LAND_DIA = 1.9868
LAND_BAND = (0.0005, -0.0005)  # (upper, lower): the gauge pin's certificate
LAND_PLACES = 4
FLATS_AF = 1.76  # stoned; .XXX general keeps both flats inside the lands
FLATS_PLACES = 3
PIN_LENGTH = 8.0  # snapped at about 8.5 and squared on the wheel

# The lands enter the rocker arm's rod-pin hole: the largest land keeps a
# running clearance in the smallest hole the parent prints (#47 drilled,
# title block DRILLED HOLES +0.10/0). The traveler reams it 2.000-2.010,
# inside that band.
_ROD_HOLE_MIN = _hole_spec.blind_cut_dia_mm(
    rocker.ROD_HOLE_SPEC
)  # DRILLED HOLES minus is 0
LAND_CLEARANCE_MIN = 0.005
if LAND_DIA + LAND_BAND[0] > _ROD_HOLE_MIN - LAND_CLEARANCE_MIN:
    raise AssertionError("diamond-pin lands do not enter the smallest rod-pin hole")
# The title block's general bands (.X: pin length, ream depth, collar; .XXX: flats).
_GENERAL_1PL = printed_band_mm(1)
_GENERAL_3PL = printed_band_mm(3)
if FLATS_AF + _GENERAL_3PL >= LAND_DIA + LAND_BAND[1]:
    raise AssertionError("diamond-pin flats can vanish inside the general band")

# --- Turned 4140 body: all axial sizes from the neck face. ---
NECK_DIA = 3.0
NECK_PLACES = 1
NECK_BAND = (0.0, -0.2)  # never over the cutter-clearance size; keeps a 0.4 bore wall
NECK_LENGTH = 4.3  # .X keeps 0.77 of the 1.57 cutter clearance; collar stays below the S4 op 25/27 cutter tip
COLLAR_DIA = 4.5
# The collar seats on the plate top. The neck face sits just under the arm's
# face B so the plate's pads and shimmed hub stand alone set Z: it is a
# backstop, never a second Z support (FixtureCAD option b).
COLLAR_END = 10.20
COLLAR_END_BAND = (
    0.0,
    -0.2,
)  # never above face B; narrow enough for the tip window below
FACE_B_ABOVE_PLATE = 10.22175  # frame-A Z-4.77825 face B over the plate top Z-15
if COLLAR_END + COLLAR_END_BAND[0] > FACE_B_ABOVE_PLATE:
    raise AssertionError("neck face can lift the arm off the profile-fixture pads")
SHANK_DIA = 2.97
SHANK_BAND = (
    0.02,
    -0.02,
)  # 2.95-2.99: bonded close slip fit in the plate's 3.000-3.010 ream
if SHANK_DIA + SHANK_BAND[0] >= plate.ROD_PIN_HOLE_DIA + plate.ROD_PIN_HOLE_BAND[1]:
    raise AssertionError("diamond-pin shank no longer slips into the profile-fixture ream")
OVERALL_LENGTH = COLLAR_END + 4.8  # shank clears the .X 7.0 hole bottom at every limit
REAM_DIA = 2.0
REAM_BAND = (0.010, 0.0)  # the shop's rod reamer, 2.000-2.010
REAM_DEPTH = 8.0
# Named wall shortfall (drawing-simplicity-policy.md "Named exceptions",
# MHA-CH-006-TL-03 row): the neck over the reamed bore is the thinnest wall,
# stated on the sheet as a MIN, rounded down.
NECK_WALL_MIN = (
    math.floor(((NECK_DIA + NECK_BAND[1]) - (REAM_DIA + REAM_BAND[0])) / 2.0 * 100.0)
    / 100.0
)
COLLAR_WALL_MIN = (
    math.floor((COLLAR_DIA - _GENERAL_1PL - (REAM_DIA + REAM_BAND[0])) / 2.0 * 100.0)
    / 100.0
)
if NECK_WALL_MIN >= (COLLAR_DIA - _GENERAL_1PL - (REAM_DIA + REAM_BAND[0])) / 2.0:
    raise AssertionError("the neck is no longer the thinnest wall round the bore")
# Lands stand LAND_HEIGHT above the neck face, the tip's direct dimension.
# The S4 op 10 outline template lies flat on the upper strap face over the rod
# hole, so the tip must stay under the thinnest strap the parent accepts (it
# prints STRAP 2.50 at .XX, ch_rocker_arm_notes.DEFAULT_DRAWING_PRECISION,
# mirrored to keep that prose out of this part's import closure), and the
# lands must still engage half the thickest strap.  Chain: tip above face B =
# LAND_HEIGHT - (FACE_B_ABOVE_PLATE - COLLAR_END), every term at its limit.
STRAP_PLACES = 2
_STRAP_MIN = rocker.ARM_THICKNESS - printed_band_mm(STRAP_PLACES)
_STRAP_MAX = rocker.ARM_THICKNESS + printed_band_mm(STRAP_PLACES)
TIP_UNDER_STRAP_MARGIN = 0.05  # the template's blued face never rides the tip
LAND_HEIGHT = 1.85
LAND_HEIGHT_PLACES = 2
LAND_HEIGHT_BAND = (0.10, -0.10)
TIP_ABOVE_FACE_B = (
    LAND_HEIGHT
    + LAND_HEIGHT_BAND[1]
    - (FACE_B_ABOVE_PLATE - (COLLAR_END + COLLAR_END_BAND[1])),
    LAND_HEIGHT
    + LAND_HEIGHT_BAND[0]
    - (FACE_B_ABOVE_PLATE - (COLLAR_END + COLLAR_END_BAND[0])),
)
if TIP_ABOVE_FACE_B[1] > _STRAP_MIN - TIP_UNDER_STRAP_MARGIN:
    raise AssertionError("diamond-pin tip can stand above the thinnest rocker strap")
if TIP_ABOVE_FACE_B[0] < _STRAP_MAX / 2.0:
    raise AssertionError("diamond-pin lands engage less than half the thickest strap")
PIN_ENGAGEMENT = PIN_LENGTH - LAND_HEIGHT
if (
    PIN_LENGTH + _GENERAL_1PL - (LAND_HEIGHT + LAND_HEIGHT_BAND[1])
    >= REAM_DEPTH - _GENERAL_1PL
):
    raise AssertionError("diamond pin can bottom in the reamed bore")
# The bonded pin backs the 0.39 neck wall: at the worst-case projection its
# shortest inserted length still runs past the deepest neck (.X) with margin.
PIN_INSERTED_MIN = PIN_LENGTH - _GENERAL_1PL - (LAND_HEIGHT + LAND_HEIGHT_BAND[0])
if PIN_INSERTED_MIN < NECK_LENGTH + _GENERAL_1PL + 0.1:
    raise AssertionError("bonded pin can stop short of the thin neck wall")
# The overall length prints .X; the shank must still clear the bottom of the
# profile fixture's pin hole so the collar, not the shank end, seats. The hole
# depth prints .X there too.
_PLATE_HOLE_DEPTH_MIN = plate.ROD_PIN_HOLE_DEPTH - _GENERAL_1PL
SHANK_LENGTH_LIMITS = [
    round(OVERALL_LENGTH - _GENERAL_1PL - (COLLAR_END + COLLAR_END_BAND[0]), 2),
    round(OVERALL_LENGTH + _GENERAL_1PL - (COLLAR_END + COLLAR_END_BAND[1]), 2),
]
if SHANK_LENGTH_LIMITS[1] >= _PLATE_HOLE_DEPTH_MIN:
    raise AssertionError("diamond-pin shank can bottom in the profile-fixture hole")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LandProfile": {"LandDia"},
    "FlatsProfile": {"FlatsAF"},
    "Flats": {"LandHeight"},
    "NeckProfile": {"NeckDia"},
    "Neck": {"NeckLength"},
    "CollarProfile": {"CollarDia"},
    "Collar": {"CollarEnd"},
    "ShankProfile": {"ShankDia"},
    "Shank": {"OverallLength"},
    "Pin": {"PinLength"},
    "ReamProfile": {"ReamDia"},
    "Ream": {"ReamDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LandProfile": {"LandDia": LAND_PLACES},
    "FlatsProfile": {"FlatsAF": FLATS_PLACES},
    "Flats": {"LandHeight": LAND_HEIGHT_PLACES},
    "NeckProfile": {"NeckDia": NECK_PLACES},
    "Neck": {"NeckLength": 1},
    "CollarProfile": {"CollarDia": 1},
    "Collar": {"CollarEnd": 1},
    "ShankProfile": {"ShankDia": 2},
    "Shank": {"OverallLength": 1},
    "Pin": {"PinLength": 1},
    "ReamProfile": {"ReamDia": 3},
    "Ream": {"ReamDepth": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked diamond-pin dimension needs authored places")

DRAWING_REFERENCE_PRECISION = 1  # the (overall) reference prints .X
SURFACE_FINISHES = ()
# Lines 3-4 stay short: the template's isometric caption sits beside them.
DRAWING_NOTES = "\n".join(
    (
        BUILT_UP_PERMISSION_NOTE
        + " PIN SET TO ITS PROJECTION, FILLING THE BORE THROUGH THE NECK.",
        "BODY LENGTHS FROM THE NECK FACE; COLLAR SEAT HOLDS THE TIP UNDER THE ARM TOP;"
        " FLATS FULL LAND LENGTH. NECK OD TURNED CONCENTRIC TO THE REAMED BORE.",
        # Named exception: MHA-CH-006-TL-03 neck wall (drawing-simplicity-policy.md, "Named exceptions").
        "HAND-LOAD LOCATOR; NO CLAMP OR CUT LOAD."
        f" NECK WALL TO BORE {NECK_WALL_MIN:.2f} MIN, COLLAR {COLLAR_WALL_MIN:.2f} MIN."
        " FITS LOCATE, BOND FILLS.",
        "SHANK BONDED IN THE ROCKER ARM PROFILE FIXTURE PIN HOLE, FLATS SQUARE TO ITS"
        " PIVOT-TO-ROD-HOLE LINE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"

_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
_ROD = ("ch_rocker_arm_spec", "ROD_HOLE_SPEC")
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "lands": ExportFeature(
        kind="pin",
        faces=(CylinderFace(LAND_DIA, contains_z_mm=-1.0, tolerance_mm=0.003),),
        requirements=("dia", "width", "height", "length"),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": _AXIS,
            "dia": (
                limits(LAND_DIA, LAND_PLACES, LAND_BAND),
                ("LAND_DIA", "LAND_BAND", _ROD),
            ),
            "dia_nominal": (LAND_DIA, ("LAND_DIA",)),
            # width = across the stoned flats (normals +-X, see "flat_pos"/"flat_neg")
            "width": (limits(FLATS_AF, FLATS_PLACES), ("FLATS_AF",)),
            "z_mm": ([-LAND_HEIGHT, 0.0], ("LAND_HEIGHT",)),
            "height": (
                limits(LAND_HEIGHT, LAND_HEIGHT_PLACES, LAND_HEIGHT_BAND),
                (
                    "LAND_HEIGHT",
                    "LAND_HEIGHT_BAND",
                    "COLLAR_END_BAND",
                    "FACE_B_ABOVE_PLATE",
                    ("ch_rocker_arm_spec", "ARM_THICKNESS"),
                ),
            ),
            # The bought pin's total length: keeps it off the bore bottom and
            # its inserted end past the thin neck.
            "length": (
                limits(PIN_LENGTH, 1),
                ("PIN_LENGTH", "REAM_DEPTH", "NECK_LENGTH"),
            ),
        },
        precision={"width": FLATS_PLACES, "height": LAND_HEIGHT_PLACES, "length": 1},
    ),
    **{
        name: ExportFeature(
            kind="face",
            faces=(PlanarFace((sign, 0.0, 0.0), FLATS_AF / 2.0),),
            requirements=("normal",),
            fields={
                "normal": ([sign, 0.0, 0.0], ("__frame__",)),
                "width": (limits(FLATS_AF, FLATS_PLACES), ("FLATS_AF",)),
            },
            precision={"width": FLATS_PLACES},
        )
        for name, sign in (("flat_pos", 1.0), ("flat_neg", -1.0))
    },
    "neck_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
        requirements=("height",),
        fields={
            "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
            "height": (
                limits(COLLAR_END, 1, COLLAR_END_BAND),
                ("COLLAR_END", "COLLAR_END_BAND", "FACE_B_ABOVE_PLATE"),
            ),
        },
        precision={"height": 1},
    ),
    "collar_seat": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), COLLAR_END),),
        requirements=("dia",),
        fields={
            "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
            "plane": (
                {"frame": "model", "axis": "z", "value": COLLAR_END},
                ("COLLAR_END",),
            ),
            "dia": (limits(COLLAR_DIA, 1), ("COLLAR_DIA",)),
        },
        precision={"dia": 1},
    ),
    "shank": ExportFeature(
        kind="boss",
        faces=(CylinderFace(SHANK_DIA, tolerance_mm=0.003),),
        requirements=("dia", "length"),
        fields={
            "at": ([0.0, 0.0, COLLAR_END], ("COLLAR_END",)),
            "axis": _AXIS,
            "dia": (limits(SHANK_DIA, 2, SHANK_BAND), ("SHANK_DIA", "SHANK_BAND")),
            "dia_nominal": (SHANK_DIA, ("SHANK_DIA",)),
            # Derived OverallLength - CollarEnd: stacked endpoint limits.
            "length": (
                SHANK_LENGTH_LIMITS,
                ("OVERALL_LENGTH", "COLLAR_END", "COLLAR_END_BAND"),
            ),
        },
        precision={"dia": 2, "length": 1},
    ),
    # The neck whose wall is the named exception, and the ream's open length
    # below the bonded pin (the pin fills the bore through the neck).
    "neck": ExportFeature(
        kind="boss",
        faces=(
            CylinderFace(NECK_DIA, contains_z_mm=NECK_LENGTH / 2.0, tolerance_mm=0.003),
        ),
        requirements=("dia", "length"),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": _AXIS,
            "dia": (
                limits(NECK_DIA, NECK_PLACES, NECK_BAND),
                ("NECK_DIA", "NECK_BAND"),
            ),
            "length": (limits(NECK_LENGTH, 1), ("NECK_LENGTH",)),
        },
        precision={"dia": NECK_PLACES, "length": 1},
    ),
    "ream": ExportFeature(
        kind="hole",
        faces=(
            CylinderFace(
                REAM_DIA,
                contains_z_mm=(PIN_ENGAGEMENT + REAM_DEPTH) / 2.0,
                tolerance_mm=0.003,
            ),
        ),
        requirements=("dia", "depth"),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": _AXIS,
            "dia": (limits(REAM_DIA, 3, REAM_BAND), ("REAM_DIA", "REAM_BAND")),
            "depth": (limits(REAM_DEPTH, 1), ("REAM_DEPTH",)),
        },
        precision={"dia": 3, "depth": 1},
    ),
}
