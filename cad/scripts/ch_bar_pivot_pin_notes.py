r"""Bar pivot pin (MHA-CH-11) drawing-only data: the marked-dimension and
precision contract and the diameter's callout.

Kept out of ``ch_bar_pivot_pin_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and ``test_ch_bar_pivot_fit`` import the spec, so drawing
data there would re-key them on every sheet edit. Imported ONLY by
``build_ch_bar_pivot_pin``, ``draw_ch_bar_pivot_pin`` and the offline tests.

The sheet prints the pin the shop makes: the part's default configuration,
the drill-rod blank cut to its length (the ``build_dt_pinion_lever_pin``
pattern). Pressing it into MHA-CH-01 and dressing both ends flush is the
channel assembly's step, so neither the installed length nor the dressing
is on this sheet (rubric-sample review 2026-11-06: the dashed blank ends,
the flush narration on the installed length and the three-line diameter
callout). No sheet note: the views and the title block carry everything.
"""

from __future__ import annotations

import ch_bar_pivot_pin_spec as pin

# Mating parts the diameter's callout names (test_ch_bar_pivot_pin_drawing
# pins each to the part registry).
BAR_NUMBER = "MHA-CH-01"  # pressed into its reamed top pin hole
LEVER_NUMBER = "MHA-CH-02"  # runs in its #47 bar-pin hole

# --- Drawing contract (drawing-simplicity-policy.md `How the repository
# implements the guidelines`: the PART owns places and bands). ---
# The diameter and the length live on the revolve's half-profile
# (``PinProfile``), so both import into the side view beside each other
# (drawing-guidelines.md rule 11 (turned parts read like the lathe)). The
# diameter is the press size, .0782 +/-.0001 at four places
# (ch_bar_pivot_pin_spec.PIN_DIA_TOLERANCE, #2339): narrower than the turned
# row, it is reached by the shop table's precision-stock route, the
# title-block drill rod selected by micrometer, named at the callout without
# restating the stock (#2136 review). The length is the cut
# blank's, at the spec's places under the title block's band (the dressing
# stock in ch_bar_pivot_pin_spec.joint_budget is judged at it).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 4, "PinLen": pin.PIN_BLANK_LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked pin dimension needs authored places")

# Descriptive text only; every value is the model's. Under the size, the
# route that reaches its band, then both mates (rule 4), each in a few words
# (rule 7: a callout is short); the title-block MATERIAL names the drill rod.
# The band against the bar hole's printed limits gives FN2's .0002-.0008 (the
# spec's budget). The callout hangs under its value: SOLIDWORKS drops a
# multi-line callout stacked above a value from the print (r1: the
# diameter's never reached the PDF).
DIAMETER_CALLOUT = "\n".join(
    (
        f"SELECTED STOCK, PRESS FIT IN {BAR_NUMBER}",
        f"RUNS IN {LEVER_NUMBER} #47 HOLE",
    )
)
