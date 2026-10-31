r"""Crankshaft drawing prose -- the cross-hole and drive-pin hole callouts.

Imported ONLY by ``draw_crankshaft`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from _surface_finish import surface_finish_by_key
from dt_crank_drive_gear_spec import inch_text
from dt_crankshaft_spec import (
    DRIVE_PIN_DEPTH_TOL,
    DRIVE_PIN_KNOCKOUT_PROCESS,
    DRIVE_PIN_SPIGOT_RIM_WORST,
    HOLE_CALLOUT_PLACES,
    SURFACE_FINISHES,
)

# Native roughness readback uses the same part-owned control as symbol authoring.
# Keep manufacturing text derivation out of the presentation-only recipe.
COLLAR_REAR_FINISH_TEXT = (
    f"Ra {surface_finish_by_key(SURFACE_FINISHES, 'collar_rear_face').roughness_ra}"
)

# Matched-fit requirement on the feature callout (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)), naming both mates
# and the acceptance of the custom 1:48 taper pin (crank_pin_spec).  It reads
# under the native #9 drill size, in the order the work is done (drill, then
# taper-ream with the hub).  Three rows, not four: the shorter block stands
# higher, so the diameters under it have room for their mates.
CROSS_HOLE_CALLOUT = "\n".join(
    (
        "MATCH TAPER-REAM 1:48 WITH",
        "HUB MHA-DT-31 FOR PIN",
        "MHA-DT-09: LIGHT DRIVE FIT",
    )
)

# Each banded size and length names the mate or stack its band serves, and a
# fit its kind, at its own callout (drawing-guidelines.md rule 4; machinist
# reviews of 5a219a81904f and f50937749).  The profile's diameters share a
# crowded band under the cross-hole callout, so each diameter takes one
# short row above its value (the fit) and one below (the mate): SolidWorks
# drops a multi-row callout above a dimension.  The station rows are 9.5 mm
# apart on the sheet, so their stacks ride on the same line as a suffix.
SLIDING_FIT = "SLIDING FIT"
SHANK_MATE = "IN MHA-DT-31"
JOURNAL_FIT = "2X RUNNING FIT"
JOURNAL_MATE = "IN MHA-DT-05"
PINION_SEAT_MATE = "IN MHA-DT-10"
# The spigot's diameter (under it, never over) and its length from the seat
# face both keep the #25 chain wrapping MHA-PD-09 clear (dt_crankshaft_spec).
SPIGOT_AIR = "#25 CHAIN AIR"
SPIGOT_AIR_MATE = "ON MHA-PD-09"
CHAIN_AIR_MATE = "CHAIN AIR\nMHA-PD-09"
COLLAR_REAR_MATE = " BEARS ON MHA-DT-05"
COLLAR_SEAT_MATE = " MHA-PD-09 SEAT"
SHAFT_LENGTH_MATE = " SETS MHA-DT-31 TO MHA-PD-09 AIR"

# The thinnest wall round the drive-pin holes, to the seat spigot's rim, at
# the printed worst case (crankshaft_spec rounds it down): stated as the fact
# the shop holds, under the holes' own callout.
# Emits approved declaration dt-crankshaft RV-02 (owner ruling 2026-10-18,
# #991; redesign tracked in #1679).
DRIVE_PIN_RIM_NOTE = f"DRIVE-PIN HOLE TO SPIGOT RIM {inch_text(DRIVE_PIN_SPIGOT_RIM_WORST, 3)} MIN."

# Under the native REAM callout on the seat spigot's two blind holes: the
# purchased dowel each receives and how it goes in (bottomed, which is what
# sets its proud length into the removable sprocket), then their rim.  One
# row each keeps the callout to four rows with the REAM line's stacked limit.
DRIVE_PIN_CALLOUT = "\n".join(
    (
        "PRESS FIT DRIVE PIN MHA-DT-VN-67 TO HOLE FLOOR",
        DRIVE_PIN_RIM_NOTE,
    )
)

# The native REAM callout prints the hole depth bare, so it would read under
# the title block's general band, though the cut's depth carries the part's
# +/-.004 (crankshaft_spec: pressed to the floor, the depth sets the pin's
# proud length).  The band is appended to the depth at the end of the
# callout's own format text, in inches at the callout's places:
# draw_dt_crankshaft refuses any other sheet.
DRIVE_PIN_DEPTH_BAND = f"<MOD-PM>{inch_text(DRIVE_PIN_DEPTH_TOL, HOLE_CALLOUT_PLACES)}"

# Under each location: the mate the +/-.0009 serves.  The MHA-PD-09 holes
# slip over the pressed dowels with a diametral clearance that must absorb
# the pin-spacing error of both parts (crankshaft_spec
# DRIVE_PIN_SPACING_ERROR_MAX check); the title block's .XXX band could not.
# Four short rows, none wider than the location value above them: the text runs
# right from the dimension line beside the end view and must end before the
# dome tip's extension lines (machinist review of 19e33c6c2: the two-row
# form ran ~44 mm wide, across them).
DRIVE_PIN_LOCATION_CALLOUT = "PINS SLIP\nINTO\nSPROCKET\nMHA-PD-09"

# The pins' knockouts (dt_crankshaft_spec DRIVE_PIN_KNOCKOUT_SPEC) print as a
# native Hole Wizard callout on the lower hole's floor: the drill reads above
# the native size so the three short rows fit the field under the end view.
KNOCKOUT_CALLOUT_ABOVE = DRIVE_PIN_KNOCKOUT_PROCESS
KNOCKOUT_CALLOUT_BELOW = "DRIVE-PIN KNOCKOUT"

# The punched witness on the dome, flagged with a leader to the mark itself
# (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)); its
# exact spot is deliberately free.
FIDUCIAL_NOTE = "PUNCH\nMARK\nBY EYE"

# Where the shop may drill a lathe centre hole (drawing-guidelines.md rule
# 11): the plain far end only, never the dome.  The leader to that
# end's rim is what names the end (rule 7: flag it where it applies); the
# unleadered "AT PLAIN END" row named an end the sheet never identified.  The
# restriction is on the centre hole, a turning location: the dome's punched
# witness (FIDUCIAL_NOTE) is a separate, required mark made by eye on the
# finished sphere, which a centre hole would destroy. Keep the four-row text
# unchanged when relocating its native leader: the drawing identifies the
# plain end in FRONT, not by the isometric's apparent top/bottom orientation.
CENTRES_NOTE = "LATHE CENTRE\nHOLE OK HERE;\nNOT IN\nDOME"
