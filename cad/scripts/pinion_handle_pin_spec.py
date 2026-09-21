r"""Pure-data dimensional contract for the pinion-handle retention pin.

The part is a plain straight pin used as the match-ream gauge for the MHA-058
handle and MHA-102 pinion-arbor joint.  Its nominal diameter and cut length are
the only dimensions owned here; the part build authors both as native driving
dimensions and the manufacturing drawing imports those dimensions verbatim.
"""

from __future__ import annotations


# AISI 1018 cold-finished stock is the registry material for this part.  The
# stock is a simple straight cylinder, with flat ends, local +Z from z=0 to
# PIN_LEN.  The match-reamed assembly hole establishes the functional fit; no
# independent fit band belongs on this pin.
PIN_DIA = 2.0
PIN_LEN = 10.5


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}

# Decimal places are authored on the model (drawing-simplicity-policy rule 2).
# The diameter is shown to two places because it is the match-ream gauge; the
# trim-to-flush length needs only the routine one-place grade.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 2, "PinLen": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("pinion handle pin drawing dimension names must be unique")
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked pin dimension needs authored places")


# The MHA-058 handle and MHA-102 arbor holes are match-reamed together on the
# actual MHA-136 pin for a light drive fit; the installed ends finish flush.
# These are the only manufacturing facts not readable from the plain cylinder.
DRAWING_NOTES = (
    "MATCH-DRILL/REAM MHA-058 HANDLE AND MHA-102 PINION ARBOR TO "
    "LIGHT DRIVE FIT ON ACTUAL MHA-136 PIN; TRIM ENDS FLUSH IN ASSEMBLY."
)
