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

import _hole_spec
import ch_rocker_arm_spec as rocker
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace

BUILT_UP_PERMISSION_NOTE = "LANDS ARE A BOUGHT GAUGE PIN BONDED INTO THE REAMED BORE."

# --- Lands: the bought gauge pin (Class X 0.0782 in plus: +0.000040 in). ---
LAND_DIA = 1.9868
LAND_BAND = (0.0005, -0.0005)  # (upper, lower): the gauge pin's certificate
LAND_PLACES = 4
FLATS_AF = 1.76  # stoned; .XXX general keeps both flats inside the lands
FLATS_PLACES = 3
PIN_LENGTH = 8.5  # snapped at about 9 and squared on the wheel

# The lands enter the rocker arm's rod-pin hole: the largest land keeps a
# running clearance in the smallest hole the parent prints (#47 drilled,
# title block DRILLED HOLES +0.10/0). The traveler reams it 2.000-2.010,
# inside that band.
_ROD_HOLE_MIN = _hole_spec.blind_cut_dia_mm(rocker.ROD_HOLE_SPEC)  # DRILLED HOLES minus is 0
LAND_CLEARANCE_MIN = 0.005
if LAND_DIA + LAND_BAND[0] > _ROD_HOLE_MIN - LAND_CLEARANCE_MIN:
    raise AssertionError("diamond-pin lands do not enter the smallest rod-pin hole")
if FLATS_AF + 0.13 >= LAND_DIA + LAND_BAND[1]:
    raise AssertionError("diamond-pin flats can vanish inside the general band")

# --- Turned 4140 body: all axial sizes from the neck face. ---
NECK_DIA = 3.0
NECK_PLACES = 3
NECK_LENGTH = 4.32  # collar stays below the S4 op 25/27 cutter tip
COLLAR_DIA = 4.5
# The collar seats on the plate top. The neck face sits just under the arm's
# face B so the plate's pads and shimmed hub stand alone set Z: it is a
# backstop, never a second Z support (FixtureCAD option b).
COLLAR_END = 10.20
COLLAR_END_BAND = (0.0, -0.05)
FACE_B_ABOVE_PLATE = 10.22175  # frame-A Z-4.77825 face B over the plate top Z-15
if COLLAR_END + COLLAR_END_BAND[0] > FACE_B_ABOVE_PLATE:
    raise AssertionError("neck face can lift the arm off the profile-fixture pads")
SHANK_DIA = 2.994
SHANK_BAND = (0.004, -0.004)  # 2.990-2.998: bonded slip fit in the plate's 3.0 H7 ream
OVERALL_LENGTH = COLLAR_END + 6.0
REAM_DIA = 2.0
REAM_BAND = (0.010, 0.0)  # the shop's rod reamer, 2.000-2.010
REAM_DEPTH = 8.0
# Rule-12 exception (FixtureCAD ruling): the Ø3.0 neck around the Ø2.0 ream
# leaves a 0.5 wall, under the 1.5 floor. shop-additions section 3 (Pedro's
# binding route) sets both sizes and the neck stays Ø3.0 for the S4 op 25/27
# cutter clearance; the bonded pin fills the bore, so the section is solid in
# service.
RULE12_EXCEPTION = "neck wall over the bonded ream: shop-additions section 3 route, cutter clearance"
# Lands stand LAND_HEIGHT above the neck face: their tip stays under the
# arm's upper strap face even with the neck face at its lowest.
LAND_HEIGHT = 2.378
LAND_HEIGHT_BAND = (0.10, -0.10)
_NECK_DROP_MAX = FACE_B_ABOVE_PLATE - (COLLAR_END + COLLAR_END_BAND[1])
if LAND_HEIGHT + LAND_HEIGHT_BAND[0] - (FACE_B_ABOVE_PLATE - COLLAR_END) > rocker.ARM_THICKNESS:
    raise AssertionError("diamond-pin tip can stand above the rocker strap")
if LAND_HEIGHT + LAND_HEIGHT_BAND[1] - _NECK_DROP_MAX < rocker.ARM_THICKNESS / 2.0:
    raise AssertionError("diamond-pin lands engage less than half the strap")
PIN_ENGAGEMENT = PIN_LENGTH - LAND_HEIGHT
_GENERAL_1PL = 0.8  # title block .X band (the pin length and ream depth print .X)
if PIN_LENGTH + _GENERAL_1PL - (LAND_HEIGHT + LAND_HEIGHT_BAND[1]) >= REAM_DEPTH - _GENERAL_1PL:
    raise AssertionError("diamond pin can bottom in the reamed bore")
# The overall length prints .X; the shank must still clear the bottom of the
# profile fixture's 7.0-deep pin hole so the collar, not the shank end, seats.
_PLATE_HOLE_DEPTH = 7.0  # ch_rocker_arm_tl_profile_fixture_spec.ROD_PIN_HOLE_DEPTH
if OVERALL_LENGTH + _GENERAL_1PL - (COLLAR_END + COLLAR_END_BAND[1]) >= _PLATE_HOLE_DEPTH:
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
    "ReamProfile": {"ReamDia"},
    "Ream": {"ReamDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LandProfile": {"LandDia": LAND_PLACES},
    "FlatsProfile": {"FlatsAF": FLATS_PLACES},
    "Flats": {"LandHeight": 3},
    "NeckProfile": {"NeckDia": NECK_PLACES},
    "Neck": {"NeckLength": 2},
    "CollarProfile": {"CollarDia": 1},
    "Collar": {"CollarEnd": 2},
    "ShankProfile": {"ShankDia": 3},
    "Shank": {"OverallLength": 1},
    "ReamProfile": {"ReamDia": 3},
    "Ream": {"ReamDepth": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked diamond-pin dimension needs authored places")

SURFACE_FINISHES = ()
DRAWING_NOTES = "\n".join(
    (
        BUILT_UP_PERMISSION_NOTE,
        "ROUND LANDS ARE UNTOUCHED GAUGE SURFACE; BORE BOTTOM MAY BE A DRILL POINT.",
        "NECK FACE IS A BACKSTOP JUST BELOW THE ROCKER ARM; THIN WALLS ROUND THE BORE ACCEPTED.",
        "SHANK: CLOSE SLIP FIT, BONDED IN THE ROCKER ARM PROFILE FIXTURE PIN HOLE WITH THE"
        " FLATS SQUARE TO ITS PIVOT-TO-ROD-HOLE LINE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"

_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
_ROD = ("ch_rocker_arm_spec", "ROD_HOLE_SPEC")
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "lands": ExportFeature(
        kind="pin",
        faces=(CylinderFace(LAND_DIA, contains_z_mm=-1.0, tolerance_mm=0.003),),
        requirements=("dia", "width"),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": _AXIS,
            "dia": (limits(LAND_DIA, LAND_PLACES, LAND_BAND), ("LAND_DIA", "LAND_BAND", _ROD)),
            "dia_nominal": (LAND_DIA, ("LAND_DIA",)),
            # width = across the stoned flats (normals +-X, see "flat_pos"/"flat_neg")
            "width": (limits(FLATS_AF, FLATS_PLACES), ("FLATS_AF",)),
            "z_mm": ([-LAND_HEIGHT, 0.0], ("LAND_HEIGHT",)),
            "height": (limits(LAND_HEIGHT, 3, LAND_HEIGHT_BAND),
                       ("LAND_HEIGHT", "LAND_HEIGHT_BAND", ("ch_rocker_arm_spec", "ARM_THICKNESS"))),
        },
        precision={"width": FLATS_PLACES, "height": 3},
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
                limits(COLLAR_END, 2, COLLAR_END_BAND),
                ("COLLAR_END", "COLLAR_END_BAND", "FACE_B_ABOVE_PLATE"),
            ),
        },
        precision={"height": 2},
    ),
    "collar_seat": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), COLLAR_END),),
        requirements=("dia",),
        fields={
            "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": COLLAR_END}, ("COLLAR_END",)),
            "dia": (limits(COLLAR_DIA, 1), ("COLLAR_DIA",)),
        },
        precision={"dia": 1},
    ),
    "shank": ExportFeature(
        kind="boss",
        faces=(CylinderFace(SHANK_DIA, tolerance_mm=0.003),),
        requirements=("dia",),
        fields={
            "at": ([0.0, 0.0, COLLAR_END], ("COLLAR_END",)),
            "axis": _AXIS,
            "dia": (limits(SHANK_DIA, 3, SHANK_BAND), ("SHANK_DIA", "SHANK_BAND")),
            "dia_nominal": (SHANK_DIA, ("SHANK_DIA",)),
            "length": (limits(OVERALL_LENGTH - COLLAR_END, 2), ("OVERALL_LENGTH", "COLLAR_END")),
        },
        precision={"dia": 3, "length": 2},
    ),
}
