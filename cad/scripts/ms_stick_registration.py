"""Where the MHA-MS-00 stick reads when it sets an amplitude bar (#2434).

Michelson's method, the stick as drawn (delegated ruling 2026-11-17, no
precedent, option 2, for the owner's review on #2144; issue #2434 comment
6970972423; book ch. 16 p. 36): the stop is clamped
on a graduation, the stick lies graduations up along the MHA-CH-06 rocker
arm's top edge with its 10 end toward the pivot, the stop's end face nearer
the 10 end bears on the arm's outer tip land (the end away from the
connecting rod), and the MHA-CH-01 bar is slid out until its outboard face
touches the stick's end face nearest the 10. The reading at the stop's end
face then sets the bar's station: the stick's 0 tick is not at the pivot, so
the reading for station d is about (d + 2.72 mm) / 14.2 and zero is the 0.2
tick. The arm land's and the stop face's own deviations are booked in
error_budget.yaml (rocker_tip_land, stop_face_square).

2-D, in the rocker's plane (machine X out along the lifting side, Y up), at
the authored level rest pose (channel_kinematics: crank home, every rocker
level, so all 20 outer tips line up under the stop). A straight stick on the
concave-up R799.746 top edge rests on the tip corner T and on its own 10-end
bottom corner E. The stop face is square to the stick and the land square to
the edge at T; the land leans out more steeply than the stick, so the face
first meets the land's bottom corner B. The 10 end meets the bar's outboard
face at whichever of its two corners reaches it first. Pure geometry from the
part specs: no SolidWorks, no drawing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import ch_rocker_arm_spec as arm
import channel_frame_geom
import channel_kinematics
import ms_stick_spec as stick
import ms_stop_spec as stop
from ms_stick_geom import DIVISION_SPACING, MINOR_PER_DIVISION

Point = tuple[float, float]

PIVOT: Point = channel_frame_geom.ROCKER_PIVOT_XY
_ARC_CENTER: Point = (channel_kinematics.ARC["acx"], channel_kinematics.ARC["acy"])
_RADIUS = arm.R_TOP
_ALPHA = (arm.TOP_ARC_LEN / 2.0) / arm.R_TOP  # half-angle of the top arc
# The outer (lifting-side, +X) tip: the top corner and the land's bottom corner.
TIP_CORNER: Point = (
    _ARC_CENTER[0] + _RADIUS * math.sin(_ALPHA),
    _ARC_CENTER[1] - _RADIUS * math.cos(_ALPHA),
)
LAND_BOTTOM: Point = (
    TIP_CORNER[0] + arm.TIP_FACE * math.sin(_ALPHA),
    TIP_CORNER[1] - arm.TIP_FACE * math.cos(_ALPHA),
)
MAX_STATION_MM = float(_config.machine("amplitude", "max_travel_mm"))

if abs(channel_kinematics.ARC["arm_tilt"]) > 0.02:
    raise AssertionError("the registration assumes the level rest pose")


def top_edge_y(x: float) -> float:
    """The rocker's top edge (machine Y) at machine X ``x``."""
    return _ARC_CENTER[1] - math.sqrt(_RADIUS * _RADIUS - (x - _ARC_CENTER[0]) ** 2)


@dataclass(frozen=True)
class Registration:
    """The stick registered on one bar at station ``station_mm`` (machine mm)."""

    station_mm: float
    reading: float  # numbered divisions at the stop's end face
    slope_deg: float  # the stick's rise toward the tip
    ten_end_bottom: Point  # E, on the top edge
    ten_end_top: Point  # the graduated face's 10-end corner
    stop_face_bottom: Point  # B, where the stop face meets the land
    bar_face_bottom: Point  # the bar's outboard face at its foot
    bar_face_up: Point  # unit vector up the bar's outboard face

    @property
    def offset_mm(self) -> float:
        """The reading's station less the bar's: the scale zero's distance
        inboard of the pivot along the stick."""
        return DIVISION_SPACING * self.reading - self.station_mm

    @property
    def land_depth_mm(self) -> float:
        """How far B lies below the stick's resting face, square to the stick."""
        u = (math.cos(math.radians(self.slope_deg)), math.sin(math.radians(self.slope_deg)))
        return (TIP_CORNER[0] - LAND_BOTTOM[0]) * -u[1] + (TIP_CORNER[1] - LAND_BOTTOM[1]) * u[0]


def _bar_face(station: float) -> tuple[Point, Point]:
    state = channel_kinematics.solve_state(station)
    tilt = -math.radians(state["bar_tilt"])  # the physical tilt
    return (state["bar_origin_x"], state["bar_origin_y"]), (math.sin(tilt), math.cos(tilt))


def _stick_frame(ten_end_x: float) -> tuple[Point, Point, Point]:
    """E, the 10-end top corner and the unit direction from E to the tip."""
    e = (ten_end_x, top_edge_y(ten_end_x))
    theta = math.atan2(TIP_CORNER[1] - e[1], TIP_CORNER[0] - e[0])
    u = (math.cos(theta), math.sin(theta))
    top = (e[0] - stick.BODY_THICKNESS * u[1], e[1] + stick.BODY_THICKNESS * u[0])
    return e, top, u


def register(station_mm: float) -> Registration:
    """The stop reading that sets a bar at ``station_mm`` from the pivot."""
    foot, up = _bar_face(station_mm)

    def face_x(y: float) -> float:
        return foot[0] + (y - foot[1]) / up[1] * up[0]

    def penetration(ten_end_x: float) -> float:
        e, top, _u = _stick_frame(ten_end_x)
        return max(face_x(e[1]) - e[0], face_x(top[1]) - top[0])

    # Slide E outboard from penetrating the bar until the first 10-end corner
    # just touches its outboard face.
    lo, hi = PIVOT[0] + station_mm - 5.0, PIVOT[0] + station_mm + 15.0
    if not (penetration(lo) > 0.0 >= penetration(hi)):
        raise RuntimeError(f"station {station_mm}: 10-end contact not bracketed")
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if penetration(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    e, top, u = _stick_frame(hi)
    # The stop face passes through B, square to the stick: its distance from
    # the 10-end face along the stick, then the graduation there.
    to_stop = (
        math.hypot(TIP_CORNER[0] - e[0], TIP_CORNER[1] - e[1])
        + (LAND_BOTTOM[0] - TIP_CORNER[0]) * u[0]
        + (LAND_BOTTOM[1] - TIP_CORNER[1]) * u[1]
    )
    reading = (stick.DIVISION_COUNT - 1) - (to_stop - stick.SCALE_END_MARGIN) / DIVISION_SPACING
    return Registration(
        station_mm=station_mm,
        reading=reading,
        slope_deg=math.degrees(math.atan2(u[1], u[0])),
        ten_end_bottom=e,
        ten_end_top=top,
        stop_face_bottom=LAND_BOTTOM,
        bar_face_bottom=foot,
        bar_face_up=up,
    )


def station_for_reading(reading: float) -> float:
    """The bar station (mm) a stop clamped at ``reading`` sets."""
    lo, hi = -10.0, MAX_STATION_MM + 10.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if register(mid).reading < reading:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def stick_reading(station_mm: float) -> float:
    """The stop reading (divisions) that sets a bar at ``station_mm``."""
    return register(station_mm).reading


# Every whole-millimetre station over the travel: the offset is nearly common.
_OFFSETS = tuple(register(float(d)).offset_mm for d in range(int(MAX_STATION_MM) + 1))
MEAN_OFFSET_MM = sum(_OFFSETS) / len(_OFFSETS)
OFFSET_SPREAD_MM = max(abs(offset - MEAN_OFFSET_MM) for offset in _OFFSETS)

# Zero: the stop on the graduation nearest the reading that sets a bar at the
# pivot (a minor tick), which must set it within a fraction of the budget.
ZERO_READING = stick_reading(0.0)
ZERO_TICK_READING = round(ZERO_READING * MINOR_PER_DIVISION) / MINOR_PER_DIVISION
ZERO_TICK_STATION_MM = station_for_reading(ZERO_TICK_READING)
if abs(ZERO_TICK_STATION_MM) > 0.1:
    raise AssertionError(
        f"the zero tick {ZERO_TICK_READING:g} sets a bar {ZERO_TICK_STATION_MM:+.3f} mm from the pivot"
    )
ZERO_TICK_TEXT = f"{ZERO_TICK_READING:.1f}"

# The stop's end face must reach down past B: below the stick's resting face
# it stands the window's spare height and the tapped floor.
STOP_FACE_DEPTH_MM = stop.WINDOW_HEIGHT - stick.BODY_THICKNESS + stop.FLOOR_THICKNESS
if not all(register(d).land_depth_mm < STOP_FACE_DEPTH_MM for d in (0.0, MAX_STATION_MM)):
    raise AssertionError("the stop's end face does not reach the tip land's bottom corner")
