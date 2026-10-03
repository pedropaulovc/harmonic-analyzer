r"""MHA-127 latch-hook outline: the tangent two-arc centreline and its holes.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure (the MHA-170 bracket geometry imports ``RIVET_YZ`` from here; the
pin hole's height is the arm's latch pin's, ``transgear_arm_geometry``).

The hook is a 10 x 0.6 strip curved EDGEWISE (in its own plane) to a
template.  Its plane is the machine YZ plane at x 57.9..58.5, face toward +X,
riveted to the -X face of the MHA-170 bracket flap (x 58.5).  In machine
(Y, Z) the strip centreline is two tangent arcs (LatchParts' re-derivation
of the contract's traced spline, 0.167 max deviation from it):

* the top end is cut square at y 306.2, where the centreline runs along -Y
  (its tangent is vertical to the cut line) at z -116.6395;
* arc 1, R850 about (306.2, -966.6395), down to the tangency junction
  (253.0041, -118.3057);
* arc 2, R490 about (283.6700, -607.3452), past the Ø5.4 latch-pin hole
  to the end, TIP_RUN 99.9 from the top cut (y 206.3, z -123.49).  The
  model carries the printed .X value; the contract's 206.25 end sits 0.05
  further on;
* the pin's axis crosses the strip's mid-plane at PIN_AXIS_YZ (y 229.0403,
  z the arm's pin, -120.43125);
* the pin hole is drawn where the arm RESTS on the hook: on the centreline,
  0.617 up the strip from the pin axis, so the largest pin's swept
  footprint bears on the hole's lower edge (Codex P1 on b2eb9a0e1: a hole
  centred on the pin let the arm drop 0.62 along the strip, the feed
  pinion 0.22 out of the rack); the fit-up set takes up its run band;
* the free end is a full round, R5 about the end point;
* the edges are the ±5 concentric offsets (R845 / R855, R485 / R495).

Part frame (``build_latch_hook``): the profile is sketched on the Front plane
with the origin at the centre of the top cut; local +X is machine +Y, local
+Y is machine +Z, and the 0.6 extrusion runs local +Z = machine +X, so the
part's origin sits at machine ``PART_ORIGIN_MACHINE`` and the strip extends
toward local -X.  ``LOCAL_TO_MACHINE`` rows map local to machine axes.
"""

from __future__ import annotations

import math

from transgear_arm_geometry import PIN_MACHINE_Z

# --- Stock -------------------------------------------------------------------
STRIP_W = 10.0
STRIP_T = 0.6
HALF_W = STRIP_W / 2.0
TIP_R = HALF_W  # full-round free end

# --- Machine (Y, Z) centreline -----------------------------------------------
PLANE_X = (57.9, 58.5)  # strip faces; +X face on the bracket flap
TOP_Y = 306.2
TOP_Z = -116.6395
R1 = 850.0
C1 = (306.2, -966.6395)
JUNCTION = (253.0041, -118.3057)
R2 = 490.0
C2 = (283.6700, -607.3452)
# The latch pin's axis on the strip's mid-plane, the arm at its drawn pose.
PIN_AXIS_YZ = (229.0403, PIN_MACHINE_Z)
# The pin hole, on the centreline where the largest pin (Ø3.18262) swept
# through the strip at its 32.56 deg incidence bears on the hole's lower edge
# (latch_hook_spec.PIN_BEARING_LIFT; the sweep is test_latch_hook_drawing's).
PIN_HOLE_YZ = (229.6570, -120.3312)
# The end's run from the top cut, as printed (.X), on arc 2.
TIP_RUN = 99.9
END_YZ = (TOP_Y - TIP_RUN, C2[1] + math.sqrt(R2**2 - (TOP_Y - TIP_RUN - C2[0]) ** 2))
CONTRACT_END_Y = 206.25

PIN_HOLE_DIA = 5.4  # over the 1/8 latch pin (98381A474)
# R9-51: a metric Ø1.65 drill clears the largest 1/16 shank (B18.1.1, 0.064
# in) at the hole's least size; latch_hook_rivet_spec holds the joint.
RIVET_HOLE_DIA = 1.65
# Two rivets across the strip at y 303, 3.9 apart and symmetric about the
# centreline (the 3.2 contract pitch left a 1.37 worst web between them).
RIVET_Y = 303.0
RIVET_PITCH = 3.9

_GEOM_TOL = 2e-3  # the published coordinates carry 4 decimals


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def centreline_z(y: float) -> float:
    """Machine z of the centreline at machine ``y`` (END_Y <= y <= TOP_Y)."""
    if not END_YZ[0] - 1e-9 <= y <= TOP_Y + 1e-9:
        raise ValueError(f"y {y} is off the hook centreline")
    centre, radius = (C1, R1) if y >= JUNCTION[0] else (C2, R2)
    return centre[1] + math.sqrt(radius**2 - (y - centre[0]) ** 2)


_RIVET_ZC = centreline_z(RIVET_Y)
# Machine (y, z) of the two rivet holes, lower first.
RIVET_YZ = (
    (RIVET_Y, _RIVET_ZC - RIVET_PITCH / 2.0),
    (RIVET_Y, _RIVET_ZC + RIVET_PITCH / 2.0),
)

# --- Import-time checks of the published chain ---------------------------------
if abs(C1[0] - TOP_Y) > 1e-9 or abs(_dist(C1, (TOP_Y, TOP_Z)) - R1) > _GEOM_TOL:
    raise AssertionError("arc 1 does not leave the square top cut along -Y")
for _label, _centre, _radius, _point in (
    ("junction on arc 1", C1, R1, JUNCTION),
    ("junction on arc 2", C2, R2, JUNCTION),
    ("end on arc 2", C2, R2, END_YZ),
):
    if abs(_dist(_centre, _point) - _radius) > _GEOM_TOL:
        raise AssertionError(
            f"latch hook {_label}: {_dist(_centre, _point):.4f} vs R{_radius:g}"
        )
# The pin hole's centre off the centreline, across the strip (+ toward the
# outer edge); the spec holds it inside the sheet's centring band.
PIN_HOLE_CENTRELINE_OFFSET = _dist(C2, PIN_HOLE_YZ) - R2
# Internal tangency: the junction and both centres are collinear, the centres
# R1 - R2 apart.
if abs(_dist(C1, C2) - (R1 - R2)) > _GEOM_TOL:
    raise AssertionError("latch hook arcs are not tangent at the junction")
if not END_YZ[0] < PIN_HOLE_YZ[0] < JUNCTION[0] < TOP_Y:
    raise AssertionError("latch hook stations out of order along the strip")


# --- Local part frame ---------------------------------------------------------
PART_ORIGIN_MACHINE = (PLANE_X[0], TOP_Y, TOP_Z)
LOCAL_TO_MACHINE = (
    (0.0, 0.0, 1.0),  # machine x = local z
    (1.0, 0.0, 0.0),  # machine y = local x
    (0.0, 1.0, 0.0),  # machine z = local y
)


def to_local(y: float, z: float) -> tuple[float, float]:
    """Machine (y, z) -> the part's Front-plane sketch (x, y)."""
    return (y - TOP_Y, z - TOP_Z)


C1_L = to_local(*C1)
C2_L = to_local(*C2)
JUNCTION_L = to_local(*JUNCTION)
END_L = to_local(*END_YZ)
PIN_HOLE_L = to_local(*PIN_HOLE_YZ)
RIVET_L = tuple(to_local(y, z) for y, z in RIVET_YZ)


def _unit(frm: tuple[float, float], to: tuple[float, float]) -> tuple[float, float]:
    d = _dist(frm, to)
    return ((to[0] - frm[0]) / d, (to[1] - frm[1]) / d)


def _offset(
    point: tuple[float, float], centre: tuple[float, float], by: float
) -> tuple[float, float]:
    """``point`` moved ``by`` along the ray from ``centre`` (+ = away)."""
    ux, uy = _unit(centre, point)
    return (point[0] + by * ux, point[1] + by * uy)


# Outline vertices (local).  Upper edge = away from the arc centres (the
# convex, outer edge); lower edge = toward them (the inner edge the forming
# template carries).
TOP_UPPER = (0.0, HALF_W)
TOP_LOWER = (0.0, -HALF_W)
JUNCTION_UPPER = _offset(JUNCTION_L, C1_L, HALF_W)
JUNCTION_LOWER = _offset(JUNCTION_L, C1_L, -HALF_W)
END_UPPER = _offset(END_L, C2_L, HALF_W)
END_LOWER = _offset(END_L, C2_L, -HALF_W)
INNER_R1 = R1 - HALF_W
OUTER_R1 = R1 + HALF_W
INNER_R2 = R2 - HALF_W
OUTER_R2 = R2 + HALF_W

# Horizontal runs from the top cut (the sheet's datum edge), positive.
JUNCTION_RUN = -JUNCTION_LOWER[0]  # to the template's tangency point
PIN_HOLE_RUN = -PIN_HOLE_L[0]
PIN_HOLE_DROP = -PIN_HOLE_L[1]  # below the top cut's centre (unprinted)
RIVET_RUN = -RIVET_L[0][0]
RIVET_LOWER_DROP = -RIVET_L[0][1]  # lower rivet below the top cut's centre


def _sweep(centre, a, b) -> float:
    ua, ub = _unit(centre, a), _unit(centre, b)
    return math.acos(max(-1.0, min(1.0, ua[0] * ub[0] + ua[1] * ub[1])))


SWEEP1 = _sweep(C1, (TOP_Y, TOP_Z), JUNCTION)
SWEEP2 = _sweep(C2, JUNCTION, END_YZ)
CENTRELINE_LEN = R1 * SWEEP1 + R2 * SWEEP2
# An offset band of an arc has area W x (centreline length); the square top
# adds nothing, the full round end a half disc.
PROFILE_AREA = STRIP_W * CENTRELINE_LEN + math.pi * TIP_R**2 / 2.0


def _outline(n: int = 400) -> list[tuple[float, float]]:
    """Dense local outline: upper edge from the top cut to the tip, the tip
    round, the lower edge back (for extents)."""
    pts: list[tuple[float, float]] = []

    def arc(centre, radius, a0, a1):
        for k in range(n + 1):
            a = a0 + (a1 - a0) * k / n
            pts.append(
                (centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a))
            )

    def ang(centre, p):
        return math.atan2(p[1] - centre[1], p[0] - centre[0])

    arc(C1_L, OUTER_R1, ang(C1_L, TOP_UPPER), ang(C1_L, JUNCTION_UPPER))
    arc(C2_L, OUTER_R2, ang(C2_L, JUNCTION_UPPER), ang(C2_L, END_UPPER))
    a_tip = ang(END_L, END_UPPER)
    arc(END_L, TIP_R, a_tip, a_tip + math.pi)
    arc(C2_L, INNER_R2, ang(C2_L, END_LOWER), ang(C2_L, JUNCTION_LOWER))
    arc(C1_L, INNER_R1, ang(C1_L, JUNCTION_LOWER), ang(C1_L, TOP_LOWER))
    return pts


_OUTLINE = _outline()
LOCAL_X_MIN = min(x for x, _ in _OUTLINE)
LOCAL_X_MAX = max(x for x, _ in _OUTLINE)
LOCAL_Y_MIN = min(y for _, y in _OUTLINE)
LOCAL_Y_MAX = max(y for _, y in _OUTLINE)
# Machine bounding box of the strip (y, z); x is PLANE_X.
BBOX_Y = (TOP_Y + LOCAL_X_MIN, TOP_Y + LOCAL_X_MAX)
BBOX_Z = (TOP_Z + LOCAL_Y_MIN, TOP_Z + LOCAL_Y_MAX)
# The contract's envelope (y 201.25, z -128.5), within the 0.05 the printed
# tip run moves the end along the strip.
if abs(BBOX_Y[0] - (CONTRACT_END_Y - TIP_R)) > 0.06 or abs(BBOX_Y[1] - TOP_Y) > 1e-6:
    raise AssertionError(f"latch hook y extent {BBOX_Y} off the contract's")
if abs(BBOX_Z[0] - (-123.5 - TIP_R)) > 0.06:
    raise AssertionError(f"latch hook z extent {BBOX_Z} off the contract's")
