r"""Rod pivot pin (MHA-CH-010) drawing-only data: the marked-dimension and
precision contract and the manufacturing notes the part build stamps into the
SLDPRT.

Kept out of ``ch_rod_pivot_pin_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and ``test_ch_rod_pivot_fit`` import the spec, so prose there
would re-key them on every drawing edit. Imported ONLY by
``build_ch_rod_pivot_pin``, ``draw_ch_rod_pivot_pin`` and the offline tests.

Policy rule 6: four lines a machinist cannot read off the views. The model is
the INSTALLED pin, so the blank's cut length prints from a blanked reference
sketch and note 1 only says to cut it; the peen-at-assembly step IS the
retention requirement; the running fit names its mating part; and the last
line states, once, that peened retention is this reconstruction's choice
(issue #746), not the documented original. The title block owns the drill
rod (MATERIAL) and its finish.
"""

from __future__ import annotations

import ch_rod_pivot_pin_spec as pin

# --- Drawing contract (policy rule 2: the PART owns places and bands). ---
# The journal and the installed length live on the revolve's half-profile
# (``PinProfile``), so both import into the side view beside each other
# (rule 7, turned part). The journal carries the drill rod's own grind band
# natively at three places; the installed length is the fork's thickness,
# printed as REFERENCE (the fork print owns it). The blank's cut length lives
# on the blanked ``BlankReference`` sketch on the same plane and carries its
# own 3-place band (the upset budget in ch_rod_pivot_pin_spec is judged at it).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
    "BlankReference": {"BlankLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3, "PinLen": 3},
    "BlankReference": {"BlankLen": 3},
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
        "2. PEEN BOTH ENDS INTO THE MHA-CH-003 FORK COUNTERSINKS AT ASSEMBLY;"
        f" DRESS TO {pin.PIN_END_PROUD_MAX:.2f} MAX PROUD.",
        "3. RUNS FREE IN THE MHA-CH-006 #47 ROD HOLE.",
        "4. PEENED RETENTION IS A RECONSTRUCTION CHOICE (#746),"
        " NOT THE ORIGINAL FASTENER.",
    )
)
