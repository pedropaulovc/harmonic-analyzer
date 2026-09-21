r"""Crank pinion retention pin: the print's numbers, in one place.

A plain straight pin (ch12 p.19) driven through the crank pinion's hub boss
and the crankshaft, match-drilled at assembly (``crank_pinion_spec`` owns the
hole: size, station, clocking). The pin is the hole's own drill size -- stock
1/8 in drill rod, cut to the boss diameter and the ends faced -- so nothing
here is a fit class: the match-drilled hole IS the fit, and the pinion's print
says how the pin goes in. Two dimensions, general grade, no band, no symbol.
"""

from __future__ import annotations

from crank_pinion_spec import BOSS_DIA, PIN_LENGTH
from crank_pinion_spec import PIN_DIA as PIN_DIA  # noqa: PLC0414  # re-export

# Size: the drill's own diameter (crank_pinion_spec.PIN_DIA, 1/8 in). Length:
# flush with the boss on both sides (PIN_LENGTH = BOSS_DIA). Re-exported so the
# build/drawing/tests read one module; the identities are asserted so the pin
# can never drift from the hole it was cut for.
if PIN_LENGTH != BOSS_DIA:
    raise AssertionError("retention pin is defined flush with the boss")
PIN_LEN = PIN_LENGTH  # 13.51

# Marked model dimensions: the two the print carries, both on the revolve's
# half-profile so both import into the side view (rule 7: a turned part's
# diameter sits beside its length). The diameter is a routine turned / cut
# size at the title block's .XX general grade -- the match-drilled hole sets
# the fit (a drill-size pin in its own drill's hole is a light drive fit).
# The length has no function beyond "not proud": one place, the .X grade
# (codex machinist review, 2026-09-21: two places claimed a need it lacks).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}

# Decimal places, authored ON THE PART (drawing-simplicity-policy.md rule 2);
# ``build_crank_pinion_pin`` applies this natively and ``draw_crank_pinion_pin``
# reads it back.
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
    raise AssertionError("crank pinion pin drawing dimension names must be unique")
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked pin dimension needs authored places")

# The one fact the views cannot show (rule 6): where the stock may come from.
# The drill-rod size is the drawing's own diameter, not a second number; the
# faced ends are the depicted geometry, so the note does not prescribe them.
DRAWING_NOTES = "STOCK 1/8 IN DRILL ROD OK."
