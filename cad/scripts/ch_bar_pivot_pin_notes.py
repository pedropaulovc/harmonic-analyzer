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
# diameter is the as-bought 5/64 drill rod: the sheet prints it as the stock
# fraction, a REFERENCE whose supplier grind (+/-.0002) governs (#290 ruling:
# fractions only on as-bought stock, shown as REF). The length is the cut
# blank's, at the spec's places under the title block's band (the dressing
# stock in ch_bar_pivot_pin_spec.joint_budget is judged at it).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3, "PinLen": pin.PIN_BLANK_LENGTH_PLACES},
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

# Descriptive text only; every value is the model's. The diameter names both
# mates (rule 4), two lines of words under the size (rule 7: a callout is
# short). The stock fraction in parentheses already says the rod is bought
# (guidelines `What the shop holds`: fractions are as-bought stock, REF), and
# the title-block MATERIAL names the drill rod. The callout hangs under its
# value: SOLIDWORKS drops a multi-line callout stacked above a value from the
# print (r1: the diameter's never reached the PDF).
PIN_DIA_FRACTION_DENOMINATOR = 64  # 5/64 drill rod
DIAMETER_CALLOUT = "\n".join(
    (
        f"PRESS FIT IN {BAR_NUMBER}",
        f"RUNS IN {LEVER_NUMBER} #47 HOLE",
    )
)
