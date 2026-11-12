"""MHA-CH-00 fitter-package data: the settings chains and the keeper plan.

Builder data only, no SolidWorks: build_ch_channel_assembly authors the
settings reference sketches from it, and draw_ch_channel_assembly reads the
same names back. The named explode lives in ``ch_channel_explode_spec``. The
sheet data (which marked dimension shows as a reference, BOM descriptions,
dimension callouts) lives in ``ch_channel_assembly_sheet``, which only the
drawing reads, so a wording edit does not rebuild the assembly.

Settings: two construction sketches on the Right plane (sketch x is machine
-z, sketch y machine y), one per bank view, so each 1:1 view shows only the
chain on its own axis (the other lies 808 mm off it, off the sheet).
``PIVOT_FEATURE`` is a chain along the pivot axis -- south ear inner face,
south washer south face, hub 0 south face, hub 19 north face;
``FULCRUM_FEATURE`` one leg on the fulcrum axis between the keeper lugs'
inner faces. The spring set and the closed-up stack length are the fit-up's
two settings (rocker_bank_layout); the lug span is shown as a reference, the
pair being set off the top frame. ``KEEPER_PLAN_FEATURE``, on the Top plane
(sketch x is machine x, sketch y machine -z), is that setting: the
MHA-FR-02 features it is set from, in phantom (the frame is not in this
assembly) -- its west front upper socket (bore, boss and the boss's keeper
relief step), the line of the upper socket centres through it, and the west
rail's inner web face leaving the boss with the web centre line beside it --
and the lug centre line, dimensioned to the lug centre (X, within
KEEPER_FITUP_X_BAND_MM) and the two lug inner faces (Z, each within
KEEPER_FITUP_LOCATION_BAND_MM).
"""

from __future__ import annotations

import math

import ch_amplitude_bar_spec as _bar
import ch_rocker_arm_spec as _arm
from sh_vn_pivot_pin_bar_spec import BUDGET as _PIN_BUDGET
from sh_vn_pivot_pin_bar_spec import RUNNING_FLOOR as _BAR_RUNNING_FLOOR

from _assembly_contract import assembly_contract

from ch_fulcrum_keeper_spec import (
    FOOT_TIP_X,
    FULCRUM_KEEPER_CENTRE_Z,
    KEEPER_FITUP_LOCATION_BAND_MM,
    KEEPER_FITUP_X_BAND_MM,
    KEEPER_FITUP_X_FROM_WEB_MM,
    KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM,
    KEEPER_INNER_FACE_SPAN_MM,
    KEEPER_WIDTH,
    KEEPER_Z_OFF,
    LUG_HALF_T,
)
from channel_frame_geom import LEVER_FULCRUM_XY, ROCKER_PIVOT_XY
from _cone_axis_constants import FRAME_FRONT_COLUMN_Z
from fr_top_frame_spec import BOSS_DIA as SOCKET_BOSS_DIA
from fr_top_frame_spec import KEEPER_BOSS_RELIEF_FROM_SOCKET
from fr_top_frame_spec import KEEPER_BOSS_RELIEF_HALF_CHORD
from fr_top_frame_spec import WEB_T as RAIL_WEB_T
from frame_column_stations import COLUMN_X
from rocker_bank_layout import (
    HUB0_SOUTH_FACE_Z,
    HUB19_NORTH_FACE_Z,
    ROCKER_SPRING_SET,
    ROCKER_SPRING_SET_BAND,
    SOUTH_EAR_INNER_Z,
    SOUTH_WASHER_Z,
    STACK_L20_ACCEPT,
    STACK_L20_ACCEPT_BAND,
)

# The sheets print the assembly contract's drawing_unit (decimal inch, #290).
UNIT = assembly_contract("ch-channel").drawing_unit

# --- Settings reference sketches --------------------------------------------
PIVOT_FEATURE = "RockerBankSettingsReference"
FULCRUM_FEATURE = "LeverBankSettingsReference"
KEEPER_PLAN_FEATURE = "KeeperPlanSettingsReference"
FEATURES = (PIVOT_FEATURE, FULCRUM_FEATURE, KEEPER_PLAN_FEATURE)
SPRING_SET_DIMENSION = "RockerSpringSet"
STACK_LENGTH_DIMENSION = "RockerStackLength"
LUG_SPAN_DIMENSION = "KeeperLugSpan"
KEEPER_X_DIMENSION = "KeeperLugX"
KEEPER_FRONT_Z_DIMENSION = "KeeperFrontFaceZ"
KEEPER_REAR_Z_DIMENSION = "KeeperRearFaceZ"

# Pivot-axis chain stations, machine z, south to north.
PIVOT_CHAIN_Z = (
    SOUTH_EAR_INNER_Z,
    SOUTH_WASHER_Z[0],
    HUB0_SOUTH_FACE_Z,
    HUB19_NORTH_FACE_Z,
)
# Fulcrum-axis leg: the keeper lugs' inner faces, south then north.
LUG_INNER_FACE_Z = (
    FULCRUM_KEEPER_CENTRE_Z - (KEEPER_Z_OFF - LUG_HALF_T),
    FULCRUM_KEEPER_CENTRE_Z + (KEEPER_Z_OFF - LUG_HALF_T),
)
PIVOT_Y = ROCKER_PIVOT_XY[1]
FULCRUM_Y = LEVER_FULCRUM_XY[1]
# Keeper plan (machine x, z): the west rail's front socket centre, where its
# web centre line (the socket axis, x = COLUMN_X) meets the line of the
# upper socket centres (z = FRAME_FRONT_COLUMN_Z); the lug centre line
# KEEPER_FITUP_X_FROM_WEB_MM west of it. The frame features are drawn (b9ae
# review rule 10: the settings run from drawn features): in phantom, the
# socket's bore and boss, the boss's keeper relief step (owner ruling
# 2026-11-11, K5 on #1038: the faced rail top runs on into the two
# fulcrum-side bosses, a straight step square to the rail
# KEEPER_BOSS_RELIEF_FROM_SOCKET rearward of the socket centre, so the
# outward keeper foot lands on the faced flat), the socket line east past
# the boss toward its pair, and the web centre line from the socket to the
# front lug inner face station; the inner web face as a visible line from
# where it leaves the boss's lower barrel to that station. The front keeper
# stands on the web: its KEEPER_WIDTH straddles the outer face (+x) and
# stops short of the inner one, so the inner face runs on beside it. At the
# .300 pitch the keeper's foot tip lands on the relief, in front of where
# the outer face leaves the boss, so the outer face shows nowhere in plan
# (r5 review: drawn on under the keeper in phantom, a face reads as a hidden
# line through it) and the plan does not draw it.
KEEPER_SOCKET_XZ = (COLUMN_X, FRAME_FRONT_COLUMN_Z)
KEEPER_LUG_X = COLUMN_X + KEEPER_FITUP_X_FROM_WEB_MM
KEEPER_PLAN_SOCKET_LINE = 30.0  # east from the socket centre, past the boss
KEEPER_PLAN_WEB_HALF_T = RAIL_WEB_T / 2.0
# Where each web face leaves the boss's (unrelieved) lower barrel, rearward
# of the socket centre.
KEEPER_PLAN_WEB_FACE_FROM_SOCKET = math.sqrt(
    (SOCKET_BOSS_DIA / 2.0) ** 2 - KEEPER_PLAN_WEB_HALF_T**2
)
# The relief step's chord across the boss, rearward of the socket centre.
KEEPER_PLAN_RELIEF_FROM_SOCKET = KEEPER_BOSS_RELIEF_FROM_SOCKET
KEEPER_PLAN_RELIEF_HALF_CHORD = KEEPER_BOSS_RELIEF_HALF_CHORD
# The front keeper's foot tip (build_fr_top_frame KEEPER_FOOT_TIP_Z_FRONT),
# rearward of the socket centre.
KEEPER_PLAN_FOOT_TIP_FROM_SOCKET = (
    FULCRUM_KEEPER_CENTRE_Z - KEEPER_Z_OFF - FOOT_TIP_X - FRAME_FRONT_COLUMN_Z
)
if KEEPER_PLAN_SOCKET_LINE <= SOCKET_BOSS_DIA / 2.0:
    raise AssertionError("the keeper plan's socket line ends inside the boss")
if abs(KEEPER_LUG_X - LEVER_FULCRUM_XY[0]) > 1e-9:
    raise AssertionError("the keeper plan's lug centre line is off the fulcrum")
if any(
    abs(face - FRAME_FRONT_COLUMN_Z - offset) > 1e-9
    for face, offset in zip(LUG_INNER_FACE_Z, KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM)
):
    raise AssertionError("the keeper plan's faces are not the fit-up stations")
_RELIEF_CHORD_RADIUS = math.hypot(
    KEEPER_PLAN_RELIEF_HALF_CHORD, KEEPER_PLAN_RELIEF_FROM_SOCKET
)
if abs(_RELIEF_CHORD_RADIUS - SOCKET_BOSS_DIA / 2.0) > 1e-6:
    raise AssertionError("the keeper plan's relief step is not a chord of the boss")
# The plan's picture, front to rear: the relief step, the foot tip on the
# faced flat behind it, the outer web face leaving the boss under the keeper
# (hidden, so not drawn), the inner face running on to the inner-face
# station. If the foot tip ever stands behind the outer face's start, that
# face shows in front of the keeper and the plan must draw it again.
if not (
    KEEPER_PLAN_RELIEF_FROM_SOCKET
    < KEEPER_PLAN_FOOT_TIP_FROM_SOCKET
    < KEEPER_PLAN_WEB_FACE_FROM_SOCKET
    < LUG_INNER_FACE_Z[0] - FRAME_FRONT_COLUMN_Z
):
    raise AssertionError(
        "the keeper plan's foot tip is not on the boss relief, in front of the "
        "outer web face"
    )
if not (
    COLUMN_X - KEEPER_PLAN_WEB_HALF_T
    < KEEPER_LUG_X - KEEPER_WIDTH / 2.0
    < COLUMN_X + KEEPER_PLAN_WEB_HALF_T
    < KEEPER_LUG_X + KEEPER_WIDTH / 2.0
):
    raise AssertionError("the front keeper no longer covers just the outer web face")

if abs(PIVOT_CHAIN_Z[1] - PIVOT_CHAIN_Z[0] - ROCKER_SPRING_SET) > 1e-9:
    raise AssertionError("the spring-set leg is not ROCKER_SPRING_SET")
if abs(PIVOT_CHAIN_Z[3] - PIVOT_CHAIN_Z[2] - STACK_L20_ACCEPT[0]) > 1e-9:
    raise AssertionError("the stack leg is not the closed-up stack length")
if abs(LUG_INNER_FACE_Z[1] - LUG_INNER_FACE_Z[0] - KEEPER_INNER_FACE_SPAN_MM) > 1e-9:
    raise AssertionError("the lug leg is not the keeper inner-face span")

# Marked for the drawing: the settings and the reference span.
DRAWING_DIMENSIONS = {
    PIVOT_FEATURE: {SPRING_SET_DIMENSION, STACK_LENGTH_DIMENSION},
    FULCRUM_FEATURE: {LUG_SPAN_DIMENSION},
    KEEPER_PLAN_FEATURE: {
        KEEPER_X_DIMENSION,
        KEEPER_FRONT_Z_DIMENSION,
        KEEPER_REAR_Z_DIMENSION,
    },
}
# Inch places per setting. The spring set (.0236) is a closure the inch grid
# does not snap (the spring's installed height), so it prints to the four
# places that state its exact nominal within its band; so do the lug inner
# faces (1.3702, 7.4102), set off the kinematic fulcrum line. The closed-up
# stack is twenty .300 hubs, exactly 6.000 in, so it prints on the plain inch
# grid at its +.004/.000 band's three places (the four-place converted-mm
# print of the 7.0565 pitch, ch-channel RV-03, is gone); three for the lug
# centre (.114, band .004). The reference lug span is on the .XX grid (6.04).
DRAWING_PRECISION = {
    PIVOT_FEATURE: {SPRING_SET_DIMENSION: 4, STACK_LENGTH_DIMENSION: 3},
    FULCRUM_FEATURE: {LUG_SPAN_DIMENSION: 2},
    KEEPER_PLAN_FEATURE: {
        KEEPER_X_DIMENSION: 3,
        KEEPER_FRONT_Z_DIMENSION: 4,
        KEEPER_REAR_Z_DIMENSION: 4,
    },
}
DIMENSION_FEATURE = {
    name: feature for feature, names in DRAWING_DIMENSIONS.items() for name in names
}
# A tolerance prints at its nominal's places (ASME inch).
TOLERANCE_PRECISION = {
    name: places
    for places_by_name in DRAWING_PRECISION.values()
    for name, places in places_by_name.items()
}
# (lower, upper) deviations; the stack accepts only long (STACK_L20_ACCEPT).
# The keeper plan's three each carry their fit-up band on their own
# dimension (owner ruling X1+B1, 2026-10-18): each inner face off the socket
# line the location band, the lug centre off the web centre its own looser
# band (owner ruling X-A, 2026-10-18).
DIMENSION_TOLERANCES = {
    SPRING_SET_DIMENSION: (-ROCKER_SPRING_SET_BAND, ROCKER_SPRING_SET_BAND),
    STACK_LENGTH_DIMENSION: (-STACK_L20_ACCEPT_BAND[1], STACK_L20_ACCEPT_BAND[0]),
    KEEPER_X_DIMENSION: (-KEEPER_FITUP_X_BAND_MM, KEEPER_FITUP_X_BAND_MM),
    **{
        name: (-KEEPER_FITUP_LOCATION_BAND_MM, KEEPER_FITUP_LOCATION_BAND_MM)
        for name in (KEEPER_FRONT_Z_DIMENSION, KEEPER_REAR_Z_DIMENSION)
    },
}

# The bar-to-bar running gap down the bank (#1038, #2341): a channel-assembly
# stack (rocker hubs, strap, bar bow), kept here so the pin part's recipe
# closure stays the two parts it joins (Codjiflo r1 on PR #2601).
#
# The bars hang free between their end joints with a running gap to each
# neighbour, so a bow toward one closes it at mid-span. MHA-CH-00 controls
# the bow by acceptance, not by a frame on MHA-CH-01 (Repitch1038 2026-11-11,
# the owner's function-over-tight-numbers preference): before the bars are
# pinned, a BAR_BOW_MAX leaf must not enter under either side face of a bar
# laid on the surface plate, and after hook-up the BAR_GAP leaf passes
# between every adjacent pair. Bought CF square can bow about .013 over the
# bar's length (A108's 3/16 in per 10 ft, #2341 triage), so the stock is
# straightened or selected to the check (parts/ch-amplitude-bar.yaml process).
BAR_BOW_MAX_IN = 0.005
BAR_BOW_MAX_MM = BAR_BOW_MAX_IN * _bar.MM_PER_IN  # 0.127


def bar_gap_budget() -> dict[str, float]:
    """Least bar-to-bar gaps along the bank at the printed worst case (mm;
    #1038, #2341).

    ``top``: the bar pivot pin joint's ``neighbour_clearance_min``
    (``sh_vn_pivot_pin_bar_spec``). ``foot``: the same
    form on the foot notch and the real MHA-CH-06 strap (.098 +/-.001): the
    pitch the rocker hubs set (never short), the widest stock, the foot
    notch's float on the thinnest strap, both ledges' bands, and the strap's
    position zone to its hub (each strap half the zone off its hub's
    mid-plane, two neighbours toward each other). ``mid_span``: two straight
    bars between those end gaps, so at least their mean. ``mid_span_bowed``:
    that, less two neighbours each bowed the full ``BAR_BOW_MAX_MM`` toward
    the other. ``leaf``: the feeler leaf MHA-CH-00 passes
    between every adjacent pair, the least of those gaps floored to the
    .001 in a feeler set is sold in, so a bank inside its bands always
    passes it.
    """
    pitch_min = _arm.HUB_LENGTH  # the arms stack hub on hub at the pitch
    w_max = _bar.BAR_WIDTH
    notch_max = _bar.BOTTOM_NOTCH_WIDTH + _bar.BOTTOM_NOTCH_WIDTH_BAND[0]
    strap_min = _arm.ARM_THICKNESS + _arm.ARM_THICKNESS_BAND[1]
    top = _PIN_BUDGET["neighbour_clearance_min"]
    foot = (
        pitch_min
        - w_max
        - (notch_max - strap_min)
        - 2.0 * _bar.NOTCH_OFFSET_TOLERANCE_MM
        - _arm.STRAP_HUB_SYMMETRY
    )
    mid_span = (top + foot) / 2.0
    mid_span_bowed = mid_span - 2.0 * BAR_BOW_MAX_MM
    least = min(top, foot, mid_span_bowed)
    leaf = (
        math.floor(round(least / _bar.MM_PER_IN * 1000.0, 9)) / 1000.0 * _bar.MM_PER_IN
    )
    return {
        "top": top,
        "foot": foot,
        "mid_span": mid_span,
        "mid_span_bowed": mid_span_bowed,
        "leaf": leaf,
    }


BAR_GAP = bar_gap_budget()
if BAR_GAP["foot"] < _BAR_RUNNING_FLOOR - 1e-9:
    raise AssertionError(
        "a bar's foot-notch float can close the bar-to-bar running gap"
    )
if BAR_GAP["mid_span_bowed"] < _BAR_RUNNING_FLOOR - 1e-9:
    raise AssertionError(
        "two neighbouring bars each bowed BAR_BOW_MAX toward the other "
        "close the mid-span running gap"
    )
if BAR_GAP["leaf"] < _BAR_RUNNING_FLOOR - 1e-9:
    raise AssertionError("the bank's feeler leaf does not prove the running floor")
