r"""Pure-data contract for the pen rod's set-screw relief groove (#2439).

PURE DATA, no SolidWorks/COM imports.  Owner ruling 2026-11-20 on #2439,
option B (in his words: "B"): turn a .010-deep groove round the pivot under
the v-block's set screw, in the setup that turns the pivot.  The purchased
MHA-SH-VN-54 cup point is unchanged and seats on the groove floor, so the
ring burr it raises stays below the pivot's fit surface in the MHA-PN-05
reamed bore (the .0005-.0025 sliding fit of pn_pen_rod_spec), and the groove
also captures the hanging block axially.

Kept out of ``pn_pen_rod_spec``, which the v-block, adjust-screw and hanger
specs import: the groove re-keys only the rod's part and drawing and the
pen carriage (``pn_pen_carriage_geom`` seats the screw on the floor and
proves the cup lands in the groove at the printed worst case).

Part frame as ``pn_pen_rod_spec``: origin on the rod axis at the SHOULDER,
the pivot running -Y.  Both walls are located from the shoulder (the face
the pivot's length is turned from, drawing-guidelines.md rules 10-11).
"""

from __future__ import annotations

import _config
import pn_pen_rod_spec as rod

# Ø.106, .010 under the Ø.126 pivot; .150 wide, centred .240 below the
# shoulder (the screw's axis station, block height .71 less its .47).
GROOVE_DIA = 2.6924  # .106
GROOVE_NEAR_STATION = 4.191  # .165, shoulder to the shoulder-side wall
GROOVE_FAR_STATION = 8.001  # .315, shoulder to the end-side wall
GROOVE_WIDTH = round(GROOVE_FAR_STATION - GROOVE_NEAR_STATION, 6)  # .150
GROOVE_DEPTH = (rod.PIVOT_DIA - GROOVE_DIA) / 2.0  # .010
# The revolve-cut profile's outer edge stands past the pivot (inside the
# square's section, below the shoulder, so it cuts only the pivot).
GROOVE_CUT_DIA = rod.ROD_SECTION

# The pivot keeps a land on each side of the groove: above it, clear of the
# shoulder root's R.008 MAX; below it, to the pivot end.
UPPER_LAND = GROOVE_NEAR_STATION - rod.SHOULDER_FILLET_R
LOWER_LAND = rod.PIVOT_LENGTH - GROOVE_FAR_STATION
if not 0.0 < GROOVE_DIA < rod.PIVOT_DIA + rod.PIVOT_BAND[1]:
    raise AssertionError("the groove does not cut below the smallest pivot")
if min(UPPER_LAND, LOWER_LAND) < 2.0:
    raise AssertionError("the groove leaves the pivot a land under 2 mm")

# The sheet: both wall stations and the floor's Ø print at three places (a
# .XX location would let the screw's point land on a land, a .XX Ø could
# leave the floor .003 under the pivot), each linked to the groove's one
# numbered note naming the screw it seats (drawing-guidelines.md rules 3-4).
GROOVE_FEATURE = "GrooveProfile"
GROOVE_DIMENSIONS = ("GrooveStation", "GrooveEndStation", "GrooveDia")
GROOVE_PLACES = 3
GROOVE_NOTE = 2
GROOVE_CALLOUT = f"SEE NOTE {GROOVE_NOTE}"
SET_SCREW_NUMBER = _config.parts("sh-vn-arbor-set-screw")["number"]
GROOVE_NOTE_TEXT = (
    f"{GROOVE_NOTE}. GROOVE: SEATS {SET_SCREW_NUMBER} SET SCREW CUP POINT."
)
DRAWING_DIMENSIONS: dict[str, set[str]] = {GROOVE_FEATURE: set(GROOVE_DIMENSIONS)}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    GROOVE_FEATURE: {name: GROOVE_PLACES for name in GROOVE_DIMENSIONS}
}
DIMENSION_CALLOUTS: dict[str, str] = {
    name: GROOVE_CALLOUT for name in GROOVE_DIMENSIONS
}
for _name, _mm in (
    ("GrooveStation", GROOVE_NEAR_STATION),
    ("GrooveEndStation", GROOVE_FAR_STATION),
    ("GrooveDia", GROOVE_DIA),
):
    _inch = _mm / 25.4
    if abs(round(_inch, GROOVE_PLACES) - _inch) > 1e-9:
        raise AssertionError(f"{_name} is off its .001 grid")
