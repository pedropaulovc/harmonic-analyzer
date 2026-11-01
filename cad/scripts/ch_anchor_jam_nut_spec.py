r"""MHA-CH-14 channel-anchor jam nut: dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  A turned brass round
nut, #6-32 tapped through, one on each MHA-CH-VN-51 channel anchor: it runs up
the anchor's protruding shank from below and is jammed against the MHA-SM-03
coefficient plate's underside while the anchor's eye is held at its clocking
(drawing-guidelines.md rule 23; owner ruling 2026-10-17, option A).

Why round, not a stock hex: the 20 anchors stand in one row at the plate's
``CHANNEL_PITCH`` (7.0565 mm, .278 in) centre to centre.  A 1/4 hex collides
corner to corner and no wrench reaches between neighbours.  The round O.D. is
the only free size, pinned between two worst cases: rule 17's .060 wall floor
from the #6-32 major (small O.D.) and the 0.25 mm modelling clearance to the
neighbour (large O.D.), its tap and the neighbour's each at the far edge of
the lever's spring-hole pattern position zone toward the other.  The pitch
leaves no geometry to trade, so the O.D. prints at three places with an
explicit band inside that window (rule 4: tightened for a function, the
neighbour named at the callout; owner ruling 2026-10-17), and the pattern zone
is held at Ø0.15 mm to leave the window open (owner ruling on code review
C06).  The .080 wall target cannot be met inside the pitch; the floor is.
The .060 MIN wall and the 0.6D engagement are declared owner-ruled shortfalls
(``machinist_exceptions`` in ``ch-anchor-jam-nut.yaml``): a thin jam nut locks
and carries no load.

Drive: one saw cut across the lower face gives two diametrically opposite
notches, the bore between them.  A forked driver (a screwdriver blade slotted
up its middle to straddle the anchor end) turns it from below.  Spanner pin
holes cannot fit: the floor-thin wall leaves no room for a pin hole.  The cut
leaves at least the wall floor of full ring between its floor and the bearing
face at the worst case of both bands.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  Lengths
stay physical millimetres, each the exact decimal of its printed inch value.

Part frame: lathe axis +Z, origin on the axis at the bearing face (z = 0,
the face jammed on the plate underside); the driven face, carrying the cut, at
z = THICKNESS.  The cut runs along local X.  ``Axis1`` is the thread axis.
"""

from __future__ import annotations

import math

import _config
from _hole_spec import HoleSpec, THREAD_MAJOR_MM, blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from sm_summing_lever_spec import CHANNEL_PITCH, GEOMETRIC_TOLERANCES_MM, HOLE_SPEC
from stock_anchor_geom import ANCHOR_9489T111

UNIT = drawing_unit("parts/ch-anchor-jam-nut", _config.parts("ch-anchor-jam-nut"))

# One source: the lever's tap names the thread the anchor carries.
THREAD = ANCHOR_9489T111.thread_size
if HOLE_SPEC.size != THREAD:
    raise AssertionError("the jam nut's thread must be the anchor's")
TAP_SPEC = HoleSpec("tapped", THREAD)
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]

MIN_WALL = WALL_FLOOR_MM  # drawing-guidelines.md rule 17 floor (.060)
# spring_mount_geom.MIN_CLEARANCE_MM (0.25) less 0.001: under the lever's
# Ø.006 tap position zone the .002 O.D. band leaves 0.2493 (owner ruling).
NEIGHBOUR_CLEARANCE = 0.249

OD = 6.604  # .260
OD_PLACES = 3
# Explicit, not the .XXX row. The O.D. window runs from the wall floor,
# THREAD_MAJOR + 2 * MIN_WALL = 6.5532 (.2580), to the neighbour gap,
# CHANNEL_PITCH - zone - NEIGHBOUR_CLEARANCE = 6.6541 (.2620) at the lever's
# Ø.006 tap position zone: .004 wide, so the title block's ±.005 cannot fit
# and ±.002 fills it.
OD_BAND = 0.0508  # .002
if OD_BAND >= printed_band_mm(OD_PLACES, unit=UNIT):
    raise AssertionError("the O.D. band is no tighter than the title block's")
OD_MAX = OD + OD_BAND
OD_MIN = OD - OD_BAND

THICKNESS = 3.556  # .14
THICKNESS_PLACES = 2
THICKNESS_MAX = THICKNESS + printed_band_mm(THICKNESS_PLACES, unit=UNIT)
THICKNESS_MIN = THICKNESS - printed_band_mm(THICKNESS_PLACES, unit=UNIT)

SLOT_WIDTH = 1.27  # .05
SLOT_DEPTH = 1.016  # .04
SLOT_PLACES = 2
SLOT_DEPTH_MAX = SLOT_DEPTH + printed_band_mm(SLOT_PLACES, unit=UNIT)
SLOT_DEPTH_MIN = SLOT_DEPTH - printed_band_mm(SLOT_PLACES, unit=UNIT)

# Rule 17 at the worst case of the printed bands.
WALL_WORST = (OD_MIN - THREAD_MAJOR) / 2.0
UNDER_SLOT_WORST = THICKNESS_MIN - SLOT_DEPTH_MAX
# The neighbour on the next tap, both nuts at their largest O.D. and both
# taps displaced toward each other across their RFS position zones: the
# centres close by the whole zone diameter (a zone radius each).
PATTERN_POSITION = float(GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"])
CENTRE_SPACING_WORST = CHANNEL_PITCH - PATTERN_POSITION
NEIGHBOUR_GAP = CHANNEL_PITCH - OD
NEIGHBOUR_GAP_WORST = CENTRE_SPACING_WORST - OD_MAX

if WALL_WORST < MIN_WALL:
    raise AssertionError(f"MHA-CH-14 wall {WALL_WORST:.3f} < {MIN_WALL}")
if UNDER_SLOT_WORST < MIN_WALL:
    raise AssertionError(f"MHA-CH-14 ring under the cut {UNDER_SLOT_WORST:.3f}")
if NEIGHBOUR_GAP_WORST < NEIGHBOUR_CLEARANCE:
    raise AssertionError(f"MHA-CH-14 neighbour gap {NEIGHBOUR_GAP_WORST:.3f}")

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


def _inch_min(value_mm: float, places: int) -> str:
    """A worst case as inch print text, floored so a MIN never overstates it."""
    text = f"{math.floor(value_mm / 25.4 * 10**places + 1e-9) / 10**places:.{places}f}"
    return text.removeprefix("0")


# The O.D.'s band is bounded both ways (reviews r8/r9 read it as a clearance
# size only): the wall to the thread, printed as a fact above the value, and
# the neighbouring nut, named as the mate below it (rule 4) -- twenty nuts
# stand side by side and the neighbour gap holds only inside the band.
OD_WALL_CALLOUT = f"WALL {_inch_min(WALL_WORST, 3)} MIN"
OD_CALLOUT = "CLEARS ADJACENT CHANNEL'S MHA-CH-14 NUT"
# A jam nut is thin by kind, and the stock anchor's shank caps it: the full
# thread it carries at its thinnest, less the incomplete thread a through tap
# leaves, falls short of 1.5D and the sheet states it as a fact.
INCOMPLETE_THREADS = 1.5
ENGAGEMENT_MIN = THICKNESS_MIN - INCOMPLETE_THREADS * ANCHOR_9489T111.thread_pitch_mm
ENGAGEMENT_MIN_D = ENGAGEMENT_MIN / THREAD_MAJOR
THICKNESS_CALLOUT = (
    f"ENGAGEMENT {_inch_min(ENGAGEMENT_MIN, 3)} MIN ({ENGAGEMENT_MIN_D:.1f}D)"
)
# No surface runs or slides: no roughness symbol.
SURFACE_FINISHES: tuple = ()
