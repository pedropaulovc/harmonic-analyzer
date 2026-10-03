"""Pure parked geometry of the alignment-pinion rig, in the machine x-y plane.

The pinion drum's parked station, the strap pivot it swings on, the strap's
lean and the follower pin's line, and the lift axis the eccentric cams turn
on.  build_drive_train_assembly places the rig from these, and the MHA-DT-000 fit-up
text (pinion_rig_tip_gap) derives the bench rest gap from the same numbers,
so neither reads the other and no library module reaches a build script (#880).

Placement only: no SolidWorks, no gates.  The assembly script keeps every
clearance and design-band assertion on these values.
"""

from __future__ import annotations

import math

import _config
from cone_line import DP_TRAIN, X_DRUM, Y_BASE_TOP, Y_DRIVE
from dt_pinion_bracket_geometry import C2C as STRAP_C2C
from dt_pinion_bracket_geometry import PIN_DROP as FPIN_DROP
from dt_pinion_pivot_block_geometry import LIFT_BORE_RISE, LIFT_BORE_SPACING

# --- alignment pinion (ch. 25): RESTORED 2026-07-02, carried DISENGAGED ------
# The rig stays level-inboard of the cylinder bank. Its user-authoritative 32T
# drum retains the train's DP 49.82, so the drum, pivot blocks and lift axis move
# together when tooth count or parked gap changes; no superseded world
# coordinate is frozen into this placement.
APINION_TEETH = int(_config.machine("alignment_pinion", "teeth"))
TIP_APINION = ((APINION_TEETH + 2.0) / DP_TRAIN) * 25.4 / 2.0
TIP_DRUM120 = (122.0 / DP_TRAIN) * 25.4 / 2.0
# U28 (user, 2026-09-23): parked out on the level line of centres.
APINION_GAP = float(_config.machine("alignment_pinion", "disengaged_tip_gap_mm"))
APINION_X = X_DRUM + TIP_DRUM120 + TIP_APINION + APINION_GAP
# Tip circles keep the configured parked gap at Delta-y = 0 (axis level).
APINION_Y = Y_DRIVE
PIVOT_Y = Y_BASE_TOP + 12.0  # 62.8: pivot block bore height
# The far side from the drum, so swinging the strap toward vertical advances
# the pinion into mesh.
PIVOT_X = APINION_X + math.sqrt(STRAP_C2C**2 - (APINION_Y - PIVOT_Y) ** 2)
# The v2 drive line makes the parked strap lean west of vertical.
STRAP_LEAN_DEG = math.degrees(math.atan2(PIVOT_X - APINION_X, APINION_Y - PIVOT_Y))
LIFT_X = PIVOT_X + LIFT_BORE_SPACING  # lift rod in the blocks' WEST bores
# v2 closure: the steep strap carries its follower contact above the pivot at
# the WEST cam station.
LIFT_Y = PIVOT_Y + LIFT_BORE_RISE

# The strap frame, parked: up its axis, and its east normal (east = machine -x).
_SPR_TH = math.radians(-STRAP_LEAN_DEG)  # the strap leans east of vertical
SPR_U = (math.sin(_SPR_TH), math.cos(_SPR_TH))
SPR_N = (-math.cos(_SPR_TH), math.sin(_SPR_TH))
# Follower-pin axis, machine frame: through the strap axis FPIN_DROP below the
# pivot, running WEST along -N (the axis RISES going west, N[1] < 0).
FPIN_C = (PIVOT_X - FPIN_DROP * SPR_U[0], PIVOT_Y - FPIN_DROP * SPR_U[1])


def pin_line_dist(centre_y: float, c=None, n=None) -> float:
    """Perpendicular distance from (LIFT_X, centre_y) to the pin axis line
    through ``c`` along ``n`` (parked: FPIN_C along SPR_N).  The skew
    perpendicular, not the vertical gap at the crossing x: the pin's closest
    approach is downhill-west of the crossing."""
    c = c if c is not None else FPIN_C
    n = n if n is not None else SPR_N
    dx, dy = LIFT_X - c[0], centre_y - c[1]
    return abs(dx * (-n[1]) - dy * (-n[0]))
