r"""Pure-data dimensional contract shared by the pinion lever retention pin and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A plain 1/16 in drill-rod pin cut
overlength, driven through the hole match-drilled at assembly through the
MHA-059 lever hub and the MHA-060 lift rod, then trimmed and peened flush at
both ends (U8 + U36; Codex P1 on #844).  The nominals drive the part's named equation globals AND the
drawing's coordinate math (``test_pinion_lever_pin_drawing.py``).
"""

from __future__ import annotations

from pinion_lever_pin_geometry import PIN_DIA as PIN_DIA, PIN_LEN as PIN_LEN

LEVER_NUMBER = "MHA-059"
LIFT_ROD_NUMBER = "MHA-060"

# Stock 1/16 in drill rod (h9 in the drill-rod catalogues).  The pin rides a
# drilled hole (title-block DRILLED HOLES +0.10/0), so it is retained by the
# peened heads, not by an interference: the band only says "use the stock".
PIN_DIA_BAND = (0.0, -0.03)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia"},
    "Pin": {"Depth"},
}

# Decimal places ARE the tolerance statement (policy rule 2).  Three on the
# 1/16 in stock diameter so the printed nominal is the drill rod's own 1.588;
# one on the overlength cut, which assembly trims and peens flush anyway.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3},
    "Pin": {"Depth": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

# Rule 6: the pin sheet carries no notes, and the MHA-059 and MHA-060 hole
# callouts carry only the hole specification (Main, 2026-09-26, as MHA-062's).
# The grip-parked drilling pose and the drive, trim and peen sequence are
# performed at assembly, so they print once, on this pinion fit-up step,
# named by its first words as RIG SET and SHAFT DRILL SET are.  The part
# callouts' pointers to it land at integration, from the step registry.
LEVER_PIN_SET_NAME = "LEVER PIN SET"
PIN_NUMBER = "MHA-135"
ASSEMBLY_STEP = "\n".join(
    (
        f"{LEVER_PIN_SET_NAME}: MATCH-DRILL {LEVER_NUMBER} HUB AND {LIFT_ROD_NUMBER} ROD",
        f"TOGETHER, GRIP PARKED; DRIVE {PIN_NUMBER},",
        "TRIM BOTH ENDS AND PEEN FLUSH WITH HUB.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
