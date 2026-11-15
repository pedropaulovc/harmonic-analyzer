"""Issue #2434: what the MHA-MS-00 stick reads when registered as Michelson did.

2-D, the rocker's plane (machine X right, Y up), from the origin/main specs:
the rocker arm level at crank home, its top edge the R799.746 arc, the outer
(lifting-side) tip land radial to it; amplitude bar i at station d (foot axis
X from the pivot), its outboard face from channel_kinematics.solve_state.

Registration (Michelson, ch. 16; engineerguy 4/4 at 0:59-1:14):
  * stick graduated face UP, stop clamped with its INBOARD end face (the end
    facing the stick's 10 end) on graduation R;
  * stick laid along the rocker's top edge, 10 end toward the pivot;
  * the stop's inboard end face bears on the rocker's outer tip land;
  * the bar is slid out until its outboard face meets the stick's 10-end face.

A straight stick on a concave-up arc rests on the tip corner T and on its own
10-end bottom corner E. The stop face is square to the stick, the land square
to the arc at T; the land leans out more steeply than the face, so the face
first meets the land's BOTTOM corner. Solves d(R) and prints the offset from
d = 14.2 R.

Run from cad/scripts of an origin/main worktree:
    uv run --frozen python <this file>
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import _rocker_interface as ri  # noqa: E402
import ch_amplitude_bar_spec as bar  # noqa: E402
import ch_rocker_arm_spec as arm  # noqa: E402
import channel_kinematics as ck  # noqa: E402
import ms_stick_spec as stick  # noqa: E402
import ms_stop_spec as stop  # noqa: E402
from ms_stick_geom import DIVISION_SPACING as P  # noqa: E402

OX, OY = ck._PIVOT
ACX, ACY = ck.ARC["acx"], ck.ARC["acy"]
R = ri.CURVE_RADIUS
ALPHA = arm._ALPHA_TOP  # half-angle of the top arc
T = (ACX + R * math.sin(ALPHA), ACY - R * math.cos(ALPHA))  # outer tip corner
B = (T[0] + arm.TIP_FACE * math.sin(ALPHA), T[1] - arm.TIP_FACE * math.cos(ALPHA))


def top_y(x: float) -> float:
    return ACY - math.sqrt(R * R - (x - ACX) ** 2)


def bar_face(d: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """Bar outboard face: (point at the bar's bottom corner, unit up-direction)."""
    s = ck.solve_state(d)
    beta = -math.radians(s["bar_tilt"])  # physical tilt
    return (s["bar_origin_x"], s["bar_origin_y"]), (math.sin(beta), math.cos(beta))


def face_x_at(d: float, y: float) -> float:
    (bx, by), (ux, uy) = bar_face(d)
    return bx + (y - by) / uy * ux


def _end_corners(xe: float):
    E = (xe, top_y(xe))
    theta = math.atan2(T[1] - E[1], T[0] - E[0])  # stick slope, rising outward
    u = (math.cos(theta), math.sin(theta))
    top = (E[0] - stick.BODY_THICKNESS * u[1], E[1] + stick.BODY_THICKNESS * u[0])
    return E, top, theta, u


def stick_reading(d: float) -> dict[str, float]:
    """Reading R at the stop face when the 10 end meets bar face at station d."""
    # The 10 end rests on the arc at its bottom corner E; slide E inboard until
    # the first of its two end corners (bottom E, top) reaches the bar face.
    def penetration(xe: float) -> float:
        E, top, _, _ = _end_corners(xe)
        return max(face_x_at(d, E[1]) - E[0], face_x_at(d, top[1]) - top[0])

    lo, hi = OX + d - 5.0, OX + d + 15.0  # penetrating .. clear
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if penetration(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    E, top, theta, u = _end_corners(hi)
    contact = "top" if face_x_at(d, top[1]) - top[0] > face_x_at(d, E[1]) - E[0] else "bottom"
    chord = math.hypot(T[0] - E[0], T[1] - E[1])
    # the stop face meets the land's bottom corner B: its station along the stick
    e = (B[0] - T[0]) * u[0] + (B[1] - T[1]) * u[1]
    gap_bottom = E[0] - face_x_at(d, E[1])
    length = chord + e  # 10-end face to the stop's reading face, along the stick
    reading = 10.0 - (length - stick.SCALE_END_MARGIN) / P
    depth_B = -((B[0] - T[0]) * -u[1] + (B[1] - T[1]) * u[0])
    return {
        "d": d,
        "reading": reading,
        "offset_mm": P * reading - d,
        "theta_deg": math.degrees(theta),
        "stop_face_beyond_T_mm": e,
        "land_corner_depth_below_stick_mm": depth_B,
        "contact_corner_of_10_end": contact,
        "bottom_corner_gap_to_bar_mm": gap_bottom,
        "E_x_from_pivot": E[0] - OX,
    }


rows = [stick_reading(d) for d in (0.0, 10.0, 22.0, 44.0, 66.0, 80.0, 88.0)]
null = -2.563  # error_budget report, this worktree
info = {
    "tip_corner_from_pivot_x": T[0] - OX,
    "tip_corner_above_pivot": T[1] - OY,
    "land_bottom_from_pivot_x": B[0] - OX,
    "top_arc_half_angle_deg": math.degrees(ALPHA),
    "stick_length": stick.BODY_LENGTH,
    "scale_zero_from_0_end": stick.SCALE_START_X,
    "scale_10_from_10_end": stick.SCALE_END_MARGIN,
    "stop_floor_below_stick": stop.WINDOW_HEIGHT - stick.BODY_THICKNESS + stop.FLOOR_THICKNESS,
    "stop_width_z": stop.TOTAL_DEPTH,
    "bar_width": bar.BAR_WIDTH,
    "rows": rows,
}
offs = [r["offset_mm"] for r in rows]
info["offset_mean"] = sum(offs) / len(offs)
info["offset_spread"] = (min(offs), max(offs))
info["zero_reading"] = next(
    r for r in [stick_reading(0.0)]
)["reading"]
print(json.dumps(info, indent=1))
Path(__file__).with_suffix(".json").write_text(json.dumps(info, indent=1))
