"""Drawing-only text of the keyed arbor kit (MHA-DT-03-TL-05).

The fitting steps the release's ASSEMBLY.md prints (ha_assembly_package,
#2889) and the key-clock setting note sheet 2 prints in their place. Only
draw_dt_cone_gear_tl_arbor_assembly, ha_assembly_package (and their tests)
import this module; no assembly builder may (``test_assembly_sheet_isolation``
pins it), so a wording edit here does not rebuild the kit. No SolidWorks.
"""

from __future__ import annotations

import dt_cone_gear_tl_arbor_assembly_spec as spec
import dt_cone_gear_tl_keyed_arbor_spec as arbor

# Fitting steps: one action each, each retention or setting followed by its
# check (rules 22, 23). LOCTITE 638 is a consumable: degrease, coat the key
# (never the keyseat), keep it off the seat the blanks slide on, cure before
# the first cut. Ends and surfaces are named by the features the views show,
# not by a view the package does not label (machinist review of farm
# 20261113T171903293Z).
_K, _A, _N = (spec.BOM_ITEMS[s] for s in (spec.KEY, spec.ARBOR, spec.NUT))
_READING = arbor.inch_text(spec.KEY_SIDE_READING, 3)
_AWAY = "AWAY FROM THE CUTTER"
if _AWAY not in spec.POINTING_DEG:
    raise AssertionError("the steps' pointing words are not a declared direction")
_SEAT_TEXT = "Ø" + arbor.inch_text(
    arbor.SEAT_DIA, arbor.DRAWING_PRECISION_BY_NAME["SeatDia"]
)
# The key's clock (spec): set on its own two side faces before the blank
# goes on, touched in turn by one test indicator at one height, the head
# turned half a turn between them (the cutter's centre plane is nothing a
# builder can touch; machinist review of farm 20261113T204539922Z); then a
# half turn, only if it points away, brings it to the cutter. Rule 26's
# private phrases (BY EYE among them) appear in no step.
_FITTING: tuple[str, ...] = (
    f"DEGREASE ITEM {_K} AND ITEM {_A}'S KEYSEAT.",
    f"COAT ITEM {_K} WITH {arbor.KEY_BOND}.",
    f"PUSH ITEM {_K} INTO ITEM {_A}'S KEYSEAT AGAINST THE KEYSEAT'S END NEAREST "
    f"ITEM {_A}'S SHOULDER.",
    f"WIPE ALL {arbor.KEY_BOND} OFF ITEM {_A}'S {_SEAT_TEXT} SEAT, LEAVING THE "
    "KEYSEAT FILLED.",
    "LET THE BOND CURE 24 H.",
    f"CHECK: ITEM {_K} DOES NOT MOVE BY HAND.",
    f"GRIP ITEM {_A}'S Ø.62 END IN THE HEAD'S 3-JAW CHUCK AGAINST ITS STEP, "
    f"ONLY ITEM {_K} ON IT.",
    f"TURN THE HEAD UNTIL ITEM {_K} POINTS {_AWAY}, ROUGHLY LEVEL.",
    f"ZERO A TEST INDICATOR, HELD IN THE SPINDLE, ON ITEM {_K}'S UPPER SIDE FACE.",
)
ZERO_STEP = len(_FITTING)
DRO_STEP = ZERO_STEP + 1
_SETTING: tuple[str, ...] = (
    "NOTE THE Z DRO READING.",
    "TURN THE HEAD 180°.",
    f"CARRY THE INDICATOR OVER ITEM {_A} TO ITEM {_K}'S UPPER SIDE FACE BY Y AND "
    f"Z ONLY, BACK AT THE STEP {DRO_STEP} Z DRO READING.",
    f"CHECK: THE INDICATOR READS ZERO WITHIN {_READING}.",
)
CHECK_STEP = ZERO_STEP + len(_SETTING)
_SETTING += (
    f"IF STEP {CHECK_STEP} FAILS, TURN THE HEAD UNTIL THE INDICATOR READS HALF "
    f"ITS STEP {CHECK_STEP} READING AND REPEAT FROM STEP {ZERO_STEP}.",
    f"IF ITEM {_K} POINTS {_AWAY}, TURN THE HEAD 180°.",
    "LOCK THE HEAD'S SPINDLE.",
    f"SLIDE THE BLANK ONTO ITEM {_A} OVER ITEM {_K}, AGAINST ITEM {_A}'S SHOULDER.",
    f"SLIDE THE BLANK'S COLLAR (SETUP TABLE) ONTO ITEM {_A} AGAINST THE BLANK.",
    f"TIGHTEN ITEM {_N} AGAINST THE COLLAR.",
    f"FOR AN {spec.CONE_NUMBER} BLANK, RUN THE TAILSTOCK CENTRE INTO ITEM {_A}'S "
    "THREADED-END CENTRE HOLE.",
    "CHECK: THE BLANK DOES NOT TURN OR SLIDE BY HAND.",
    "UNLOCK THE HEAD'S SPINDLE.",
    "TURN THE HEAD BY THE BLANK'S FIRST INDEX (SETUP TABLE).",
)
STEPS: tuple[str, ...] = tuple(
    f"{number}. {step}" for number, step in enumerate((*_FITTING, *_SETTING), start=1)
)
INDEX_STEP = len(STEPS)
# The sections ASSEMBLY.md prints (ha_assembly_package, #2889); the checks are
# steps of their own (rule 22).
STEP_SECTIONS = (("FITTING STEPS (PARTS LIST AND SETUP TABLE ON SHEET 1)", STEPS),)
ASSEMBLY_CHECKS: tuple[str, ...] = ()
# Sheet 2's note where the steps stood: the key clock's measurable acceptance
# stays on the sheet (rule 22), with where its procedure prints.
KEY_CLOCK_NOTE = "\n".join(
    (
        "FITTING STEPS: ASSEMBLY.MD.",
        f"KEY CLOCK (STEPS {ZERO_STEP}-{CHECK_STEP}): ITEM {_K}'S TWO SIDE FACES,",
        "THE HEAD TURNED 180° BETWEEN THEM, READ ALIKE ON ONE TEST",
        f"INDICATOR WITHIN {_READING}.",
    )
)
