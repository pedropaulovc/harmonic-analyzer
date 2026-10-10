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

from mg_wheel_drum_geom import DRUM_BORE, DRUM_LEN, DRUM_LEN_BAND, DRUM_WIRE_R

# --- rim (DIMENSIONS.md ch21: Ø100 annotated) ----------------------------------
RIM_OUTER_DIA = 100.0
RIM_RING_RADIAL = 6.0
RIM_AXIAL = 8.0  # centred on the spokes' mid-plane
RIM_INNER_DIA = RIM_OUTER_DIA - 2 * RIM_RING_RADIAL  # 88
# Pen-wire U-groove on the rim's mid-plane: a R0.6 bottom with straight walls.
GROOVE_R = 0.6
GROOVE_DEPTH = 1.2
GROOVE_BOTTOM_DIA = RIM_OUTER_DIA - 2 * GROOVE_DEPTH  # 97.6
# Printed bands, (upper, lower): the seat proof is mg_magnifying_wheel_spec's.
GROOVE_R_BAND = (0.10, -0.10)
GROOVE_BOTTOM_BAND = (0.10, -0.10)
PEN_WIRE_DIA = 0.8  # the pen wire the groove carries (pn_pen_wire_geom)
RIM_WIRE_R = round(GROOVE_BOTTOM_DIA / 2.0 + PEN_WIRE_DIA / 2.0, 6)  # 49.2
WIRE_RATIO = RIM_WIRE_R / DRUM_WIRE_R  # 4.995, the wheel's magnification

# --- hub: Ø25 boss, then the drum spigot -----------------------------------------
HUB_DIA = 25.0
HUB_LEN = 19.6  # back face to spigot front face, both faced
HUB_BACK_Z = 7.09  # back face above the spokes' mid-plane (stack: d 0.91)
SPIGOT_DIA = DRUM_BORE
SPIGOT_LEN = DRUM_LEN  # nominally flush with the drum's front face
HUB_STEP_Z = round(HUB_BACK_Z - (HUB_LEN - SPIGOT_LEN), 6)  # -3.51, boss front face
HUB_FRONT_Z = round(HUB_BACK_Z - HUB_LEN, 6)  # -12.51, spigot front face
DRUM_MID_Z = round((HUB_STEP_Z + HUB_FRONT_Z) / 2.0, 6)  # -8.01, where the drum sits
BORE_DIA = round(0.1890 * 25.4, 6)  # 4.8006, reamed: runs on the 3/16 pin

# Printed bands, (upper, lower) deviations.
HUB_DIA_BAND = (0.10, -0.10)
HUB_LEN_BAND = (0.10, -0.10)
SPIGOT_BAND = (0.029, 0.018)  # p6: press fit under the drum's H7 bore
# Spigot length plus-only against the drum's minus-only length: the drum,
# pressed to the boss, never stands proud of the spigot face, so the front
# washer bears on the spigot (the iron), never on the drum.
SPIGOT_LEN_BAND = (0.10, 0.0)
BORE_BAND = (0.010, 0.0)
DRUM_RECESS = (
    SPIGOT_LEN + SPIGOT_LEN_BAND[1] - (DRUM_LEN + DRUM_LEN_BAND[0]),
    SPIGOT_LEN + SPIGOT_LEN_BAND[0] - (DRUM_LEN + DRUM_LEN_BAND[1]),
)  # 0.0 .. 0.2: the drum face below the spigot face
if DRUM_RECESS[0] < 0.0:
    raise AssertionError(f"the drum can stand proud of the spigot: {DRUM_RECESS}")

# --- spokes ------------------------------------------------------------------------
SPOKE_COUNT = 6  # counted on the p.51 full-page photo; 0 and 180 deg on the bar
SPOKE_AXIAL = 4.0
SPOKE_OVERLAP = 1.0  # the sketched spoke runs this far into the hub and rim
# Taper: the sketched root end (inside the hub) and tip end (inside the rim).
SPOKE_ROOT_WIDTH = 6.5
SPOKE_TIP_WIDTH = 5.0
SPOKE_X0 = HUB_DIA / 2.0 - SPOKE_OVERLAP  # 11.5
SPOKE_X1 = RIM_INNER_DIA / 2.0 + SPOKE_OVERLAP  # 45.0
HUB_FILLET_R = 3.0
RIM_FILLET_R = 4.0
# The rim bore's two edges (the spoke faces stay sharp). R1 at most: TIE 2
# breaks into the bore at mid-width, so a bigger round eats its ligament to
# the rim side faces (mg_magnifying_wheel_spec). The pattern round is the
# maximum; it only comes out smaller.
CAST_ROUND_R = 1.0
CAST_ROUND_BAND = (0.0, -0.5)

# --- wire ties ---------------------------------------------------------------------
TIE_HOLE_DIA = 1.0
TIE_HOLE_BAND = (0.05, 0.0)
TIE_POSITION_TOL = 0.05
# TIE 1 (lever wire): straight axial hole through the Ø25 boss on the drum's
# wire-centre radius, 6 o'clock from the front at rest.
TIE1_R = DRUM_WIRE_R  # 9.85
TIE1_CLOCK_DEG = -90.0
# TIE 2 (pen wire): radial hole, groove bottom to rim ID, about 4:30 from the
# front (photographed); 2 deg short of it so the worst printed casting keeps a
# 2.0 wall to the 240 deg spoke's rim fillet (mg_magnifying_wheel_spec).
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
        RIM_INNER_DIA / 2.0, RIM_FILLET_R, False
    )
    return 2 * SPOKE_COUNT * SPOKE_AXIAL * per_side


if not SPOKE_X0 < side_meets_circle(HUB_DIA / 2.0)[0]:
    raise AssertionError("spoke root does not start inside the hub")
if not side_meets_circle(RIM_INNER_DIA / 2.0)[0] < SPOKE_X1 < GROOVE_BOTTOM_DIA / 2.0:
    raise AssertionError("spoke tip must end inside the rim, short of the groove")
