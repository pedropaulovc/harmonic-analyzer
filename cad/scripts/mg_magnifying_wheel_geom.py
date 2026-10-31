r"""Magnifying-wheel nominal geometry -- the drawing-FREE constant block shared
by the part build, its ``_spec`` (drawing contract), the wire solvers and
``build_mg_magnifier_assembly``.

PURE DATA + math, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends on whatever module
it imports a constant from, so the drawing contract must NOT live here.

A gray-iron spider (ch21 pp.50-53): turned hub, bore and rim, six tapered
cast spokes. The hub carries an integral spigot on its front (pen) side; the
brass drum (``mg_wheel_drum_geom``) is pressed on it.

Part frame: wheel axis local Z, origin on the spokes' mid-plane, local +Z
toward the wheel bar (machine +z; the wheel is placed at identity). Front
view = looking along -Z from the pen side; a front-view clock angle phi maps
to local (x, y) = (-cos phi, sin phi), i.e. local angle 180 - phi.
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _printed_tolerance import angular_band_deg, printed_deviations
from mg_wheel_drum_geom import (
    DRUM_BORE,
    DRUM_BORE_BAND,
    DRUM_LEN,
    DRUM_LEN_BAND,
    DRUM_OD,
    DRUM_OD_DEVIATIONS,
    DRUM_WIRE_R,
    LEVER_WIRE_DIA,
)

import _mg_wheel_rim_geometry as _rim

# #290: the registry row's drawing_unit (in) is this sheet's unit.  The hub
# stations, boss Ø, spoke thickness and rim stay millimetre nominals (the
# lever-wire run, the drum lane and the pen interfaces read them) and print
# rounded; every check takes their PRINTED limits.  The cast spoke shapes and
# the ties sit on the inch grid.
UNIT = drawing_unit("parts/mg-magnifying-wheel", _config.parts("mg-magnifying-wheel"))


def printed_limits(
    model: float, places: int, band: tuple[float, float] | None = None
) -> tuple[float, float]:
    """(min, max) mm a part may show for ``model`` printed at ``places``:
    the title block's row, or the (upper, lower) ``band`` about the print.
    The model must lie inside them."""
    limits = None if band is None else (band[1], band[0])
    lower, upper = printed_deviations(model, places, limits, unit=UNIT)
    if not lower <= 0.0 <= upper:
        raise AssertionError(f"model {model} lies outside its printed limits")
    return model + lower, model + upper


WIRE_RATIO = _rim.RIM_WIRE_R / DRUM_WIRE_R  # 4.995, the wheel's magnification

# --- hub: Ø30 boss, then the drum spigot -----------------------------------------
# The boss holds TIE 1's wall at the title block's .XX on its Ø and on
# TIE 1's two coordinates, plus the hole's angular allowance and drill wander
# (mg_magnifying_wheel_spec.TIE1_HUB_WALL): the Ø25 boss held it only by
# banding both.
HUB_DIA = 30.0  # prints 1.18
HUB_LEN = 19.6  # back face to spigot front face, both faced; prints .772
# The hub sits off-centre toward the pen, its back face 0.09 proud of the
# rim's back face (RIM_AXIAL / 2), so the lever wire's slant down to the drum
# clears the rim's pen face (sh_vn_music_wire_lever_geom.RUN_GAPS) with the wheel on the
# pen-rod line; at 7.09 (hub about centred) that run hit the rim.
HUB_BACK_Z = 4.09
SPIGOT_DIA = DRUM_BORE
SPIGOT_LEN = 9.0  # the drum's .354 face sits .0003 under it; prints .354
HUB_STEP_Z = round(HUB_BACK_Z - (HUB_LEN - SPIGOT_LEN), 6)  # -6.51, boss front face
HUB_FRONT_Z = round(HUB_BACK_Z - HUB_LEN, 6)  # -15.51, spigot front face
DRUM_MID_Z = round((HUB_STEP_Z + HUB_FRONT_Z) / 2.0, 6)  # -11.01, where the drum sits
# Reamed on the owned .1885 reamer to a stated running clearance on the
# finished axle (mg_wheel_group HUB_RUNNING), so the Ø prints as a reference
# nominal.
BORE_DIA = 4.7879  # .1885

# Printed bands, (upper, lower) deviations.  The overall sets the axle's
# locknut stack (mg_wheel_group reads HUB_LEN_LIMITS).
HUB_LEN_PLACES = 3
HUB_LEN_BAND = (0.0762, -0.0762)  # +/-.003
HUB_LEN_LIMITS = printed_limits(HUB_LEN, HUB_LEN_PLACES, HUB_LEN_BAND)  # .769-.775
# Spigot length plus-only against the drum's minus-only length: the drum,
# pressed to the boss, never stands proud of the spigot face, so the front
# washer bears on the spigot (the iron), never on the drum.  Both print .354,
# so the comparison is between printed limits.
SPIGOT_LEN_PLACES = 3
SPIGOT_LEN_BAND = (0.1016, 0.0)  # +.004/.000
SPIGOT_LEN_LIMITS = printed_limits(SPIGOT_LEN, SPIGOT_LEN_PLACES, SPIGOT_LEN_BAND)
DRUM_RECESS = (
    SPIGOT_LEN_LIMITS[0] - (DRUM_LEN + DRUM_LEN_BAND[0]),
    SPIGOT_LEN_LIMITS[1] - (DRUM_LEN + DRUM_LEN_BAND[1]),
)  # .000 .. .008: the drum face below the spigot face
if DRUM_RECESS[0] < -1e-9:
    raise AssertionError(f"the drum can stand proud of the spigot: {DRUM_RECESS}")
# Matched fit (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): the drum is reamed first, and the
# spigot is turned to this diametral interference in that finished bore, so
# the spigot's Ø prints as a reference nominal (#290 owner ruling, M3).
DRUM_PRESS = (0.00508, 0.03302)  # .0002-.0013
if DRUM_PRESS[0] <= 0.0:
    raise AssertionError(f"the drum is not a press fit on the spigot: {DRUM_PRESS}")
# The finished spigot over every reamed bore: its smallest in the smallest bore.
SPIGOT_DIA_MIN = DRUM_BORE + DRUM_BORE_BAND[1] + DRUM_PRESS[0]  # .4992

# --- spokes ------------------------------------------------------------------------
# The as-cast sizes (spokes, fillets, rim bore, the web's plane) print .XX
# with this explicit band, a casting's allowance (#290 owner ruling (b)).
CAST_TOL = 0.762  # +/-.03
SPOKE_COUNT = 6  # counted on the p.51 full-page photo; 0 and 180 deg on the bar
SPOKE_AXIAL = 4.0  # prints .16
SPOKE_OVERLAP = 1.0  # the sketched spoke runs this far into the hub and rim
# Taper: the sketched root end (inside the hub) and tip end (inside the rim).
SPOKE_ROOT_WIDTH = 6.604  # .26
SPOKE_TIP_WIDTH = 5.08  # .20
SPOKE_X0 = HUB_DIA / 2.0 - SPOKE_OVERLAP  # 14.0
SPOKE_X1 = _rim.RIM_INNER_DIA / 2.0 + SPOKE_OVERLAP  # 45.0
HUB_FILLET_R = 3.048  # .12
RIM_FILLET_R = 4.064  # .16
# The rim bore's two edges (the spoke faces stay sharp). TIE 2 breaks into the
# bore at mid-width, so a bigger round eats its ligament to the rim side faces
# (mg_magnifying_wheel_spec): the R prints as a single limit, R.03 MAX, so no
# round is larger and a sharp edge falls under the title block's edge break.
# Section A-A cannot import a fillet radius whose arc is the cut, so the R is
# a sheet radial on the cut arc (user, option (a), 2026-10-12).
CAST_ROUND_R = 0.762  # .03

# --- wire ties ---------------------------------------------------------------------
# Both ties are drilled: the title block's DRILLED HOLES row governs their
# size (mg_magnifying_wheel_spec takes its plus in every wall).
TIE_HOLE_DIA = 1.016  # .040, a #60 drill
# drawing-guidelines.md rule 17 (walls and webs): a drilled axis may wander
# this far off true over its depth (the fleet's mg_magnifying_clamp_geom and
# fr_top_frame_spec figure), on top of the title block's angular allowance.
DRILL_WANDER_DEG = 0.3
# TIE 1 (lever wire): straight axial hole through the boss, located from the
# bore centre by two coordinates at the title block's .XX (no band of its
# own): 8 o'clock seen from the front at rest (local +x, -y; the front view
# mirrors local x), midway between the 180 and 240 deg spokes.  The drum,
# pressed hard against the boss step, covers that face out to its O.D., so
# the hole stands outboard of the drum: at the largest printed drum (.XX),
# the hole's worst printed station and axis offset, the smallest drilled
# hole still opens a full wire diameter beyond the drum for the wire's end.
# At 6 o'clock no band let the wire both clear the drum and keep its wrap
# (mg_wheel_group.LEVER_WIRE_WRAP_LEFT_DEG): the next spoke gap clockwise
# gives the wrap 60 deg more.
TIE1_PLACES = 2
TIE1_X = 9.652  # .38
TIE1_Y = -5.588  # -.22
TIE1_R = math.hypot(TIE1_X, TIE1_Y)  # 11.153
TIE1_CLOCK_DEG = 180.0 - math.degrees(math.atan2(TIE1_Y, TIE1_X)) - 360.0  # -149.9
TIE1_DEPTH_MAX = HUB_LEN_LIMITS[1] - SPIGOT_LEN_LIMITS[0]  # 10.693
# How far TIE 1's axis may stand off its nominal, anywhere along the hole: a
# disk over both printed coordinates' square, plus the axis's tilt (the
# title block's angle and drill wander) over the boss.
_TIE1_COORD = max(
    abs(d)
    for value in (TIE1_X, TIE1_Y)
    for d in printed_deviations(value, TIE1_PLACES, unit=UNIT)
)
TIE1_OFFSET_MAX = math.hypot(_TIE1_COORD, _TIE1_COORD) + TIE1_DEPTH_MAX * math.tan(
    math.radians(angular_band_deg(unit=UNIT) + DRILL_WANDER_DEG)
)  # 0.602
# The drum's wire-centre radius across its printed O.D. (.XX).
DRUM_WIRE_R_RANGE = (
    (DRUM_OD + DRUM_OD_DEVIATIONS[0]) / 2.0 + LEVER_WIRE_DIA / 2.0,
    (DRUM_OD + DRUM_OD_DEVIATIONS[1]) / 2.0 + LEVER_WIRE_DIA / 2.0,
)  # 9.671 .. 9.925
TIE1_DRUM_OPENING = (
    TIE1_R
    - TIE1_OFFSET_MAX
    + TIE_HOLE_DIA / 2.0
    - (DRUM_WIRE_R_RANGE[1] - LEVER_WIRE_DIA / 2.0)
)  # 1.534
if TIE1_DRUM_OPENING < LEVER_WIRE_DIA:
    raise AssertionError(
        f"the drum covers TIE 1: {TIE1_DRUM_OPENING:.3f} open < {LEVER_WIRE_DIA} wire"
    )
# TIE 2 (pen wire): radial hole, groove bottom to rim ID, about 4:30 from the
# front (photographed); 2 deg short of it so the worst printed casting keeps
# its wall to the 240 deg spoke's rim fillet (mg_magnifying_wheel_spec).
TIE2_CLOCK_DEG = -43.0


def clock_to_local_deg(phi: float) -> float:
    """Front-view clock angle (CCW from 3 o'clock) -> local XY angle."""
    return (180.0 - phi) % 360.0


def spoke_half_width(
    x: float, root: float = SPOKE_ROOT_WIDTH, tip: float = SPOKE_TIP_WIDTH
) -> float:
    """Spoke half-width at seed-frame station ``x`` (seed spoke on local +X),
    for a spoke cast ``root`` wide at SPOKE_X0 and ``tip`` wide at SPOKE_X1."""
    t = (x - SPOKE_X0) / (SPOKE_X1 - SPOKE_X0)
    return (root + t * (tip - root)) / 2.0


def side_meets_circle(r: float) -> tuple[float, float]:
    """Where the seed spoke's +Y side line crosses the circle of radius ``r``."""
    lo, hi = 0.0, r
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if mid * mid + spoke_half_width(mid) ** 2 < r * r:
            lo = mid
        else:
            hi = mid
    return lo, spoke_half_width(lo)


def _side_normal(root: float, tip: float) -> tuple[tuple[float, float], float]:
    """Unit normal of the +Y side line pointing away from the spoke, and the
    line's offset c (points p on the line satisfy p . n = c)."""
    dx = SPOKE_X1 - SPOKE_X0
    dy = spoke_half_width(SPOKE_X1, root, tip) - spoke_half_width(SPOKE_X0, root, tip)
    length = math.hypot(dx, dy)
    n = (-dy / length, dx / length)
    c = SPOKE_X0 * n[0] + spoke_half_width(SPOKE_X0, root, tip) * n[1]
    return n, c


def fillet(
    circle_r: float,
    fillet_r: float,
    outside: bool,
    root: float = SPOKE_ROOT_WIDTH,
    tip: float = SPOKE_TIP_WIDTH,
) -> dict[str, tuple]:
    """The +Y-side fillet between the seed spoke and a circle about the axis:
    the hub OD (``outside``: the fillet lies outside the circle) or the rim ID
    (inside it). Returns the fillet centre and its two tangent points.
    ``root``/``tip`` are the spoke's widths, so a wall proof can take them at
    their printed limits."""
    n, c = _side_normal(root, tip)
    reach = circle_r + fillet_r if outside else circle_r - fillet_r
    # Centre on the line p . n = c + fillet_r, at distance ``reach`` from 0.
    k = c + fillet_r
    foot = (k * n[0], k * n[1])
    along = math.sqrt(reach * reach - k * k)
    t = (n[1], -n[0])
    centre = (foot[0] + along * t[0], foot[1] + along * t[1])
    if centre[0] < 0.0:
        centre = (foot[0] - along * t[0], foot[1] - along * t[1])
    on_side = (centre[0] - fillet_r * n[0], centre[1] - fillet_r * n[1])
    scale = circle_r / math.hypot(*centre)
    on_circle = (centre[0] * scale, centre[1] * scale)
    return {"centre": centre, "on_side": on_side, "on_circle": on_circle}


def _arc(cx: float, cy: float, r: float, a0: float, a1: float, n: int = 400):
    da = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi  # the short way
    return [
        (cx + r * math.cos(a0 + da * i / n), cy + r * math.sin(a0 + da * i / n))
        for i in range(n + 1)
    ]


def fillet_area(circle_r: float, fillet_r: float, outside: bool) -> float:
    """Section area one fillet adds (the region between the spoke side, the
    circle and the fillet arc), by a fine polygon."""
    f = fillet(circle_r, fillet_r, outside)
    vertex = side_meets_circle(circle_r)
    (cx, cy), (sx, sy), (ox, oy) = f["centre"], f["on_side"], f["on_circle"]
    pts = [vertex, (sx, sy)]
    pts += _arc(
        cx, cy, fillet_r, math.atan2(sy - cy, sx - cx), math.atan2(oy - cy, ox - cx)
    )
    pts += _arc(
        0.0, 0.0, circle_r, math.atan2(oy, ox), math.atan2(vertex[1], vertex[0])
    )
    area = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1], strict=True):
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0


def fillets_volume() -> float:
    """Material the 2 x 6 hub fillets and 2 x 6 rim fillets add."""
    per_side = fillet_area(HUB_DIA / 2.0, HUB_FILLET_R, True) + fillet_area(
        _rim.RIM_INNER_DIA / 2.0, RIM_FILLET_R, False
    )
    return 2 * SPOKE_COUNT * SPOKE_AXIAL * per_side


if not SPOKE_X0 < side_meets_circle(HUB_DIA / 2.0)[0]:
    raise AssertionError("spoke root does not start inside the hub")
if (
    not side_meets_circle(_rim.RIM_INNER_DIA / 2.0)[0]
    < SPOKE_X1
    < _rim.GROOVE_BOTTOM_DIA / 2.0
):
    raise AssertionError("spoke tip must end inside the rim, short of the groove")
