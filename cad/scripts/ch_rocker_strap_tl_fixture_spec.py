r"""Pure-data contract for the rocker-strap sub-plate fixture (MHA-CH-13-TL-00).

PURE DATA, no SolidWorks/COM and no drawing imports. A shop fixture (owner
ask 2026-11-17): the sub-plate MHA-CH-13-TL-01 with its fence and end stop
milled integral, the hub plug MHA-CH-13-TL-02 in its counterbore, the hub
washer MHA-CH-13-TL-VN-52 (a #10 SAE washer picked by measurement from the
owned pack), four Mitee-Bite Pitbull 26000 edge clamps MHA-CH-13-TL-VN-50
(each with its supplied #4-40 screw) in their pockets and the #10-32 x 5/8
button-head hub screw MHA-CH-13-TL-VN-51 (owner rulings 2026-11-23:
"change the screw to #10-32 ... The washer is then a #10 SAE washer you
already own ... The made washer, its drawing and its lathe traveler are
deleted."; "Pick one washer from the pack of 100 by measurement and keep
it with the fixture"; reversing 2026-11-17's "Use a 1/4-20 hub screw").
The ``_tl_`` stem keeps the kit out of every machine assembly and BOM
(``_buildgraph.is_shop_fixture``). The strap blank and its tape are not kit
items; the plan view shows the blank in phantom where it lies.

Kit frame = the plate's frame = the strap programs' G54: X0 the end-stop
face, Y0 the fence face, Z0 the plate top, +Z up. The kit shows the outline
setup (the strap plan's RS04 stage): the plug in the counterbore, the washer
on the blank's nominal top and the hub screw seated on it, every clamp in
its pocket, its heel on the pocket's back wall. Every part is fixed (0 DOF).

The shop TOMLs and the strap plan are never read here (they are not COM-leaf
inputs): the clamp torque below mirrors the strap plan's
``clamp_torque_in_lb``, and ``test_ch_rocker_strap_tl_fixture_assembly``
asserts the two agree.
"""

from __future__ import annotations

import textwrap

import _config
import ch_rocker_strap_tl_hub_plug_spec as plug
import ch_rocker_strap_tl_sub_plate_spec as plate
import ch_rocker_strap_tl_vn_edge_clamp_spec as clamp
import ch_rocker_strap_tl_vn_hub_washer_spec as washer
import _mcmaster_91255a267 as hub_screw
from _assembly_contract import assembly_contract

ASM_NAME = "ch-rocker-strap-tl-fixture"
# Literal, so only this kit's contract re-keys the sheets that read it.
CONTRACT = assembly_contract("ch-rocker-strap-tl-fixture")
DRAWING_NUMBER = CONTRACT.number
INCH = 25.4

PLATE = "ch-rocker-strap-tl-sub-plate"
PLUG = "ch-rocker-strap-tl-hub-plug"
WASHER = "ch-rocker-strap-tl-vn-hub-washer"
CLAMP = "ch-rocker-strap-tl-vn-edge-clamp"
SCREW = "ch-rocker-strap-tl-vn-hub-screw"

# BOM order = insertion order: the steps and the screw schedule cite these
# item numbers.
BOM_ORDER: tuple[str, ...] = (PLATE, PLUG, WASHER, CLAMP, SCREW)
BOM_ITEMS: dict[str, str] = {stem: str(i + 1) for i, stem in enumerate(BOM_ORDER)}
COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    stem: (stem, None) for stem in BOM_ORDER
}
QUANTITIES: dict[str, int] = {PLATE: 1, PLUG: 1, WASHER: 1, CLAMP: 4, SCREW: 1}

# --- The blank the kit holds (not a kit item) ----------------------------------
# The strap plan's tape stack under the blank (blue painter's tape on both
# faces, CA glue between: tape_stack_mm 0.28 nominal, every bond miked into
# tape_stack_min_mm..tape_stack_max_mm); the blank at the finished strap
# thickness's nominal (ch_rocker_arm_spec.ARM_THICKNESS, .098), the washer on
# its top. All mirrored, so the kit does not re-key on the rocker arm's spec;
# test_ch_rocker_strap_tl_fixture_assembly asserts them.
TAPE = 0.28
TAPE_MIN = 0.23
TAPE_MAX = 0.33
STRAP_THICKNESS = 2.4892
BLANK_TOP_Z = TAPE + STRAP_THICKNESS

# --- The hub screw (MHA-CH-13-TL-VN-51; owner ruling 2026-11-23: #10-32) -------
HUB_SCREW_THREAD = "#10-32 UNF X 5/8"
(HUB_SCREW_SKU,) = _config.parts("ch-rocker-strap-tl-vn-hub-screw")["supplier_skus"]
HUB_SCREW_HEAD_DIA = hub_screw.HEAD_DIA
HUB_SCREW_HEAD_HEIGHT = hub_screw.HEAD_HEIGHT
HUB_SCREW_LENGTH = hub_screw.LENGTH
BLANK_LENGTH = 12.0 * INCH
BLANK_WIDTH = 1.5 * INCH

# --- Poses (kit frame, mm; rows are each part's X/Y/Z images) ------------------
IDENTITY_ROWS = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
HUB = (plate.HUB_X, plate.HUB_Y)
PLUG_POSITION = (*HUB, plate.COUNTERBORE_FLOOR_Z)
WASHER_POSITION = (*HUB, BLANK_TOP_Z)
SCREW_POSITION = (*HUB, BLANK_TOP_Z + washer.THICKNESS)
# The clamp's part frame: z = 0 its seat on the pocket floor, its screw axis
# on part z, its knife toward +Y: seated with its heel on the pocket's back
# wall its knife reaches the blank's edge.
CLAMP_POSITIONS: tuple[tuple[float, float, float], ...] = tuple(
    (station, plate.CLAMP_SCREW_Y, plate.POCKET_FLOOR_Z)
    for station in plate.CLAMP_STATIONS
)
if len(CLAMP_POSITIONS) != QUANTITIES[CLAMP]:
    raise AssertionError("one edge clamp per clamp station")
for _station in CLAMP_POSITIONS:
    if abs(_station[1] + clamp.HEEL_Y - plate.POCKET_BACK_WALL_Y) > 1e-9:
        raise AssertionError("an edge clamp's heel is off its pocket's back wall")
    if abs(_station[1] + clamp.KNIFE_Y - plate.BLANK_EDGE_Y) > 1e-9:
        raise AssertionError("an edge clamp's knife misses the blank's edge")
if plate.COUNTERBORE_FLOOR_Z + plug.OVERALL_LENGTH >= TAPE_MIN + STRAP_THICKNESS:
    raise AssertionError("the plug's pilot stands above the blank's top")
if plate.COUNTERBORE_FLOOR_Z + plug.OVERALL_LENGTH <= TAPE_MAX:
    raise AssertionError("the plug's pilot does not reach into the blank's hub hole")

# --- Sheet words ------------------------------------------------------------
# Torque: the strap plan's clamp_torque_in_lb (6, 0.5 ft-lb), reduced from the
# maker's 1.3 ft-lb maximum so the edge clamps do not bow the thin blank.
CLAMP_TORQUE_FT_LB = 0.5
if CLAMP_TORQUE_FT_LB >= clamp.MAX_TORQUE_FT_LB:
    raise AssertionError("the clamp torque reaches the maker's maximum")
# Printed in in-lb, the unit a torque screwdriver for a #4-40 reads.
CLAMP_TORQUE_IN_LB = CLAMP_TORQUE_FT_LB * 12.0
# The fence is indicated parallel to the table's X travel with a test
# indicator in the spindle (rule 22: a setting finer than .XXX names its
# indicator), over the fence face between its notches.
FENCE_READING_IN = 0.001

SCREW_TABLE_TITLE = "SCREW SCHEDULE"
SCREW_TABLE_HEADER = ("ITEM", "NUMBER", "DESCRIPTION", "QTY", "THREAD", "TORQUE")
BLANK_LABEL = "MHA-CH-13 BLANK, NOT PART OF THE FIXTURE"
# The hold the strap traveler bonds each blank with for its outline
# (shop-equipment consumables.hold-painters-tape-ca; plan tape_stack_mm),
# named without a figure: the stack's band is the traveler's check.
TAPE_NAME = "BLUE TAPE, CA GLUE, BLUE TAPE"

STEP_WIDTH = 62  # characters a printed line, inside the sheet's right border


def numbered(steps: tuple[str, ...], start: int = 1) -> tuple[str, ...]:
    """Each step wrapped under its number, the number's indent kept."""
    lines: list[str] = []
    for number, step in enumerate(steps, start=start):
        head = f"{number}. "
        lines += textwrap.wrap(
            step, STEP_WIDTH, initial_indent=head, subsequent_indent=" " * len(head)
        )
    return tuple(lines)


# --- The parts list and the screw schedule ------------------------------------
# Literal rows, so the sheet re-keys only on its own vendor parts.
CLAMP_NUMBER = str(_config.parts("ch-rocker-strap-tl-vn-edge-clamp")["number"])
SCREW_NUMBER = str(_config.parts("ch-rocker-strap-tl-vn-hub-screw")["number"])
(CLAMP_SKU,) = _config.parts("ch-rocker-strap-tl-vn-edge-clamp")["supplier_skus"]
(WASHER_SKU,) = _config.parts("ch-rocker-strap-tl-vn-hub-washer")["supplier_skus"]
if WASHER_SKU != washer.SKU:
    raise AssertionError("the washer's registry row and its catalogue disagree")
# The washer's selection (owner ruling 2026-11-23: "OD .505 or under and
# bore .220 or under"), checked once on sheet 1: the OD by micrometer, the
# bore by the pin gauge of its limit, which must not enter (so the bore is
# under the .220 the reach is worked at). The two limits are typed into the
# step, as the clamp torque and the fence reading are: they select a bought
# part at fitting, and no model dimension can carry a selection limit (the
# washer is modelled at its catalogue nominal).
WASHER_BORE_NO_GO = washer.SELECT_BORE_MAX
WASHER_OD_TEXT = washer.SELECT_OD_TEXT
WASHER_BORE_NO_GO_TEXT = washer.inch_text(WASHER_BORE_NO_GO, 3)
BOM_DESCRIPTIONS: dict[str, str] = {
    PLATE: "STRAP SUB-PLATE, FENCE AND END STOP INTEGRAL",
    PLUG: "HUB PLUG",
    WASHER: f"SAE WASHER NO. 10, McMASTER-CARR {WASHER_SKU}, SELECTED",
    CLAMP: f"EDGE CLAMP, MITEE-BITE {CLAMP_SKU}, WITH ITS SCREW",
    SCREW: f"BUTTON HEAD SCREW {HUB_SCREW_THREAD}, McMASTER-CARR {HUB_SCREW_SKU}",
}
# One row per screw: the screw schedule the steps cite. The clamp's screw is
# supplied with it (item 4 is the clamp with its screw).
SCREW_TABLE_ROWS: tuple[tuple[str, ...], ...] = (
    (
        BOM_ITEMS[CLAMP],
        CLAMP_NUMBER,
        "CLAMP SCREW",
        str(QUANTITIES[CLAMP]),
        clamp.SCREW_THREAD.upper(),
        f"{CLAMP_TORQUE_IN_LB:g} IN-LB",
    ),
    (
        BOM_ITEMS[SCREW],
        SCREW_NUMBER,
        "HUB SCREW",
        str(QUANTITIES[SCREW]),
        HUB_SCREW_THREAD,
        "SNUG",
    ),
)

# --- Fitting steps -------------------------------------------------------------
# One action each, each check followed by its remedy (rules 22, 23). Sheet
# 1: the fixture into the vise once, the fence indicated along X, the work
# zero, the clamps. Sheet 2: each blank, in the order of the MHA-CH-13
# traveler's setups (plan.toml: setup 1 saws, setups 2-4 face and make the
# hub hole under the edge clamps, setup 5 cuts the outline on tape over the
# plug, screwed down through the washer). Parallels mirror the strap
# plan's vise_parallel_height (1 in).
_P, _G, _W, _C, _S = (BOM_ITEMS[s] for s in BOM_ORDER)
_READING = f"{FENCE_READING_IN:.3f}".removeprefix("0")
_STEPS: tuple[str, ...] = (
    f"SET ITEM {_P} ON 1.00 IN PARALLELS UNDER ITS LONG EDGES IN THE 6 IN VISE, "
    "CENTRED, THE FENCE TOWARD THE FIXED JAW.",
    f"TIGHTEN THE VISE ON ITEM {_P}'S LONG EDGES.",
    "SWEEP THE FENCE FACE ALONG X BETWEEN THE FENCE NOTCHES WITH A TEST "
    "INDICATOR IN THE SPINDLE.",
    f"CHECK: THE INDICATOR READS WITHIN {_READING}.",
)
_CHECK_STEP = len(_STEPS)
_STEPS += (
    f"IF STEP {_CHECK_STEP} FAILS, LOOSEN THE VISE, TAP ITEM {_P} ROUND AND "
    "REPEAT FROM STEP 2.",
    "SET THE WORK ZERO: X0 ON THE END-STOP FACE, Y0 ON THE FENCE FACE, Z0 ON "
    "THE PLATE TOP.",
    f"SET EACH ITEM {_C} IN ITS POCKET, CLAMPING EDGE TOWARD THE FENCE, BACK "
    "FACE ON THE POCKET WALL FARTHEST FROM THE FENCE.",
    f"RUN EACH ITEM {_C} SCREW IN FINGER TIGHT.",
    f"CHECK: ITEM {_W} MIKES {WASHER_OD_TEXT} OR UNDER ON ITS OUTSIDE DIAMETER AND "
    f"A {WASHER_BORE_NO_GO_TEXT} PIN GAUGE DOES NOT ENTER ITS BORE.",
)
_WASHER_CHECK = len(_STEPS)
_STEPS += (
    f"IF STEP {_WASHER_CHECK} FAILS, TAKE ANOTHER ITEM {_W} FROM ITS PACK AND "
    f"REPEAT STEP {_WASHER_CHECK}.",
    f"MARK ITEM {_W}: IT STAYS WITH THE FIXTURE.",
)
ASSEMBLY_STEPS = "\n".join(
    ("FITTING STEPS, ONCE (EACH BLANK: SHEET 2)", *numbered(_STEPS))
)

_CLAMPED: tuple[str, ...] = (
    "SEAT THE BLANK ON THE PLATE AGAINST FENCE AND END STOP.",
    f"TIGHTEN EVERY ITEM {_C} SCREW TO {CLAMP_TORQUE_IN_LB:g} IN-LB (SCREW SCHEDULE).",
    "CHECK: THE BLANK DOES NOT MOVE BY HAND.",
)
_FIRST = len(_STEPS) + 1
_CLAMP_CHECK = _FIRST + len(_CLAMPED) - 1
_CLAMPED += (
    f"IF STEP {_CLAMP_CHECK} FAILS, RESEAT THE BLANK; REPEAT FROM STEP {_FIRST}.",
)
# The bond steps follow the traveler's (cad/process/ch_rocker_strap/plan.toml,
# setup 5; owner rulings 2026-11-23: blue painter's tape on both faces, CA
# glue between, proved by the stack and a hand push test, no pull test),
# terse and one action each: the traveler carries the stack's band and
# arithmetic. Pressing and the 5 minute wait stay one step (the 25-line
# limit above the exploded clamps), the wait being no action.
_TAPE_FIRST = _CLAMP_CHECK + 2
_TAPED: tuple[str, ...] = (
    f"BACK EVERY ITEM {_C} OFF AND LIFT THE BLANK OFF THE PLATE.",
    "WIPE PLATE TOP AND BLANK UNDERSIDE WITH ISOPROPYL ALCOHOL.",
    "TAPE THE PLATE: 2 STRIPS ALONG X FROM THE FENCE, BUTTED, NOT "
    "OVERLAPPED; CUT AWAY AT THE COUNTERBORE.",
    "TAPE THE UNDERSIDE: 2 STRIPS BUTTED AT MID-WIDTH, TRIMMED FLUSH "
    "AND CLEAR OF THE HUB HOLE.",
    "BURNISH BOTH TAPES DOWN HARD, EDGES INCLUDED.",
    f"DROP ITEM {_G} INTO THE COUNTERBORE, PILOT UP.",
    "RUN A ZIGZAG OF THICK CA ON THE PLATE'S TAPE.",
    "MIST ACCELERATOR ON THE BLANK'S TAPE.",
    f"LOWER THE BLANK ONTO ITEM {_G} AND THE FENCE WITHIN 10 S.",
    "PRESS THE BLANK DOWN 1 MINUTE, THEN WAIT 5 MINUTES.",
)
_STACK_CHECK = _TAPE_FIRST + len(_TAPED)
_PUSH_CHECK = _STACK_CHECK + 2
_TAPED += (
    "CHECK: THE STACK IS IN THE MHA-CH-13 TRAVELER'S BAND.",
    f"IF STEP {_STACK_CHECK} FAILS, PEEL, CLEAN AND REPEAT FROM STEP "
    f"{_TAPE_FIRST + 1}.",
    "CHECK: THE BLANK DOES NOT MOVE UNDER A HARD HAND PUSH.",
    f"IF STEP {_PUSH_CHECK} FAILS, PEEL, CLEAN AND REPEAT FROM STEP {_TAPE_FIRST + 1}.",
    f"PUT ITEM {_W} ON THE BLANK, CENTRED OVER ITS HUB HOLE.",
    f"RUN ITEM {_S} THROUGH ITEM {_W} INTO ITEM {_P}, SNUG.",
)
BLANK_STEPS = "\n".join(
    (
        "EACH BLANK, WITH THE MHA-CH-13 TRAVELER",
        f"SETUPS 2-4 (FACES, HUB HOLE), UNDER ITEM {_C}:",
        *numbered(_CLAMPED, start=_FIRST),
        f"SETUP 5 (OUTLINE), ON {TAPE_NAME}:",
        *numbered(_TAPED, start=_TAPE_FIRST),
    )
)
