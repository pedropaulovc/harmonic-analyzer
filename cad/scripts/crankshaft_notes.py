r"""Crankshaft drawing prose -- the cross-hole and drive-pin hole callouts.

Imported ONLY by ``draw_crankshaft`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from crankshaft_spec import DRIVE_PIN_SPIGOT_RIM_WORST

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

# The thinnest wall round the drive-pin holes, to the seat spigot's rim, at
# the printed worst case (crankshaft_spec rounds it down): stated as the fact
# the shop holds, under the holes' own callout.
# Named exception: MHA-026 rim (drawing-simplicity-policy.md, "Named exceptions").
DRIVE_PIN_RIM_NOTE = "\n".join(
    (
        "DRIVE-PIN HOLE TO",
        f"SPIGOT RIM {DRIVE_PIN_SPIGOT_RIM_WORST:.2f} MIN.",
    )
)

# Under the native REAM callout on the seat spigot's two blind holes: the
# purchased dowel each receives and how it goes in (bottomed, which is what
# sets its proud length into the removable sprocket), then their rim.
DRIVE_PIN_CALLOUT = "\n".join(
    (
        "PRESS FIT DRIVE PIN",
        "MHA-173 TO HOLE FLOOR",
        DRIVE_PIN_RIM_NOTE,
    )
)
