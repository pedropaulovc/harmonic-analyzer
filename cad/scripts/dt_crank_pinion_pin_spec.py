r"""Crank pinion retention pin: the print's numbers, in one place.

A plain straight pin (ch12 p.19) driven through the crank pinion's hub boss
and the crankshaft, match-drilled at assembly (``dt_crank_pinion_spec`` owns the
hole: size, station, clocking). The pin is the hole's own drill size -- stock
1/8 in drill rod, cut to the boss diameter and the ends faced -- so nothing
here is a fit class: the match-drilled hole IS the fit, and the pinion's print
says how the pin goes in. Two dimensions, general grade, no band, no symbol.
"""

from __future__ import annotations

from dt_crank_pinion_spec import BOSS_DIA, PIN_LENGTH
from dt_crank_pinion_spec import PIN_DIA as PIN_DIA  # noqa: PLC0414  # re-export

# Size: the drill's own diameter (dt_crank_pinion_spec.PIN_DIA, 1/8 in). Length:
# flush with the boss on both sides (PIN_LENGTH = BOSS_DIA). Re-exported so the
# build/drawing/tests read one module; the identities are asserted so the pin
# can never drift from the hole it was cut for.
if PIN_LENGTH != BOSS_DIA:
    raise AssertionError("retention pin is defined flush with the boss")
PIN_LEN = PIN_LENGTH  # .56 in

# Marked model dimensions: the two the print carries, both on the revolve's
# half-profile so both import into the side view (drawing-guidelines.md rule 11 (turned parts read like the lathe): a turned part's
# diameter sits beside its length). The diameter is the as-bought 1/8 in
# rod's, so the sheet prints it as a fraction reference (#290: the supplier's
# tolerance governs; the match-drilled hole sets the fit -- a drill-size pin
# in its own drill's hole is a light drive fit). The length is flush with
# the boss's .XX diameter, so it prints at the same .XX grade.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}

# Decimal places, authored ON THE PART (drawing-simplicity-policy.md `How the repository implements the guidelines`);
# ``build_dt_crank_pinion_pin`` applies this natively and ``draw_dt_crank_pinion_pin``
# reads it back.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3, "PinLen": 2},
}
# The diameter's as-bought fraction: 1/8 in.
PIN_DIA_FRACTION_DENOMINATOR = 8
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

# Under the fraction: the stock's own diameter tolerance governs, quoted as
# reference for each stock the MATERIAL cell allows (machinist review: the
# two differ). Drill rod is ground to ±.0002 (ch_rod_pivot_pin_spec's figure);
# 1018 cold-drawn rounds to 1 1/2 in are +.000/-.002 (ASTM A108).
PIN_DIA_CALLOUT = "STOCK, AS SUPPLIED; SUPPLIER TOL. (REF):\nDRILL ROD ±.0002, 1018 CF +.000/-.002"

# No manufacturing note (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)): the title-block MATERIAL "AISI 1018 CF or
# drill rod, 1/8 in" is the one statement of the stock, and the faced ends are
# the depicted geometry.
