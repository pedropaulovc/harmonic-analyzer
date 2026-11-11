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
# (drawing-guidelines.md rule 11 (turned parts read like the lathe), turned part). The journal
# is the press size, .0782 +/-.0001 at four places
# (ch_rod_pivot_pin_spec.PIN_DIA_TOLERANCE, #2339): narrower than the turned
# row, it is reached by the shop table's precision-stock route, the
# title-block drill rod selected by micrometer, named at the callout without
# restating the stock (#2136 review). The installed length is set at assembly, flush with
# the fork's outer faces, so it prints at two places under the title block's
# .XX band, a plain inch step that holds the fork thickness's +/-.006
# worst case (fan-out round 1, rule 19: a set size needs limits; round 2,
# rule 4: a converted +/-.006 read as a precision nobody chose). The blank's
# cut length lives on the blanked ``BlankReference`` sketch on the same plane
# as a single MIN limit at two places (the dressing stock in
# ch_rod_pivot_pin_spec.joint_budget is judged at it).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
    "BlankReference": {"BlankLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 4, "PinLen": 2},
    "BlankReference": {"BlankLen": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
# The installed length is set at assembly (rule 19's `SET AT ASSEMBLY`), its
# limits the .XX band; how it is set, dressing the ends flush with the fork,
# is MHA-CH-00's step, not this sheet's (rule 7: 'FLUSH WITH MHA-CH-03' read
# as its END FLUSH WITH narration example, local repeat after round 3).
PIN_LENGTH_CALLOUT = "SET AT ASSEMBLY"
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked pin dimension needs authored places")

# The journal's fits, flagged at its Ø callout (drawing-guidelines.md rule 4
# (tighten only for function, and name the mate); machinist review
# 2026-10-15, #1522): below the size, the route that reaches its band, then
# each mate named with the fit it needs (rule 7). All below: SOLIDWORKS
# stores a line break in the ABOVE compartment but never prints it
# (draw_pd_transgear_pin._printable_above_callouts). The band against the
# fork hole's printed limits gives FN2's .0002-.0008 (the spec's budget), so
# the press fit needs no measured hole.
PIN_DIA_CALLOUT = "\n".join(
    (
        "SELECTED STOCK, PRESS FIT IN MHA-CH-03",
        "RUNNING FIT IN MHA-CH-06 #47 HOLE",
    )
)
