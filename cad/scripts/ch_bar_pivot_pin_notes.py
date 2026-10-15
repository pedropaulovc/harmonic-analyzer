r"""Bar pivot pin (MHA-CH-011) drawing-only data: the marked-dimension and
precision contract, the dimension callouts and the manufacturing note the
part build stamps into the SLDPRT.

Kept out of ``ch_bar_pivot_pin_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and ``test_ch_bar_pivot_fit`` import the spec, so drawing
data there would re-key them on every sheet edit. Imported ONLY by
``build_ch_bar_pivot_pin``, ``draw_ch_bar_pivot_pin`` and the offline tests.

drawing-guidelines.md rule 7 (notes: few, flagged, never a method). The model
is the INSTALLED pin, so the blank's cut length prints from a blanked
reference sketch (drawing-simplicity-policy.md `How the repository implements
the guidelines`: its band rides that model dimension, never note text) and the
one note says the views show the installed state. Machinist round 1 (#1305):
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
BAR_NUMBER = "MHA-CH-001"  # pressed into its reamed top pin hole
LEVER_NUMBER = "MHA-CH-002"  # runs in its #47 bar-pin hole

# --- Drawing contract (drawing-simplicity-policy.md `How the repository
# implements the guidelines`: the PART owns places and bands). ---
# The diameter and the installed length live on the revolve's half-profile
# (``PinProfile``), so both import into the side view beside each other
# (drawing-guidelines.md rule 11 (turned parts read like the lathe)). The
# diameter carries the drill rod's own grind band natively at three places;
# the installed length is the bar's width, printed as REFERENCE (the bar's
# stock owns it). The blank's cut length lives on the blanked
# ``BlankReference`` sketch on the same plane and carries its own band at two
# places (the dressing stock in ch_bar_pivot_pin_spec.joint_budget is judged
# at it).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
    "BlankReference": {"BlankLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3, "PinLen": 2},
    "BlankReference": {"BlankLen": 2},
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
# names the stock that holds its band and both mates (rule 4); its callout
# stacks above it, the others hang below their values.
DIAMETER_CALLOUT = (
    "5/64 DRILL ROD, AS SUPPLIED\n"
    f"PRESS FIT IN {BAR_NUMBER}\n"
    f"RUNS IN {LEVER_NUMBER} #47 HOLE"
)
DIMENSION_CALLOUTS_ABOVE: dict[str, str] = {"PinDia": DIAMETER_CALLOUT}
DIMENSION_CALLOUTS_BELOW: dict[str, str] = {
    "PinLen": f"INSTALLED, FLUSH WITH {BAR_NUMBER}",
    "BlankLen": "BLANK",
}

DRAWING_NOTES = "1. VIEWS SHOW THE INSTALLED PIN; CUT THE BLANK SHOWN."
