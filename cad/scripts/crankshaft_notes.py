r"""Crankshaft drawing prose -- the taper-pin cross-hole callout.

Imported ONLY by ``draw_crankshaft`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from crank_pinion_spec import PINION_NUMBER

# Matched-fit requirement on the feature callout (rule 6), naming both mates
# and the acceptance of the custom 1:48 taper pin (crank_pin_spec).  It reads
# under the native #9 drill size, in the order the work is done (drill, then
# taper-ream with the hub); short lines keep it narrow beside the cross-hole.
CROSS_HOLE_CALLOUT = "\n".join(
    (
        "MATCH TAPER-REAM 1:48",
        "WITH CRANK HUB MHA-137",
        "TO TAPER PIN MHA-024:",
        "LIGHT DRIVE FIT",
    )
)

# The 16T retention-pin hole is match-drilled through the pinion boss at
# assembly, so the shaft print names only where the hole comes from, in the
# base's transfer wording (draw_harmonic_base, U28).  The procedure -- ream
# to the pin, seat it, flush both sides -- is assembly work: it stays in
# crank_pinion_spec.CRANKSHAFT_PIN_HOLE_PROCESS for the MHA-A03 step that
# fits the pinion, never on this part print (rule 6).
PINION_PIN_TRANSFER_NOTE = f"TRANSFER FROM {PINION_NUMBER}\nAT ASSEMBLY"
