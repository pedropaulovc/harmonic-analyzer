r"""Pure-data contract for MHA-139, the crank handle pivot screw (user ruling U33).

A made slotted shoulder screw turned from 3/8-in cold-finished rod.  The oak
handle MHA-022 spins on the shoulder; the thread screws into the crank arm
MHA-020's #8-32 tapped through hole and the shoulder seats tight on the arm
face, so the shoulder length alone sets the handle's end play.  The tip is
filed flush with the arm's inboard face at assembly (``INSTALLED_CONFIG``).

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
from crank_handle_butt_cup_spec import (
    BODY_DIA as CUP_BODY_DIA,
    BODY_DIA_TOL as CUP_BODY_DIA_TOL,
    FLANGE_THICKNESS as CUP_FLANGE_THICKNESS,
    FLOOR_HOLE_DIA as CUP_FLOOR_HOLE_DIA,
    POCKET_CLEARANCE as CUP_POCKET_CLEARANCE,
    POCKET_DEPTH as CUP_POCKET_DEPTH,
    POCKET_DEPTH_TOL as CUP_POCKET_DEPTH_TOL,
    POCKET_DIA as CUP_POCKET_DIA,
    WALL_FLOOR_MM,
)
from crank_handle_ferrule_spec import LENGTH as FERRULE_LENGTH
from crank_handle_spec import (
    HANDLE_LENGTH,
    PIVOT_BORE_BAND,
    PIVOT_BORE_DIA,
    WOOD_LENGTH,
)
from crank_hub_geometry import (
    ARM_STOCK_THICKNESS,
    ARM_STOCK_THICKNESS_MIN,
    ARM_THICKNESS,
    EDGE_BREAK_MAX_MM,
    GENERAL_1PL_TOL_MM,
    MM_PER_IN,
)


STOCK_DIA = 0.375 * MM_PER_IN

# User ruling 2026-09-29 (ch11 p.14): the head sits recessed in the MHA-153
# butt cup's pocket, which is bored to suit it, and bears on the cup floor.
# Its +/-0.10 band keeps a bearing annulus outside the drilled floor hole at
# the worst case, after an edge break on each.
HEAD_DIA = 8.0
HEAD_DIA_TOL = 0.10
# A 4.0 head (user ruling 2026-09-29, MHA-139 machinist review): with the
# slot's own band below, the worst case leaves 2.0 of head under the slot,
# not 0.4.  Banded (Codex P2 on #1139, user ruling 2026-09-30): at .X the
# longest head, at the widest fitted end play, stood 1.6 proud of the cup.
HEAD_LENGTH = 4.0
HEAD_LENGTH_TOL = 0.10
SLOT_WIDTH = 1.0
# Banded (MHA-139 re-review): at .X the slot could print as nothing.
SLOT_DEPTH = 1.0
SLOT_DEPTH_TOL = 0.20

# The running surface under the oak bore.  (upper, lower) deviations from the
# Ø6.00 nominal; the model carries the band natively (policy rule 2).
SHOULDER_DIA = 6.00
SHOULDER_DIA_BAND = (-0.03, -0.08)
# Arm face to the head's underside, which bears on the MHA-153 cup floor.
# User ruling 2026-09-29 (after the machinist reviews): the shoulder is
# turned to suit the bonded handle -- its measured length from the ferrule's
# arm face to the cup floor, plus the end play -- so no part in the handle
# stack carries a band for it.  The model carries the nominal stack plus the
# nominal end play, printed as a reference under the to-suit callout.
END_PLAY_RANGE = (0.25, 1.00)
END_PLAY_NOMINAL = 0.5
HANDLE_STACK_NOMINAL = round(
    FERRULE_LENGTH + WOOD_LENGTH + CUP_FLANGE_THICKNESS - CUP_POCKET_DEPTH, 6
)
SHOULDER_LENGTH = round(HANDLE_STACK_NOMINAL + END_PLAY_NOMINAL, 6)

# #8-32, not U33's #10-24 (Main, U29/1.25D follow-up, 2026-09-25): the arm
# governs the worst-case engagement, so the only lever on its D count at the
# current bands is D itself.  #10-24 gave 1.15D, 0.005D over the U33b floor;
# #8-32 gives 1.34D with the same relief width and thread length.
THREAD_SIZE = "#8-32"
# The threaded section is modelled as a plain cylinder at the basic #8 major
# diameter, the fleet convention for a stock screw in a tap-drill-modelled hole.
THREAD_MODEL_DIA = THREAD_MAJOR_MM[THREAD_SIZE]
# 10.0 +0/-0.5: the shortest thread section, 9.5, less the relief and 1.5
# pitches of die run-in still carries full thread across the arm's 7.94
# (5/16-in) stock thickness, so the ARM governs the worst-case engagement,
# not the screw (the 9.0 of U33b left the MHA-139 machinist review short).
# The tip is cut proud of the arm's inboard face and filed flush at assembly
# (below).
THREAD_LENGTH = 10.0
THREAD_LENGTH_BAND = (0.0, -0.5)
# 45-degree thread-start chamfer on the tip, inside the 0.49 thread depth.
# Like the relief lead, the model holds the 45 degrees by equation and the
# print gives the axial leg with an "X 45 DEG" callout.  Banded (MHA-139
# re-review): at .X the 0.4 could print as nothing; +0.05/-0.10 keeps a real
# chamfer that never cuts past the thread depth.
TIP_CHAMFER = 0.4
TIP_CHAMFER_BAND = (0.05, -0.10)
# The title block states the UN thread class, so the callout names no class.
THREAD_CALLOUT = f"{THREAD_SIZE} UNC"
THREADS_PER_IN = 32
THREAD_PITCH = MM_PER_IN / THREADS_PER_IN
# #8-32 external minor diameter.  ASSUMPTION, not sourced from ASME B1.1 in
# this repo: the UN basic profile with its P/8 root flat puts the root at
# major - 1.5 H = major - 1.299038 P = 3.135 (the same construction gives
# #10-24's 3.451, the root the McMaster 91829A560 vendor model cuts).  The
# UNR-2A reference maximum, 2A major max 0.1631 in (0.164 basic less the
# 0.0009 allowance) less 1.226869 P (17/24 H each side), is 0.1248 in =
# 3.169.  The relief floor sits at or below the smaller of the two so the
# die's incomplete threads clear it.
THREAD_MAJOR_2A_MAX_IN = 0.1631
THREAD_MINOR_BASIC_ROOT = THREAD_MODEL_DIA - 1.5 * math.sqrt(3.0) / 2.0 * THREAD_PITCH
THREAD_MINOR_UNR_2A_MAX = (
    THREAD_MAJOR_2A_MAX_IN - 1.226869 / THREADS_PER_IN
) * MM_PER_IN
# Thread relief (Main's ruling on the die-runout doubt; Ø3.0 under the #8-32
# root): a groove in the first RELIEF_WIDTH of the threaded section, against
# the seat face, so the die's incomplete lead threads run out into air and the shoulder
# pulls down tight on the arm face.  Routine (.X) sizes under the title-block
# band.
RELIEF_DIA = 3.0
RELIEF_WIDTH = 1.5
# A 45-degree lead from the relief floor up into the seat face, so the groove
# leaves no sharp inside corner.  0.5 keeps the lead inside the Ø4.166 thread
# major, i.e. inside the arm's tapped hole, so the whole seat annulus that
# bears on the arm face stays flat.  The 45 degrees is enforced in the model by
# an equation, and printed as a callout on the lead's axial size, as limits
# (MHA-139 re-review: at .X the lead could print as nothing).
RELIEF_LEAD = 0.4
RELIEF_LEAD_LIMITS = (0.3, 0.5)
CHAMFER_CALLOUT = "X 45 DEG"
# The 45-degree lead rides the relief's Ø callout rather than a third
# dimension crowded into the 1.5-mm groove at 3:1 (machinist review).
RELIEF_CALLOUT = (
    f"{RELIEF_LEAD_LIMITS[0]:.1f}-{RELIEF_LEAD_LIMITS[1]:.1f} {CHAMFER_CALLOUT} LEAD"
)
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
THREAD_LENGTH_MIN, THREAD_LENGTH_MAX = _limits(THREAD_LENGTH, THREAD_LENGTH_BAND)
HANDLE_BORE_MIN, HANDLE_BORE_MAX = _limits(PIVOT_BORE_DIA, PIVOT_BORE_BAND)

# Head top below the cup's flange face at nominal: the head reads recessed in
# the cup (the photographs).
HEAD_RECESS_NOMINAL = round(HANDLE_LENGTH - (SHOULDER_LENGTH + HEAD_LENGTH), 6)
# ... and at the printed worst case (Codex P2 on #1139): the shallowest pocket
# over the longest head, with the handle pushed to the arm so the fitted end
# play opens under the head at its widest.  The shoulder is fitted to the
# cup floor, so neither the handle stack nor the cup overall enters.
HEAD_RECESS_WORST = round(
    (CUP_POCKET_DEPTH - CUP_POCKET_DEPTH_TOL)
    - (HEAD_LENGTH + HEAD_LENGTH_TOL)
    - END_PLAY_RANGE[1],
    6,
)
# The pocket is bored to suit the actual head, so its wall is judged at the
# largest head plus the widest clearance, inside the smallest cup body.
POCKET_MAX = HEAD_DIA + HEAD_DIA_TOL + CUP_POCKET_CLEARANCE[1]
CUP_POCKET_WALL_MIN = round(((CUP_BODY_DIA - CUP_BODY_DIA_TOL) - POCKET_MAX) / 2.0, 6)
# The slot's worst-case web: the shortest head under the deepest slot.
SLOT_WEB_MIN = round(
    HEAD_LENGTH - HEAD_LENGTH_TOL - (SLOT_DEPTH + SLOT_DEPTH_TOL), 6
)
TIP_CHAMFER_MIN, TIP_CHAMFER_MAX = (
    round(TIP_CHAMFER + TIP_CHAMFER_BAND[1], 6),
    round(TIP_CHAMFER + TIP_CHAMFER_BAND[0], 6),
)
# Under-head bearing annulus on the cup floor at the worst case: the smallest
# head over the largest drilled floor hole, less a title-block edge break on
# each.
_FLOOR_HOLE_MAX = CUP_FLOOR_HOLE_DIA + 0.10  # DRILLED HOLES +0.10/0
HEAD_BEARING_RADIAL_MIN = round(
    ((HEAD_DIA - HEAD_DIA_TOL) - _FLOOR_HOLE_MAX) / 2.0 - 2.0 * EDGE_BREAK_MAX_MM, 6
)
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
# The arm is 5/16-in cold-finished flat bar left at stock thickness
# (crank_hub_geometry.ARM_STOCK_THICKNESS).  Its sheet prints the 8.0 as a
# reference to that stock (Codex #892: a toleranced 8.0 took the .X band and
# accepted a 7.2 arm, 1.02D), so the thinnest accepted arm is the mill's
# ARM_STOCK_THICKNESS_MIN.  The thick side keeps the .X band as a bound on
# what the model allows.
ARM_PRINTED_THICKNESS_MAX = ARM_THICKNESS + GENERAL_1PL_TOL_MM
# The relief width is a routine .X size (MHA-139 re-review, 2026-09-29).  The
# .XX band it once carried held the #10-24 thread over the U33b floor; the
# #8-32 thread clears the floor at .X too (asserted below), and the printed
# engagement minimum follows from it.
RELIEF_WIDTH_MAX = round(RELIEF_WIDTH + GENERAL_1PL_TOL_MM, 6)
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
# Worst case in the thinnest stock arm: min(full-thread reach, arm 7.84 less
# the exit break) - relief 2.01.
FULL_THREAD_WORST = round(
    min(FULL_THREAD_REACH_MIN, ARM_STOCK_THICKNESS_MIN - TAP_EXIT_BREAK)
    - RELIEF_WIDTH_MAX,
    6,
)
ENGAGEMENT_GOVERNED_BY = (
    "arm"
    if ARM_STOCK_THICKNESS_MIN - TAP_EXIT_BREAK <= FULL_THREAD_REACH_MIN
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
# User ruling 2026-09-29 (ch11 p.14 re-check): the photographs show no screw
# end on the arm's inboard face, so the screw is cut long, seated with its
# threadlocker, then filed flush with that face and its edge broken.  The
# drive train places that fitted state as the INSTALLED configuration (the
# MHA-135 precedent); the default stays the as-turned screw the sheet prints.
# Filing removes at most FILE_ALLOWANCE_MAX, and even the shortest screw in
# the thickest stock arm carries full thread past the face before filing, so
# nothing of the tip chamfer survives and the arm still governs engagement.
INSTALLED_CONFIG = "INSTALLED"
# Flush with the modelled arm, which carries the printed 8.0.
INSTALLED_THREAD_LENGTH = ARM_THICKNESS
INSTALLED_TIP_CHAMFER = EDGE_BREAK_MAX_MM
ARM_STOCK_THICKNESS_MAX = 2.0 * ARM_STOCK_THICKNESS - ARM_STOCK_THICKNESS_MIN
FILE_ALLOWANCE_MAX = round(THREAD_LENGTH_MAX - ARM_STOCK_THICKNESS_MIN, 6)
FILE_ALLOWANCE_MIN = round(FULL_THREAD_REACH_MIN - ARM_STOCK_THICKNESS_MAX, 6)
# The one manufacturing note: the named exception, stated with the worst-case
# engagement its policy row records (the stock arm, after the exit break) and
# worded like the other sheets' rule-12 statements.  The ruling ID (U33b)
# stays here; it means nothing to the book's reader.
# A MIN never rounds up: 1.155 prints 1.15, floored to two places.
FULL_THREAD_WORST_DIAMETERS_PRINTED = math.floor(FULL_THREAD_WORST_DIAMETERS * 100.0) / 100.0
# Named exception: MHA-139 engagement (drawing-simplicity-policy.md, "Named exceptions").
ENGAGEMENT_NOTE = (
    f"THREAD ENGAGEMENT {FULL_THREAD_WORST_DIAMETERS_PRINTED:.2f}D MIN."
)
# The fitted shoulder and the head band's reason, stated once (user ruling
# 2026-09-29, after the MHA-139 machinist review).
DRAWING_NOTES = "\n".join(
    (
        ENGAGEMENT_NOTE,
        "FACE THE UNDER-HEAD TO SUIT THE BONDED MHA-022: UNDER-HEAD TO SEAT =",
        "  ITS FERRULE FACE TO CUP FLOOR PLUS "
        f"{END_PLAY_RANGE[0]:.2f}-{END_PLAY_RANGE[1]:.2f}. THE HEAD BEARS ON THE",
        f"  MHA-153 FLOOR; THE BAND KEEPS {HEAD_BEARING_RADIAL_MIN:.1f} BEARING OUTSIDE ITS HOLE.",
    )
)

# Flat seat annulus that bears on the arm face, outside the 45-degree lead:
# nominal, and after the minimum shoulder and the title-block edge break.
SEAT_FLAT_ANNULUS_AREA = math.pi / 4.0 * (SHOULDER_DIA**2 - SEAT_FLAT_INNER_DIA**2)
SEAT_FLAT_ANNULUS_AREA_MIN = (
    math.pi
    / 4.0
    * ((SHOULDER_DIA_MIN - 2.0 * EDGE_BREAK_MAX_MM) ** 2 - SEAT_FLAT_INNER_DIA**2)
)
# The relief neck is the screw's weakest section: pi/4 x 3.0^2 = 7.07 mm^2
# against the #8-32 UNC tensile stress area of 0.0140 in^2 = 9.03 mm^2, about
# 78 percent.  Seating torque is therefore limited by the neck, not the thread;
# the handle's working load is a hand grip and never loads it axially.
NECK_AREA = math.pi / 4.0 * RELIEF_DIA**2
TENSILE_STRESS_AREA = 0.0140 * MM_PER_IN**2
NECK_TO_STRESS_AREA = NECK_AREA / TENSILE_STRESS_AREA

# User ruling 2026-09-25 (MHA-020 review B2): the exception stands because a
# steel screw in a steel tap develops full strength at about 1D of full
# thread.  Below 1D that reason is gone, whatever the U33b floor says.
FULL_STRENGTH_ENGAGEMENT_D = 1.0
for _ok, _what in (
    (
        min(FULL_THREAD_WORST, FULL_THREAD_WORST_PRINTED_ARM)
        >= FULL_STRENGTH_ENGAGEMENT_D * THREAD_MODEL_DIA,
        "worst-case engagement is under 1D: the steel-in-steel full-strength "
        "reason for the named exception no longer holds",
    ),
    (
        END_PLAY_RANGE[0] <= END_PLAY_NOMINAL <= END_PLAY_RANGE[1],
        "the modelled end play is outside the fitted band",
    ),
    (DIAMETRAL_CLEARANCE_MIN > 0.0, "shoulder can bind in the oak bore"),
    (
        RELIEF_DIA <= min(THREAD_MINOR_BASIC_ROOT, THREAD_MINOR_UNR_2A_MAX),
        f"relief floor stands above the {THREAD_SIZE} external minor diameter",
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
        FILE_ALLOWANCE_MIN > 0.0,
        "shortest screw's full thread does not reach the thickest stock arm's "
        "inboard face, so it cannot be filed flush on full thread",
    ),
    (
        INSTALLED_TIP_CHAMFER < TIP_CHAMFER,
        "the fitted edge break is not smaller than the as-turned tip chamfer",
    ),
    (
        TIP_CHAMFER_MAX <= 0.61343 * THREAD_PITCH,
        f"tip chamfer cuts deeper than the {THREAD_SIZE} thread (17/24 H)",
    ),
    (
        TIP_CHAMFER + RELIEF_WIDTH < THREAD_LENGTH_MIN,
        "tip chamfer and relief leave no full thread",
    ),
    (
        all(len(line) <= 72 for line in DRAWING_NOTES.splitlines()),
        "an MHA-139 note line is over 72 characters",
    ),
    (HEAD_DIA > HANDLE_BORE_MAX, "head passes through the handle bore"),
    (HEAD_DIA < STOCK_DIA, "head is not turnable from 3/8-in rod"),
    (
        CUP_POCKET_WALL_MIN >= WALL_FLOOR_MM,
        "the MHA-153 pocket bored to suit the largest head leaves under 1.5 of wall",
    ),
    (HEAD_BEARING_RADIAL_MIN > 0.0, "no under-head bearing is left on the cup floor"),
    (
        CUP_FLOOR_HOLE_DIA > SHOULDER_DIA_MAX,
        "the MHA-153 floor hole does not pass the shoulder",
    ),
    (HEAD_RECESS_NOMINAL >= 0.0, "the head stands proud of the cup at nominal"),
    (
        HEAD_RECESS_WORST > 0.0,
        "the longest head stands proud of the shallowest cup pocket at full end play",
    ),
    (SHOULDER_DIA_MIN > THREAD_MODEL_DIA, "shoulder has no seat annulus"),
    (HEAD_LENGTH - SLOT_DEPTH >= 2.0, "under 2.0 of head remains under the slot"),
    (SLOT_WEB_MIN >= WALL_FLOOR_MM, "under 1.5 of head remains under the slot at its limits"),
):
    if not _ok:
        raise AssertionError(f"MHA-139: {_what}")

# Every axial LOCATION reads from the TIP, the one faced end (MHA-139
# re-reviews, 2026-09-29): the seat face (the thread length, with its own band
# for the engagement check), the under-head face (UnderHeadLocation, a
# reference: the shoulder is turned to suit the bonded handle) and the head
# face (the reference overall, for stock cut-off).  The head length, the slot
# depth, the relief width and the two 45-degree legs are local sizes of their
# features.  A head-face origin cannot work: the seat is fitted, so the thread
# length would ride on the handle stack.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ScrewProfile": {
        "HeadDia",
        "HeadLength",
        "ShoulderDia",
        "ThreadLength",
        "ReliefDia",
        "ReliefWidth",
        "TipChamfer",
    },
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
    "StationReference": {"OverallLength", "UnderHeadLocation"},
}
# Decimal places ARE the tolerance (policy rule 2): the shoulder diameter is
# the running fit and prints its band at two places, the head diameter its
# cup-floor bearing band, and the relief width prints at two places for the
# U33b engagement floor; every other size is routine (.X), the fitted
# shoulder length a reference.  The thread length carries its own +0/-0.5
# band at one place.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ScrewProfile": {
        "HeadDia": 2,
        "HeadLength": 2,
        "ShoulderDia": 2,
        "ThreadLength": 1,
        "ReliefDia": 1,
        "ReliefWidth": 1,
        "TipChamfer": 2,
    },
    "SlotProfile": {"SlotWidth": 1},
    "DriverSlot": {"SlotDepth": 2},
    "StationReference": {"OverallLength": 1, "UnderHeadLocation": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-139 dimension needs authored places")
REFERENCE_DIMENSIONS = frozenset({"OverallLength", "UnderHeadLocation"})

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:1"
