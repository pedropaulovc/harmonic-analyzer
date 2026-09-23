r"""Pure-data contract for MHA-139, the crank handle pivot screw (user ruling U33).

A made slotted shoulder screw turned from 3/8-in cold-finished rod.  The oak
handle MHA-022 spins on the shoulder; the thread screws into the crank arm
MHA-020's #10-24 tapped through hole and the shoulder seats tight on the arm
face, so the shoulder length alone sets the handle's end play.

Local frame: the axis is local +Z.  The slotted head face is at z=0, the head
runs to the under-head face at z=HEAD_LENGTH, the shoulder to the arm seat face
at z=HEAD_LENGTH+SHOULDER_LENGTH, and the threaded section (a thread-relief
groove against the seat face, then the full thread) to the tip at
z=OVERALL_LENGTH.

PURE DATA, no SolidWorks/COM imports.  The part build and the drawing both read
these names; the derived fit facts below are asserted at import so a retune of
the handle, the arm or this screw that breaks the running fit fails before any
CAD is built.
"""

from __future__ import annotations

import math

from _gtol_spec import CylinderFace
from _hole_spec import THREAD_MAJOR_MM
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from crank_handle_spec import (
    HANDLE_LENGTH,
    HANDLE_LENGTH_BAND,
    PIVOT_BORE_BAND,
    PIVOT_BORE_DIA,
)
from crank_hub_geometry import (
    ARM_THICKNESS,
    EDGE_BREAK_MAX_MM,
    GENERAL_1PL_TOL_MM,
    GENERAL_2PL_TOL_MM,
    MM_PER_IN,
)


STOCK_DIA = 0.375 * MM_PER_IN

HEAD_DIA = 8.0
HEAD_LENGTH = 3.0
SLOT_WIDTH = 1.0
SLOT_DEPTH = 1.0

# The running surface under the oak bore.  (upper, lower) deviations from the
# Ø6.00 nominal; the model carries the band natively (policy rule 2).
SHOULDER_DIA = 6.00
SHOULDER_DIA_BAND = (-0.03, -0.08)
SHOULDER_LENGTH = 58.50
SHOULDER_LENGTH_TOL = 0.25

THREAD_SIZE = "#10-24"
# The threaded section is modelled as a plain cylinder at the basic #10 major
# diameter, the fleet convention for a stock screw in a tap-drill-modelled hole.
THREAD_MODEL_DIA = THREAD_MAJOR_MM[THREAD_SIZE]
# 9.0 +0/-0.5 (Main, on U33b): the shortest thread section, 8.5, less the
# 0.5 tip chamfer still carries full thread across the arm's 7.94 (5/16-in)
# stock thickness, so the ARM governs the worst-case engagement, not the
# screw.  Fixed by geometry, not a tighter relief band (U27).  The price is a
# tip standing up to PROUD_INBOARD_MAX past the arm's inboard face.
THREAD_LENGTH = 9.0
THREAD_LENGTH_BAND = (0.0, -0.5)
# 45-degree thread-start chamfer on the tip, about the thread depth.  Like the
# relief lead, the model holds the 45 degrees by equation and the print gives
# the axial leg with an "X 45 DEG" callout.
TIP_CHAMFER = 0.5
# The title block states the UN thread class, so the callout names no class.
THREAD_CALLOUT = f"{THREAD_SIZE} UNC"
THREAD_PITCH = MM_PER_IN / 24.0
# #10-24 external minor diameter.  ASSUMPTION, not sourced from ASME B1.1 in
# this repo: the UN basic profile with its P/8 root flat puts the root at
# major - 1.5 H = major - 1.299038 P = 3.451, which is exactly the root the
# McMaster 91829A560 vendor model cuts (diagnostics/diag_build_91829A560.py,
# ROOT_R 1.7256).  The UNR-2A reference maximum, major max 0.1890 in less
# 1.226869 P (17/24 H each side), is 0.1379 in = 3.503.  The relief floor sits
# at or below the smaller of the two so the die's incomplete threads clear it.
THREAD_MINOR_BASIC_ROOT = THREAD_MODEL_DIA - 1.5 * math.sqrt(3.0) / 2.0 * THREAD_PITCH
THREAD_MINOR_UNR_2A_MAX = (0.1890 - 1.226869 / 24.0) * MM_PER_IN
# Thread relief (Main's ruling on the die-runout doubt, amended to Ø3.4): a
# groove in the first RELIEF_WIDTH of the threaded section, against the seat
# face, so the die's incomplete lead threads run out into air and the shoulder
# pulls down tight on the arm face.  Routine (.X) sizes under the title-block
# band.
RELIEF_DIA = 3.4
RELIEF_WIDTH = 1.5
# A 45-degree lead from the relief floor up into the seat face, so the groove
# leaves no sharp inside corner.  0.5 keeps the lead inside the Ø4.826 thread
# major, i.e. inside the arm's tapped hole, so the whole seat annulus that
# bears on the arm face stays flat.  The 45 degrees is enforced in the model by
# an equation, and printed as a callout on the lead's axial size.
RELIEF_LEAD = 0.5
CHAMFER_CALLOUT = "X 45 DEG"
# The 45-degree lead rides the relief's Ø callout rather than a third
# dimension crowded into the 1.5-mm groove at 3:1 (machinist review).
RELIEF_CALLOUT = f"{RELIEF_LEAD:.1f} {CHAMFER_CALLOUT} LEAD"
SEAT_FLAT_INNER_DIA = RELIEF_DIA + 2.0 * RELIEF_LEAD

SEAT_STATION = HEAD_LENGTH + SHOULDER_LENGTH
RELIEF_END_STATION = SEAT_STATION + RELIEF_WIDTH
OVERALL_LENGTH = SEAT_STATION + THREAD_LENGTH

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_shoulder",
        MACHINED_UM,
        CylinderFace(
            SHOULDER_DIA,
            contains_z_mm=HEAD_LENGTH + SHOULDER_LENGTH / 2.0,
        ),
    ),
)


def _limits(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    """``(minimum, maximum)`` of an ``(upper, lower)`` deviation band."""
    upper, lower = band
    return round(nominal + lower, 6), round(nominal + upper, 6)


SHOULDER_DIA_MIN, SHOULDER_DIA_MAX = _limits(SHOULDER_DIA, SHOULDER_DIA_BAND)
SHOULDER_LENGTH_MIN, SHOULDER_LENGTH_MAX = _limits(
    SHOULDER_LENGTH, (SHOULDER_LENGTH_TOL, -SHOULDER_LENGTH_TOL)
)
THREAD_LENGTH_MIN, THREAD_LENGTH_MAX = _limits(THREAD_LENGTH, THREAD_LENGTH_BAND)
HANDLE_LENGTH_MIN, HANDLE_LENGTH_MAX = _limits(HANDLE_LENGTH, HANDLE_LENGTH_BAND)
HANDLE_BORE_MIN, HANDLE_BORE_MAX = _limits(PIVOT_BORE_DIA, PIVOT_BORE_BAND)

# The shoulder seats on the arm face, so the handle runs between the arm and
# the under-head face: end play is shoulder length less wood overall.
END_PLAY_MIN = round(SHOULDER_LENGTH_MIN - HANDLE_LENGTH_MAX, 6)
END_PLAY_MAX = round(SHOULDER_LENGTH_MAX - HANDLE_LENGTH_MIN, 6)
# Wood-on-steel running clearance, on diameter.
DIAMETRAL_CLEARANCE_MIN = round(HANDLE_BORE_MIN - SHOULDER_DIA_MAX, 6)
DIAMETRAL_CLEARANCE_MAX = round(HANDLE_BORE_MAX - SHOULDER_DIA_MIN, 6)
# Engagement in the MHA-020 tapped through hole.  The relief sits in the arm's
# first RELIEF_WIDTH below the seat face, so only the full thread beyond it
# engages, and never deeper than the arm is thick.
#
# U33b (2026-09-23): user accepted ~1.2D steel-in-steel for MHA-139 in the
# MHA-020 arm; exception to the 1.5D rule.
ENGAGEMENT_EXCEPTION_FLOOR_D = 1.15
ENGAGEMENT_FLOOR = ENGAGEMENT_EXCEPTION_FLOOR_D * THREAD_MODEL_DIA
# The arm is 5/16-in cold-finished flat bar left at stock thickness; its
# printed 8.0 carries the .X title-block band.
ARM_STOCK_THICKNESS = 0.3125 * MM_PER_IN
ARM_PRINTED_THICKNESS_MAX = ARM_THICKNESS + GENERAL_1PL_TOL_MM
# The relief width prints at .XX (Main, on the rule-12 audit note): at .X its
# +0.8 alone took the stock-arm case under the U33b floor once the tapped
# hole's exit edge break is counted.  A lathe shoulder length holds 0.5 as
# easily as the shoulder's own 0.25.
RELIEF_WIDTH_MAX = round(RELIEF_WIDTH + GENERAL_2PL_TOL_MM, 6)
# The title-block edge break on the tapped hole's inboard exit edge takes up
# to its size of thread off the arm end of the engagement.
TAP_EXIT_BREAK = EDGE_BREAK_MAX_MM
# The tip chamfer's threads are partial, so full thread ends TIP_CHAMFER short
# of the tip: FULL_THREAD_REACH is the full-thread end measured from the seat
# face.  Which side governs each case is the smaller term of the min().
FULL_THREAD_REACH_NOMINAL = round(THREAD_LENGTH - TIP_CHAMFER, 6)
FULL_THREAD_REACH_MIN = round(THREAD_LENGTH_MIN - TIP_CHAMFER, 6)
FULL_THREAD_NOMINAL = round(
    min(FULL_THREAD_REACH_NOMINAL, ARM_THICKNESS) - RELIEF_WIDTH, 6
)
# Worst case in the stock arm: min(full-thread reach, arm 7.94 less the exit
# break) - relief 2.01.
FULL_THREAD_WORST = round(
    min(FULL_THREAD_REACH_MIN, ARM_STOCK_THICKNESS - TAP_EXIT_BREAK)
    - RELIEF_WIDTH_MAX,
    6,
)
ENGAGEMENT_GOVERNED_BY = (
    "arm"
    if ARM_STOCK_THICKNESS - TAP_EXIT_BREAK <= FULL_THREAD_REACH_MIN
    else "screw"
)
# Worst case in an arm at its printed maximum 8.8: the screw always governs.
FULL_THREAD_WORST_PRINTED_ARM = round(
    min(FULL_THREAD_REACH_MIN, ARM_PRINTED_THICKNESS_MAX - TAP_EXIT_BREAK)
    - RELIEF_WIDTH_MAX,
    6,
)
FULL_THREAD_NOMINAL_DIAMETERS = FULL_THREAD_NOMINAL / THREAD_MODEL_DIA
FULL_THREAD_WORST_DIAMETERS = FULL_THREAD_WORST / THREAD_MODEL_DIA
FULL_THREAD_WORST_PRINTED_ARM_DIAMETERS = (
    FULL_THREAD_WORST_PRINTED_ARM / THREAD_MODEL_DIA
)
# The tip may stand proud of the arm's inboard face by up to this much.
PROUD_INBOARD_MAX = round(THREAD_LENGTH_MAX - ARM_STOCK_THICKNESS, 6)
# The one manufacturing note: the accepted exception, rendered from the floor.
# The ruling ID (U33b) stays here; it means nothing to the book's reader.
DRAWING_NOTES = (
    f"THREAD ENGAGEMENT {ENGAGEMENT_EXCEPTION_FLOOR_D:.2f}D MIN, "
    "ACCEPTED EXCEPTION TO THE 1.5D RULE."
)

# Flat seat annulus that bears on the arm face, outside the 45-degree lead:
# nominal, and after the minimum shoulder and the title-block edge break.
SEAT_FLAT_ANNULUS_AREA = math.pi / 4.0 * (SHOULDER_DIA**2 - SEAT_FLAT_INNER_DIA**2)
SEAT_FLAT_ANNULUS_AREA_MIN = (
    math.pi
    / 4.0
    * ((SHOULDER_DIA_MIN - 2.0 * EDGE_BREAK_MAX_MM) ** 2 - SEAT_FLAT_INNER_DIA**2)
)
# The relief neck is the screw's weakest section: pi/4 x 3.4^2 = 9.08 mm^2
# against the #10-24 UNC tensile stress area of 0.0175 in^2 = 11.29 mm^2, about
# 80 percent.  Seating torque is therefore limited by the neck, not the thread;
# the handle's working load is a hand grip and never loads it axially.
NECK_AREA = math.pi / 4.0 * RELIEF_DIA**2
TENSILE_STRESS_AREA = 0.0175 * MM_PER_IN**2
NECK_TO_STRESS_AREA = NECK_AREA / TENSILE_STRESS_AREA

for _ok, _what in (
    (END_PLAY_MIN > 0.0, "handle is clamped: no end play at worst case"),
    (END_PLAY_MAX <= 1.0, "handle end play exceeds 1.0 at worst case"),
    (DIAMETRAL_CLEARANCE_MIN > 0.0, "shoulder can bind in the oak bore"),
    (
        RELIEF_DIA <= min(THREAD_MINOR_BASIC_ROOT, THREAD_MINOR_UNR_2A_MAX),
        "relief floor stands above the #10-24 external minor diameter",
    ),
    (RELIEF_WIDTH < THREAD_LENGTH, "relief consumes the whole thread section"),
    (RELIEF_LEAD < RELIEF_WIDTH, "relief lead consumes the relief floor"),
    (
        SEAT_FLAT_INNER_DIA < THREAD_MODEL_DIA,
        "relief lead reaches past the thread major into the seat annulus",
    ),
    (SEAT_FLAT_ANNULUS_AREA_MIN > 0.0, "no flat seat annulus is left"),
    (
        FULL_THREAD_WORST >= ENGAGEMENT_FLOOR,
        "stock-arm worst-case engagement is under the U33b floor",
    ),
    (
        FULL_THREAD_WORST_PRINTED_ARM >= ENGAGEMENT_FLOOR,
        "printed-arm worst-case engagement is under the U33b floor",
    ),
    (
        THREAD_LENGTH_MIN >= ARM_STOCK_THICKNESS,
        "shortest thread section does not span the stock arm",
    ),
    (
        TIP_CHAMFER <= 0.61343 * THREAD_PITCH,
        "tip chamfer cuts deeper than the #10-24 thread (17/24 H)",
    ),
    (
        TIP_CHAMFER + RELIEF_WIDTH < THREAD_LENGTH_MIN,
        "tip chamfer and relief leave no full thread",
    ),
    (len(DRAWING_NOTES) <= 72, "U33b note line is over 72 characters"),
    (HEAD_DIA > HANDLE_BORE_MAX, "head passes through the handle bore"),
    (HEAD_DIA < STOCK_DIA, "head is not turnable from 3/8-in rod"),
    (SHOULDER_DIA_MIN > THREAD_MODEL_DIA, "shoulder has no seat annulus"),
    (HEAD_LENGTH - SLOT_DEPTH >= 2.0, "under 2.0 of head remains under the slot"),
):
    if not _ok:
        raise AssertionError(f"MHA-139: {_what}")

# Lengths are one baseline from the UNDER-HEAD face (policy rule 7): the head
# and the shoulder both start there, it is the face the handle runs against,
# and it is the face the shop indicates after reversing the part to face and
# slot the head.  The shoulder length therefore prints directly with its own
# band and sets the end play without a stack.  The thread length is the SIZE
# of the threaded feature from the arm seat face, not a location; printing it
# as a 66.50 station from the under-head face would stack the shoulder's
# +/-0.25 onto the thread's -0.5 that the engagement check needs separate.
# The relief width and the two 45-degree legs are likewise sizes.  The overall
# is a reference restatement for stock cut-off.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ScrewProfile": {
        "HeadDia",
        "HeadLength",
        "ShoulderDia",
        "ShoulderLength",
        "ThreadLength",
        "ReliefDia",
        "ReliefWidth",
        "TipChamfer",
    },
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
    "StationReference": {"OverallLength"},
}
# Decimal places ARE the tolerance (policy rule 2): the two shoulder sizes are
# the running fit and print their bands at two places, and the relief width
# prints at two places for the U33b engagement floor; every other size is
# routine (.X).  The thread length carries its own +0/-0.5 band at one place.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ScrewProfile": {
        "HeadDia": 1,
        "HeadLength": 1,
        "ShoulderDia": 2,
        "ShoulderLength": 2,
        "ThreadLength": 1,
        "ReliefDia": 1,
        "ReliefWidth": 2,
        "TipChamfer": 1,
    },
    "SlotProfile": {"SlotWidth": 1},
    "DriverSlot": {"SlotDepth": 1},
    "StationReference": {"OverallLength": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-139 dimension needs authored places")
REFERENCE_DIMENSIONS = frozenset({"OverallLength"})

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:1"
