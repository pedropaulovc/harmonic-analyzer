"""Tap, wall and free-eye budgets for the gooseneck's counter-spring screw.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4, supersedes #1951's clamped
eye: the whole gooseneck is still 1/2 in tube ending flush in the solid
Ø.500 end piece (sm_gooseneck_geom), but the counter spring's upper eye now
rides FREE on the 1/4 shoulder of a purchased shoulder screw (MHA-SM-VN-56)
under an MHA-SM-VN-57 washer beneath its head.  Owner ruling 2026-11-08
(Pedro, #2144 item 11.4): keep the slotted design; slotted McMaster 91829A566
found by vendor search, pending owner confirmation, with the McMaster
93475A250 washer found for that shoulder (the ruling's 91259A576 5/16
shoulder drops the arm 0.79 mm and its leading half-turn meets the tube).
The shoulder end seats on the end face and the 10-24 thread runs into a plain
#10-24 UNC blind tap: no counterbore, no position frames, no datums.  The
tap's axis carries the implied-zero coaxial offset of the title block's .XXX
row.

One owner minor (cad/config/parts/sm-gooseneck.yaml RV-04, drafted pending
the owner's confirmation) stands against rule 18: the catalogue screw's 3/8
thread, less its undercut and tip lead, engages ENGAGEMENT_MIN (1.16D) of
full thread, under 1.5D.  The check raises unless that declaration is
present (sm_gooseneck_spec).  MHA-SM-01 prints decimal inch (#290): every term
below charges the limits its sheet prints.
"""

from __future__ import annotations

import math

import sm_gooseneck_geom as gooseneck
import sm_vn_counter_spring_stock_geom as spring
import sm_vn_gooseneck_shoulder_screw_spec as screw
import sm_vn_gooseneck_shoulder_washer_spec as washer
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
# The tap's axis to the end piece's OD: no frame and no datum (owner ruling
# 2026-11-08, #2144 item 11.4), so the implied-zero coaxial offset is the
# title block's .XXX row, a radial offset of its band.
THREAD_AXIS_OFFSET_MAX = printed_band_mm(3, unit=UNIT)
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
#   tube's bore yields (0.014 at SF 1.5): a window too narrow on a stock bore
#   measured in the shop.
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
#   end, L/D 0.5 on a 9 mm shaft 0.6) holds about 2.2 N m, over the
#   shoulder screw's seating torque reacting through the head.
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


def owner_minor(row: dict, exception_id: str, part: str) -> None:
    """Refuse a shortfall the owner has not declared as a ``minor``.

    ``row`` is the part's registry row, read by the part's own spec through a
    literal ``_config.parts(<dashed-name>)``: this module reads no registry
    row, so the channel-seat consumers of settled_spring_seats do not re-key
    on the part's row (codjiflo P3 on #1997).  The review itself validates
    every declaration's form (machinist_exceptions.load_exceptions).
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


# --- The free eye on the shoulder ---------------------------------------------
# Owner ruling 2026-11-08 (Pedro), #2144 item 11.4, supersedes #1951's clamped
# eye: the loop is no longer clamped (the clamp preload, coil-bound gap and
# clamped-gap stacks are gone); it hangs on the shoulder between the end face
# and the washer, free to slide and swivel.  The catalogue limits:
SHOULDER_DIA_MIN = screw.SHOULDER_DIA + screw.SHOULDER_DIA_BAND[1]
SHOULDER_DIA_MAX = screw.SHOULDER_DIA + screw.SHOULDER_DIA_BAND[0]
SHOULDER_LENGTH_MIN = screw.SHOULDER_LENGTH + screw.SHOULDER_LENGTH_BAND[1]
SHOULDER_LENGTH_MAX = screw.SHOULDER_LENGTH + screw.SHOULDER_LENGTH_BAND[0]
# The washer slides onto the shoulder at its tightest pair, and its float on
# the shoulder (the loose pair, half the diametral clearance) still leaves the
# head (Ø.357 MIN, the spec's B18.3 allowance) bearing on it all round.
WASHER_SHOULDER_CLEARANCE_MIN = washer.ID_MIN - SHOULDER_DIA_MAX
WASHER_FLOAT_MAX = (washer.ID_MAX - SHOULDER_DIA_MIN) / 2.0
HEAD_WASHER_OVERLAP_MIN = screw.HEAD_DIA_MIN / 2.0 - (
    washer.ID_MAX / 2.0 + WASHER_FLOAT_MAX
)
# The washer's bore can sit on the screw's head fillet, charged at B18.3's
# 1/4 row (the spec's allowance): from the under-head neck (Ø.227 MIN) to the
# head face inside Ø.276 MAX: its
# largest radius is the difference, and the washer's inner edge can come no
# nearer the axis than the shoulder's smallest surface.  The fillet's height
# there stands the washer off the head face.
_FILLET_R_MAX = (screw.HEAD_FILLET_TRANSITION_DIA_MAX - screw.SHOULDER_NECK_DIA_MIN) / 2.0
_FILLET_OUTER_R = screw.HEAD_FILLET_TRANSITION_DIA_MAX / 2.0
_WASHER_EDGE_R = SHOULDER_DIA_MIN / 2.0
WASHER_SEAT_STANDOFF_MAX = (
    _FILLET_R_MAX
    - math.sqrt(max(0.0, _FILLET_R_MAX**2 - (_FILLET_OUTER_R - _WASHER_EDGE_R) ** 2))
    if _WASHER_EDGE_R < _FILLET_OUTER_R
    else 0.0
)
# The loop's FREE envelope along the shoulder (LOOP_RISE + wire, the
# 1330K524's 1.75 turns of 1.6002 wire): sm_gooseneck_geom.SPRING_EYE_GAP.
LOOP_ENVELOPE = gooseneck.SPRING_EYE_GAP
# The eye's room: the end face to the washer's face, at the worst limits.
EYE_SPACE_MIN = SHOULDER_LENGTH_MIN - washer.THICKNESS_MAX - WASHER_SEAT_STANDOFF_MAX
EYE_SPACE_MAX = SHOULDER_LENGTH_MAX - washer.THICKNESS_MIN
# The eye's axial play along the shoulder: positive at the tightest stack, so
# the loop never jams between the washer and the end face.
EYE_AXIAL_PLAY_MIN = EYE_SPACE_MIN - LOOP_ENVELOPE
EYE_AXIAL_PLAY_MAX = EYE_SPACE_MAX - LOOP_ENVELOPE
# The eye rides free on the shoulder: the Ø.374 eye over the largest
# shoulder.
EYE_SHOULDER_CLEARANCE_MIN = spring.EYE_ID_MM - SHOULDER_DIA_MAX
# Retention: the washer's worst-case overlap of the eye's ID; the 1.0 check
# is the one the retired made screw's head was held to.  The bare head
# (Ø.357 MIN) would keep only HEAD_ONLY_RETENTION_MIN, under the eye's own
# radius, which is why the washer is there.
RETENTION_TARGET = 1.0
WASHER_RETENTION = (washer.OD - spring.EYE_ID_MM) / 2.0
WASHER_RETENTION_MIN = (washer.OD_MIN - spring.EYE_ID_MM) / 2.0
HEAD_ONLY_RETENTION_MIN = (screw.HEAD_DIA_MIN - spring.EYE_ID_MM) / 2.0
# The washer (1.8 MAX) covers less than the under-head neck allowance (.093
# MAX wide), so the loop's head-side wire can bear over the neck.  Its
# step down from the shoulder is under the wire's radius, so the round wire
# rides back up onto the shoulder as the loop slides: it cannot wedge there.
SHOULDER_NECK_STEP_MAX = (SHOULDER_DIA_MAX - screw.SHOULDER_NECK_DIA_MIN) / 2.0
WIRE_R = spring.WIRE_RADIUS_MM

# --- The screw's strength under the counter spring ---------------------------
# The slotted 18-8 screw is rated 70,000 psi tensile (Rockwell B55, shear not
# rated).  The eye's pull bends it as a cantilever off the end face: the load
# can act no farther out than the washer's face (EYE_SPACE_MAX), and the
# least section at that face is the thread's undercut land (Ø3.3528), which
# the end piece's tap mouth actually supports, so the root stress below is a
# bound.  Callers pass the spring's catalogue maximum load (spring_mount_geom
# reads it from the registry; this module reads no row).
LOAD_LEVER_MAX = EYE_SPACE_MAX
_ROOT_SECTION_MODULUS = math.pi * screw.THREAD_NECK_DIA_MIN**3 / 32.0
_ROOT_AREA = math.pi * screw.THREAD_NECK_DIA_MIN**2 / 4.0


def root_stress_mpa(load_n: float) -> tuple[float, float]:
    """Bending and direct-shear stress (MPa) at the undercut land for ``load_n``
    hung at the washer's face."""
    return load_n * LOAD_LEVER_MAX / _ROOT_SECTION_MODULUS, load_n / _ROOT_AREA


# --- The end piece's blind tap (drawing-guidelines.md rule 18) -----------------
# The shoulder seats on the end face, so the screw's tip stands its catalogue
# thread length (3/8) into the tap.  The full thread runs past that tip at the
# printed band; a bottoming tap's 1.5-pitch
# lead (TAP_LEAD) past the deepest full thread stays inside the shallowest
# full-Ø drill; the drill's 118-degree point may cross into the shank, where
# DRILL_POINT_SHANK_WALL_MIN is its wall (below).  Both depths run from the
# end face (the Hole Wizard start face) and print .XX on the inch sheet.
TAP_THREAD_DEPTH = 0.44 * MM_PER_IN
TAP_DRILL_DEPTH = 0.56 * MM_PER_IN
TAP_DEPTH_BAND = printed_band_mm(2, unit=UNIT)
TAP_LEAD = 1.5 * screw.PITCH
TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    screw.THREAD_SIZE,
    end="blind",
    depth_mm=TAP_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": TAP_THREAD_DEPTH},
)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
TAP_DRILL_DIA_MAX = TAP_DRILL_DIA + drilled_oversize_mm(unit=UNIT)
TAP_THREAD_DEPTH_MIN = TAP_THREAD_DEPTH - TAP_DEPTH_BAND
TAP_THREAD_DEPTH_MAX = TAP_THREAD_DEPTH + TAP_DEPTH_BAND
TAP_DRILL_DEPTH_MIN = TAP_DRILL_DEPTH - TAP_DEPTH_BAND
TAP_DRILL_DEPTH_MAX = TAP_DRILL_DEPTH + TAP_DEPTH_BAND
SCREW_REACH_MAX = screw.THREAD_LENGTH
TIP_THREAD_MARGIN_MIN = TAP_THREAD_DEPTH_MIN - SCREW_REACH_MAX
TAP_LEAD_DRILL_MARGIN_MIN = TAP_DRILL_DEPTH_MIN - (TAP_THREAD_DEPTH_MAX + TAP_LEAD)

# Full-thread engagement, mated: the screw's full thread starts past its
# undercut (the spec's THREAD_NECK_WIDTH_MAX, 2.3368 from the shoulder face)
# and ends 1.5 pitches short of
# its tip; the receiver's starts past the end face's .010 break and ends at
# its least full-thread depth.
SCREW_END_INCOMPLETE_MAX = 1.5 * screw.PITCH
SCREW_FULL_THREAD_START_MAX = screw.THREAD_NECK_WIDTH_MAX
SCREW_FULL_THREAD_END_MIN = screw.THREAD_LENGTH - SCREW_END_INCOMPLETE_MAX
ENGAGEMENT_MIN = min(SCREW_FULL_THREAD_END_MIN, TAP_THREAD_DEPTH_MIN) - max(
    SCREW_FULL_THREAD_START_MAX, EDGE_BREAK
)
ENGAGEMENT_MIN_D = 1.5
# Rule 20's stated fact, floored (never rounded up): inches to the sheet's
# .001 and diameters to .01.
ENGAGEMENT_CALLOUT_MIN = (
    math.floor(round(ENGAGEMENT_MIN / MM_PER_IN * 1000.0, 6)) / 1000.0
)
ENGAGEMENT_CALLOUT_D = math.floor(round(ENGAGEMENT_MIN / screw.MAJOR_DIA * 100.0, 6)) / 100.0

# drawing-guidelines.md rule 17 walls, FULL worst case, every term cited:
#  * the end piece's head OD at its lower printed limit (PLUG_DIA_DEVIATIONS,
#    title-block .XX);
#  * the tap at its basic major plus 0.025 root oversize (TAP_ROOT_OVERSIZE);
#  * the tap's implied-zero offset from the OD (THREAD_AXIS_OFFSET_MAX) and
#    its drill's wander (DRILL_WANDER_MAX);
#  * 0.3 degrees of drill run-off over the deepest thread and its lead: the
#    head OD is turned before brazing and the hole is drilled after, in a
#    DIFFERENT setup located on the tube, so the run-off term applies;
#  * the title-block .010 edge break on the tap's mouth and on the head's OD
#    edge at the end face (both counted together).
TAP_ROOT_OVERSIZE = 0.025
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
# The drill's point past the head, inside the shank: the deepest point's cone
# is widest in the shank at the head's end, against the shank at its lower
# printed limit, the drill's location terms and its run-off.  The head's end
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

if TAP_SPEC.size != screw.THREAD_SIZE or TAP_SPEC.thread_class != "2B":
    raise AssertionError("gooseneck shoulder screw does not match its blind tap")
if min(WASHER_SHOULDER_CLEARANCE_MIN, HEAD_WASHER_OVERLAP_MIN) <= 0.0:
    raise AssertionError("gooseneck washer does not slide on the shoulder under the head")
if EYE_AXIAL_PLAY_MIN <= 0.0:
    raise AssertionError("gooseneck spring loop jams between the washer and the end face")
if EYE_SHOULDER_CLEARANCE_MIN <= 0.0:
    raise AssertionError("gooseneck spring eye does not ride free on the shoulder")
if WASHER_RETENTION_MIN < RETENTION_TARGET:
    raise AssertionError("gooseneck washer does not retain the spring eye")
if SHOULDER_NECK_STEP_MAX >= WIRE_R:
    raise AssertionError("gooseneck spring wire can wedge in the shoulder's neck")
if ENGAGEMENT_MIN <= 0.0:
    raise AssertionError("gooseneck shoulder screw engages no full thread")
if TIP_THREAD_MARGIN_MIN <= 0.0:
    raise AssertionError("gooseneck screw tip reaches past the end piece's full thread")
if TAP_LEAD_DRILL_MARGIN_MIN < 0.0:
    raise AssertionError("gooseneck end piece's tap lead runs past its drill")
if TAP_DRILL_DEPTH_MAX > PLUG_HEAD_LENGTH_MIN:
    raise AssertionError("gooseneck end piece's full-Ø drill runs into its shank")
if min(PLUG_WALL_MIN, DRILL_POINT_SHANK_WALL_MIN) < PLUG_WALL_TARGET:
    raise AssertionError(
        "gooseneck end piece loses a drawing-guidelines.md rule 17 (walls and webs) wall"
    )
# ENGAGEMENT_MIN < ENGAGEMENT_MIN_D * MAJOR_DIA stands only on owner minor
# sm-gooseneck RV-04; the part spec (sm_gooseneck_spec) checks the declaration.
