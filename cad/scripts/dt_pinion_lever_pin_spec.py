r"""Pure-data dimensional contract shared by the pinion lever retention pin and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A plain 1/16 in drill-rod pin cut
overlength, inserted through the hole match-drilled at assembly through the
MHA-DT-16 lever hub and the MHA-DT-17 lift rod, then trimmed and peened flush at
both ends (U8 + U36; Codex P1 on #844).  The pin is a slip fit in the drilled
hole and the peened heads retain it (#1064), so the step says INSERT, not
DRIVE.  The nominals drive the part's named equation globals AND the
drawing's coordinate math (``test_dt_pinion_lever_pin_drawing.py``).
"""

from __future__ import annotations

from dt_pinion_lever_pin_geometry import PIN_DIA as PIN_DIA, PIN_LEN as PIN_LEN
from dt_pinion_lever_pin_geometry import UNIT as UNIT

LEVER_NUMBER = "MHA-DT-16"
LIFT_ROD_NUMBER = "MHA-DT-17"

# Stock 1/16 in drill rod, held +/-.0003 as supplied (#290 fit F15).  The pin
# rides a .064 drilled hole (title-block DRILLED HOLES +.004/0), so it is
# retained by the peened heads, not by an interference: the band only says
# "use the stock", and the largest pin still clears the smallest hole by .0012.
PIN_DIA_BAND = (0.00762, -0.00762)

# drawing-guidelines.md rule 11 (turned parts read like the lathe) (turned parts): both dimensions live on the revolved half-profile, so
# the diameter prints on the side view beside the length, not on the end view
# (machinist review of 7f7fc1717).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}

# Decimal places ARE the tolerance statement (drawing-guidelines.md rule 3 (decimal places carry the tolerance)).  Four on the
# 1/16 in stock diameter so the printed nominal is the drill rod's own .0625;
# two on the overlength cut, which assembly trims and peens flush anyway.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 4, "PinLen": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the pin sheet carries no notes, and the MHA-DT-16 and MHA-DT-17 hole
# callouts carry only the hole specification (Main, 2026-09-26, as MHA-DT-19's).
# The grip-parked drilling pose and the insert, trim and peen sequence are
# performed at assembly, so they print once, on this pinion fit-up step,
# named by its first words as RIG SET and SHAFT DRILL SET are.  The part
# callouts' pointers to it land at integration, from the step registry.
LEVER_PIN_SET_NAME = "LEVER PIN SET"
LEVER_PIN_SET_STEP_KEY = "lever-pin-set"
PIN_NUMBER = "MHA-DT-30"
ASSEMBLY_STEP = "\n".join(
    (
        f"{LEVER_PIN_SET_NAME}: MATCH-DRILL {LEVER_NUMBER} HUB AND {LIFT_ROD_NUMBER} ROD",
        f"TOGETHER, GRIP PARKED; INSERT {PIN_NUMBER},",
        "TRIM BOTH ENDS AND PEEN FLUSH WITH HUB.",
    )
)
# drawing-guidelines.md rule 4 (tighten only for function, and name the mate):
# the stock band names the hole the pin slips into and says the stock holds
# it; the overlength cut points at the step that trims it (rule 19).  That
# pointer comes from the MHA-DT-00 step registry, which part scripts must not
# reach (test_part_isolation), so the drawing composes it.
PIN_DIA_CALLOUT = "\n".join(
    (
        "1/16 DRILL ROD, STOCK OK",
        f"SLIP FIT IN {LEVER_NUMBER}",
        f"AND {LIFT_ROD_NUMBER} PIN HOLE",
    )
)
PIN_LEN_CALLOUT = "CUT LENGTH"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
