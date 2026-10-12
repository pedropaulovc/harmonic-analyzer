r"""Rod pivot pin (MHA-CH-010) drawing-only data: the marked-dimension and
precision contract and the manufacturing notes the part build stamps into the
SLDPRT.

Kept out of ``ch_rod_pivot_pin_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and ``test_ch_rod_pivot_fit`` import the spec, so prose there
would re-key them on every drawing edit. Imported ONLY by
``build_ch_rod_pivot_pin``, ``draw_ch_rod_pivot_pin`` and the offline tests.

drawing-guidelines.md rule 7 (notes: few, flagged, never a method): four lines a machinist cannot read off the views. The model is
the INSTALLED pin, so the blank's cut length prints from a blanked reference
sketch (drawing-simplicity-policy.md `How the repository implements the guidelines`: its band rides that model dimension, never note text) and
note 1 only says to cut it; the press and its removal are the retention
requirement (user ruling 2026-10-09, PR #1292 review F1); the flush dressing
keeps the inter-arm gap's neighbour clearance; the running fit names its
mating part. The title block owns the drill rod (MATERIAL) and its finish.
"""

from __future__ import annotations

import ch_rod_pivot_pin_spec as pin

if pin.PIN_END_PROUD_MAX != 0.0:
    raise AssertionError("note 3 states flush ends")

# --- Drawing contract (drawing-simplicity-policy.md `How the repository implements the guidelines`: the PART owns places and bands). ---
# The journal and the installed length live on the revolve's half-profile
# (``PinProfile``), so both import into the side view beside each other
# (drawing-guidelines.md rule 11 (turned parts read like the lathe), turned part). The journal carries the drill rod's own grind band
# natively at three places; the installed length is the fork's thickness,
# printed as REFERENCE (the fork print owns it) at its three places. The
# blank's cut length lives on the blanked ``BlankReference`` sketch on the
# same plane and carries its own band at two places, as it is written
# (the dressing stock in ch_rod_pivot_pin_spec.joint_budget is judged at it).
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

DRAWING_NOTES = "\n".join(
    (
        "1. CUT BLANK TO THE BLANK LENGTH SHOWN; INSTALLED STATE SHOWN.",
        "2. PRESS IN; REMOVABLE WITH PUNCH.",
        "3. PRESSED IN THE MHA-CH-003 REAMED FORK PIN HOLE;"
        " DRESS BOTH ENDS FLUSH, NEVER PROUD.",
        "4. RUNS FREE IN THE MHA-CH-006 #47 ROD HOLE.",
    )
)
