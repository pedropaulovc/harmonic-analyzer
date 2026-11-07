r"""Crankshaft drawing prose -- the callouts and the numbered sheet notes.

Imported ONLY by ``draw_crankshaft`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from _surface_finish import surface_finish_by_key
import dt_crank_hub_geometry as hub
import dt_crank_pinion_spec as pinion
from dt_crank_drive_gear_spec import inch_text
from dt_crankshaft_spec import (
    DRIVE_PIN_DEPTH_TOL,
    DRIVE_PIN_KNOCKOUT_PROCESS,
    DRIVE_PIN_SPIGOT_RIM_WORST,
    HOLE_CALLOUT_PLACES,
    JOURNAL_BORE_BAND,
    JOURNAL_BORE_DIA,
    JOURNAL_DIA,
    JOURNAL_DIA_BAND,
    PINION_SEAT_DIA,
    PINION_SEAT_DIA_BAND,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SURFACE_FINISHES,
)

# Native roughness readback uses the same part-owned control as symbol authoring.
# Keep manufacturing text derivation out of the presentation-only recipe.
COLLAR_REAR_FINISH_TEXT = (
    f"Ra {surface_finish_by_key(SURFACE_FINISHES, 'collar_rear_face').roughness_ra}"
)


def see_note(number: int) -> str:
    """The callout text that links a feature to numbered sheet note ``number``."""
    return f"SEE NOTE {number}"


# Note 1: the MHA-DT-09 cross-hole.  The native callout prints the #9 drill
# and SEE NOTE 1 (drawing-guidelines.md rule 7: size and process lines plus
# at most two lines of words).  The note states the matched taper ream: the
# mate it is reamed with, the pin it takes and its fit by the standard name
# (rule 26: DRIVE, not LIGHT DRIVE), and the acceptance that ends the ream.
# The acceptance is the crank hub's own note 1 for the same joint (#2231:
# the driven pin's keeper ring MHA-DT-27 still clears the hub;
# dt_crank_pin_ring_spec.PIN_PROUD books that clearance).  Two lines: rule 7
# keeps the sheet's notes to about four short lines.
CROSS_HOLE_NOTE_NUMBER = 1
CROSS_HOLE_CALLOUT = see_note(CROSS_HOLE_NOTE_NUMBER)
CROSS_HOLE_NOTE = "\n".join(
    (
        f"{CROSS_HOLE_NOTE_NUMBER}. TAPER-REAM 1:48 AT ASSEMBLY WITH CRANK HUB MHA-DT-31 FOR PIN",
        "   MHA-DT-09, DRIVE FIT; STOP WHILE ITS KEEPER RING MHA-DT-27 CLEARS THE HUB.",
    )
)

# Note 2: the seat spigot.  Its diameter (held under nominal) and its length
# from the seat face are one feature with one reason: the #25 chain wrapping
# the sprocket passes over the spigot and in front of the collar body
# (dt_crankshaft_spec).  Rule 4: one feature's tight dimensions name the mate
# once, on one numbered note linked to each; rule 26: never AIR for clearance.
SPIGOT_NOTE_NUMBER = 2
SPIGOT_CALLOUT = see_note(SPIGOT_NOTE_NUMBER)
SPIGOT_NOTE = f"{SPIGOT_NOTE_NUMBER}. SPIGOT CLEARS THE #25 CHAIN ON SPROCKET MHA-PD-09."


def _clearance(
    bore: float,
    bore_band: tuple[float, float],
    shaft: float,
    shaft_band: tuple[float, float],
) -> tuple[float, float]:
    """``(least, most)`` diametral clearance of a shaft in a bore, from both
    parts' printed limits (each band is ``(upper, lower)`` deviations)."""
    return (
        bore + min(bore_band) - (shaft + max(shaft_band)),
        bore + max(bore_band) - (shaft + min(shaft_band)),
    )


# The three fit diameters.  Each band (.0008 wide) is narrower than the shop's
# turned-diameter row, so each callout names its fit route (rule 4, "What the
# shop holds") in its two lines of words (rule 7): the fit and its mate above
# the value, the route and the clearance from both parts' printed limits
# under it.  The limits themselves are unchanged.
def fit_route(clearance: tuple[float, float]) -> str:
    """The route row under a fit diameter: turned to the mate's measured bore."""
    least, most = clearance
    return f"TURN TO MEASURED BORE (CLEARANCE {inch_text(least, 4)}-{inch_text(most, 4)})"


SHANK_FIT = "SLIDING FIT IN MHA-DT-31,"
SHANK_ROUTE = fit_route(_clearance(hub.HUB_BORE_DIA, hub.HUB_BORE_BAND, SHAFT_DIA, SHAFT_DIA_BAND))
JOURNAL_FIT = "2X RUNNING FIT IN MHA-DT-05,"
JOURNAL_ROUTE = fit_route(
    _clearance(JOURNAL_BORE_DIA, JOURNAL_BORE_BAND, JOURNAL_DIA, JOURNAL_DIA_BAND)
)
PINION_SEAT_FIT = "SLIDING FIT IN MHA-DT-10,"
PINION_SEAT_ROUTE = fit_route(
    _clearance(pinion.BORE_DIA, pinion.BORE_DIA_BAND, PINION_SEAT_DIA, PINION_SEAT_DIA_BAND)
)

# The sheet's numbered notes, in one block under the general note.
SHEET_NOTES = "\n".join((CROSS_HOLE_NOTE, SPIGOT_NOTE))

# The banded far-end stations name their stack on their own row: a callout
# below would lift the value into the row above.  No AIR (rule 26).
COLLAR_REAR_MATE = " BEARS ON MHA-DT-05"
COLLAR_SEAT_MATE = " MHA-PD-09 SEAT"
SHAFT_LENGTH_MATE = " SETS CLEARANCE MHA-DT-31 TO MHA-PD-09"
# The one Ø.375 ±.010 covers both bare necks; the callout names where they are.
NECKS = "2X"
NECK_LANDS = "BEHIND COLLAR\nAND AT SEAT STEP"

# The thinnest wall round the drive-pin holes, to the seat spigot's rim, at
# the printed worst case (crankshaft_spec rounds it down): stated as the fact
# the shop holds, under the holes' own callout.
# Emits approved declaration dt-crankshaft RV-02 (owner ruling 2026-10-18,
# #991; redesign tracked in #1679).
DRIVE_PIN_RIM_NOTE = f"DRIVE-PIN HOLE TO SPIGOT RIM {inch_text(DRIVE_PIN_SPIGOT_RIM_WORST, 3)} MIN."

# Under the native REAM callout on the seat spigot's two blind holes, two
# lines of words (rule 7): the purchased dowel each is a press fit for and the
# sprocket the pins drive -- the mate the holes' tight locations serve, named
# once here and not on the location dimensions (rule 7: a location carries
# its value and band only) -- then their rim.  How far the dowel goes in is
# the MHA-DT-00 step 4 press, not this sheet's (rule 7: an assembly
# instruction on a part sheet is narration).
DRIVE_PIN_CALLOUT = "\n".join(
    (
        "PRESS FIT PIN MHA-DT-VN-67 FOR SPROCKET MHA-PD-09",
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

# The pins' knockouts (dt_crankshaft_spec DRIVE_PIN_KNOCKOUT_SPEC) print as a
# native Hole Wizard callout on the lower hole's floor: the drill reads above
# the native size so the three short rows fit the field under the end view.
KNOCKOUT_CALLOUT_ABOVE = DRIVE_PIN_KNOCKOUT_PROCESS
KNOCKOUT_CALLOUT_BELOW = "DRIVE-PIN KNOCKOUT"

# The punched witness on the dome, flagged with a leader to the mark itself
# (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).  Its
# spot is free: the MHA-DT-00 hub step aligns it with the hub's mark before
# the taper ream, so any spot on the dome serves.  Rule 26: a plain
# requirement, never BY EYE.  Two rows: a note stacked one word a row read
# as a five-line callout (rule 7), so the note stands below the knockout
# callout where the rows have room.
FIDUCIAL_NOTE = "PUNCH MARK,\nLOCATION NOT CRITICAL"

# The 16T retention-pin hole is match-drilled through the seated pinion's
# boss at assembly.  Its location is the pinion's own radial hole, dimensioned
# on MHA-DT-10 from its boss face, so the callout names that hole as the
# route (rule 4: transferring through the mate; rule 26: a location is never
# a sentence such as AT BOSS MID-LENGTH).  The size line carries the pin's
# REF diameter (the hole is reamed to fit the pin), so no dimension stands on
# the hole's hidden edges (rule 9).  Two lines of words (rule 7); the fit by
# its standard name, matching the MHA-DT-10 sheet (DRIVE FIT ON PIN
# MHA-DT-29).  The pin's flush ends and hand-removal check are the MHA-DT-00
# step 4 acceptance, not this sheet's (rule 7).
PINION_PIN_CALLOUT = "\n".join(
    (
        f"(<MOD-DIAM>{inch_text(pinion.PIN_DIA, pinion.PIN_HOLE_DIA_PLACES)})"
        " MATCH DRILL AND REAM AT ASSEMBLY",
        f"THRU RADIAL HOLE OF PINION {pinion.PINION_NUMBER},",
        f"DRIVE FIT ON PIN {pinion.PIN_NUMBER}",
    )
)

# Where the shop may drill a lathe centre hole (drawing-guidelines.md rule
# 11): the plain far end only, never the dome.  The leader to that
# end's rim is what names the end (rule 7: flag it where it applies); the
# unleadered "AT PLAIN END" row named an end the sheet never identified.  The
# restriction is on the centre hole, a turning location: the dome's punched
# witness (FIDUCIAL_NOTE) is a separate, required mark on the finished
# sphere, which a centre hole would destroy. Keep the four-row text
# unchanged when relocating its native leader: the drawing identifies the
# plain end in FRONT, not by the isometric's apparent top/bottom orientation.
CENTRES_NOTE = "LATHE CENTRE\nHOLE OK HERE;\nNOT IN\nDOME"
