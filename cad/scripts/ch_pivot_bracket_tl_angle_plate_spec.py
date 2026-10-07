r"""Pure-data contract for the pivot bracket's reworked angle plate (MHA-CH-008-TL-02).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). A bought
4 x 5 x 3-1/2 in cast-iron angle plate holds the rocker pivot bracket for its
S4 setup (prechips bracket plan S4 hold): the bracket's finished seat face
lies flat on the upright's front face, its foot free end rests on the
shop-made ledge (MHA-CH-008-TL-01) screwed to the upright, and the clamping
kit's bridge presses the foot toward the plate on two 3/8-16 studs through
the upright. The plate is modelled at its bought envelope (slots omitted);
the shop adds four holes only: two tapped holes for the ledge screws and two
stud clearance holes for the bridge.

Frame (model, mm): origin at the plate's left end, on the base's underside
(the table plane) and in the upright's front face. +X runs along the plate,
+Y up from the table, +Z out of the upright's front face toward the part.
The bought plate is X 0..PLATE_LENGTH, the base Y 0..BASE_THICK by
Z -PLATE_WIDTH..0 and the upright Y BASE_THICK..PLATE_HEIGHT by
Z -UPRIGHT_THICK..0. The inventory's fixture frame (bracket plan setup frame
TC: front upright face Y=0, plate behind the part on +Y, Z up with Z0 the
bracket's faced outer face) is a rigid copy of it:
TC = (x - PLATE_LENGTH/2, -z, y - (PLATE_HEIGHT + PART_PROUD)).
The ledge's model frame is this one translated by
(PLATE_LENGTH/2 - ledge width/2, BLOCK_HEIGHT, 0).
"""

from __future__ import annotations

import ch_pivot_bracket_spec as bracket
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm

# Bought plate envelope (inventory: 4 x 5 x 3-1/2 in machined cast-iron plate).
PLATE_LENGTH = 127.0  # 5 in, along X
PLATE_WIDTH = 101.6  # 4 in, the base's depth behind the upright face
PLATE_HEIGHT = 88.9  # 3-1/2 in, table to the upright's top edge
BASE_THICK = 12.7
UPRIGHT_THICK = 12.7
CENTRE_X = PLATE_LENGTH / 2.0

# The S4 stack, from the table up. The bracket's faced outer face stands
# PART_PROUD above the plate top, so its foot free end (FOOT_LEN below that
# face) lands at LEDGE_TOP_Y; the ledge stands on a 1-2-3 block's 2 in side
# while its screws are tightened.
PART_PROUD = 2.0
BLOCK_HEIGHT = 50.8
LEDGE_TOP_Y = PLATE_HEIGHT + PART_PROUD - bracket.FOOT_LEN  # 66.7

# Ledge screws: two #10-24 x 5/8 SHCS (shop-to-shop UNC, fastener policy) at
# 8.0 under the ledge top, 10.0 apart about the plate centre. The taps are
# spotted through the ledge's own holes with the ledge standing on its block,
# so the screw fit never depends on either part's printed hole stations:
# those ride the title block's general tolerance.
SCREW_THREAD = "#10-24"
TAP_SPEC = HoleSpec("tapped", SCREW_THREAD)
LEDGE_CLEARANCE_SPEC = HoleSpec("drilled_number", "#5")
SCREW_CLEARANCE = blind_cut_dia_mm(LEDGE_CLEARANCE_SPEC) - THREAD_MAJOR_MM[SCREW_THREAD]
SCREW_HALF_PITCH = 5.0
SCREW_BELOW_LEDGE_TOP = 8.0
SCREW_Y = LEDGE_TOP_Y - SCREW_BELOW_LEDGE_TOP  # 58.7
TAP_X = (CENTRE_X - SCREW_HALF_PITCH, CENTRE_X + SCREW_HALF_PITCH)

# Bridge studs: 3/8-16 studs through letter-X clearance holes, 40.0 apart
# about the centre, 14.0 under the plate top (the bridge bar clears the foot).
STUD_DIA = 9.525
STUD_SPEC = HoleSpec("drilled_letter", "X")
STUD_HALF_PITCH = 20.0
STUD_Y = PLATE_HEIGHT - 14.0  # 74.9
STUD_X = (CENTRE_X - STUD_HALF_PITCH, CENTRE_X + STUD_HALF_PITCH)
STUD_NUT_DIA = 16.5  # 3/8-16 hex nut envelope (inventory bridge row)

# Every station rides the title block's one-place band: the taps are spotted
# from the ledge and the studs float in both the upright and the bridge.
STATION_PLACES = 1
# Every hole lies in the upright, clear of the base and of the top edge.
for _y, _spec in ((SCREW_Y, TAP_SPEC), (STUD_Y, STUD_SPEC)):
    _r = (blind_cut_dia_mm(_spec) + drilled_oversize_mm()) / 2.0
    if not BASE_THICK + 2.0 <= _y - _r and _y + _r <= PLATE_HEIGHT - 2.0:
        raise AssertionError("an upright hole leaves under 2.0 of wall")
# The through taps get the upright's full thickness: at least one and a half
# major diameters of full thread for the #10 screws.
if UPRIGHT_THICK < 1.5 * THREAD_MAJOR_MM[SCREW_THREAD]:
    raise AssertionError("the upright is too thin for the ledge screws' thread")

# The bought envelope prints as reference: its four section sizes in the side
# view, its length under the face. The tap stations are reference too: the
# spots taken through the seated ledge govern them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"Width", "Height", "BaseThick", "UprightThick"},
    "Plate": {"Length"},
    "LedgeTaps": {"Tap1X", "Tap2X", "Tap1Y"},
    "StudHoles": {"Stud1X", "Stud2X", "Stud1Y"},
}
REFERENCE_DIMENSIONS = (
    DRAWING_DIMENSIONS["PlateProfile"] | DRAWING_DIMENSIONS["Plate"] | DRAWING_DIMENSIONS["LedgeTaps"]
)
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: dict.fromkeys(names, STATION_PLACES) for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked angle-plate dimension needs authored places")

SURFACE_FINISHES = ()
DRAWING_NOTES = "\n".join(
    (
        "BOUGHT ANGLE PLATE: ADD THE FOUR HOLES ONLY. SIZES IN ( ) ARE REFERENCE.",
        "CLAMP THE PIVOT BRACKET LEDGE OVER THE TAP LOCATIONS AND SPOT",
        "THE TAPS THROUGH ITS HOLES: THE SPOTS GOVERN THE TAPS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"


def _station(value: float) -> list[float]:
    return limits(value, STATION_PLACES)


# Hole stations: ``station`` is the model X from the plate's left end, ``height``
# the model Y from the table face (the base underside) -- each one dimension.
_INTO_PLATE = ([0.0, 0.0, -1.0], ("__frame__",))
_TAP_DRILL = blind_cut_dia_mm(TAP_SPEC)
_STUD_DRILL = blind_cut_dia_mm(STUD_SPEC)
_DRILLED = (drilled_oversize_mm(), 0.0)
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "seat_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), 0.0),),
        requirements=(),
        fields={
            "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
            # Where the bracket's seat face lies on it: the foot's width about
            # the centre, from the ledge top to the plate's top edge.
            "bounds": (
                {
                    "x": [CENTRE_X - bracket.FOOT_W / 2.0, CENTRE_X + bracket.FOOT_W / 2.0],
                    "y": [LEDGE_TOP_Y, PLATE_HEIGHT],
                },
                (
                    "CENTRE_X",
                    "LEDGE_TOP_Y",
                    "PLATE_HEIGHT",
                    ("ch_pivot_bracket_spec", "FOOT_W"),
                    ("ch_pivot_bracket_spec", "FOOT_LEN"),
                ),
            ),
        },
    ),
    "table_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
        requirements=(),
        fields={
            "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        },
    ),
}
for _side, _x in (("left", TAP_X[0]), ("right", TAP_X[1])):
    EXPORT_FEATURES[f"ledge_tap_{_side}"] = ExportFeature(
        kind="hole",
        faces=(CylinderFace(_TAP_DRILL, contains_x_mm=_x),),
        requirements=("station", "height"),
        fields={
            "at": ([_x, SCREW_Y, 0.0], ("TAP_X", "SCREW_Y")),
            "axis": _INTO_PLATE,
            "thread": (f"{SCREW_THREAD} UNC-{TAP_SPEC.thread_class}", ("TAP_SPEC", "SCREW_THREAD")),
            "tap_drill_mm": (_TAP_DRILL, ("TAP_SPEC",)),
            "thru": (True, ("TAP_SPEC",)),
            "station": (_station(_x), ("TAP_X", "STATION_PLACES")),
            "station_nominal": (_x, ("TAP_X",)),
            "height": (
                _station(SCREW_Y),
                ("SCREW_Y", "STATION_PLACES", ("ch_pivot_bracket_spec", "FOOT_LEN")),
            ),
            "height_nominal": (SCREW_Y, ("SCREW_Y",)),
            "height_from": ("table_face", ("__frame__",)),
        },
        precision={"station": STATION_PLACES, "height": STATION_PLACES},
    )
for _side, _x in (("left", STUD_X[0]), ("right", STUD_X[1])):
    EXPORT_FEATURES[f"stud_hole_{_side}"] = ExportFeature(
        kind="hole",
        faces=(CylinderFace(_STUD_DRILL, contains_x_mm=_x),),
        requirements=("dia", "station", "height"),
        fields={
            "at": ([_x, STUD_Y, 0.0], ("STUD_X", "STUD_Y")),
            "axis": _INTO_PLATE,
            "drill": (STUD_SPEC.size, ("STUD_SPEC",)),
            "dia": (limits(_STUD_DRILL, 2, _DRILLED), ("STUD_SPEC", "STUD_DIA")),
            "nominal_dia": (_STUD_DRILL, ("STUD_SPEC",)),
            "thru": (True, ("STUD_SPEC",)),
            "station": (_station(_x), ("STUD_X", "STATION_PLACES")),
            "station_nominal": (_x, ("STUD_X",)),
            "height": (_station(STUD_Y), ("STUD_Y", "STATION_PLACES")),
            "height_nominal": (STUD_Y, ("STUD_Y",)),
            "height_from": ("table_face", ("__frame__",)),
        },
        precision={"dia": 2, "station": STATION_PLACES, "height": STATION_PLACES},
    )
