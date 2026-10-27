"""Seat, full-thread and wall budgets for the gooseneck's clamped spring eye.

The shop-turned screw passes through the brazed plug into the open tube.
Its incomplete tip threads lie beyond the receiver, rather than reducing
the plug's usable full-thread length. The upper eye is clamped,
not left free to swivel (user ruling 2026-09-21).  Owner ruling 2026-10-26
(#1951, option B): the loop sits on the screw's plain Ø3.50 shoulder, and the
#8-32 thread past the shoulder's 45-degree lead runs through the MHA-SM-01
plug, retapped #8-32 UNC-2B THRU.  An arm-end counterbore clears the screw's
die run-out (codjiflo P1 on #1997): the run-out's incomplete threads never
enter the plug's full 2B thread, even with the loop clamped to its least gap.
"""

from __future__ import annotations

import math

import _config
import sm_gooseneck_geom as gooseneck
import sm_vn_counter_spring_stock_geom as spring
import sm_gooseneck_spring_screw_geom as screw
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

TAP_SPEC = HoleSpec("tapped", screw.THREAD_SIZE, end="through_all", thread_class="2B")
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
PLUG_DIA = gooseneck.TUBE_DIA - 2.0 * gooseneck.WALL_T
PLUG_DIAMETER_BAND = printed_band_mm(2)
PLUG_LENGTH_BAND = printed_band_mm(2)
THREAD_AXIS_OFFSET_MAX = 0.15
DRILL_WANDER_MAX = 0.10
# The plug is turned to the measured tube bore for a silver-braze (BAg-7)
# joint: the diametral faying clearance is the mating requirement. The
# retained Ø band still limits the plug, and the wall budget below uses its
# lower limit.
BRAZE_CLEARANCE_MIN = 0.05
BRAZE_CLEARANCE_MAX = 0.13
EDGE_BREAK = float(_config.title_block("edge_break")["chamfer_max_mm"])

# The two gaps between the head face and the plug face.  SPRING_EYE_GAP is the
# loop's FREE envelope (LOOP_RISE + wire): the CAD station the model, the
# native seat calibration and the loop-pass stations use.  The clamped loop is
# coil-bound: the 1330K524 eye is a 1.75-turn helix of pitch 1.8745 over
# 1.6002 wire, so its overlapping turns stand 0.274 apart, and its axial rate
# G d^4 / (8 D^3 n) (Shigley's Mechanical Engineering Design 10th ed. eq.
# 10-9; music wire G 82.7 GPa max, Table 10-5; mean D 11.0998, n 1.75) is
# LOOP_AXIAL_RATE ~ 28 N/mm, so it binds at LOOP_BIND_FORCE ~ 14 N, far under
# the 231-693 N clamp preload sm_gooseneck_spring_screw_spec.clamp_preload_n
# sweeps.  Bound, the loop rises one wire diameter per turn: CLAMPED_GAP_MAX,
# the most the gap can be under clamp.
#
# The finite faces let it sit deeper.  The plug-side helix tip stands at
# r 8.55 from the screw axis, outside the Ø16 tube face (r 8.0), and the
# rigid helix can rock: the smallest footprints (head r <= (12.50 - 0.51)/2 -
# 0.25; plug face from the 3.04 mouth reach out to 5.75 when the plug is
# proud, or to 7.70 at the tube; a wire section past a rim still bears on
# it) leave it 3.88-4.13 untilted and 3.27 rocked to minimum width, 3.27 on
# the screw axis with the head face tilted SCREW_TILT_MAX against the plug
# face (test_sm_gooseneck_spring_joint's numeric sweep).  The floor holds
# anyway: the two stacked pull-side layers (helix angles 30 and 390 degrees,
# centreline ~4.8 from the screw axis, wire r 4.0-5.6) bear on the seat inside
# BOTH faces, so the gap is never under two wire diameters: CLAMPED_GAP_MIN,
# the least the gap can be, where the screw sits deepest.  Each check takes
# the gap worst for it.
LOOP_SHEAR_MODULUS_MPA = 82_700.0
LOOP_AXIAL_RATE = (
    LOOP_SHEAR_MODULUS_MPA
    * spring.WIRE_DIA_MM**4
    / (8.0 * (2.0 * spring.COIL_MEAN_RADIUS_MM) ** 3 * spring.LOOP_TURNS)
)
CLAMPED_LOOP_RISE = spring.LOOP_TURNS * spring.WIRE_DIA_MM
CLAMPED_GAP_MAX = (spring.LOOP_TURNS + 1.0) * spring.WIRE_DIA_MM
CLAMPED_GAP_MIN = 2.0 * spring.WIRE_DIA_MM
LOOP_BIND_FORCE = LOOP_AXIAL_RATE * (gooseneck.SPRING_EYE_GAP - CLAMPED_GAP_MAX)

# The screw is not square in the plug (codjiflo round 5 on #1997).  Its radial
# play in the 2B thread, bounded crest-to-root by the tap's major +
# TAP_ROOT_OVERSIZE against the 2A major minimum (the flank play is smaller),
# can sit on opposite sides at the two ends of the engaged thread, so it tilts
# by SCREW_TILT_MAX over the 1.5D the engagement keeps at least
# (ENGAGEMENT_MIN, asserted below).  Past the engaged thread its offset from
# the thread axis grows with that tilt.
TAP_ROOT_OVERSIZE = 0.025
SCREW_RADIAL_PLAY_MAX = (
    screw.MAJOR_DIA + TAP_ROOT_OVERSIZE - screw.THREAD_MAJOR_2A_MIN
) / 2.0
ENGAGEMENT_MIN_D = 1.5
SCREW_TILT_MAX = math.atan(
    2.0 * SCREW_RADIAL_PLAY_MAX / (ENGAGEMENT_MIN_D * screw.MAJOR_DIA)
)

# The screw's own full thread starts behind its shoulder lead and the die's
# run-out (sm_gooseneck_spring_screw_geom.FULL_THREAD_STATION, from the head),
# no later than the "5.67 MAX" MHA-SM-04 prints (FULL_THREAD_STATION_MAX).
# The run-out's incomplete threads are FAT (full crest, shallow root): in the
# plug's full 2B thread they jam before the head clamps.  They reach deepest
# past the plug face at the least clamped gap, and the tilt dips the full-
# thread circle's low side a further half major x sin(tilt).  The gap floor
# holds on the screw axis with the head face tilted that much against the plug
# face (test_sm_gooseneck_spring_joint), so the arm-end counterbore's depth
# clears the intrusion by COUNTERBORE_RUNOUT_MARGIN_MIN.
SCREW_RUNOUT_TILT_DIP = screw.MAJOR_DIA / 2.0 * math.sin(SCREW_TILT_MAX)
SCREW_RUNOUT_INTRUSION_MAX = (
    screw.FULL_THREAD_STATION_MAX - CLAMPED_GAP_MIN + SCREW_RUNOUT_TILT_DIP
)
SCREW_RUNOUT_INTRUSION_FREE_MAX = (
    screw.FULL_THREAD_STATION_MAX - gooseneck.SPRING_EYE_GAP + SCREW_RUNOUT_TILT_DIP
)
COUNTERBORE_RUNOUT_MARGIN_MIN = 0.05
# Printed LIMIT depth from the plug face: its MIN rounded UP to the print's
# two places, a 0.10 band, the model at mid-band.
COUNTERBORE_DEPTH_BAND = 0.10
COUNTERBORE_DEPTH_MIN = (
    math.ceil((SCREW_RUNOUT_INTRUSION_MAX + COUNTERBORE_RUNOUT_MARGIN_MIN) * 100.0)
    / 100.0
)
COUNTERBORE_DEPTH_MAX = round(COUNTERBORE_DEPTH_MIN + COUNTERBORE_DEPTH_BAND, 6)
COUNTERBORE_DEPTH = round((COUNTERBORE_DEPTH_MIN + COUNTERBORE_DEPTH_MAX) / 2.0, 6)
# The tilted screw's largest offset from the thread axis inside the
# counterbore, at the plug face: the deepest floor plus the receiver's 0.25
# floor break past its first full thread.
SCREW_FACE_OFFSET_MAX = SCREW_RADIAL_PLAY_MAX + (
    COUNTERBORE_DEPTH_MAX + EDGE_BREAK
) * math.tan(SCREW_TILT_MAX)
# Ø printed under the title block's DRILLED HOLES row (+0.10/0).  The fat
# run-out (basic major, at or above the 2A major max) must clear the bore's
# SMALLEST size with the screw and the bore each off the thread axis by their
# full bands: the counterbore's printed axis band to the tap
# (COUNTERBORE_AXIS_OFFSET_MAX, MHA-SM-01 note 4) and the tilted screw's
# SCREW_FACE_OFFSET_MAX, its largest anywhere in the bore.  With the tilt,
# Ø4.70 left -0.03 of it, so the bore is Ø4.90.
COUNTERBORE_DIA = 4.90
COUNTERBORE_DIA_MAX = COUNTERBORE_DIA + drilled_oversize_mm()
COUNTERBORE_AXIS_OFFSET_MAX = 0.10
RUNOUT_RADIAL_CLEARANCE_MIN = (
    (COUNTERBORE_DIA - screw.MAJOR_DIA) / 2.0
    - COUNTERBORE_AXIS_OFFSET_MAX
    - SCREW_FACE_OFFSET_MAX
)
# The floor's corner to the wall is a stop in the run-out's path: the title
# block's INSIDE CORNERS R1.0 MAX would reach it (codjiflo P1 round 5 on
# #1997), so MHA-SM-01 note 4 prints FLOOR CORNER R0.10 MAX.  The run-out's
# crest corner stands at least COUNTERBORE_RUNOUT_MARGIN_MIN above the floor
# and RUNOUT_RADIAL_CLEARANCE_MIN off the wall; RUNOUT_FLOOR_CORNER_CLEARANCE_MIN
# (below) is its clearance to the round's material.
COUNTERBORE_FLOOR_CORNER_R_MAX = 0.10

# The RECEIVER's full thread, the figure MHA-SM-01 prints: from the
# counterbore floor to the inner end, less the title-block 0.25 edge break on
# the tap edge at the floor and at the inner end.  The tap exits into air;
# neither tap lead nor screw tip is counted.  It is also the MATED full
# thread: the screw's full thread starts inside the counterbore (run-out
# intrusion < depth, asserted below, at either gap) and runs past the
# longest plug's inner end (FULL_THREAD_REACH_MIN, asserted below).
ENGAGEMENT_NOMINAL = gooseneck.PLUG_LENGTH - COUNTERBORE_DEPTH - 2.0 * EDGE_BREAK
ENGAGEMENT_MIN = (
    gooseneck.PLUG_LENGTH - PLUG_LENGTH_BAND - COUNTERBORE_DEPTH_MAX - 2.0 * EDGE_BREAK
)

# drawing-guidelines.md rule 17 wall between the tap and the plug's turned
# OD, FULL worst case (brief 2026-10-26), every term cited:
#  * the plug OD at its lower printed limit (PLUG_DIAMETER_BAND, title-block
#    .XX: the retained Ø band on MHA-SM-01 note 3);
#  * the tap at its basic major plus 0.025 root oversize (TAP_ROOT_OVERSIZE);
#  * the tap's locating band, thread axis to tube axis (MHA-SM-01 note 4,
#    THREAD_AXIS_OFFSET_MAX), and its printed DRILL WANDER (same note);
#  * 0.3 degrees of drill run-off over the longest plug: the plug OD is turned
#    before brazing and the hole is drilled after, in a DIFFERENT setup
#    located on the tube (note 4), so the run-off term applies;
#  * the title-block 0.25 edge break on the tap edge (counterbore floor or
#    inner end) and on the plug blank's OD edge at a face (both counted
#    together, although they never share a station and the braze fillet
#    fills the second).
DRILL_RUNOFF_DEG = 0.3
DRILL_RUNOFF_MAX = (gooseneck.PLUG_LENGTH + PLUG_LENGTH_BAND) * math.tan(
    math.radians(DRILL_RUNOFF_DEG)
)
PLUG_WALL_NOMINAL = (PLUG_DIA - screw.MAJOR_DIA) / 2.0
PLUG_WALL_MIN = (
    (PLUG_DIA - PLUG_DIAMETER_BAND) / 2.0
    - (screw.MAJOR_DIA + TAP_ROOT_OVERSIZE) / 2.0
    - THREAD_AXIS_OFFSET_MAX
    - DRILL_WANDER_MAX
    - DRILL_RUNOFF_MAX
    - 2.0 * EDGE_BREAK
)
PLUG_WALL_TARGET = 2.0
# The same wall at the counterbore, FULL worst case, every term cited:
#  * the plug OD at its lower printed limit (as above);
#  * the counterbore at its largest size (COUNTERBORE_DIA_MAX: title-block
#    DRILLED HOLES +0.10/0);
#  * its location: the tap axis to the tube axis (THREAD_AXIS_OFFSET_MAX) plus
#    the counterbore axis to the tap axis (COUNTERBORE_AXIS_OFFSET_MAX), both
#    MHA-SM-01 note 4;
#  * 0.3 degrees of drill run-off over the deepest counterbore: cut after
#    braze, a DIFFERENT setup from the turned plug OD, so the term applies;
#  * the title-block 0.25 edge break on the counterbore mouth and on the plug
#    blank's OD edge at the face.
COUNTERBORE_RUNOFF_MAX = COUNTERBORE_DEPTH_MAX * math.tan(
    math.radians(DRILL_RUNOFF_DEG)
)
COUNTERBORE_WALL_MIN = (
    (PLUG_DIA - PLUG_DIAMETER_BAND) / 2.0
    - COUNTERBORE_DIA_MAX / 2.0
    - THREAD_AXIS_OFFSET_MAX
    - COUNTERBORE_AXIS_OFFSET_MAX
    - COUNTERBORE_RUNOFF_MAX
    - 2.0 * EDGE_BREAK
)
HEAD_RETENTION = (screw.HEAD_DIA - spring.EYE_ID_MM) / 2.0
HEAD_RETENTION_MIN = (screw.HEAD_DIA + screw.HEAD_DIA_LOWER - spring.EYE_ID_MM) / 2.0

# The loop on its seat.  The clamp fixes the loop's two pull-side passes (the
# wire that bears on the screw) at these stations from the head face: the
# half-turn clocking sends loop +Z toward the plug (spring_mount_geom
# counter_pose, build_sm_summing_assembly).  Both passes must bear on the
# plain seat alone, so the wire's section clears every other surface.
# LOOP_PASS_X is the free (CAD, native-seat) state; the coil-bound loop rises
# CLAMPED_LOOP_RISE in CLAMPED_GAP_MAX.
#
# Rocked states.  Over every tilt whose width fits CLAMPED_GAP_MAX the passes
# can reach the whole stacking envelope (plug-side out to ~3.73), but the
# clamped loop holds only where friction can hold it: its head- and plug-face
# contacts, on the face plane, within mu x gap of each other (the loop's
# moment balance; MHA-SM-00 step 8 clamps it before the spring's lower loop
# is hooked, so the preload is its only load).  At twice the clamp's highest
# friction (sm_gooseneck_spring_screw_spec.CLAMP_FRICTIONS), which also covers
# the head face's SCREW_TILT_MAX, with rim contacts counted, every such state
# sits near the width minimum (codjiflo round 5 on #1997): gap 3.27-3.63,
# head-side pass 0.80 and over, plug-side pass 2.79 at most, short of the free
# state's.  So the lead clearance below holds at the free and coil-bound
# untilted states (test_sm_gooseneck_spring_joint sweeps the held states), and
# the corner clearance holds for a wire touching the head face itself,
# station WIRE_R, the floor in every state.
_PASS_T = (1.0 / (4.0 * spring.LOOP_TURNS), 5.0 / (4.0 * spring.LOOP_TURNS))


def _loop_station(gap: float, rise: float, t: float) -> float:
    """Wire-centreline station from the head face at helix fraction ``t``."""
    return gap / 2.0 - rise / 2.0 + rise * t


LOOP_PASS_X = tuple(
    _loop_station(gooseneck.SPRING_EYE_GAP, spring.LOOP_RISE_MM, t) for t in _PASS_T
)
CLAMPED_LOOP_PASS_X = tuple(
    _loop_station(CLAMPED_GAP_MAX, CLAMPED_LOOP_RISE, t) for t in _PASS_T
)
WIRE_R = spring.WIRE_RADIUS_MM


# Plug-side pass vs the 45-degree lead at the SHORTEST shoulder.  The wire
# rests on the seat, so the clearance depends on the stations only.
def _lead_clearance(plug_pass: float) -> float:
    return (screw.SHOULDER_LENGTH_MIN - plug_pass + WIRE_R) / math.sqrt(2.0) - WIRE_R


def _fillet_clearance(u: float, v: float, fillet_r: float, body_r: float) -> float:
    """Clearance from a round body (``body_r`` 0: a point) to a corner round.

    In the axial section, from the inside corner: the body's centre stands
    ``u`` and ``v`` off the corner's two faces; the round's material is the
    corner square ``[0, fillet_r]^2`` outside the circle centred ``(fillet_r,
    fillet_r)``.  Each face is budgeted on its own, so only the quarter arc
    counts.  Valid on either side of the round's tangent points; negative is
    overlap.
    """
    to_centre = math.hypot(u - fillet_r, v - fillet_r)
    if 0.0 <= u <= fillet_r and 0.0 <= v <= fillet_r:
        return fillet_r - to_centre - body_r  # negative in the round's material
    nearest = min(math.hypot(u - fillet_r, v), math.hypot(u, v - fillet_r))
    if to_centre > 0.0:
        # The arc point on the ray from the fillet centre, if on the quarter.
        arc_u = fillet_r + fillet_r * (u - fillet_r) / to_centre
        arc_v = fillet_r + fillet_r * (v - fillet_r) / to_centre
        if arc_u <= fillet_r and arc_v <= fillet_r:
            nearest = min(nearest, abs(to_centre - fillet_r))
    return nearest - body_r


LOOP_LEAD_CLEARANCE_MIN = min(
    _lead_clearance(LOOP_PASS_X[1]), _lead_clearance(CLAMPED_LOOP_PASS_X[1])
)
# The under-head fillet MHA-SM-04 prints "R0.50 MAX", against a wire bearing on
# the seat; the clearance grows with the station past WIRE_R, so the head-face
# floor is the least of every state.
LOOP_CORNER_CLEARANCE_MIN = _fillet_clearance(
    WIRE_R, WIRE_R, screw.UNDERHEAD_CORNER_R, WIRE_R
)
# The counterbore floor's "R0.10 MAX" against the run-out's crest corner at
# its least axial and radial clearances (both above).
RUNOUT_FLOOR_CORNER_CLEARANCE_MIN = _fillet_clearance(
    COUNTERBORE_DEPTH_MIN - SCREW_RUNOUT_INTRUSION_MAX,
    RUNOUT_RADIAL_CLEARANCE_MIN,
    COUNTERBORE_FLOOR_CORNER_R_MAX,
    0.0,
)

# The loop against the counterbore mouth.  The eye's inner surface bears on
# the seat on the pull side, so its axis stands EYE_ID/2 - SEAT/2 from the
# screw axis.  The mouth's reach from the screw axis is the counterbore's
# largest radius, its 0.25 edge break, and both axis offsets
# (COUNTERBORE_AXIS_OFFSET_MAX and SCREW_FACE_OFFSET_MAX, as for the run-out).
# Two facts, each at the worse seat limit and the worse untilted gap:
#  * LOOP_FACE_CONTACT_RADIUS_MIN: the wire that meets the plug face is the
#    loop's plug-side tip (end of the helix), half a turn past the plug-side
#    pull pass, on the far side of the eye: its distance from the screw axis;
#  * LOOP_MOUTH_STANDOFF_MIN: every wire inside the mouth's reach is the
#    seat-bearing pull pass, this far short of the plug face.
# Rocked and held (above), the loop may instead bear on the mouth's rim, its
# 0.25 break, which is plug material; the wire that dips inside the mouth is
# then the seat-bearing plug-side pass, which the held-state sweep keeps short
# of the free state's station, so it clears the lead.
COUNTERBORE_MOUTH_REACH = (
    COUNTERBORE_DIA_MAX / 2.0
    + EDGE_BREAK
    + COUNTERBORE_AXIS_OFFSET_MAX
    + SCREW_FACE_OFFSET_MAX
)
_COIL_R = spring.COIL_MEAN_RADIUS_MM


def _loop_face_clearance(
    gap: float, rise: float, seat_dia: float
) -> tuple[float, float]:
    """``(face-contact radius, mouth standoff)`` for one gap and seat size.

    Helix angle ``theta`` is measured so the pull passes (``_PASS_T``) sit at
    ``sin(theta) = 1``, toward the screw; the centreline's distance from the
    screw axis is ``sqrt(R^2 + d^2 - 2 R d sin(theta))``.
    """
    d = (spring.EYE_ID_MM - seat_dia) / 2.0
    tip_radius = _COIL_R + d - WIRE_R  # t = 1: theta = 270 degrees
    reach = COUNTERBORE_MOUTH_REACH + WIRE_R
    sin_inside = (_COIL_R**2 + d**2 - reach**2) / (2.0 * _COIL_R * d)
    half_arc = math.acos(max(-1.0, min(1.0, sin_inside)))
    t_last = _PASS_T[1] + half_arc / (2.0 * math.pi * spring.LOOP_TURNS)
    standoff = gap - (_loop_station(gap, rise, t_last) + WIRE_R)
    return tip_radius, standoff


_FACE_CASES = tuple(
    _loop_face_clearance(gap, rise, seat)
    for gap, rise in (
        (gooseneck.SPRING_EYE_GAP, spring.LOOP_RISE_MM),
        (CLAMPED_GAP_MAX, CLAMPED_LOOP_RISE),
    )
    for seat in (screw.SEAT_DIA_MIN, screw.SEAT_DIA_MAX)
)
LOOP_FACE_CONTACT_RADIUS_MIN = min(case[0] for case in _FACE_CASES)
LOOP_MOUTH_STANDOFF_MIN = min(case[1] for case in _FACE_CASES)

# Tip budgets: the free gap leaves the screw shallowest (protrusion, full-thread
# reach), the least clamped gap drives it deepest (tip to bend).
SCREW_REACH = screw.LENGTH - gooseneck.SPRING_EYE_GAP
SCREW_REACH_MIN = SCREW_REACH + screw.LENGTH_LOWER
SCREW_REACH_MAX = SCREW_REACH + screw.LENGTH_UPPER
CLAMPED_SCREW_REACH_MAX = screw.LENGTH + screw.LENGTH_UPPER - CLAMPED_GAP_MIN
SCREW_END_INCOMPLETE_MAX = 1.5 * screw.PITCH
FULL_THREAD_REACH_MIN = SCREW_REACH_MIN - SCREW_END_INCOMPLETE_MAX
PLUG_INNER_X = gooseneck.ARM_END_X + gooseneck.PLUG_LENGTH
SCREW_TIP_X = gooseneck.ARM_END_X + SCREW_REACH
TIP_PROTRUSION = SCREW_REACH - gooseneck.PLUG_LENGTH
TIP_PROTRUSION_MIN = SCREW_REACH_MIN - (gooseneck.PLUG_LENGTH + PLUG_LENGTH_BAND)
# The straight tube's hollow bore continues to the bend exit at part X=-BEND_R.
# The longest accepted screw, clamped deepest, still ends in the open bore.
TIP_TO_BEND_MIN = gooseneck.ARM_RUN - CLAMPED_SCREW_REACH_MAX
TIP_BORE_RADIAL_CLEARANCE_MIN = (
    (PLUG_DIA - PLUG_DIAMETER_BAND - screw.MAJOR_DIA) / 2.0
    - THREAD_AXIS_OFFSET_MAX
    - DRILL_WANDER_MAX
    - DRILL_RUNOFF_MAX
)

if TAP_SPEC.size != screw.THREAD_SIZE or TAP_SPEC.thread_class != "2B":
    raise AssertionError("gooseneck spring screw does not match its through tap")
if ENGAGEMENT_MIN < ENGAGEMENT_MIN_D * screw.MAJOR_DIA:
    raise AssertionError("gooseneck spring screw loses 1.5D full engagement")
if (
    COUNTERBORE_DEPTH_MIN - SCREW_RUNOUT_INTRUSION_MAX < COUNTERBORE_RUNOUT_MARGIN_MIN
    or SCREW_RUNOUT_INTRUSION_FREE_MAX > SCREW_RUNOUT_INTRUSION_MAX
):
    raise AssertionError("gooseneck screw run-out reaches the plug's full thread")
if min(RUNOUT_RADIAL_CLEARANCE_MIN, RUNOUT_FLOOR_CORNER_CLEARANCE_MIN) <= 0.0:
    raise AssertionError("gooseneck screw run-out rubs the plug counterbore")
if FULL_THREAD_REACH_MIN <= gooseneck.PLUG_LENGTH + PLUG_LENGTH_BAND:
    raise AssertionError("gooseneck screw incomplete tip thread reaches the plug")
if min(TIP_PROTRUSION_MIN, TIP_TO_BEND_MIN, TIP_BORE_RADIAL_CLEARANCE_MIN) <= 0.0:
    raise AssertionError("gooseneck screw tip is not clear in the open tube bore")
if min(PLUG_WALL_MIN, COUNTERBORE_WALL_MIN) < PLUG_WALL_TARGET:
    raise AssertionError(
        "gooseneck plug loses a drawing-guidelines.md rule 17 (walls and webs) wall"
    )
if HEAD_RETENTION_MIN < 1.0:
    raise AssertionError("gooseneck screw head does not retain the spring eye")
if min(LOOP_LEAD_CLEARANCE_MIN, LOOP_CORNER_CLEARANCE_MIN) <= 0.0:
    raise AssertionError("gooseneck spring loop bears off the screw's plain seat")
if not LOOP_PASS_X[0] < LOOP_PASS_X[1] < screw.SHOULDER_LENGTH_MIN:
    raise AssertionError("gooseneck spring loop passes do not lie on the seat")
if not CLAMPED_LOOP_PASS_X[0] < CLAMPED_LOOP_PASS_X[1] < screw.SHOULDER_LENGTH_MIN:
    raise AssertionError("clamped gooseneck spring loop passes leave the seat")
if (
    LOOP_FACE_CONTACT_RADIUS_MIN <= COUNTERBORE_MOUTH_REACH
    or LOOP_MOUTH_STANDOFF_MIN <= 0.0
):
    raise AssertionError("gooseneck spring loop bears over the plug counterbore")
