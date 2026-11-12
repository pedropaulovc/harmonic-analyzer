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

import _config
import dt_cone_gear_tl_arbor_collar_spec as collar
import dt_cone_gear_tl_arbor_key_spec as key
import dt_cone_gear_tl_keyed_arbor_spec as arbor
import dt_cone_gear_tl_vn_arbor_nut_spec as nut

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
BOM_DESCRIPTIONS: dict[str, str] = {
    ARBOR: "KEYED CUTTING ARBOR",
    **{
        member(name): collar.CONFIGURATION_DESCRIPTIONS[name]
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

# --- Sheet ----------------------------------------------------------------------
# The two settings the sheet states as reference dimensions, on one hidden
# assembly sketch on the Right Plane (the side view's plane): the blank's
# near face from the jaw step (the 3-jaw's stop, the #2 cutter's run-out) and
# the seat's length the blank engages.
SETTINGS_SKETCH = "ArborSettings"
STANDOFF_DIMENSION = "BlankStandoff"
SEAT_DIMENSION = "SeatEngagement"
SETTINGS: dict[str, tuple[float, float, float]] = {
    # name: (radius below the axis, start z, end z), mm
    STANDOFF_DIMENSION: (arbor.STANDOFF_DIA / 2.0, arbor.GRIP_LENGTH, arbor.SHOULDER_Z),
    SEAT_DIMENSION: (arbor.SEAT_DIA / 2.0, arbor.SHOULDER_Z, arbor.SEAT_END_Z),
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    SETTINGS_SKETCH: {STANDOFF_DIMENSION, SEAT_DIMENSION}
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    SETTINGS_SKETCH: {STANDOFF_DIMENSION: 2, SEAT_DIMENSION: 2}
}
DIMENSION_CALLOUTS: dict[str, str] = {
    STANDOFF_DIMENSION: "JAW STEP TO BLANK FACE",
    SEAT_DIMENSION: "SEAT",
}


def _gear_span(configuration: str) -> str:
    tags = collar.GEARS_BY_CONFIGURATION[configuration]
    cones = [int(t[1:]) for t in tags if t.startswith("T")]
    text = f"{cones[0]}T-{cones[-1]}T"
    if any(not t.startswith("T") for t in tags):
        text += f" AND {arbor.crank.TEETH}T"
    return text


_COLLAR_ITEMS = "; ".join(
    f"ITEM {BOM_ITEMS[member(name)]} {_gear_span(name)}"
    for name in collar.CONFIGURATIONS
)
# Three fitting steps (rule 22, one action each); the key's clock is the
# last, the setting every cut depends on. LOCTITE 638 is a consumable.
ASSEMBLY_STEPS = "\n".join(
    (
        "FITTING STEPS",
        f"1. BOND ITEM {BOM_ITEMS[KEY]} IN ITEM {BOM_ITEMS[ARBOR]}'S KEYSEAT WITH "
        "LOCTITE 638, ITS SQUARE",
        "   END ON THE END RADIUS'S CENTRE; LET IT CURE.",
        f"2. SLIDE THE BLANK ON THE SEAT OVER ITEM {BOM_ITEMS[KEY]} TO THE SHOULDER; "
        "FIT ITS",
        f"   COLLAR ({_COLLAR_ITEMS})",
        f"   AND ITEM {BOM_ITEMS[NUT]}; TIGHTEN.",
        f"3. ITEM {BOM_ITEMS[KEY]} CARRIES THE BLANK'S CLOCK: SET IT ON THE CUTTER "
        "CENTRELINE",
        "   BEFORE THE FIRST CUT.",
    )
)
if sum(1 for line in ASSEMBLY_STEPS.splitlines() if line[:2].rstrip(".").isdigit()) > 3:
    raise AssertionError("at most three fitting steps")
