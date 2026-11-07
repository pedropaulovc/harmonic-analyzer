r"""Rod pivot pin (MHA-CH-10) drawing-only data: the marked-dimension and
precision contract and the journal's callout.

Kept out of ``ch_rod_pivot_pin_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and ``test_ch_rod_pivot_fit`` import the spec, so prose there
would re-key them on every drawing edit. Imported ONLY by
``build_ch_rod_pivot_pin``, ``draw_ch_rod_pivot_pin`` and the offline tests.

The model is the INSTALLED pin, so the blank's cut length prints from a
blanked reference sketch as a single MIN limit (drawing-simplicity-policy.md
`How the repository implements the guidelines`: the model dimension, never
note text, owns it), and the installed length prints as the size set at
assembly with its limits and acceptance (rule 19: a supply size and a
set-at-assembly size for one feature). The journal's two fits are flagged at
its Ø callout, where they apply (rules 4 and 7): pressed in the fork's reamed
hole (user ruling 2026-10-09, PR #1292 review F1), running in the arm's #47
hole. The sheet carries no note: pressing the pin and dressing its ends is
MHA-CH-00's rod-forks-pinned step. The title block owns the drill rod
(MATERIAL) and its finish.
"""

from __future__ import annotations

# --- Drawing contract (drawing-simplicity-policy.md `How the repository implements the guidelines`: the PART owns places and bands). ---
# The journal and the installed length live on the revolve's half-profile
# (``PinProfile``), so both import into the side view beside each other
# (drawing-guidelines.md rule 11 (turned parts read like the lathe), turned part). The journal is the as-bought
# 5/64 drill rod: the sheet prints it as the stock fraction, a REFERENCE whose
# supplier grind (+/-.0002) governs (#290 ruling: fractions only on as-bought
# stock, shown as REF). The installed length is set at assembly, flush with
# the fork's outer faces, so it carries the fork thickness's worst-case
# band natively at three places (fan-out round 1, rule 19: a set size needs
# limits). The blank's cut length lives on the blanked ``BlankReference``
# sketch on the same plane as a single MIN limit at two places (the dressing
# stock in ch_rod_pivot_pin_spec.joint_budget is judged at it).
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
# The installed length's setting and acceptance, under its band (rule 19's
# `SET AT ASSEMBLY`; the mate by number, rule 4).
PIN_LENGTH_CALLOUT = "SET AT ASSEMBLY\nFLUSH WITH MHA-CH-03 FORK FACES"
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked pin dimension needs authored places")

# The journal's fits, flagged at its Ø callout (drawing-guidelines.md rule 4
# (tighten only for function, and name the mate); machinist review
# 2026-10-15, #1522): below the stock fraction, each mate named with the fit
# it needs, two lines of words (rule 7); the parenthesised fraction already
# says the rod is as bought. All below: SOLIDWORKS stores a line break in the
# ABOVE compartment but never prints it
# (draw_pd_transgear_pin._printable_above_callouts).
PIN_DIA_FRACTION_DENOMINATOR = 64  # 5/64 drill rod
# The bought rod's size is an untoleranced REF: the supplier's catalogue
# grind governs it, and the title-block MATERIAL names the drill rod
# (#2136 machinist review: a band on an as-supplied REF over-specifies).
PIN_DIA_CALLOUT = "\n".join(
    (
        "PRESS FIT IN MHA-CH-03 FORK HOLE",
        "RUNNING FIT IN MHA-CH-06 #47 HOLE",
    )
)
