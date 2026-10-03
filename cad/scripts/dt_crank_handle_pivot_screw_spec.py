r"""Pure-data contract for MHA-DT-032, the crank handle pivot screw (user ruling U33).

A made slotted shoulder screw turned from 1/4-in cold-finished rod.  The oak
handle MHA-DT-008 spins on the shoulder; the thread screws into the crank arm
MHA-DT-006's #4-40 tapped through hole and the shoulder seats tight on the arm
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
from dt_crank_handle_butt_cup_spec import (
    BODY_DIA as CUP_BODY_DIA,
    BODY_DIA_TOL as CUP_BODY_DIA_TOL,
    FLOOR_HOLE_DIA as CUP_FLOOR_HOLE_DIA,
    POCKET_CLEARANCE as CUP_POCKET_CLEARANCE,
    POCKET_DEPTH as CUP_POCKET_DEPTH,
    POCKET_DEPTH_TOL as CUP_POCKET_DEPTH_TOL,
    POCKET_DIA as CUP_POCKET_DIA,
    POCKET_WALL_FLOOR_MM as CUP_POCKET_WALL_FLOOR_MM,
    WALL_FLOOR_MM,
)
from dt_crank_handle_spec import (
    HANDLE_LENGTH,
    PIVOT_BORE_BAND,
    PIVOT_BORE_DIA,
)
from dt_crank_hub_geometry import (
    ARM_STOCK_THICKNESS,
    ARM_STOCK_THICKNESS_MIN,
    ARM_THICKNESS,
    EDGE_BREAK_MAX_MM,
    GENERAL_1PL_TOL_MM,
    MM_PER_IN,
)


STOCK_DIA = 0.25 * MM_PER_IN

# User ruling 2026-09-29 (ch11 p.14): the head sits recessed in the MHA-DT-035
# butt cup's pocket, which is bored to suit it, and bears on the cup floor.
# Its +/-0.10 band keeps a bearing annulus outside the drilled floor hole at
# the worst case, after an edge break on each.  Ø6 (user ruling 2026-09-30,
# ch30 eight-views-4): the photographed head, which lets the cup and the butt
# shrink to the photographed size.
HEAD_DIA = 6.0
HEAD_DIA_TOL = 0.10
# A 4.0 head (user ruling 2026-09-29, MHA-DT-032 machinist review): with the
# slot's own band below, the worst case leaves 2.0 of head under the slot,
# not 0.4.  Banded (Codex P2 on #1139, user ruling 2026-09-30): at .X the
# longest head, at the widest fitted end play, stood 1.6 proud of the cup.
HEAD_LENGTH = 4.0
HEAD_LENGTH_TOL = 0.10
SLOT_WIDTH = 1.0
# Banded (MHA-DT-032 re-review): at .X the slot could print as nothing.
SLOT_DEPTH = 1.0
SLOT_DEPTH_TOL = 0.20

# The running surface under the oak bore.  (upper, lower) deviations from the
# Ø4.00 nominal; the model carries the band natively (policy rule 2).  Ø4.00
# (user ruling 2026-09-30): the tenon keeps 1.5 of oak over its bore.
SHOULDER_DIA = 4.00
SHOULDER_DIA_BAND = (-0.03, -0.08)
# The shoulder's thread-end face is the seat on the arm face.  Under the
# title block's 0.25 edge break on it and on the tapped mouth, a #6-32 left no
# seat (local review of 1f3067ef2); a Ø6 collar cannot pass the oak bore
# (local review of fbf82ad96).  So the thread is #4-40 (user ruling
# 2026-09-30) and the sheet breaks the seat edge 0.1 max, as MHA-DT-006 does its
# tapped mouth: a 0.34 radial seat at the worst case.
SEAT_EDGE_BREAK_MAX = 0.1
# Arm face to the head's underside, which bears on the MHA-DT-035 cup floor.
# User ruling 2026-09-29 (after the machinist reviews): the shoulder is
# turned to suit the bonded handle -- its measured length from the ferrule's
# arm face to the cup floor, plus the end play -- so no part in the handle
# stack carries a band for it.  The model carries the nominal stack plus the
# nominal end play, printed as a reference under the to-suit callout.
END_PLAY_RANGE = (0.25, 1.00)
END_PLAY_NOMINAL = 0.5
# The cup's face sits on the handle's basic length, so the stack from the
# ferrule's arm face to the cup floor is that length less the pocket.
HANDLE_STACK_NOMINAL = round(HANDLE_LENGTH - CUP_POCKET_DEPTH, 6)
SHOULDER_LENGTH = round(HANDLE_STACK_NOMINAL + END_PLAY_NOMINAL, 6)

# #4-40 (user ruling 2026-09-30, after #6-32): the thread that leaves the Ø4
# shoulder a seat on the arm.  In the 5/16-in arm it clears the policy's 1.5D
# engagement at the worst case, so the #8-32's U33b exception (1.26D) stays
# retired.
THREAD_SIZE = "#4-40"
# The threaded section is modelled as a plain cylinder at the basic #6 major
# diameter, the fleet convention for a stock screw in a tap-drill-modelled hole.
THREAD_MODEL_DIA = THREAD_MAJOR_MM[THREAD_SIZE]
# 10.0 +0/-0.5: the shortest thread section, 9.5, less the relief and 1.5
# pitches of die run-in still carries full thread across the arm's 7.94
# (5/16-in) stock thickness, so the ARM governs the worst-case engagement,
# not the screw (the 9.0 of U33b left the MHA-DT-032 machinist review short).
# The tip is cut proud of the arm's inboard face and filed flush at assembly
# (below).
THREAD_LENGTH = 10.0
THREAD_LENGTH_BAND = (0.0, -0.5)
# 45-degree thread-start chamfer on the tip, inside the 0.39 thread depth.
# Like the relief lead, the model holds the 45 degrees by equation and the
# print gives the axial leg with an "X 45 DEG" callout.  Banded (MHA-DT-032
# re-review): at .X the 0.4 could print as nothing; +0.05/-0.10 keeps a real
# chamfer that never cuts past the thread depth.
TIP_CHAMFER = 0.3
TIP_CHAMFER_BAND = (0.05, -0.10)
# The title block states the UN thread class, so the callout names no class.
THREAD_CALLOUT = f"{THREAD_SIZE} UNC"
THREADS_PER_IN = 40
THREAD_PITCH = MM_PER_IN / THREADS_PER_IN
# #4-40 external minor diameter.  ASSUMPTION, not sourced from ASME B1.1 in
# this repo: the UN basic profile with its P/8 root flat puts the root at
# major - 1.5 H = major - 1.299038 P = 2.020 (the same construction gives
# #10-24's 3.451, the root the McMaster 91829A560 vendor model cuts).  The
# UNR-2A reference maximum, 2A major max 0.1114 in (0.112 basic less the
# 0.0006 allowance) less 1.226869 P (17/24 H each side), is 0.0807 in =
# 2.051.  The relief floor sits at or below the smaller of the two so the
# die's incomplete threads clear it.
THREAD_MAJOR_2A_MAX_IN = 0.1114
THREAD_MINOR_BASIC_ROOT = THREAD_MODEL_DIA - 1.5 * math.sqrt(3.0) / 2.0 * THREAD_PITCH
THREAD_MINOR_UNR_2A_MAX = (
    THREAD_MAJOR_2A_MAX_IN - 1.226869 / THREADS_PER_IN
) * MM_PER_IN
# The deepest die-cut root the relief must clear (local review of 21bb244c5).
# ASSUMPTION, not sourced from ASME B1.1 in this repo: the #4-40 UNC-2A pitch
# diameter minimum is 0.0925 in (Machinery's Handbook), and a root cut a full
# basic half-depth (0.649519 P) below it is 0.0763 in = 1.937.
THREAD_PD_2A_MIN_IN = 0.0925
THREAD_MINOR_2A_MIN_EST = (
    THREAD_PD_2A_MIN_IN - 0.649519 / THREADS_PER_IN
) * MM_PER_IN
# The arm's tapped mouth is printed on MHA-DT-006 as an inspectable maximum
# (local review of aed772158: an assumed tap major was load-bearing and
# printed nowhere), and the screw floats off the hole's axis by the 2A/2B
# pitch-diameter fit.  #4-40 UNC class 2B pitch diameter 0.0958-0.0991 in
# (ITP class-2B table, Machinery's Handbook; not sourced in this repo): with
# the 2A minimum 0.0925 in the screw can sit 0.084 off axis.
TAPPED_MOUTH_DIA_MAX = 3.1
THREAD_PD_2B_MAX_IN = 0.0991
THREAD_FIT_OFFSET_MAX = round(
    (THREAD_PD_2B_MAX_IN - THREAD_PD_2A_MIN_IN) / 2.0 * MM_PER_IN, 6
)
# Thread relief (Main's ruling on the die-runout doubt): a groove in the first RELIEF_WIDTH of the threaded section, against
# the seat face, so the die's incomplete lead threads run out into air and the shoulder
# pulls down tight on the arm face.  Routine (.X) sizes under the title-block
# band.
# Banded (Codex P1 on #1139): at .X the relief could stand above the thread
# root (no die run-out) and, with the lead, reach past the shoulder's seat.
# Ø1.85 +/-0.05 keeps the largest relief under the deepest die-cut root
# estimated above, Ø1.937 (local reviews of 747487c71 and 21bb244c5).
RELIEF_DIA = 1.85
RELIEF_DIA_TOL = 0.05
RELIEF_DIA_MAX = round(RELIEF_DIA + RELIEF_DIA_TOL, 6)
# Routine at 2.2 (the MHA-DT-032 machinist review of crank-v4-16 called a
# +/-0.10 band over-specification): at .X the straight floor past the
# longest lead, 1.4 - 0.4 = 1.0, keeps 1.5 #4-40 pitches of die run-out
# (local review of 20dac9d3f: the lead is not floor), and the widest 3.0
# still leaves the 1.5D engagement.
RELIEF_WIDTH = 2.2
# A 45-degree lead from the relief floor up into the seat face, so the groove
# leaves no sharp inside corner.  0.3 keeps the lead inside the Ø2.845 thread
# major, i.e. inside the arm's tapped hole, so the whole seat annulus that
# bears on the arm face stays flat.  The 45 degrees is enforced in the model by
# an equation, and printed as a callout on the lead's axial size, as limits
# (MHA-DT-032 re-review: at .X the lead could print as nothing).
RELIEF_LEAD = 0.3
# The model owns the band (policy rule 2; Codex P2 on #1139): the ReliefLead
# dimension carries +/-0.10 and the callout prints the limits it gives, so a
# nominal edit cannot leave the printed limits behind.
RELIEF_LEAD_TOL = 0.10
RELIEF_LEAD_LIMITS = (
    round(RELIEF_LEAD - RELIEF_LEAD_TOL, 6),
    round(RELIEF_LEAD + RELIEF_LEAD_TOL, 6),
)
CHAMFER_CALLOUT = "X 45 DEG"
# The 45-degree lead rides the relief's Ø callout rather than a third
# dimension crowded into the 1.5-mm groove at 3:1 (machinist review).
RELIEF_CALLOUT = (
    f"{RELIEF_LEAD_LIMITS[0]:.1f}-{RELIEF_LEAD_LIMITS[1]:.1f} {CHAMFER_CALLOUT} LEAD"
)
SEAT_FLAT_INNER_DIA = RELIEF_DIA + 2.0 * RELIEF_LEAD
# ... and at its printed worst: the largest relief under the longest lead.
SEAT_FLAT_INNER_DIA_MAX = round(RELIEF_DIA_MAX + 2.0 * RELIEF_LEAD_LIMITS[1], 6)

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

# Head top below the cup's face at nominal: the head reads recessed in
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
# each, on the narrow side with the head pushed off-centre as far as its
# running play allows (local review of fbf82ad96: the concentric figure
# overstated it).  The play is the smaller of the head's in the pocket and
# the shoulder's in the floor hole.
_FLOOR_HOLE_MAX = CUP_FLOOR_HOLE_DIA + 0.10  # DRILLED HOLES +0.10/0
HEAD_BEARING_RADIAL_CONCENTRIC_MIN = round(
    ((HEAD_DIA - HEAD_DIA_TOL) - _FLOOR_HOLE_MAX) / 2.0 - 2.0 * EDGE_BREAK_MAX_MM, 6
)
HEAD_RUNNING_OFFSET_MAX = round(
    min(CUP_POCKET_CLEARANCE[1] / 2.0, (_FLOOR_HOLE_MAX - (SHOULDER_DIA + SHOULDER_DIA_BAND[1])) / 2.0),
    6,
)
HEAD_BEARING_RADIAL_MIN = round(HEAD_BEARING_RADIAL_CONCENTRIC_MIN - HEAD_RUNNING_OFFSET_MAX, 6)
# Wood-on-steel running clearance, on diameter.
DIAMETRAL_CLEARANCE_MIN = round(HANDLE_BORE_MIN - SHOULDER_DIA_MAX, 6)
DIAMETRAL_CLEARANCE_MAX = round(HANDLE_BORE_MAX - SHOULDER_DIA_MIN, 6)
# Engagement in the MHA-DT-006 tapped through hole.  The relief sits in the arm's
# first RELIEF_WIDTH below the seat face, so only the full thread beyond it
# engages, and never deeper than the arm is thick.  The drawing-simplicity
# policy's 1.5D rule holds at the worst case, with no exception.
ENGAGEMENT_RULE_D = 1.5
ENGAGEMENT_FLOOR = ENGAGEMENT_RULE_D * THREAD_MODEL_DIA
# The arm is 5/16-in cold-finished flat bar left at stock thickness
# (dt_crank_hub_geometry.ARM_STOCK_THICKNESS).  Its sheet prints the 8.0 as a
# reference to that stock (Codex #892: a toleranced 8.0 took the .X band and
# accepted a 7.2 arm, 1.02D), so the thinnest accepted arm is the mill's
# ARM_STOCK_THICKNESS_MIN.  The thick side keeps the .X band as a bound on
# what the model allows.
ARM_PRINTED_THICKNESS_MAX = ARM_THICKNESS + GENERAL_1PL_TOL_MM
# The relief width is a routine .X size; the #4-40 thread clears the 1.5D
# rule with it at .X (asserted below).
RELIEF_WIDTH_MAX = round(RELIEF_WIDTH + GENERAL_1PL_TOL_MM, 6)
RELIEF_WIDTH_MIN = round(RELIEF_WIDTH - GENERAL_1PL_TOL_MM, 6)
# The straight floor the die's incomplete teeth run out into: the shortest
# relief less the longest lead.
RELIEF_FLOOR_MIN = round(RELIEF_WIDTH_MIN - RELIEF_LEAD_LIMITS[1], 6)
# The title-block edge break on the tapped hole's inboard exit edge takes up
# to its size of thread off the arm end of the engagement.
TAP_EXIT_BREAK = EDGE_BREAK_MAX_MM
# The tip chamfer's threads are partial, so full thread ends TIP_CHAMFER short
# of the tip: FULL_THREAD_REACH is the full-thread end measured from the seat
# face.  Which side governs each case is the smaller term of the min().  The
# shortest reach takes the longest printed chamfer (Codex P2 on #1138: the
# nominal chamfer overstated it, and with it the filing allowance).
FULL_THREAD_REACH_NOMINAL = round(THREAD_LENGTH - TIP_CHAMFER, 6)
FULL_THREAD_REACH_MIN = round(THREAD_LENGTH_MIN - TIP_CHAMFER_MAX, 6)
FULL_THREAD_NOMINAL = round(
    min(FULL_THREAD_REACH_NOMINAL, ARM_THICKNESS) - RELIEF_WIDTH, 6
)
# Worst case in the thinnest stock arm: min(full-thread reach, arm 7.84 less
# the exit break) - the widest relief.
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
# MHA-DT-030 precedent); the default stays the as-turned screw the sheet prints.
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
# The fitted shoulder and both head bands' reasons, stated once (user ruling
# 2026-09-29, after the MHA-DT-032 machinist review; the length band's reason
# after the 1d2be3aaf re-review called it over-specification unstated).
DRAWING_NOTES = "\n".join(
    (
        "FACE THE UNDER-HEAD TO SUIT THE BONDED MHA-DT-008: UNDER-HEAD TO SEAT",
        f"  FACE (SHOULDER END, EDGE BROKEN {SEAT_EDGE_BREAK_MAX:.1f} MAX, ON MHA-DT-006) = FERRULE FACE",
        f"  TO CUP FLOOR PLUS {END_PLAY_RANGE[0]:.2f}-{END_PLAY_RANGE[1]:.2f}. "
        "HEAD BEARS ON MHA-DT-035 FLOOR; DIA BAND",
        f"  KEEPS {HEAD_BEARING_RADIAL_MIN:.1f} BEARING, LENGTH BAND KEEPS IT BELOW CUP FACE.",
    )
)

# The shoulder's seat on the arm face: from the arm's printed maximum mouth
# (the larger of it and the relief lead's envelope) out to the smallest
# shoulder less its 0.1-max seat break, less the screw's float off the
# hole's axis on the narrow side.
SEAT_CONTACT_INNER_DIA = max(TAPPED_MOUTH_DIA_MAX, SEAT_FLAT_INNER_DIA_MAX)
SEAT_CONTACT_OUTER_DIA_MIN = round(SHOULDER_DIA_MIN - 2.0 * SEAT_EDGE_BREAK_MAX, 6)
SEAT_RADIAL_MIN = round(
    (SEAT_CONTACT_OUTER_DIA_MIN - SEAT_CONTACT_INNER_DIA) / 2.0 - THREAD_FIT_OFFSET_MAX, 6
)
SEAT_FLAT_ANNULUS_AREA = math.pi / 4.0 * (SHOULDER_DIA**2 - TAPPED_MOUTH_DIA_MAX**2)
SEAT_FLAT_ANNULUS_AREA_MIN = (
    math.pi / 4.0 * (SEAT_CONTACT_OUTER_DIA_MIN**2 - SEAT_CONTACT_INNER_DIA**2)
)
# The relief neck is the screw's weakest section: pi/4 x 1.85^2 = 2.69 mm^2
# against the #4-40 UNC tensile stress area of 0.00604 in^2 = 3.90 mm^2, about
# 69 percent.  Seating torque is therefore limited by the neck, not the thread;
# the handle's working load is a hand grip and never loads it axially.
NECK_AREA = math.pi / 4.0 * RELIEF_DIA**2
TENSILE_STRESS_AREA = 0.00604 * MM_PER_IN**2
NECK_TO_STRESS_AREA = NECK_AREA / TENSILE_STRESS_AREA

for _ok, _what in (
    (
        END_PLAY_RANGE[0] <= END_PLAY_NOMINAL <= END_PLAY_RANGE[1],
        "the modelled end play is outside the fitted band",
    ),
    (DIAMETRAL_CLEARANCE_MIN > 0.0, "shoulder can bind in the oak bore"),
    (
        RELIEF_DIA_MAX <= min(THREAD_MINOR_BASIC_ROOT, THREAD_MINOR_UNR_2A_MAX),
        f"relief floor stands above the {THREAD_SIZE} external minor diameter",
    ),
    (RELIEF_WIDTH < THREAD_LENGTH, "relief consumes the whole thread section"),
    (RELIEF_LEAD < RELIEF_WIDTH, "relief lead consumes the relief floor"),
    (
        SEAT_FLAT_INNER_DIA_MAX < THREAD_MODEL_DIA,
        "relief lead reaches past the thread major into the seat annulus",
    ),
    (SEAT_FLAT_ANNULUS_AREA_MIN > 0.0, "no flat seat annulus is left"),
    (SEAT_RADIAL_MIN >= 0.2, "the shoulder's seat on the arm face is under 0.2 radial"),
    (
        TAPPED_MOUTH_DIA_MAX > THREAD_MODEL_DIA + 2.0 * 0.05,
        "the printed tapped mouth leaves no room to deburr the thread's start",
    ),
    (
        RELIEF_DIA_MAX <= THREAD_MINOR_2A_MIN_EST,
        "the largest relief stands above the deepest die-cut root",
    ),
    (
        RELIEF_FLOOR_MIN >= 1.5 * THREAD_PITCH,
        "the shortest relief's straight floor is under 1.5 pitches of die run-out",
    ),
    (
        FULL_THREAD_WORST >= ENGAGEMENT_FLOOR,
        "stock-arm worst-case engagement is under the 1.5D rule",
    ),
    (
        FULL_THREAD_WORST_PRINTED_ARM >= ENGAGEMENT_FLOOR,
        "printed-arm worst-case engagement is under the 1.5D rule",
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
        "an MHA-DT-032 note line is over 72 characters",
    ),
    (HEAD_DIA > HANDLE_BORE_MAX, "head passes through the handle bore"),
    (HEAD_DIA + HEAD_DIA_TOL < STOCK_DIA, "head is not turnable from 1/4-in rod"),
    (
        CUP_POCKET_WALL_MIN >= CUP_POCKET_WALL_FLOOR_MM,
        "the MHA-DT-035 pocket bored to suit the largest head leaves under its 0.8 wall",
    ),
    (HEAD_BEARING_RADIAL_MIN >= 0.1, "under 0.1 of under-head bearing on the cup floor"),
    (
        CUP_FLOOR_HOLE_DIA > SHOULDER_DIA_MAX,
        "the MHA-DT-035 floor hole does not pass the shoulder",
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
        raise AssertionError(f"MHA-DT-032: {_what}")

# Every axial LOCATION reads from the TIP, the one faced end (MHA-DT-032
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
# 1.5D engagement rule; every other size is routine (.X), the fitted
# shoulder length a reference.  The thread length carries its own +0/-0.5
# band at one place.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ScrewProfile": {
        "HeadDia": 2,
        "HeadLength": 2,
        "ShoulderDia": 2,
        "ThreadLength": 1,
        "ReliefDia": 2,
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
    raise AssertionError("every marked MHA-DT-032 dimension needs authored places")
REFERENCE_DIMENSIONS = frozenset({"OverallLength", "UnderHeadLocation"})

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:1"
