r"""MHA-CH-012 channel-anchor jam nut: dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  A turned brass round
nut, #6-32 tapped through, one on each MHA-VN-012 channel anchor: it runs up
the anchor's protruding shank from below and is jammed against the MHA-SM-003
coefficient plate's underside while the anchor's eye is held at its clocking
(drawing-guidelines.md rule 23; coordinator ruling 2026-10-16, option A).

Why round, not a stock hex: the 20 anchors stand in one row at the plate's
``CHANNEL_PITCH`` (7.0565), so neighbouring nuts are 7.06 apart centre to
centre.  A 1/4 hex collides corner to corner and no wrench reaches between
neighbours.  The round O.D. is the only free size, pinned between two worst
cases: rule 17's 1.5 wall floor from the #6-32 major (small O.D.) and the
0.25 modelling clearance to the neighbour (large O.D.).  The pitch leaves no
geometry to trade, so the O.D. prints at three places (the title block's
.XXX row, a plain lathe turning).  The 2.0 wall target cannot be met inside
the pitch; the floor is.

Drive: one saw cut across the lower face gives two diametrically opposite
notches, the bore between them.  A forked driver (a screwdriver blade slotted
up its middle to straddle the anchor end) turns it from below.  Spanner pin
holes cannot fit: the 1.5 wall leaves no room for a pin hole.  The cut
leaves at least the wall floor of full ring between its floor and the bearing
face at the worst case of both bands.

Part frame: lathe axis +Z, origin on the axis at the bearing face (z = 0,
the face jammed on the plate underside); the driven face, carrying the cut, at
z = THICKNESS.  The cut runs along local X.  ``Axis1`` is the thread axis.
"""

from __future__ import annotations

import math

from _hole_spec import HoleSpec, THREAD_MAJOR_MM, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm
from sm_summing_lever_spec import CHANNEL_PITCH, HOLE_SPEC
from stock_anchor_geom import ANCHOR_9489T111

# One source: the lever's tap names the thread the anchor carries.
THREAD = ANCHOR_9489T111.thread_size
if HOLE_SPEC.size != THREAD:
    raise AssertionError("the jam nut's thread must be the anchor's")
TAP_SPEC = HoleSpec("tapped", THREAD)
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]

MIN_WALL = 1.5  # drawing-guidelines.md rule 17 floor
NEIGHBOUR_CLEARANCE = 0.25  # spring_mount_geom.MIN_CLEARANCE_MM (asserted there)

OD = 6.66
OD_PLACES = 3
OD_BAND = printed_band_mm(OD_PLACES)
OD_MAX = OD + OD_BAND
OD_MIN = OD - OD_BAND

THICKNESS = 3.60
THICKNESS_PLACES = 2
THICKNESS_MAX = THICKNESS + printed_band_mm(THICKNESS_PLACES)
THICKNESS_MIN = THICKNESS - printed_band_mm(THICKNESS_PLACES)

SLOT_WIDTH = 1.20
SLOT_DEPTH = 1.00
SLOT_PLACES = 2
SLOT_DEPTH_MAX = SLOT_DEPTH + printed_band_mm(SLOT_PLACES)
SLOT_DEPTH_MIN = SLOT_DEPTH - printed_band_mm(SLOT_PLACES)

# Rule 17 at the worst case of the printed bands.
WALL_WORST = (OD_MIN - THREAD_MAJOR) / 2.0
UNDER_SLOT_WORST = THICKNESS_MIN - SLOT_DEPTH_MAX
# The neighbour on the next tap, both nuts at their largest O.D.
NEIGHBOUR_GAP = CHANNEL_PITCH - OD
NEIGHBOUR_GAP_WORST = CHANNEL_PITCH - OD_MAX

if WALL_WORST < MIN_WALL:
    raise AssertionError(f"MHA-CH-012 wall {WALL_WORST:.3f} < {MIN_WALL}")
if UNDER_SLOT_WORST < MIN_WALL:
    raise AssertionError(f"MHA-CH-012 ring under the cut {UNDER_SLOT_WORST:.3f}")
if NEIGHBOUR_GAP_WORST < NEIGHBOUR_CLEARANCE:
    raise AssertionError(f"MHA-CH-012 neighbour gap {NEIGHBOUR_GAP_WORST:.3f}")

# Marked model dimensions and the places the part authors on them
# (drawing-simplicity-policy.md): every size takes the title block's row for
# its places; the tap is a Hole Wizard callout.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "NutProfile": {"NutOd"},
    "Nut": {"NutThickness"},
    "DriveSlotProfile": {"SlotWidth"},
    "DriveSlot": {"SlotDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "NutProfile": {"NutOd": OD_PLACES},
    "Nut": {"NutThickness": THICKNESS_PLACES},
    "DriveSlotProfile": {"SlotWidth": SLOT_PLACES},
    "DriveSlot": {"SlotDepth": SLOT_PLACES},
}

# The Hole Wizard cuts the tap-drill cylinder; the thread is cosmetic.
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
# The sketch rectangle's span along X: past the O.D. so the cut runs out both
# sides (a construction size, not marked for the drawing).
SLOT_SPAN = OD + 2.0
# Rule 12 (hole and slot callouts say what to do), without naming a method.
SLOT_CALLOUT = "SLOT THRU ACROSS"
# The O.D.'s three places are bounded both ways (review r8 read them as a
# clearance size only): the wall to the thread below, printed as a fact
# above the value, and the neighbouring nut above, named below it -- twenty
# nuts stand side by side at the anchor pitch and the 0.25 gap holds only
# at the .XXX band.
OD_WALL_CALLOUT = f"WALL {math.floor(WALL_WORST * 10) / 10:.1f} MIN"
OD_CALLOUT = "CLEARS NEXT MHA-CH-012"
# A jam nut is thin by kind, and the stock anchor's shank caps it: the full
# thread it carries at its thinnest, less the incomplete thread a through tap
# leaves, falls short of 1.5D and the sheet states it as a fact.
INCOMPLETE_THREADS = 1.5
ENGAGEMENT_MIN = THICKNESS_MIN - INCOMPLETE_THREADS * ANCHOR_9489T111.thread_pitch_mm
ENGAGEMENT_MIN_D = ENGAGEMENT_MIN / THREAD_MAJOR
THICKNESS_CALLOUT = f"ENGAGEMENT {ENGAGEMENT_MIN:.1f} MIN ({ENGAGEMENT_MIN_D:.1f}D)"
# No surface runs or slides: no roughness symbol.
SURFACE_FINISHES: tuple = ()
