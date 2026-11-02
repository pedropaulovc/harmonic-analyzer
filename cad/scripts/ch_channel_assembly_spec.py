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
assembly) -- its west front upper socket (bore and boss), the line of the
upper socket centres through it, and the west rail's web faces leaving the
boss with the web centre line splitting them -- and the lug centre line,
dimensioned to the lug centre (X, within KEEPER_FITUP_X_BAND_MM) and the
two lug inner faces (Z, each within KEEPER_FITUP_LOCATION_BAND_MM).
"""

from __future__ import annotations

import math

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
# socket's bore and boss, the socket line east past the boss toward its pair,
# and the web centre line from the socket to the front lug inner face
# station; the web faces as visible lines, each from where it leaves the boss
# for as far as it shows in plan. The front keeper stands on the web: its
# KEEPER_WIDTH straddles the outer face (+x) and stops short of the inner
# one, so the inner face runs on beside it to the inner-face station and the
# outer face stops at the keeper's foot tip (r5 review: drawn on to the
# station in phantom, the faces read as hidden lines through the keeper).
KEEPER_SOCKET_XZ = (COLUMN_X, FRAME_FRONT_COLUMN_Z)
KEEPER_LUG_X = COLUMN_X + KEEPER_FITUP_X_FROM_WEB_MM
KEEPER_PLAN_SOCKET_LINE = 30.0  # east from the socket centre, past the boss
KEEPER_PLAN_WEB_HALF_T = RAIL_WEB_T / 2.0
# Where each web face leaves the boss, rearward of the socket centre.
KEEPER_PLAN_WEB_FACE_FROM_SOCKET = math.sqrt(
    (SOCKET_BOSS_DIA / 2.0) ** 2 - KEEPER_PLAN_WEB_HALF_T**2
)
# The front keeper's foot tip (build_fr_top_frame KEEPER_FOOT_TIP_Z_FRONT),
# rearward of the socket centre: where the outer web face goes under it.
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
if not (
    KEEPER_PLAN_WEB_FACE_FROM_SOCKET
    < KEEPER_PLAN_FOOT_TIP_FROM_SOCKET
    < LUG_INNER_FACE_Z[0] - FRAME_FRONT_COLUMN_Z
):
    raise AssertionError("the keeper plan's web faces end before they start")
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
# Inch places per setting. The stations are closures the inch grid does not
# snap (the channel pitch, the spring's installed height, the kinematic
# fulcrum line), so each banded one prints to the places that state its exact
# nominal within its band: four for the spring set (.0236), the closed-up
# stack (5.5563, so the "never short" acceptance holds) and the lug inner
# faces (1.5946, 7.1846); three for the lug centre (.114, band .004). The
# reference lug span is on the .XX grid (5.59).
DRAWING_PRECISION = {
    PIVOT_FEATURE: {SPRING_SET_DIMENSION: 4, STACK_LENGTH_DIMENSION: 4},
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
