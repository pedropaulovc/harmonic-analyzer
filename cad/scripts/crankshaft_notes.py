r"""Crankshaft drawing prose -- the taper-pin cross-hole callout.

Imported ONLY by ``draw_crankshaft`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

import textwrap

from crank_pinion_spec import CRANKSHAFT_PIN_HOLE_PROCESS

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
# assembly, so the shaft print names the operation and its acceptance, not a
# size or a station (the pinion print carries the same leader note).  The
# words are the part's "Pinion Pin Hole Process" property, which
# crank_pinion_spec owns for both prints; each line is re-wrapped short so the
# note fits the free field above the far-end seat.
PINION_PIN_NOTE_WIDTH = 30
PINION_PIN_NOTE = "\n".join(
    wrapped
    for line in CRANKSHAFT_PIN_HOLE_PROCESS.split("\n")
    for wrapped in textwrap.wrap(
        line, PINION_PIN_NOTE_WIDTH, break_on_hyphens=False
    )
)
