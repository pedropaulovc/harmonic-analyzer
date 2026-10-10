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
bracket's faced outer face -- the foot's ear-end face at FOOT_Z0, in the
plane of the ear's inboard face, the face fit-up sets and the hold-down
station is given from) is a rigid copy of it:
TC = (x - PLATE_LENGTH/2, -z, y - (PLATE_HEIGHT + PART_PROUD[c])) for
configuration c: the N bracket's longer foot raises its faced outer face, and
so its Z0, N_RAISE higher than the S one's. The ledge's model frame is this one translated by
(PLATE_LENGTH/2 - ledge width/2, BLOCK_HEIGHT, 0).
"""

from __future__ import annotations

import math

import ch_pivot_bracket_sides as sides
import ch_pivot_bracket_spec as bracket
from _feature_requirements import ExportFeature, limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm

# Bought plate envelope (inventory: 4 x 5 x 3-1/2 in machined cast-iron plate).
PLATE_LENGTH = 127.0  # 5 in, along X
PLATE_WIDTH = 101.6  # 4 in, the base's depth behind the upright face
PLATE_HEIGHT = 88.9  # 3-1/2 in, table to the upright's top edge
BASE_THICK = 12.7
UPRIGHT_THICK = 12.7
CENTRE_X = PLATE_LENGTH / 2.0

# The S4 stack, from the table up. The bracket's foot free end rests on the
# ledge top at LEDGE_TOP_Y, so its faced outer face (FOOT_LEN above that)
# stands PART_PROUD above the plate top; the ledge stands on a 1-2-3 block's
# 2 in side while its screws are tightened. At least 4 mm, not 2: the
# prechips bracket plan's S4 op 10 facing cutter overhangs the plate side at
# the faced outer face and passed only 2.0 over the upright at 2 mm (review
# blocker BR-B1). MHA-CH-008's two configurations differ only in foot length
# (both feet end flush with the support), so one ledge serves both: sized
# for the shorter S foot, it stands the N bracket N_RAISE prouder, which only
# widens the cutter's margin over the upright. The plan touches Z on the part.
# The 4 mm floor holds at the stack's worst case (CodeRabbit on 3d649fd90):
# the ledge at its printed one-place low limit, the S foot at its -0.10, and
# the plate PLATE_HEIGHT_ALLOWANCE taller than nominal. The plate is bought
# and its height is reference, never inspected; 0.25 (about 0.010 in) is an
# assumed allowance for a machined angle plate's height, which also covers
# the stud row's top wall below.
LEDGE_CONFIG = "S"
PART_PROUD_MIN = 4.0
PLATE_HEIGHT_ALLOWANCE = 0.25
BLOCK_HEIGHT = 50.8
_LEDGE_HEIGHT_FLOOR = (
    PLATE_HEIGHT
    + PLATE_HEIGHT_ALLOWANCE
    + PART_PROUD_MIN
    - (sides.FOOT_LEN[LEDGE_CONFIG] - bracket.FOOT_LEN_BAND)
    - BLOCK_HEIGHT
)
_LEDGE_BAND = _LEDGE_HEIGHT_FLOOR - limits(_LEDGE_HEIGHT_FLOOR, 1)[0]
_LEDGE_HEIGHT = math.ceil(round((_LEDGE_HEIGHT_FLOOR + _LEDGE_BAND) * 10.0, 6)) / 10.0
LEDGE_TOP_Y = round(BLOCK_HEIGHT + _LEDGE_HEIGHT, 6)  # 77.7
PART_PROUD = {
    name: LEDGE_TOP_Y + foot_len - PLATE_HEIGHT
    for name, foot_len in sides.FOOT_LEN.items()
}  # S 5.24, N 6.85
N_RAISE = PART_PROUD["N"] - PART_PROUD[LEDGE_CONFIG]  # 1.61
PART_PROUD_WORST = (
    BLOCK_HEIGHT
    + limits(_LEDGE_HEIGHT, 1)[0]
    + sides.FOOT_LEN[LEDGE_CONFIG]
    - bracket.FOOT_LEN_BAND
    - (PLATE_HEIGHT + PLATE_HEIGHT_ALLOWANCE)
)  # 4.09
if (
    min(PART_PROUD.values()) != PART_PROUD[LEDGE_CONFIG]
    or PART_PROUD_WORST < PART_PROUD_MIN
):
    raise AssertionError("the ledge must stand the shorter foot's bracket 4 mm proud at worst case")

# Ledge screws: two #10-24 x 5/8 SHCS (shop-to-shop UNC, fastener policy) at
# 10.5 under the ledge top, 10.0 apart about the plate centre: wide enough that
# the two heads stay clear with the ledge's holes at their worst one-place
# stations (asserted in the ledge spec). The taps are
# spotted through the ledge's own holes with the ledge standing on its block,
# so the screw fit never depends on either part's printed hole stations:
# those ride the title block's general tolerance.
SCREW_THREAD = "#10-24"
TAP_SPEC = HoleSpec("tapped", SCREW_THREAD)
LEDGE_CLEARANCE_SPEC = HoleSpec("drilled_number", "#5")
SCREW_CLEARANCE = blind_cut_dia_mm(LEDGE_CLEARANCE_SPEC) - THREAD_MAJOR_MM[SCREW_THREAD]
SCREW_HEAD_DIA_MAX = 7.925  # 0.312 in, ASME B18.3 #10 socket head cap screw
# ASME B18.3 head-to-body concentricity: 2% of body diameter or 0.006 in TIR,
# whichever is greater (0.006 in governs for #10; Unbrako engineering guide,
# p. 9), so each head may sit up to half that off its shank axis.
SCREW_HEAD_ECCENTRICITY_MAX = 0.006 * 25.4 / 2.0  # 0.0762
# The heads only have to stand apart, never bear on each other; 0.3 is the
# authored daylight margin over contact at the worst printed pitch.
SCREW_HEAD_GAP_MIN = 0.3
SCREW_HALF_PITCH = 5.0
SCREW_BELOW_LEDGE_TOP = 10.5
SCREW_Y = round(LEDGE_TOP_Y - SCREW_BELOW_LEDGE_TOP, 6)  # 67.2
TAP_X = (CENTRE_X - SCREW_HALF_PITCH, CENTRE_X + SCREW_HALF_PITCH)

# Bridge studs: 3/8-16 studs through letter-X clearance holes, 40.0 apart
# about the centre. The bridge bar lies on the foot top in the free run both
# configurations share: from the S ear's face (EAR_T under its faced outer
# face) to the common foot end on the ledge, where the ledge's front face
# carries on flush with the foot top. That run's centre is out of reach (its
# stud hole would break the upright's top wall), so the studs stand at the
# highest one-place row whose hole keeps the 2.0 wall at the exported worst
# case (the row at its .X high limit, the drill at its printed 10.08 +0.10,
# the plate PLATE_HEIGHT_ALLOWANCE short): 80.7, 8.2 under the nominal plate
# top, leaving 2.06 (80.8 would leave 1.96).
# STUD_BELOW_PART_TOP under each configuration's outer face (the prechips S4
# hold's Setup Z, S -13.44, N -15.05). The S ear occupies the top EAR_T = 8
# of the part and stands EAR_TOP_Y - FOOT_H = 27.2 off the foot top, so a bar
# centred on the stud row clears it only up to 2 * (13.44 - EAR_T) = 10.88
# wide.
STUD_DIA = 9.525
STUD_SPEC = HoleSpec("drilled_letter", "X")
STUD_HALF_PITCH = 20.0
STUD_Y = 80.7
STUD_BELOW_PART_TOP = {
    name: PLATE_HEIGHT + proud - STUD_Y for name, proud in PART_PROUD.items()
}
if not bracket.EAR_T < STUD_BELOW_PART_TOP[LEDGE_CONFIG] < sides.FOOT_LEN[LEDGE_CONFIG]:
    raise AssertionError("the bridge studs' line is off the feet's shared free run")
STUD_X = (CENTRE_X - STUD_HALF_PITCH, CENTRE_X + STUD_HALF_PITCH)
STUD_NUT_DIA = 16.5  # 3/8-16 hex nut envelope (inventory bridge row)

# Every station rides the title block's one-place band: the taps are spotted
# from the ledge and the studs float in both the upright and the bridge.
STATION_PLACES = 1
# The letter-X drill prints at two places (10.08) under the DRILLED HOLES row
# (a machinist review called three places over-specified), so the exported
# band is taken off that printed value: [10.08, 10.18], exactly the sheet's.
STUD_DIA_PLACES = 2
STUD_DIA_PRINTED = round(blind_cut_dia_mm(STUD_SPEC), STUD_DIA_PLACES)
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
# The spot note governs the taps (their printed stations are reference); the
# taps' exported note is this same sentence.
_TAP_SPOT_LINES = (
    "CLAMP THE PIVOT BRACKET LEDGE OVER THE TAP LOCATIONS AND SPOT",
    "THE TAPS THROUGH ITS HOLES: THE SPOTS GOVERN THE TAPS.",
)
TAP_SPOT_NOTE = " ".join(_TAP_SPOT_LINES)
DRAWING_NOTES = "\n".join(
    (
        "BOUGHT ANGLE PLATE: ADD THE FOUR HOLES ONLY. SIZES IN ( ) ARE REFERENCE.",
        *_TAP_SPOT_LINES,
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"


def _station(value: float) -> list[float]:
    return limits(value, STATION_PLACES)


# Hole stations: ``station`` is the model X from the plate's left end, ``height``
# the model Y from the table face (the base underside) -- each one dimension.
_INTO_PLATE = ([0.0, 0.0, -1.0], ("__frame__",))
_TAP_DRILL = blind_cut_dia_mm(TAP_SPEC)
_STUD_DRILL = blind_cut_dia_mm(STUD_SPEC)
_DRILLED = (drilled_oversize_mm(), 0.0)
# The Hole Wizard tap callout prints its #25 drill to two places (3.80); that
# printed size, under the DRILLED HOLES row, is the drill's inspected band.
TAP_DRILL_PLACES = 2
TAP_DRILL_PRINTED = round(_TAP_DRILL, TAP_DRILL_PLACES)
# The stud row's wall to the upright's top edge at the bands it exports: the
# row at its one-place high limit, the hole at its printed drill's high limit,
# the plate PLATE_HEIGHT_ALLOWANCE short (Codex P2 on cc1d22b66: the 81.5 row
# left 1.51; CodeRabbit on 3d649fd90: the bought plate's height is unprinted).
STUD_TOP_WALL_MIN = (
    PLATE_HEIGHT
    - PLATE_HEIGHT_ALLOWANCE
    - _station(STUD_Y)[1]
    - limits(STUD_DIA_PRINTED, STUD_DIA_PLACES, _DRILLED)[1] / 2.0
)
if STUD_TOP_WALL_MIN < 2.0:
    raise AssertionError(
        f"the stud holes leave {STUD_TOP_WALL_MIN:.2f} under the upright's top"
        " edge at the exported worst case, under the 2.0 wall"
    )
# The bridge bar (the inventory clamping kit's 1/2 in bar, centred on the
# stud row) lies on the foot top and the ledge's front face, over the two
# ledge screw heads that stand off that face between the studs. Its lower
# edge must clear the heads with the stud row at its one-place low limit,
# the ledge holes (stationed from the ledge bottom on its block) at their
# high limit and each head at its eccentricity (local Codex review of
# 86bd09c32: the 9.0 screw row overlapped the bar by 0.7).
BRIDGE_WIDTH = 12.7
BRIDGE_HEAD_GAP_MIN = 0.3
BRIDGE_HEAD_GAP = (
    _station(STUD_Y)[0]
    - BRIDGE_WIDTH / 2.0
    - (BLOCK_HEIGHT + _station(round(SCREW_Y - BLOCK_HEIGHT, 6))[1])
    - SCREW_HEAD_DIA_MAX / 2.0
    - SCREW_HEAD_ECCENTRICITY_MAX
)
if BRIDGE_HEAD_GAP < BRIDGE_HEAD_GAP_MIN:
    raise AssertionError(
        f"the bridge bar clears the ledge screw heads by {BRIDGE_HEAD_GAP:.2f}"
        " at worst case, under the 0.3 daylight margin"
    )
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
                    ("ch_pivot_bracket_sides", "FOOT_LEN"),
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
# Each tap's printed stations are reference (the spot note governs), so they
# export as nominals with no band. The tap is THRU: its one drilled cylinder
# carries the thread, the spot note and the printed drill band together.
for _side, _x in (("left", TAP_X[0]), ("right", TAP_X[1])):
    EXPORT_FEATURES[f"ledge_tap_{_side}"] = ExportFeature(
        kind="hole",
        faces=(CylinderFace(_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "note", "dia"),
        fields={
            "at": ([_x, SCREW_Y, 0.0], ("TAP_X", "SCREW_Y")),
            "axis": _INTO_PLATE,
            "thread": (f"{SCREW_THREAD} UNC-{TAP_SPEC.thread_class}", ("TAP_SPEC", "SCREW_THREAD")),
            "tap_drill_mm": (_TAP_DRILL, ("TAP_SPEC",)),
            "dia": (
                limits(TAP_DRILL_PRINTED, TAP_DRILL_PLACES, _DRILLED),
                ("TAP_SPEC", "TAP_DRILL_PRINTED", "TAP_DRILL_PLACES"),
            ),
            "nominal_dia": (TAP_DRILL_PRINTED, ("TAP_DRILL_PRINTED",)),
            "thru": (True, ("TAP_SPEC",)),
            "station_nominal": (_x, ("TAP_X",)),
            "height_nominal": (SCREW_Y, ("SCREW_Y",)),
            "height_from": ("table_face", ("__frame__",)),
            "note": (TAP_SPOT_NOTE, ("TAP_SPOT_NOTE", "LEDGE_CLEARANCE_SPEC")),
        },
        precision={"dia": TAP_DRILL_PLACES},
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
            "dia": (
                limits(STUD_DIA_PRINTED, STUD_DIA_PLACES, _DRILLED),
                ("STUD_SPEC", "STUD_DIA_PRINTED", "STUD_DIA_PLACES"),
            ),
            "nominal_dia": (STUD_DIA_PRINTED, ("STUD_DIA_PRINTED",)),
            "thru": (True, ("STUD_SPEC",)),
            "station": (_station(_x), ("STUD_X", "STATION_PLACES")),
            "station_nominal": (_x, ("STUD_X",)),
            "height": (_station(STUD_Y), ("STUD_Y", "STATION_PLACES")),
            "height_nominal": (STUD_Y, ("STUD_Y",)),
            "height_from": ("table_face", ("__frame__",)),
        },
        precision={"dia": STUD_DIA_PLACES, "station": STATION_PLACES, "height": STATION_PLACES},
    )
