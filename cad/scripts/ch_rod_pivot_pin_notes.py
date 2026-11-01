r"""Rod pivot pin (MHA-CH-10) drawing-only data: the marked-dimension and
precision contract, the journal's callout and the manufacturing note the part
build stamps into the SLDPRT.

Kept out of ``ch_rod_pivot_pin_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and ``test_ch_rod_pivot_fit`` import the spec, so prose there
would re-key them on every drawing edit. Imported ONLY by
``build_ch_rod_pivot_pin``, ``draw_ch_rod_pivot_pin`` and the offline tests.

drawing-guidelines.md rule 7 (notes: few, flagged, never a method): one line a
machinist cannot read off the views. The model is the INSTALLED pin, so the
blank's cut length prints from a blanked reference sketch as a single MIN
limit (drawing-simplicity-policy.md `How the repository implements the
guidelines`: the model dimension, never note text, owns it). The journal's two
fits are flagged at its Ø callout, where they apply (rules 4 and 7): stock
size, pressed in the fork's reamed hole (user ruling 2026-10-09, PR #1292
review F1), running in the arm's #47 hole. The note keeps what no callout
carries: the views show the installed pin, its ends dressed flush at
assembly (the inter-arm gap's neighbour clearance). The title block owns the
drill rod (MATERIAL) and its finish.
"""

from __future__ import annotations

import ch_rod_pivot_pin_spec as pin

if pin.PIN_END_PROUD_MAX != 0.0:
    raise AssertionError("the note states flush ends")

# --- Drawing contract (drawing-simplicity-policy.md `How the repository implements the guidelines`: the PART owns places and bands). ---
# The journal and the installed length live on the revolve's half-profile
# (``PinProfile``), so both import into the side view beside each other
# (drawing-guidelines.md rule 11 (turned parts read like the lathe), turned part). The journal is the as-bought
# 5/64 drill rod: the sheet prints it as the stock fraction, a REFERENCE whose
# supplier grind (+/-.0002) governs (#290 ruling: fractions only on as-bought
# stock, shown as REF); the installed length is the fork's thickness,
# printed as REFERENCE (the fork print owns it) at its three places. The
# blank's cut length lives on the blanked ``BlankReference`` sketch on the
# same plane as a single MIN limit at two places (the dressing stock in
# ch_rod_pivot_pin_spec.joint_budget is judged at it).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
    "BlankReference": {"BlankLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3, "PinLen": 3},
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

# The journal's stock and fits, flagged at its Ø callout (drawing-guidelines.md
# rule 4 (tighten only for function, and name the mate); machinist review
# 2026-10-15, #1522): below the stock fraction, the drill rod as supplied,
# then each mate named with the fit it needs. All below: SOLIDWORKS stores a
# line break in the ABOVE compartment but never prints it
# (draw_pd_transgear_pin._printable_above_callouts).
PIN_DIA_FRACTION_DENOMINATOR = 64  # 5/64 drill rod
PIN_DIA_CALLOUT = "\n".join(
    (
        "DRILL ROD, AS SUPPLIED",
        "PRESS FIT IN MHA-CH-03 FORK HOLE",
        "RUNNING FIT IN MHA-CH-06 #47 HOLE",
    )
)

DRAWING_NOTES = (
    "1. INSTALLED STATE SHOWN: BOTH ENDS DRESSED FLUSH WITH THE MHA-CH-03"
    " FORK FACES AT ASSEMBLY, NEVER PROUD."
)
