r"""Crankshaft drawing prose -- the cross-hole and drive-pin hole callouts.

Imported ONLY by ``draw_crankshaft`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from crankshaft_spec import DRIVE_PIN_DEPTH_TOL, DRIVE_PIN_SPIGOT_RIM_WORST

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
DRIVE_PIN_RIM_NOTE = f"DRIVE-PIN HOLE TO SPIGOT RIM {DRIVE_PIN_SPIGOT_RIM_WORST:.2f} MIN."

# Under the native REAM callout on the seat spigot's two blind holes: the
# purchased dowel each receives and how it goes in (bottomed, which is what
# sets its proud length into the removable sprocket), then their rim.  One
# row each keeps the callout to four rows with the REAM line's stacked limit.
DRIVE_PIN_CALLOUT = "\n".join(
    (
        "PRESS FIT DRIVE PIN MHA-173 TO HOLE FLOOR",
        DRIVE_PIN_RIM_NOTE,
    )
)

# The native REAM callout prints the hole depth bare, so it reads under the
# title block's .XX +/-0.51, though the cut's depth carries the part's
# +/-0.10 (crankshaft_spec: pressed to the floor, the depth sets the pin's
# proud length).  The band is appended to the depth at the end of the
# callout's own format text, in mm: draw_crankshaft refuses a non-mm sheet.
DRIVE_PIN_DEPTH_BAND = f"<MOD-PM>{DRIVE_PIN_DEPTH_TOL:.2f}"

# Under the lower 7.000 location: the mate the +/-0.025 serves.  The MHA-081
# holes (2.5, drilled +0.10/0) slip over the pressed dowels (Ø2.389 max) with
# 0.111 diametral clearance, which must absorb the pin-spacing error of both
# parts: 2 x (2 x 0.025) = 0.100 < 0.111.  The title block's .XXX +/-0.13
# would need 4 x 0.13 = 0.52; the widest per-part band the clearance allows is
# +/-0.0278 (crankshaft_spec DRIVE_PIN_SPACING_ERROR_MAX check).
# Four short rows, none wider than the 7.000 value above them: the text runs
# right from the dimension line beside the end view and must end before the
# dome tip's extension lines (machinist review of 19e33c6c2: the two-row
# form ran ~44 mm wide, across them).
DRIVE_PIN_LOCATION_CALLOUT = "PINS SLIP\nINTO\nSPROCKET\nMHA-081"
