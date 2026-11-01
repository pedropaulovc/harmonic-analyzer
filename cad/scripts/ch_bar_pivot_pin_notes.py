r"""Bar pivot pin (MHA-CH-11) drawing-only data: the marked-dimension and
precision contract, the dimension callouts and the manufacturing note the
part build stamps into the SLDPRT.

Kept out of ``ch_bar_pivot_pin_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and ``test_ch_bar_pivot_fit`` import the spec, so drawing
data there would re-key them on every sheet edit. Imported ONLY by
``build_ch_bar_pivot_pin``, ``draw_ch_bar_pivot_pin`` and the offline tests.

drawing-guidelines.md rule 7 (notes: few, flagged, never a method). The model
is the INSTALLED pin, so the blank -- its ends drawn thin dashed beyond the
installed outline -- and its cut length print from a blanked reference sketch
(drawing-simplicity-policy.md `How the repository implements the guidelines`:
its band rides that model dimension, never note text), and the one note says
which outline is which (ENFORCE review 2026-10-23: the blank was dimensioned
but never drawn). Machinist round 1 (#1305):
the mates and the drill-rod stock moved from the notes to the diameter they
govern, the flush ends to the installed length; the press/punch line was a
method and left. The title block owns the drill rod (MATERIAL) and its finish.
"""

from __future__ import annotations

import ch_bar_pivot_pin_spec as pin

if pin.PIN_END_PROUD_MAX != 0.0:
    raise AssertionError("the installed-length callout states flush ends")

# Mating parts the callouts name (test_ch_bar_pivot_pin_drawing pins each to
# the part registry).
BAR_NUMBER = "MHA-CH-01"  # pressed into its reamed top pin hole
LEVER_NUMBER = "MHA-CH-02"  # runs in its #47 bar-pin hole

# --- Drawing contract (drawing-simplicity-policy.md `How the repository
# implements the guidelines`: the PART owns places and bands). ---
# The diameter and the installed length live on the revolve's half-profile
# (``PinProfile``), so both import into the side view beside each other
# (drawing-guidelines.md rule 11 (turned parts read like the lathe)). The
# diameter is the as-bought 5/64 drill rod: the sheet prints it as the stock
# fraction, a REFERENCE whose supplier grind (+/-.0002) governs (#290 ruling:
# fractions only on as-bought stock, shown as REF); the installed length is
# the bar's width, printed as REFERENCE (the bar's stock owns it). The blank's
# cut length lives on the blanked ``BlankReference`` sketch on the same plane
# and prints at the spec's places under the title block's band (the dressing
# stock in ch_bar_pivot_pin_spec.joint_budget is judged at it).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
    "BlankReference": {"BlankLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3, "PinLen": 2},
    "BlankReference": {"BlankLen": pin.PIN_BLANK_LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
REFERENCE_DIMENSIONS = frozenset({"PinLen"})
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked pin dimension needs authored places")

# Descriptive text only; every value and band is the model's. The diameter
# names its stock and both mates (rule 4). Every callout hangs under its
# value: SOLIDWORKS drops a multi-line callout stacked above a value from the
# print (r1: the diameter's never reached the PDF). The installed length's
# stays narrower than the pin at 10:1, clear of both length rows' witnesses;
# note 1 names the solid and dashed outlines.
PIN_DIA_FRACTION_DENOMINATOR = 64  # 5/64 drill rod
DIAMETER_CALLOUT = (
    "DRILL ROD, AS SUPPLIED\n"
    f"PRESS FIT IN {BAR_NUMBER}\n"
    f"RUNS IN {LEVER_NUMBER} #47 HOLE"
)
DIMENSION_CALLOUTS: dict[str, str] = {
    "PinLen": f"FLUSH WITH {BAR_NUMBER}",
    "BlankLen": "BLANK",
}

DRAWING_NOTES = (
    "1. SOLID OUTLINE IS THE INSTALLED PIN; THIN DASHED ENDS SHOW THE BLANK."
)
