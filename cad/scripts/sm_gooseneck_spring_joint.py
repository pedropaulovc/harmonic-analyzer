"""Seat, full-thread and wall budgets for the gooseneck's clamped spring eye.

Owner rulings 2026-10-27 (#1951).  The whole gooseneck is 1/2 in tube and its
arm ends flush in a solid Ø.500 end piece (sm_gooseneck_geom): MHA-SM-04's
1/4-28 UNF thread runs into the end piece's blind 1/4-28 UNF-2B tap, and the
loop of MHA-SM-VN-51 is clamped on the screw's plain Ø.250 body between the
head and the end face.  The upper eye is clamped, not left free to swivel
(user ruling 2026-09-21).  An arm-end counterbore clears the screw's die
run-out (codjiflo P1 on #1997): its incomplete threads never enter the end
piece's full 2B thread, even with the loop clamped to its least gap.

Two owner minors (2026-10-27, #1951) stand against unchanged checks: the
counterbore wall under rule 17's .080 target (cad/config/parts/sm-gooseneck.yaml
RV-01) and the Ø11.50 head's retention under the 1.0 check
(cad/config/parts/sm-gooseneck-spring-screw.yaml RV-01).  Each check raises
unless its declaration is present; the .060 wall floor and positive retention
always hold.  Both parts print decimal inch (#290): every term below charges
the limits their sheets print.
"""

from __future__ import annotations

import math

import sm_gooseneck_geom as gooseneck
import sm_gooseneck_spring_screw_geom as screw
import sm_vn_counter_spring_stock_geom as spring
from _hole_spec import DRILL_POINT_H, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    printed_band_mm,
    printed_deviations,
)

MM_PER_IN = gooseneck.MM_PER_IN
# MHA-SM-01 prints decimal inch (#290): every gooseneck band below is the
# inch sheet's, read through its geometry module's SHEET_UNIT.
UNIT = gooseneck.SHEET_UNIT
# The inch title block's .010 edge break: every budget charges it.  The
# native counter-seat certificate (cad/config/machine/springs.yaml
# upper_support, settled_spring_seats) records the support as calibrated,
# under the millimetre sheet's 0.25 break; spring seats stay as calibrated
# (#290 ruling), so the record keeps that value.
EDGE_BREAK = edge_break_chamfer_mm(unit=UNIT)
CALIBRATED_EDGE_BREAK = 0.25
# The end piece's head Ø (.50) and length (.85) print at the title block's
# .XX; the shank Ø (.363, below) at .XXX.  (lower, upper) mm about the model.
PLUG_DIA_DEVIATIONS = printed_deviations(gooseneck.PLUG_DIA, 2, unit=UNIT)
PLUG_HEAD_LENGTH_DEVIATIONS = printed_deviations(
    gooseneck.PLUG_HEAD_LENGTH, 2, unit=UNIT
)
# The thread axis's location limit, ".006 MAX RADIAL" under the tap callout.
THREAD_AXIS_OFFSET_MAX = 0.006 * MM_PER_IN
# The tap drill's wander off its axis at the point: a shop-capability term
# the wall budgets charge and the print does not carry (as the fleet's other
# drill-wander budgets, e.g. fr_top_frame_spec.KEEPER_TAP_DRILL_WANDER_DEG).
# A print row for it read as method and could not be inspected after tapping
# (machinist review of e487a1bb4; codjiflo P2 on #1997).
DRILL_WANDER_MAX = 0.10
# The end piece's shank is turned to the measured tube bore (the stock bore
# spans 9.02-9.91, sm_gooseneck_geom), and the diametral clearance is the
# mating requirement.  The retained Ø band still limits the shank, and the
# wall budget below uses its lower limit.  Owner ruling 2026-10-27 (#1997):
# the end piece is joined BEFORE the bend, cooled or fully cured first, so the
# solid shank, .046 short of the bend's exit tangent, supports the tube through
# the bend.  Three joints were weighed (#1997 joint-options note):
# - Press fit: rejected.  Shigley 10e eq. 3-57/3-58 (same steel, solid shaft)
#   caps the diametral interference at about 0.021 before the thinnest
#   tube's bore yields (0.014 at SF 1.5), and holding the clamp torque at
#   the screw's yield (DIN 7190 steel-steel friction 0.12) needs about
#   0.008: a 0.006 window on a stock bore measured in the shop.
# - Silver braze, BAg-7: the filler maker's flux-brazed window, 0.002-0.005 in
#   (0.051-0.127 mm) PER SIDE (Lucas-Milhaupt, "The Effect of Joint
#   Clearance on Braze Joint Strength", Table 1; per side as in its
#   "Designing Braze Joints at Temperature"), so .004-.010 in diametral;
#   the window takes .0040-.0098 in (0.1016-0.24892) so it stays inside the
#   LOCTITE 638 gap below, and prints rounded inward at four places.
# - LOCTITE 638 retaining compound, the alternative: the same window, inside
#   the TDS's 0.25 mm gap fill (TDS, August 2016).  ISO 10123 shear 25
#   N/mm^2 minimum at 24 h, derated by the Henkel Retaining Compound Design
#   Guide's factors (alloy steel 0.9, clearance 0.3 at the window's wide
#   end, L/D 0.5 on a 9 mm shaft 0.6) holds about 2.2 N m: 3.7 times the
#   clamp's worst tightening torque at its needed preload.
# The leg sleeve's stock select-fit takes the same window (sm_gooseneck_spec).
BRAZE_CLEARANCE_MIN = 0.1016  # .0040 in
BRAZE_CLEARANCE_MAX = 0.24892  # .0098 in
# LOCTITE 638 TDS (August 2016): bond gaps up to 0.25 mm.
LOCTITE_638_GAP_MAX = 0.25
if BRAZE_CLEARANCE_MAX > LOCTITE_638_GAP_MAX:
    raise AssertionError("the end piece's joint window passes LOCTITE 638's gap fill")
# The shank's Ø at .XXX, on the inch grid: the tube's nominal bore less the
# window's middle, .370 - .0069 = .363.
PLUG_SHANK_DIA = (
    round(
        (gooseneck.TUBE_BORE_DIA - (BRAZE_CLEARANCE_MIN + BRAZE_CLEARANCE_MAX) / 2.0)
        / MM_PER_IN,
        3,
    )
    * MM_PER_IN
)
PLUG_SHANK_DIA_DEVIATIONS = printed_deviations(PLUG_SHANK_DIA, 3, unit=UNIT)

# MHA-SM-04 as its inch sheet prints it (sm_gooseneck_spring_screw_geom
# PRINTED_BANDS / PRINTED_LIMITS): every screw term below charges these.
SCREW_LENGTH_LOWER, SCREW_LENGTH_UPPER = screw.PRINTED_BANDS["UnderHeadLength"]
SCREW_HEAD_DIA_MIN = screw.HEAD_DIA + screw.PRINTED_BANDS["HeadDia"][0]
SCREW_BODY_DIA_MIN = screw.BODY_DIA + screw.PRINTED_BANDS["BodyDia"][0]
SCREW_BODY_DIA_MAX = screw.BODY_DIA + screw.PRINTED_BANDS["BodyDia"][1]
SCREW_HEAD_RELIEF_CHAMFER_MAX = (
    screw.HEAD_RELIEF_CHAMFER + screw.PRINTED_BANDS["HeadReliefChamfer"][1]
)
SCREW_PLAIN_LENGTH_MIN = screw.PRINTED_LIMITS["PlainLength"]
SCREW_FULL_THREAD_STATION_MAX = screw.PRINTED_LIMITS["FullThread"]
SCREW_UNDERHEAD_CORNER_R_MAX = screw.PRINTED_LIMITS["UnderHeadCornerR"]


def owner_minor(row: dict, exception_id: str, part: str) -> None:
    """Refuse a shortfall the owner has not declared as a ``minor``.

    ``row`` is the part's registry row, read by the part's own spec through a
    literal ``_config.parts(<dashed-name>)``: this module reads no registry
    row, so the channel-seat consumers of settled_spring_seats (which reads
    the counterbore from here) do not re-key on these parts' rows (codjiflo
    P3 on #1997).  The review itself validates every declaration's form
    (machinist_exceptions.load_exceptions).
    """
    declared = row.get("machinist_exceptions") or ()
    if not any(
        isinstance(entry, dict)
        and entry.get("id") == exception_id
        and entry.get("kind") == "minor"
        for entry in declared
    ):
        raise AssertionError(
            f"{part}: no owner minor {exception_id} declares this shortfall"
        )


# The two gaps between the head face and the end face.  SPRING_EYE_GAP is the
# loop's FREE envelope (LOOP_RISE + wire): the CAD station the model, the
# native seat calibration and the loop-pass stations use.  The clamped loop is
# coil-bound: the 1330K524 eye is a 1.75-turn helix of pitch 1.8745 over
# 1.6002 wire, so its overlapping turns stand 0.274 apart, and its axial rate
# G d^4 / (8 D^3 n) (Shigley's Mechanical Engineering Design 10th ed. eq.
# 10-9; music wire G 82.7 GPa max, Table 10-5; mean D 11.0998, n 1.75) is
# LOOP_AXIAL_RATE ~ 28 N/mm, so it binds at LOOP_BIND_FORCE ~ 14 N, far under
# the clamp preload sm_gooseneck_spring_screw_spec.clamp_preload_n sweeps.
# Bound, the loop rises one wire diameter per turn: CLAMPED_GAP_MAX, the most
# the gap can be under clamp.  The two stacked pull-side layers bear on the
# body inside BOTH faces, so where they bear the gap is never under two wire
# diameters: CLAMPED_GAP_MIN (CLAMPED_AXIS_GAP_MIN, below, is the least on the
# screw's axis, where the screw sits deepest).  Each check takes the gap worst
# for it.
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

# The screw is not square in the end piece (codjiflo round 5 on #1997).  Its
# radial play in the 2B thread, bounded crest-to-root by the tap's major +
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
# The two stacked pull passes hold the faces CLAMPED_GAP_MIN apart where they
# bear on the body.  Their centreline stands the coil radius less the eye's
# offset from the screw axis, at most LOOP_PASS_RADIUS_MAX (at the largest
# body).  On the screw's own axis the head face, tilted SCREW_TILT_MAX against
# the end face, can stand closer by the tilt over that radius.  A rocked loop
# reaches toward this floor because the relieved head
# (sm_gooseneck_spring_screw_geom) bears only inside its flat
# (test_rocked_loop_keeps_the_gap_floor_and_bears_on_the_body).  Wherever the
# screw's station along its axis matters (its run-out and its tip), this is
# the least gap.
LOOP_PASS_RADIUS_MAX = (
    spring.COIL_MEAN_RADIUS_MM - (spring.EYE_ID_MM - SCREW_BODY_DIA_MAX) / 2.0
)
CLAMPED_AXIS_GAP_MIN = CLAMPED_GAP_MIN - math.tan(SCREW_TILT_MAX) * LOOP_PASS_RADIUS_MAX

# The screw's own full thread starts no later than the ".225 MAX" MHA-SM-04
# prints (SCREW_FULL_THREAD_STATION_MAX, from the head).  The run-out's incomplete
# threads are FAT (full crest, shallow root): in the end piece's full 2B
# thread they jam before the head clamps.  They reach deepest past the end
# face at the least gap on the screw's axis, and the tilt dips the
# full-thread circle's low side a further half major x sin(tilt), so the
# arm-end counterbore's depth clears the intrusion by
# COUNTERBORE_RUNOUT_MARGIN_MIN.
SCREW_RUNOUT_TILT_DIP = screw.MAJOR_DIA / 2.0 * math.sin(SCREW_TILT_MAX)
SCREW_RUNOUT_INTRUSION_MAX = (
    SCREW_FULL_THREAD_STATION_MAX - CLAMPED_AXIS_GAP_MIN + SCREW_RUNOUT_TILT_DIP
)
SCREW_RUNOUT_INTRUSION_FREE_MAX = (
    SCREW_FULL_THREAD_STATION_MAX - gooseneck.SPRING_EYE_GAP + SCREW_RUNOUT_TILT_DIP
)
COUNTERBORE_RUNOUT_MARGIN_MIN = 0.05
# Printed LIMIT depth from the end face: its MIN rounded UP to the inch
# sheet's .001, a .004 band.  The model stays at the calibrated 2.78 (the
# native counter-seat certificate records it; spring seats stay as
# calibrated, #290), inside the band.
COUNTERBORE_DEPTH_BAND = 0.004 * MM_PER_IN
COUNTERBORE_DEPTH_MIN = (
    math.ceil(
        round(
            (SCREW_RUNOUT_INTRUSION_MAX + COUNTERBORE_RUNOUT_MARGIN_MIN)
            / MM_PER_IN
            * 1000.0,
            6,
        )
    )
    / 1000.0
    * MM_PER_IN
)
COUNTERBORE_DEPTH_MAX = COUNTERBORE_DEPTH_MIN + COUNTERBORE_DEPTH_BAND
COUNTERBORE_DEPTH = 2.78
if not COUNTERBORE_DEPTH_MIN <= COUNTERBORE_DEPTH <= COUNTERBORE_DEPTH_MAX:
    raise AssertionError("gooseneck counterbore model depth leaves its printed band")
# The tilted screw's largest offset from the thread axis inside the
# counterbore, at the end face: the deepest floor plus the receiver's .010
# floor break past its first full thread.
SCREW_FACE_OFFSET_MAX = SCREW_RADIAL_PLAY_MAX + (
    COUNTERBORE_DEPTH_MAX + EDGE_BREAK
) * math.tan(SCREW_TILT_MAX)
# Ø printed as its own .004 LIMIT band (codjiflo P1 on #1997: a flat-floored
# counterbore is milled, not drilled, so the title block's DRILLED HOLES row
# cannot be assumed to govern it, and the .XXX row's -.005 would let the
# run-out reach the wall), its lower limit the largest .001 under the
# calibrated 7.00 model (.275).  The fat run-out (basic major, at or above
# the body's upper limit) must clear the bore's SMALLEST size with the screw
# and the bore each off the thread axis by their full bands: the
# counterbore's printed axis band to the tap (COUNTERBORE_AXIS_OFFSET_MAX,
# MHA-SM-01 note) and the tilted screw's SCREW_FACE_OFFSET_MAX, its largest
# anywhere in the bore.
COUNTERBORE_DIA = 7.00
COUNTERBORE_DIA_BAND = 0.004 * MM_PER_IN
COUNTERBORE_DIA_MIN = (
    math.floor(round(COUNTERBORE_DIA / MM_PER_IN * 1000.0, 6)) / 1000.0 * MM_PER_IN
)
COUNTERBORE_DIA_MAX = COUNTERBORE_DIA_MIN + COUNTERBORE_DIA_BAND
COUNTERBORE_AXIS_OFFSET_MAX = 0.004 * MM_PER_IN
RUNOUT_RADIAL_CLEARANCE_MIN = (
    (COUNTERBORE_DIA_MIN - screw.MAJOR_DIA) / 2.0
    - COUNTERBORE_AXIS_OFFSET_MAX
    - SCREW_FACE_OFFSET_MAX
)
# The floor's corner to the wall is a stop in the run-out's path: the title
# block's INSIDE CORNERS R.040 MAX would reach it (codjiflo P1 round 5 on
# #1997), so MHA-SM-01 prints FLOOR CORNER R.004 MAX, a native radial
# dimension the model carries at its limit, banded from sharp up to it.
COUNTERBORE_FLOOR_CORNER_R_MAX = 0.004 * MM_PER_IN
# (upper, lower)
COUNTERBORE_FLOOR_CORNER_R_BAND = (0.0, -COUNTERBORE_FLOOR_CORNER_R_MAX)
COUNTERBORE_FLOOR_CORNER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.004 MAX"

# Tip budgets: the free gap leaves the screw shallowest (full-thread reach),
# the least gap on its axis drives it deepest.
SCREW_REACH = screw.LENGTH - gooseneck.SPRING_EYE_GAP
SCREW_REACH_MIN = SCREW_REACH + SCREW_LENGTH_LOWER
SCREW_REACH_MAX = SCREW_REACH + SCREW_LENGTH_UPPER
CLAMPED_SCREW_REACH_MAX = screw.LENGTH + SCREW_LENGTH_UPPER - CLAMPED_AXIS_GAP_MIN
SCREW_END_INCOMPLETE_MAX = 1.5 * screw.PITCH
FULL_THREAD_REACH_MIN = SCREW_REACH_MIN - SCREW_END_INCOMPLETE_MAX

# The end piece's blind tap (drawing-guidelines.md rule 18).  Its full thread
# runs past the deepest screw tip at the printed band; a bottoming tap's
# 1.5-pitch lead (TAP_LEAD) past the deepest full thread stays inside the
# shallowest full-Ø drill; the drill's 118-degree point may cross into the
# shank, where DRILL_POINT_SHANK_WALL_MIN is its wall (below).  The tap
# starts on the counterbore's floor, its start face: the counterbore is cut
# first, and both printed depths run from that floor (a tap started on the
# end face and counterbored after read back a shortened native thread depth,
# 17.22 for 17.60, farm run 20261027T181248453Z).  From the end face, each
# depth stacks on the counterbore's LIMIT depth.  Both depths print .XX on
# the inch sheet (.58 thread, .68 drill), modelled on that grid.
TAP_THREAD_DEPTH_FROM_FLOOR = 0.58 * MM_PER_IN
TAP_DRILL_DEPTH_FROM_FLOOR = 0.68 * MM_PER_IN
TAP_DEPTH_BAND = printed_band_mm(2, unit=UNIT)
TAP_LEAD = 1.5 * screw.PITCH
TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    screw.THREAD_SIZE,
    end="blind",
    depth_mm=TAP_DRILL_DEPTH_FROM_FLOOR,
    thread_class="2B",
    overrides_mm={"ThreadDepth": TAP_THREAD_DEPTH_FROM_FLOOR},
)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
TAP_DRILL_DIA_MAX = TAP_DRILL_DIA + drilled_oversize_mm(unit=UNIT)
TAP_THREAD_DEPTH = COUNTERBORE_DEPTH + TAP_THREAD_DEPTH_FROM_FLOOR
TAP_DRILL_DEPTH = COUNTERBORE_DEPTH + TAP_DRILL_DEPTH_FROM_FLOOR
TAP_THREAD_DEPTH_MIN = (
    COUNTERBORE_DEPTH_MIN + TAP_THREAD_DEPTH_FROM_FLOOR - TAP_DEPTH_BAND
)
TAP_THREAD_DEPTH_MAX = (
    COUNTERBORE_DEPTH_MAX + TAP_THREAD_DEPTH_FROM_FLOOR + TAP_DEPTH_BAND
)
TAP_DRILL_DEPTH_MIN = (
    COUNTERBORE_DEPTH_MIN + TAP_DRILL_DEPTH_FROM_FLOOR - TAP_DEPTH_BAND
)
TAP_DRILL_DEPTH_MAX = (
    COUNTERBORE_DEPTH_MAX + TAP_DRILL_DEPTH_FROM_FLOOR + TAP_DEPTH_BAND
)
TIP_THREAD_MARGIN_MIN = TAP_THREAD_DEPTH_MIN - CLAMPED_SCREW_REACH_MAX
# Both depths run from the same floor, so its band cancels here.
TAP_LEAD_DRILL_MARGIN_MIN = (TAP_DRILL_DEPTH_FROM_FLOOR - TAP_DEPTH_BAND) - (
    TAP_THREAD_DEPTH_FROM_FLOOR + TAP_DEPTH_BAND + TAP_LEAD
)

# The RECEIVER's full thread, mated: from the counterbore floor (and its .010
# break) to the shallower of the screw's last full thread at the free gap and
# the end piece's least full-thread depth.
ENGAGEMENT_NOMINAL = (
    min(SCREW_REACH - SCREW_END_INCOMPLETE_MAX, TAP_THREAD_DEPTH)
    - COUNTERBORE_DEPTH
    - EDGE_BREAK
)
ENGAGEMENT_MIN = (
    min(FULL_THREAD_REACH_MIN, TAP_THREAD_DEPTH_MIN)
    - COUNTERBORE_DEPTH_MAX
    - EDGE_BREAK
)

# drawing-guidelines.md rule 17 walls, FULL worst case, every term cited:
#  * the end piece's head OD at its lower printed limit (PLUG_DIA_DEVIATIONS,
#    title-block .XX);
#  * the tap at its basic major plus 0.025 root oversize (TAP_ROOT_OVERSIZE);
#  * the tap's locating band, thread axis to tube axis, and its printed DRILL
#    WANDER (THREAD_AXIS_OFFSET_MAX, DRILL_WANDER_MAX; the MHA-SM-01 note);
#  * 0.3 degrees of drill run-off over the deepest thread and its lead: the
#    head OD is turned before brazing and the hole is drilled after, in a
#    DIFFERENT setup located on the tube, so the run-off term applies;
#  * the title-block .010 edge break on the tap edge (counterbore floor) and
#    on the head's OD edge at a face (both counted together, although they
#    never share a station).
DRILL_RUNOFF_DEG = 0.3
_RUNOFF = math.tan(math.radians(DRILL_RUNOFF_DEG))
DRILL_RUNOFF_MAX = (TAP_THREAD_DEPTH_MAX + TAP_LEAD) * _RUNOFF
PLUG_WALL_NOMINAL = (gooseneck.PLUG_DIA - screw.MAJOR_DIA) / 2.0
PLUG_WALL_MIN = (
    (gooseneck.PLUG_DIA + PLUG_DIA_DEVIATIONS[0]) / 2.0
    - (screw.MAJOR_DIA + TAP_ROOT_OVERSIZE) / 2.0
    - THREAD_AXIS_OFFSET_MAX
    - DRILL_WANDER_MAX
    - DRILL_RUNOFF_MAX
    - 2.0 * EDGE_BREAK
)
# Rule 17 on the inch sheet: .080 target, .060 floor.
PLUG_WALL_TARGET = WALL_TARGET_MM
PLUG_WALL_FLOOR = WALL_FLOOR_MM
# The same wall at the counterbore: its largest printed size, its location
# (the tap's band plus COUNTERBORE_AXIS_OFFSET_MAX), run-off over its deepest
# floor, the two .010 breaks.  Under the .080 target: owner minor
# sm-gooseneck RV-01 (2026-10-27, #1951); MHA-SM-01 states it, floored to
# .001 in, as COUNTERBORE_WALL_CALLOUT_MIN.
COUNTERBORE_RUNOFF_MAX = COUNTERBORE_DEPTH_MAX * _RUNOFF
COUNTERBORE_WALL_MIN = (
    (gooseneck.PLUG_DIA + PLUG_DIA_DEVIATIONS[0]) / 2.0
    - COUNTERBORE_DIA_MAX / 2.0
    - THREAD_AXIS_OFFSET_MAX
    - COUNTERBORE_AXIS_OFFSET_MAX
    - COUNTERBORE_RUNOFF_MAX
    - 2.0 * EDGE_BREAK
)
# Inches, floored (never rounded up) to the sheet's .001.
COUNTERBORE_WALL_CALLOUT_MIN = (
    math.floor(round(COUNTERBORE_WALL_MIN / MM_PER_IN * 1000.0, 6)) / 1000.0
)
# The drill's point past the head, inside the shank: the deepest point's cone
# is widest in the shank at the head's end, against the shank at its lower
# printed limit, the drill's location bands and its run-off.  The head's end
# stands PLUG_HEAD_LENGTH from the end face at its title-block .XX band, so
# both drill envelopes take the SHORTEST head (codjiflo P1 on #1997): the
# full-Ø drill stays inside it, and the point's cone meets the shank there.
PLUG_HEAD_LENGTH_MIN = gooseneck.PLUG_HEAD_LENGTH + PLUG_HEAD_LENGTH_DEVIATIONS[0]
_POINT_TIP_MAX = TAP_DRILL_DEPTH_MAX + DRILL_POINT_H * TAP_DRILL_DIA_MAX / 2.0
DRILL_POINT_RADIUS_AT_SHANK = max(
    0.0,
    TAP_DRILL_DIA_MAX
    / 2.0
    * (_POINT_TIP_MAX - PLUG_HEAD_LENGTH_MIN)
    / (DRILL_POINT_H * TAP_DRILL_DIA_MAX / 2.0),
)
DRILL_POINT_SHANK_WALL_MIN = (
    (PLUG_SHANK_DIA + PLUG_SHANK_DIA_DEVIATIONS[0]) / 2.0
    - min(DRILL_POINT_RADIUS_AT_SHANK, TAP_DRILL_DIA_MAX / 2.0)
    - THREAD_AXIS_OFFSET_MAX
    - DRILL_WANDER_MAX
    - _POINT_TIP_MAX * _RUNOFF
)

# Head retention: the head's worst-case overlap of the eye's ID.  The 1.0
# check stands; the Ø11.50 head (the reference photo's proportion) keeps
# 0.95 at its printed LIMIT band's .449 under owner minor
# sm-gooseneck-spring-screw RV-01 (2026-10-27, #1951).
HEAD_RETENTION_TARGET = 1.0
HEAD_RETENTION = (screw.HEAD_DIA - spring.EYE_ID_MM) / 2.0
HEAD_RETENTION_MIN = (SCREW_HEAD_DIA_MIN - spring.EYE_ID_MM) / 2.0

# The head's clamp flat.  The relief chamfer (sm_gooseneck_spring_screw_geom)
# ends the flat under-head face at the smallest head less the largest
# chamfer; the clamp's first pull pass, the loop's wire nearest the screw
# axis (at most LOOP_PASS_RADIUS_MAX off it), still bears on it.
HEAD_FLAT_RADIUS_MIN = SCREW_HEAD_DIA_MIN / 2.0 - SCREW_HEAD_RELIEF_CHAMFER_MAX
HEAD_FLAT_BEARING_MARGIN_MIN = HEAD_FLAT_RADIUS_MIN - LOOP_PASS_RADIUS_MAX

# The loop on its seat.  The clamp fixes the loop's two pull-side passes (the
# wire that bears on the screw) at these stations from the head face: the
# half-turn clocking sends loop +Z toward the end piece (spring_mount_geom
# counter_pose, build_sm_summing_assembly).  Both passes must bear on the
# plain body, so each lies short of the thread's earliest start
# (PLAIN_LENGTH_MIN).  LOOP_PASS_X is the free (CAD, native-seat) state; the
# coil-bound loop rises CLAMPED_LOOP_RISE in CLAMPED_GAP_MAX.
#
# Rocked states.  A rocked loop's passes can reach anywhere between the faces,
# but the screw offers them one diameter there: the body is the die's blank,
# and a die-cut run-out's crests stand at that blank, never above it, so no
# held or rocked state meets a step it could wedge on (the 45-degree lead of
# the #8-32 shoulder screw is gone, and with it the held-state filter codjiflo
# questioned on #1997).  The screw's reaction on the wire is radial in every
# state, and the end face bounds the farthest bearing wire at gap - WIRE_R.
# The corner clearance holds for a wire touching the head face itself,
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


# The plug-side pass short of the thread's earliest start, at either state.
LOOP_PLAIN_MARGIN_MIN = SCREW_PLAIN_LENGTH_MIN - max(
    LOOP_PASS_X[1], CLAMPED_LOOP_PASS_X[1]
)
# The under-head fillet MHA-SM-04 prints "R.020 MAX", against a wire bearing on
# the body; the clearance grows with the station past WIRE_R, so the head-face
# floor is the least of every state.
LOOP_CORNER_CLEARANCE_MIN = _fillet_clearance(
    WIRE_R, WIRE_R, SCREW_UNDERHEAD_CORNER_R_MAX, WIRE_R
)
# The counterbore floor's "R.004 MAX" against the run-out's crest corner at
# its least axial and radial clearances (both above).
RUNOUT_FLOOR_CORNER_CLEARANCE_MIN = _fillet_clearance(
    COUNTERBORE_DEPTH_MIN - SCREW_RUNOUT_INTRUSION_MAX,
    RUNOUT_RADIAL_CLEARANCE_MIN,
    COUNTERBORE_FLOOR_CORNER_R_MAX,
    0.0,
)

# The loop against the counterbore mouth.  The eye's inner surface bears on
# the body on the pull side, so its axis stands EYE_ID/2 - BODY/2 from the
# screw axis.  The mouth's reach from the screw axis is the counterbore's
# largest radius, its .010 edge break, and both axis offsets
# (COUNTERBORE_AXIS_OFFSET_MAX and SCREW_FACE_OFFSET_MAX, as for the run-out).
# Two facts, each at the worse body limit and the worse untilted gap:
#  * LOOP_FACE_CONTACT_RADIUS_MIN: the wire that meets the end face is the
#    loop's plug-side tip (end of the helix), half a turn past the plug-side
#    pull pass, on the far side of the eye: its distance from the screw axis;
#  * LOOP_MOUTH_STANDOFF_MIN: every wire inside the mouth's reach is the
#    body-bearing pull pass, this far short of the end face.
COUNTERBORE_MOUTH_REACH = (
    COUNTERBORE_DIA_MAX / 2.0
    + EDGE_BREAK
    + COUNTERBORE_AXIS_OFFSET_MAX
    + SCREW_FACE_OFFSET_MAX
)
_COIL_R = spring.COIL_MEAN_RADIUS_MM


def _loop_face_clearance(
    gap: float, rise: float, body_dia: float
) -> tuple[float, float]:
    """``(face-contact radius, mouth standoff)`` for one gap and body size.

    Helix angle ``theta`` is measured so the pull passes (``_PASS_T``) sit at
    ``sin(theta) = 1``, toward the screw; the centreline's distance from the
    screw axis is ``sqrt(R^2 + d^2 - 2 R d sin(theta))``.
    """
    d = (spring.EYE_ID_MM - body_dia) / 2.0
    tip_radius = _COIL_R + d - WIRE_R  # t = 1: theta = 270 degrees
    reach = COUNTERBORE_MOUTH_REACH + WIRE_R
    sin_inside = (_COIL_R**2 + d**2 - reach**2) / (2.0 * _COIL_R * d)
    half_arc = math.acos(max(-1.0, min(1.0, sin_inside)))
    t_last = _PASS_T[1] + half_arc / (2.0 * math.pi * spring.LOOP_TURNS)
    standoff = gap - (_loop_station(gap, rise, t_last) + WIRE_R)
    return tip_radius, standoff


_FACE_CASES = tuple(
    _loop_face_clearance(gap, rise, body)
    for gap, rise in (
        (gooseneck.SPRING_EYE_GAP, spring.LOOP_RISE_MM),
        (CLAMPED_GAP_MAX, CLAMPED_LOOP_RISE),
    )
    for body in (SCREW_BODY_DIA_MIN, SCREW_BODY_DIA_MAX)
)
LOOP_FACE_CONTACT_RADIUS_MIN = min(case[0] for case in _FACE_CASES)
LOOP_MOUTH_STANDOFF_MIN = min(case[1] for case in _FACE_CASES)

if TAP_SPEC.size != screw.THREAD_SIZE or TAP_SPEC.thread_class != "2B":
    raise AssertionError("gooseneck spring screw does not match its blind tap")
if ENGAGEMENT_MIN < ENGAGEMENT_MIN_D * screw.MAJOR_DIA:
    raise AssertionError("gooseneck spring screw loses 1.5D full engagement")
if (
    COUNTERBORE_DEPTH_MIN - SCREW_RUNOUT_INTRUSION_MAX < COUNTERBORE_RUNOUT_MARGIN_MIN
    or SCREW_RUNOUT_INTRUSION_FREE_MAX > SCREW_RUNOUT_INTRUSION_MAX
):
    raise AssertionError("gooseneck screw run-out reaches the end piece's full thread")
if min(RUNOUT_RADIAL_CLEARANCE_MIN, RUNOUT_FLOOR_CORNER_CLEARANCE_MIN) <= 0.0:
    raise AssertionError("gooseneck screw run-out rubs the end piece's counterbore")
if TIP_THREAD_MARGIN_MIN <= 0.0:
    raise AssertionError("gooseneck screw tip reaches past the end piece's full thread")
if TAP_LEAD_DRILL_MARGIN_MIN < 0.0:
    raise AssertionError("gooseneck end piece's tap lead runs past its drill")
if TAP_DRILL_DEPTH_MAX > PLUG_HEAD_LENGTH_MIN:
    raise AssertionError("gooseneck end piece's full-Ø drill runs into its shank")
if (
    min(PLUG_WALL_MIN, COUNTERBORE_WALL_MIN, DRILL_POINT_SHANK_WALL_MIN)
    < PLUG_WALL_FLOOR
):
    raise AssertionError(
        "gooseneck end piece loses a drawing-guidelines.md rule 17 (walls and webs) floor"
    )
if min(PLUG_WALL_MIN, DRILL_POINT_SHANK_WALL_MIN) < PLUG_WALL_TARGET:
    raise AssertionError(
        "gooseneck end piece loses a drawing-guidelines.md rule 17 (walls and webs) wall"
    )
# COUNTERBORE_WALL_MIN < PLUG_WALL_TARGET and HEAD_RETENTION_MIN <
# HEAD_RETENTION_TARGET each stand only on an owner minor; the part specs
# (sm_gooseneck_spec, sm_gooseneck_spring_screw_spec) check the declarations.
if HEAD_FLAT_BEARING_MARGIN_MIN <= 0.0:
    raise AssertionError("gooseneck screw's relief chamfer takes the loop off its flat")
if min(LOOP_PLAIN_MARGIN_MIN, LOOP_CORNER_CLEARANCE_MIN) <= 0.0:
    raise AssertionError("gooseneck spring loop bears off the screw's plain body")
if not LOOP_PASS_X[0] < LOOP_PASS_X[1] < SCREW_PLAIN_LENGTH_MIN:
    raise AssertionError("gooseneck spring loop passes do not lie on the plain body")
if not CLAMPED_LOOP_PASS_X[0] < CLAMPED_LOOP_PASS_X[1] < SCREW_PLAIN_LENGTH_MIN:
    raise AssertionError("clamped gooseneck spring loop passes leave the plain body")
if (
    LOOP_FACE_CONTACT_RADIUS_MIN <= COUNTERBORE_MOUTH_REACH
    or LOOP_MOUTH_STANDOFF_MIN <= 0.0
):
    raise AssertionError("gooseneck spring loop bears over the end piece's counterbore")
