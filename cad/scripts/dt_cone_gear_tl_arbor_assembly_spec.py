r"""Pure-data contract for the keyed arbor kit (MHA-DT-03-TL-05), a shop fixture.

Issue #2465: the keyed tooth-cutting arbor MHA-DT-03-TL-03 with its bonded key
MHA-DT-03-TL-06, the three backing collars MHA-DT-03-TL-04 and the 1/4-28 nut
MHA-DT-03-TL-VN-50. The ``_tl_`` stem keeps the kit out of every machine
assembly and BOM (``_buildgraph.is_shop_fixture``); it exists so its parts
belong to a registered assembly (test_part_coverage.py) and carry a fitting
sheet.

Kit frame = the arbor's frame (axis +Z, z = 0 the grip's end face, the
keyseat on +X). The kit shows the 64T setup: the key on the keyseat floor,
its square end on the end radius's centre line; the Ø1.75 collar where the
64T's far face stands; the nut on it. The other two collars wait on the axis
beyond the arbor's end. Every part is fixed (0 DOF).
"""

from __future__ import annotations

import math
import textwrap

import _config
import dt_cone_gear_tl_arbor_collar_spec as collar
import dt_cone_gear_tl_arbor_key_spec as key
import dt_cone_gear_tl_keyed_arbor_spec as arbor
import dt_cone_gear_tl_vn_arbor_nut_spec as nut
import dt_crank_drive_gear_spec as crank
from _printed_tolerance import printed_band_mm

ASM_NAME = "dt-cone-gear-tl-arbor"
INCH = arbor.INCH

ARBOR = arbor.PART_NAME
COLLAR = collar.PART_NAME
KEY = key.PART_NAME
NUT = "dt-cone-gear-tl-vn-arbor-nut"


def member(configuration: str) -> str:
    """The logical BOM family of one collar member."""
    return f"{COLLAR}--{configuration}"


# BOM order = insertion order: the steps cite these item numbers.
BOM_ORDER: tuple[str, ...] = (
    ARBOR,
    *(member(name) for name in collar.CONFIGURATIONS),
    KEY,
    NUT,
)
BOM_ITEMS: dict[str, str] = {stem: str(i + 1) for i, stem in enumerate(BOM_ORDER)}
MEMBER_IDENTITIES: dict[str, tuple[str, str | None]] = {
    member(name): (COLLAR, name) for name in collar.CONFIGURATIONS
}
COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    stem: MEMBER_IDENTITIES.get(stem, (stem, None)) for stem in BOM_ORDER
}
NUMBERS: dict[str, str] = {
    ARBOR: arbor.PART_NUMBER,
    **{member(name): collar.PART_NUMBER for name in collar.CONFIGURATIONS},
    KEY: key.PART_NUMBER,
    NUT: str(_config.parts("dt-cone-gear-tl-vn-arbor-nut")["number"]),
}
# The three collars are members of one tabulated drawing, one sheet each
# (dt_cone_gear_tl_arbor_collar_spec.SHEET_NAMES): each row names its own
# sheet of TL-04, so a row identifies one part drawing (machinist review of
# farm 20261113T071241685Z).
_COLLAR_SHORT = collar.PART_NUMBER.removeprefix("MHA-DT-03-")
if _COLLAR_SHORT == collar.PART_NUMBER:
    raise AssertionError("the collar no longer shares the kit's MHA-DT-03 prefix")
COLLAR_SHEETS: dict[str, int] = {
    name: index + 1 for index, name in enumerate(collar.CONFIGURATIONS)
}
if collar.SHEET_NAMES != tuple(f"COLLAR {name}" for name in collar.CONFIGURATIONS):
    raise AssertionError("TL-04's sheets no longer run in member order")
BOM_DESCRIPTIONS: dict[str, str] = {
    ARBOR: "KEYED CUTTING ARBOR",
    **{
        member(name): (
            f"{collar.CONFIGURATION_DESCRIPTIONS[name]}, "
            f"{_COLLAR_SHORT} SHEET {COLLAR_SHEETS[name]}"
        )
        for name in collar.CONFIGURATIONS
    },
    KEY: "ARBOR KEY, 1/16 SQ X .15",
    NUT: f"HEX NUT {nut.THREAD}, McMASTER-CARR {nut.SKU}",
}

# --- Poses (kit frame, mm; rows are each part's X/Y/Z images) ---------------------
IDENTITY_ROWS = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
KIT_COLLAR = collar.CONFIGURATIONS[0]
if arbor.COLLAR_BY_GEAR[f"{arbor.crank.TEETH}T"] != len(arbor.COLLAR_DIAS) - 1:
    raise AssertionError("the kit's 64T setup no longer takes the largest collar")
BLANK_FACE_Z = arbor.SHOULDER_Z + arbor.KIT_BLANK_FACE
COLLAR_FAR_Z = BLANK_FACE_Z + collar.LENGTH
SPARE_GAP = 0.25 * INCH
SPARE_START_Z = arbor.ARBOR_END_Z + 2.0 * SPARE_GAP
POSITIONS: dict[str, tuple[float, float, float]] = {
    ARBOR: (0.0, 0.0, 0.0),
    member(collar.CONFIGURATIONS[0]): (0.0, 0.0, BLANK_FACE_Z),
    member(collar.CONFIGURATIONS[1]): (0.0, 0.0, SPARE_START_Z),
    member(collar.CONFIGURATIONS[2]): (
        0.0,
        0.0,
        SPARE_START_Z + collar.LENGTH + SPARE_GAP,
    ),
    KEY: (key.FLOOR_OFFSET_MM, 0.0, key.END_Z_MM),
    NUT: (0.0, 0.0, COLLAR_FAR_Z),
}
if COLLAR_FAR_Z + nut.THICKNESS > arbor.ARBOR_END_Z:
    raise AssertionError("the kit's nut runs off the arbor's thread")
if key.END_Z_MM + key.LENGTH >= BLANK_FACE_Z:
    raise AssertionError("the kit's key reaches the collar")

# --- The first cut's index ---------------------------------------------------------
# Both gear families centre a TOOTH, not a gap, on the keyway's centreline
# (+X): the cone gears cut each gap half a pitch either side of it (the core
# gap rotated by pi/N, _cone_gear_native.native_gap_segments; the keyway
# clock in dt_cone_gear_spec), and the 64T's straight inclined space is
# clocked so a tooth centres on it at mid-face on the pitch circle
# (dt_crank_drive_gear_spec.TOOTH_SPACE). The key set on the cutter
# centreline would put the first space on the keyway (Codjiflo review of
# #2664), so the blank is indexed before the first cut: half a pitch, either
# way, on a cone gear. The 64T's cutter plane crosses its axis a quarter face
# from mid-face (TOOTH_SPACE_CROSSING from its chamfered, z = 0, face), where
# its seed space stands TOOTH_SPACE.azimuth_rad counter-clockwise about the
# gear's +z from the keyway; half a pitch would leave its mid-face tooth
# about .55° off the key, over the arbor's setting allowance
# (KEY_SETTING_ALLOWANCE_DEG). Turning the blank counter-clockwise seen from
# the chamfered face carries that space under the cutter. The setup table
# prints every blank's index in degrees, so no row says "half a pitch" beside
# an angle that is not one (machinist review of farm 20261113T071241685Z).
CONE_FIRST_INDEX_PITCHES = 0.5
CRANK_FIRST_INDEX_DEG = round(math.degrees(crank.TOOTH_SPACE.azimuth_rad), 2)
CRANK_FIRST_INDEX_SENSE = "COUNTER-CLOCKWISE SEEN FROM ITS CHAMFERED BORE FACE"


def cone_first_index_deg(teeth: int) -> float:
    """A cone blank's first index, degrees as printed (either way)."""
    return round(CONE_FIRST_INDEX_PITCHES * 360.0 / teeth, 2)


def blank_teeth(tag: str) -> int:
    """Tooth count of a keyed blank's tag (``T030`` or ``64T``)."""
    return int(tag[1:]) if tag.startswith("T") else int(tag.removesuffix("T"))


def blank_collar(tag: str) -> str:
    """The collar member that backs blank ``tag``."""
    (name,) = (
        name
        for name in collar.CONFIGURATIONS
        if tag in collar.GEARS_BY_CONFIGURATION[name]
    )
    return name


# --- The key's clock on the cutter -------------------------------------------------
# The key faces the cutter when its two side faces stand equally either side
# of the cutter's centre plane. Turned by a small angle, both side faces move
# the same way by their radius times the angle, so the two readings part by
# twice that; the least radius a side face shows is the keyseat's edge. The
# reading's band at the shop's indicator row (.001) holds the key's clock well
# inside the arbor's setting allowance, which the index then shares.
KEY_SIDE_READING = 0.001 * INCH
KEY_SIDE_LEVER_MIN = arbor.KEYSEAT_EDGE_DEPTH_MIN + arbor.KEYSEAT_FLOOR_MAX
KEY_CLOCK_FROM_READING_DEG = math.degrees(KEY_SIDE_READING / (2.0 * KEY_SIDE_LEVER_MIN))
if KEY_CLOCK_FROM_READING_DEG >= arbor.KEY_SETTING_ALLOWANCE_DEG / 2.0:
    raise AssertionError("the key's side-face reading spends half the clock allowance")

# --- The blank the views show -------------------------------------------------------
# No blank is in the kit, but the views show the 64T's (this sheet's setup) in
# phantom where it goes (rule 22: order and facing): seated on item 1's
# shoulder under item 2, as MHA-DT-03-TL-00's sheets show the dividing head
# they fit. Its chamfered bore face goes toward item 2: that chamfer's mouth
# can reach past the Ø.50 shoulder at their limits, leaving that face nothing
# to bear on there; the plain face bears flat on the shoulder, and item 2's
# face covers the mouth.
SHOWN_BLANK = arbor.KEYED_GEARS[-1]
SHOWN_BLANK_OD = crank.OUTSIDE_DIA
SHOWN_BLANK_FACE = arbor.KIT_BLANK_FACE
CHAMFER_MOUTH_MAX_DIA = (
    crank.BORE_DIA + max(crank.BORE_DIA_BAND) + 2.0 * crank.BORE_SOUTH_CHAMFER_MAX
)
SHOULDER_MIN_DIA = arbor.STANDOFF_DIA - printed_band_mm(2, unit=arbor.UNIT)
if CHAMFER_MOUTH_MAX_DIA <= SHOULDER_MIN_DIA:
    raise AssertionError("the 64T's chamfered face always bears on the shoulder")
if CHAMFER_MOUTH_MAX_DIA >= collar.OD_BY_CONFIGURATION[KIT_COLLAR]:
    raise AssertionError("item 2 no longer covers the 64T's chamfer mouth")
CHAMFERED_FACE_TOWARD = (
    f"CHAMFERED BORE FACE TOWARD ITEM {BOM_ITEMS[member(KIT_COLLAR)]}"
)
SHOWN_BLANK_LABEL = "\n".join(
    (f"{SHOWN_BLANK.number} {crank.TEETH}T BLANK, NOT IN KIT", CHAMFERED_FACE_TOWARD)
)
_SEAT_TEXT = "Ø" + arbor.inch_text(
    arbor.SEAT_DIA, arbor.DRAWING_PRECISION_BY_NAME["SeatDia"]
)

# --- Sheet words ------------------------------------------------------------------
# The setup table (sheet 1, under the parts list): each blank by drawing
# number and tooth count, the collar item that backs it and its first index.
_TABLE_ROWS: list[str] = []
for _blank in arbor.KEYED_GEARS:
    _teeth = blank_teeth(_blank.tag)
    _item = BOM_ITEMS[member(blank_collar(_blank.tag))]
    if _blank.tag.startswith("T"):
        _TABLE_ROWS.append(
            f"{_blank.number} ({_teeth}T): ITEM {_item}, "
            f"{cone_first_index_deg(_teeth):.2f}° EITHER WAY"
        )
    else:
        _TABLE_ROWS += [
            f"{_blank.number} ({_teeth}T): ITEM {_item}, "
            f"{CRANK_FIRST_INDEX_DEG:.2f}° COUNTER-CLOCKWISE",
            f"   {CRANK_FIRST_INDEX_SENSE.removeprefix('COUNTER-CLOCKWISE ')}, "
            f"WHICH GOES TOWARD ITEM {_item}",
        ]
SETUP_TABLE = "\n".join(
    (
        "SETUP TABLE: EACH BLANK'S COLLAR AND FIRST INDEX",
        f"(THE FIRST INDEX CENTRES A TOOTH, NOT A SPACE, ON ITEM {BOM_ITEMS[KEY]})",
        *_TABLE_ROWS,
    )
)

# Fitting steps (sheet 2, beside the exploded view): one action each, each
# retention or setting followed by its check (rules 22, 23). LOCTITE 638 is
# a consumable: degrease, coat the key (never the keyseat), keep it off the
# seat the blanks slide on, cure before the first cut. Ends and surfaces are
# named by the features the views show, not by a view the package does not
# label (machinist review of farm 20261113T171903293Z).
_K, _A, _N = (BOM_ITEMS[s] for s in (KEY, ARBOR, NUT))
_STEPS: tuple[str, ...] = (
    f"DEGREASE ITEM {_K} AND ITEM {_A}'S KEYSEAT.",
    f"COAT ITEM {_K} WITH {arbor.KEY_BOND}.",
    f"PUSH ITEM {_K} INTO ITEM {_A}'S KEYSEAT AGAINST THE KEYSEAT'S END NEAREST "
    f"ITEM {_A}'S SHOULDER.",
    f"WIPE ALL {arbor.KEY_BOND} OFF ITEM {_A}'S {_SEAT_TEXT} SEAT, LEAVING THE "
    "KEYSEAT FILLED.",
    "LET THE BOND CURE 24 H.",
    f"CHECK: ITEM {_K} DOES NOT MOVE BY HAND.",
    f"SLIDE THE BLANK ONTO ITEM {_A} OVER ITEM {_K}, AGAINST ITEM {_A}'S SHOULDER.",
    f"SLIDE THE BLANK'S COLLAR (SETUP TABLE) ONTO ITEM {_A} AGAINST THE BLANK.",
    f"TIGHTEN ITEM {_N} AGAINST THE COLLAR.",
    "CHECK: THE BLANK DOES NOT TURN OR SLIDE BY HAND.",
    f"WITH ITEM {_A} IN THE DIVIDING HEAD, TURN THE HEAD UNTIL ITEM {_K} FACES "
    "THE CUTTER.",
    f"CHECK WITH A TEST INDICATOR: ITEM {_K}'S TWO SIDE FACES STAND THE SAME "
    "DISTANCE FROM THE CUTTER'S CENTRE PLANE WITHIN "
    f"{arbor.inch_text(KEY_SIDE_READING, 3)}.",
    "TURN THE HEAD BY THE BLANK'S FIRST INDEX (SETUP TABLE).",
)
STEP_WIDTH = 66  # characters a printed line, inside the sheet's right border


def _numbered(steps: tuple[str, ...]) -> tuple[str, ...]:
    lines: list[str] = []
    for number, step in enumerate(steps, start=1):
        head = f"{number}. "
        lines += textwrap.wrap(
            step,
            STEP_WIDTH,
            initial_indent=head,
            subsequent_indent=" " * len(head),
        )
    return tuple(lines)


ASSEMBLY_STEPS = "\n".join(
    ("FITTING STEPS (PARTS LIST AND SETUP TABLE ON SHEET 1)", *_numbered(_STEPS))
)
