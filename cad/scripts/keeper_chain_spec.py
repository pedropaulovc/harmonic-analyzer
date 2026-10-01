r"""Crank-pin keeper chain (MHA-149) and its loop link (MHA-150), pure data.

The ch11 p.14 photographs show the brass eye on the crank arm and the brass
ring on the taper pin's head; the chain that tied the removable pin to the arm
is lost. It is reconstructed with purchased McMaster-Carr bead chain:

* 3606T118 -- unfinished brass bead chain, trade size 3, 3/32 in beads,
  20 lbf, cut to BEAD_COUNT beads.
* 3606T811 -- brass loop link for trade-size-3 chain: the capsule coupler that
  snaps over an end bead at each end and closes the cut length into a loop.

The chain is one closed loop through the eye and the ring, with a single
joint. McMaster publishes no CAD, and no dimension beyond the bead diameter,
for either item (read 2026-09-29). The pitch is the trade-size-3 average of 94
beads per foot (Ball Chain Mfg. and Frank Winne size charts). The link is
9 mm long, as #3 connectors are listed, and its proportions are read off
McMaster's 3606T811 photograph. The rod and the link's wall, crimps, tip holes
and mouths are assumptions named below; each only decides clearances the
functions here prove.

Frame ("crank frame"): machine axes, origin on the crank axis at the arm's
front (outboard) face, machine z -183. The arm fills z 0..ARM_THICKNESS and
the hub barrel ARM_THICKNESS..HUB_LENGTH. The chain part is authored in this
frame and placed with an identity rotation. The link is authored along local
X with its mouths and rod slot on +Y, and placed at LINK_ORIGIN with its axis
on machine Z.

Geometry, rest pose (arm hanging down, gravity -Y). The loop hangs from two
wires:

* eye, plane z = EYE_LOOP_Z: the chain crosses the eye along X, its rod
  bearing on the inside of the loop's bottom wire with a bead either side.
* ring, plane z = RING_PLANE_Z: the same wrap on the ring's lowest point.
* two strands join the wraps round the arm's -X edge, nested so they never
  cross. The inner strand runs from the eye's +X bead to the ring's hub-side
  bead, beside the edge at INNER_SIDE_X. The outer strand runs from the eye's
  -X bead to the ring's outboard bead, further out at OUTER_SIDE_X and
  lower. The link sits on the outer strand, axis along z beside the arm edge.
  Each strand's sag is solved so it closes on a whole number of pitches.

Both strands pull straight when the taper pin is drawn out of the hub
(PIN_WITHDRAWAL), so each is at least that reach plus STRAND_SLACK_PITCHES.
"""

from __future__ import annotations

import math

from crank_arm_spec import ANCHOR_SCREW_X, ANCHOR_SCREW_Y, ARM_THICKNESS, HALF_WIDTH
from crank_hub_geometry import HUB_BARREL_DIA, HUB_LENGTH, SERVICE_PIN_STATION
from crank_pin_eye_spec import ANCHOR_AIR, LOOP_INNER_R, LOOP_R
from crank_pin_eye_spec import TAIL_LEN as EYE_TAIL_LEN
from crank_pin_eye_spec import WIRE_DIA as EYE_WIRE_DIA
from crank_pin_ring_spec import MEAN_R, PIN_PROUD, RING_BOTTOM_X, RING_CENTRE_X
from crank_pin_ring_spec import WIRE_DIA as RING_WIRE_DIA
from crank_pin_spec import BIG_END_DIA, PIN_LENGTH, RING_HOLE_X, SMALL_END_DIA
from fillister_screw_spec import HEAD_DIA as SCREW_HEAD_DIA
from fillister_screw_spec import HEAD_H as SCREW_HEAD_H
from fillister_screw_spec import SHANK_DIA as SCREW_SHANK_DIA


Vec = tuple[float, float, float]

MM_PER_IN = 25.4

# --- purchased-part nominals --------------------------------------------------
CHAIN_SKU = "3606T118"
LINK_SKU = "3606T811"
BEAD_DIA = 3.0 / 32.0 * MM_PER_IN  # 2.38125, the catalogue bead diameter
BEAD_R = BEAD_DIA / 2.0
PITCH = 12.0 * MM_PER_IN / 94.0  # 3.2426, trade size 3 average
# Assumption: the connecting rod. It is hidden inside the beads except for
# the ~0.9 mm between them.
ROD_DIA = 0.5
ROD_R = ROD_DIA / 2.0
# The loop link: a rolled capsule, domed at both ends, the end beads caught in
# the domes behind a crimp. LINK_LENGTH is the listed #3 size; LINK_OD is the
# 0.37 diameter-to-length read off the photograph; the rest are assumptions.
LINK_LENGTH = 9.0
LINK_OD = 3.3
LINK_WALL = 0.3
LINK_END_BEAD_X = LINK_LENGTH / 2.0 - LINK_OD / 2.0  # end-bead centre = dome centre
LINK_CRIMP_X = 1.45  # crimp groove centre, just inboard of each end bead
LINK_CRIMP_DEPTH = 0.15
LINK_TIP_HOLE = 0.7  # the rod leaves each dome through this
# How the link goes on and holds (the dark band in the photograph, on +Y):
# each dome has a side mouth NARROWER than a bead. The end bead snaps in
# through it as the rolled wall flexes, and it cannot come back out; its rod
# rides the slot that runs along the top to the tip hole. The grooves at
# LINK_CRIMP_X are the rolled crimps' outside form, not a retainer.
LINK_MOUTH_LENGTH = 2.0  # along the axis, centred on each dome
LINK_MOUTH_WIDTH = 2.1  # under BEAD_DIA: the bead snaps past it
LINK_SLOT_WIDTH = LINK_TIP_HOLE
LINK_BEAD_SPACING = 2.0 * LINK_END_BEAD_X  # the joint's gap between end beads

AIR = 0.02  # minimum air the solve leaves between parts that must not touch

# --- pose inputs from the part specs (crank frame) ----------------------------
HUB_R = HUB_BARREL_DIA / 2.0
ARM_Z = (0.0, ARM_THICKNESS)
HUB_Z = (ARM_THICKNESS, HUB_LENGTH)
PIN_Z = SERVICE_PIN_STATION
PIN_X0 = -HUB_R - PIN_PROUD  # the pin's big end
RING_X = PIN_X0 + RING_HOLE_X  # the ring's through leg and plane
SCREW_XY = (-ANCHOR_SCREW_Y, -ANCHOR_SCREW_X)
SCREW_HEAD_Z = (-(EYE_WIRE_DIA + ANCHOR_AIR) - SCREW_HEAD_H, -(EYE_WIRE_DIA + ANCHOR_AIR))
EYE_ROOT: Vec = (
    SCREW_XY[0],
    SCREW_XY[1] - (SCREW_SHANK_DIA / 2.0 + ANCHOR_AIR + EYE_TAIL_LEN),
    -(EYE_WIRE_DIA / 2.0 + ANCHOR_AIR),
)
EYE_LOOP_CENTRE: Vec = (EYE_ROOT[0], EYE_ROOT[1], EYE_ROOT[2] - LOOP_R)
EYE_LOOP_Z = EYE_LOOP_CENTRE[2]
# The chain wraps the ring's lowest point, in the pin axis's z plane.
RING_PLANE_Z = PIN_Z

# The pin comes out along -X until its small end clears the hub barrel, plus
# a finger's grip of margin.
PIN_WITHDRAWAL_MARGIN = 3.0
PIN_WITHDRAWAL = PIN_X0 + PIN_LENGTH + HUB_R + PIN_WITHDRAWAL_MARGIN



def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Vec) -> float:
    return math.sqrt(_dot(a, a))


def _dist(a: Vec, b: Vec) -> float:
    return _norm(_sub(a, b))


def _catmull_rom(points: list[Vec], samples: int = 40) -> list[Vec]:
    """Centripetal Catmull-Rom polyline through points[1:-1]."""
    out: list[Vec] = []
    for i in range(1, len(points) - 2):
        p0, p1, p2, p3 = points[i - 1 : i + 3]
        t0 = 0.0
        t1 = t0 + _dist(p0, p1) ** 0.5
        t2 = t1 + _dist(p1, p2) ** 0.5
        t3 = t2 + _dist(p2, p3) ** 0.5
        for k in range(samples):
            if k == 0:
                # Exactly the knot, not its float reconstruction: a strand
                # starts on its wrap bead, which the loop then names by value.
                out.append(p1)
                continue
            t = t1 + (t2 - t1) * k / samples

            def lerp(pa: Vec, pb: Vec, ta: float, tb: float) -> Vec:
                return _add(
                    _scale(pa, (tb - t) / (tb - ta)), _scale(pb, (t - ta) / (tb - ta))
                )

            a1 = lerp(p0, p1, t0, t1)
            a2 = lerp(p1, p2, t1, t2)
            a3 = lerp(p2, p3, t2, t3)
            b1 = lerp(a1, a2, t0, t2)
            b2 = lerp(a2, a3, t1, t3)
            out.append(lerp(b1, b2, t1, t2))
    out.append(points[-2])
    return out


def _chord_walk(curve: list[Vec], steps: int) -> list[Vec]:
    """``steps`` chords of exactly PITCH along the polyline from curve[0]."""
    beads = [curve[0]]
    seg = 0
    for _ in range(steps):
        centre = beads[-1]
        while True:
            if seg >= len(curve) - 1:
                return beads
            a, b = curve[seg], curve[seg + 1]
            if _dist(centre, b) >= PITCH:
                # First crossing of the pitch sphere on segment a -> b.
                d = _sub(b, a)
                f = _sub(a, centre)
                qa, qb, qc = _dot(d, d), 2.0 * _dot(f, d), _dot(f, f) - PITCH**2
                t = (-qb + math.sqrt(qb * qb - 4.0 * qa * qc)) / (2.0 * qa)
                beads.append(_add(a, _scale(d, t)))
                break
            seg += 1
    return beads




# --- the two wraps ---------------------------------------------------------------
EYE_ROD_Y = EYE_LOOP_CENTRE[1] - LOOP_INNER_R + ROD_R + AIR
RING_ROD_Y = -RING_BOTTOM_X + RING_WIRE_DIA / 2.0 + ROD_R + AIR
_HALF = PITCH / 2.0
_UP: Vec = (0.0, PITCH, 0.0)
EYE_OUTER: Vec = (EYE_ROOT[0] - _HALF, EYE_ROD_Y, EYE_LOOP_Z)
EYE_INNER: Vec = (EYE_ROOT[0] + _HALF, EYE_ROD_Y, EYE_LOOP_Z)
RING_OUTER: Vec = (RING_X - _HALF, RING_ROD_Y, RING_PLANE_Z)
RING_INNER: Vec = (RING_X + _HALF, RING_ROD_Y, RING_PLANE_Z)

# The strands drape outboard of the arm's -X edge at these x.
INNER_SIDE_X = -(HALF_WIDTH + BEAD_R + 1.6)
OUTER_SIDE_X = INNER_SIDE_X - (BEAD_DIA + 1.2)
STRAND_SLACK_PITCHES = 2
# The link's height below the eye's wrap, and how far the inner strand's
# lowest bead hangs below the outer strand's. Seen from the front, the eye's
# +X bead is to the right of its -X bead, so the inner strand must pass below
# and right of the outer one to keep the U's nested.  The drop is the rest
# height at which the outer halves close on whole pitches: 17.5 keeps the
# #1140 loop's 11 + 14 outer beads and 56-bead cut with the ring on the
# Ø22.25 barrel (as on the Ø20.6 one; on the Ø25.4 one 18.0 closed).
LINK_DROP = 17.5
STRAND_GAP = BEAD_DIA + 1.6



def _close(curve_for, steps: int, end: Vec) -> tuple[list[Vec], float] | None:
    """Beads from the curve's start to ``end``, ``steps`` pitches apart.

    ``curve_for(low_y)`` gives the polyline for a sag; the low point is
    bisected until the last chord closes on ``end`` exactly. None when no sag
    in range closes this many pitches.
    """

    def residual(low_y: float) -> float:
        beads = _chord_walk(curve_for(low_y), steps - 1)
        if len(beads) < steps:
            return -PITCH  # curve too short: the walk ran off its end
        return _dist(beads[-1], end) - PITCH

    lo, hi = end[1] - 90.0, max(end[1], curve_for(0.0)[0][1]) - 1.0
    if residual(lo) <= 0.0 or residual(hi) >= 0.0:
        return None
    for _ in range(56):  # 90 mm / 2**56: far below any COM tolerance
        mid = (lo + hi) / 2.0
        if residual(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    low_y = (lo + hi) / 2.0
    if abs(residual(low_y)) > 1e-7:
        return None  # bisected onto the walk's run-off edge, not a closure
    return _chord_walk(curve_for(low_y), steps - 1) + [end], low_y


def _reach(start: Vec, end: Vec) -> float:
    """Shortest strand from ``start`` to ``end`` once the pin is drawn out.

    Straight to the arm's front -X corner, then straight to ``end`` moved out
    with the pin, minimised over the height where it rounds the corner.
    """
    moved = _add(end, (-PIN_WITHDRAWAL, 0.0, 0.0))
    corner_x, corner_z = -(HALF_WIDTH + BEAD_R), -BEAD_R
    return min(
        _dist(start, (corner_x, y, corner_z)) + _dist((corner_x, y, corner_z), moved)
        for y in (start[1] + 0.25 * k for k in range(-200, 200))
    )


def _inner_curve(low_y: float) -> list[Vec]:
    return _catmull_rom(
        [
            _add(EYE_INNER, _UP),
            EYE_INNER,
            (INNER_SIDE_X, low_y, EYE_LOOP_Z),
            (INNER_SIDE_X, low_y, RING_PLANE_Z),
            RING_INNER,
            _add(RING_INNER, _UP),
        ]
    )


INNER_REACH = _reach(EYE_INNER, RING_INNER)
OUTER_REACH = _reach(EYE_OUTER, RING_OUTER)


# --- the loop link, on the outer strand beside the arm edge --------------------
LINK_ORIGIN: Vec = (OUTER_SIDE_X, EYE_ROD_Y - LINK_DROP, (EYE_LOOP_Z + RING_PLANE_Z) / 2.0)
LINK_AXIS: Vec = (0.0, 0.0, 1.0)
LINK_END_EYE: Vec = _sub(LINK_ORIGIN, (0.0, 0.0, LINK_END_BEAD_X))
LINK_END_RING: Vec = _add(LINK_ORIGIN, (0.0, 0.0, LINK_END_BEAD_X))
# The rods leave the domes along the axis: the beads next to the end beads
# sit on it too.
_BEFORE_LINK: Vec = _sub(LINK_END_EYE, (0.0, 0.0, PITCH))
_AFTER_LINK: Vec = _add(LINK_END_RING, (0.0, 0.0, PITCH))


def _outer_eye_curve(low_y: float) -> list[Vec]:
    return _catmull_rom(
        [_add(EYE_OUTER, _UP), EYE_OUTER, (OUTER_SIDE_X, low_y, EYE_LOOP_Z), _BEFORE_LINK, LINK_END_EYE]
    )


def _outer_ring_curve(low_y: float) -> list[Vec]:
    return _catmull_rom(
        [LINK_END_RING, _AFTER_LINK, (OUTER_SIDE_X, low_y, RING_PLANE_Z), RING_OUTER, _add(RING_OUTER, _UP)]
    )


def _solve_half(curve_for, end: Vec) -> tuple[list[Vec], float]:
    """The pitch count whose solved sag sits nearest the link's height."""
    best: tuple[float, list[Vec], float] | None = None
    for steps in range(2, 30):
        solved = _close(curve_for, steps, end)
        if solved is None:
            continue
        miss = abs(solved[1] - LINK_ORIGIN[1])
        if best is None or miss < best[0]:
            best = (miss, *solved)
    if best is None:
        raise AssertionError("keeper chain's outer strand does not close")
    return best[1], best[2]


OUTER_EYE_BEADS, OUTER_EYE_LOW_Y = _solve_half(_outer_eye_curve, _BEFORE_LINK)
OUTER_RING_BEADS, OUTER_RING_LOW_Y = _solve_half(_outer_ring_curve, RING_OUTER)
OUTER_BOTTOM_Y = min(p[1] for p in OUTER_EYE_BEADS + OUTER_RING_BEADS)


def _solve_inner() -> tuple[list[Vec], float]:
    """The shortest closing inner strand that reaches and hangs below the outer."""
    steps = math.ceil(INNER_REACH / PITCH) + STRAND_SLACK_PITCHES
    for extra in range(20):
        solved = _close(_inner_curve, steps + extra, RING_INNER)
        if solved is not None and min(p[1] for p in solved[0]) <= OUTER_BOTTOM_Y - STRAND_GAP:
            return solved
    raise AssertionError("keeper chain's inner strand does not close below the outer")


INNER_BEADS, INNER_LOW_Y = _solve_inner()

# Chain order: the ring-side end bead in the link, the outer strand to the
# ring, round the ring, the inner strand back to the eye, round the eye, the
# outer strand to the eye-side end bead in the link.
BEAD_CENTRES: tuple[Vec, ...] = tuple(
    [LINK_END_RING]
    + OUTER_RING_BEADS
    + INNER_BEADS[::-1]
    + OUTER_EYE_BEADS
    + [LINK_END_EYE]
)
BEAD_COUNT = len(BEAD_CENTRES)
CHAIN_LENGTH = (BEAD_COUNT - 1) * PITCH
INNER_LENGTH = (len(INNER_BEADS) - 1) * PITCH
OUTER_LENGTH = (
    (len(OUTER_EYE_BEADS) - 1 + len(OUTER_RING_BEADS) - 1 + 2) * PITCH + LINK_BEAD_SPACING
)
def _seg_point_dist(p: Vec, a: Vec, b: Vec) -> float:
    d = _sub(b, a)
    t = max(0.0, min(1.0, _dot(_sub(p, a), d) / _dot(d, d)))
    return _dist(p, _add(a, _scale(d, t)))


def _seg_seg_dist(a0: Vec, a1: Vec, b0: Vec, b1: Vec, samples: int = 24) -> float:
    return min(
        _seg_point_dist(_add(a0, _scale(_sub(a1, a0), k / samples)), b0, b1)
        for k in range(samples + 1)
    )


def _polyline_dist(p: Vec, pts: list[Vec]) -> float:
    return min(_seg_point_dist(p, pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def _eye_centreline() -> list[Vec]:
    cx, cy, cz = EYE_LOOP_CENTRE
    loop = [
        (cx, cy + LOOP_R * math.sin(2 * math.pi * k / 72), cz + LOOP_R * math.cos(2 * math.pi * k / 72))
        for k in range(73)
    ]
    return loop


def _eye_tail() -> list[Vec]:
    return [EYE_ROOT, _add(EYE_ROOT, (0.0, EYE_TAIL_LEN, 0.0))]


def _ring_centreline() -> list[Vec]:
    """The round ring's wire centreline in the plane x = RING_X."""
    return [
        (
            RING_X,
            -RING_CENTRE_X + MEAN_R * math.cos(2.0 * math.pi * k / 144),
            PIN_Z + MEAN_R * math.sin(2.0 * math.pi * k / 144),
        )
        for k in range(145)
    ]


def _pin_radius_at(x: float) -> float:
    s = (x - PIN_X0) / PIN_LENGTH
    return (BIG_END_DIA - (BIG_END_DIA - SMALL_END_DIA) * s) / 2.0


def _solid_gap(p: Vec, r: float) -> dict[str, float]:
    """Air from a sphere of radius r at p to each rigid neighbour."""
    x, y, z = p
    gaps: dict[str, float] = {}
    # Arm: the straight bar below the axis, |x| <= HALF_WIDTH.
    dx = max(0.0, abs(x) - HALF_WIDTH)
    dz = max(0.0, ARM_Z[0] - z, z - ARM_Z[1])
    dy = max(0.0, y)  # the rounded top end lies above y = 0
    gaps["arm"] = math.sqrt(dx * dx + dy * dy + dz * dz) - r
    # Hub barrel.
    dr = max(0.0, math.hypot(x, y) - HUB_R)
    dzh = max(0.0, HUB_Z[0] - z, z - HUB_Z[1])
    gaps["hub"] = math.hypot(dr, dzh) - r if math.hypot(x, y) >= HUB_R or dzh > 0.0 else -r
    # Taper pin (conical; radius sampled at the nearest station).
    xs = max(PIN_X0, min(PIN_X0 + PIN_LENGTH, x))
    dxp = abs(x - xs)
    drp = max(0.0, math.hypot(y, z - PIN_Z) - _pin_radius_at(xs))
    gaps["pin"] = math.hypot(dxp, drp) - r
    # Anchor screw head.
    drs = max(0.0, math.hypot(x - SCREW_XY[0], y - SCREW_XY[1]) - SCREW_HEAD_DIA / 2.0)
    dzs = max(0.0, SCREW_HEAD_Z[0] - z, z - SCREW_HEAD_Z[1])
    gaps["screw"] = math.hypot(drs, dzs) - r
    # Wires.
    gaps["eye"] = min(
        _polyline_dist(p, _eye_centreline()), _polyline_dist(p, _eye_tail())
    ) - EYE_WIRE_DIA / 2.0 - r
    gaps["ring"] = _polyline_dist(p, _ring_centreline()) - RING_WIRE_DIA / 2.0 - r
    return gaps




def _link_local(p: Vec) -> tuple[float, float, float]:
    """``p`` in the link's frame: axial, then the radial offsets."""
    rel = _sub(p, LINK_ORIGIN)
    axial = _dot(rel, LINK_AXIS)
    radial = _norm(_sub(rel, _scale(LINK_AXIS, axial)))
    return axial, radial, 0.0


def _link_gap(p: Vec) -> float:
    """Distance from p to the outside of the link's domed capsule."""
    axial, radial, _ = _link_local(p)
    r = LINK_OD / 2.0
    over = abs(axial) - LINK_END_BEAD_X
    if over <= 0.0:
        return max(0.0, radial - r)
    return max(0.0, math.hypot(over, radial) - r)


def _captured_gap(p: Vec) -> float:
    """Air between a captured end bead and its dome's inside."""
    axial, radial, _ = _link_local(p)
    dome = math.hypot(abs(axial) - LINK_END_BEAD_X, radial)
    return LINK_OD / 2.0 - LINK_WALL - dome - BEAD_R


def clearance_report() -> dict[str, float]:
    """Smallest air (mm) per contact class; every value must be >= 0.

    The two end beads are proved against their domes' insides, every other
    bead against the link's outside.
    """
    beads = BEAD_CENTRES
    captured = {0, len(beads) - 1}
    worst: dict[str, float] = {}

    def note(key: str, value: float) -> None:
        worst[key] = min(worst.get(key, math.inf), value)

    for i, p in enumerate(beads):
        for key, gap in _solid_gap(p, BEAD_R).items():
            note(f"bead-{key}", gap)
        if i in captured:
            note("bead-in-link", _captured_gap(p))
        else:
            note("bead-link", _link_gap(p) - BEAD_R)
        for j in range(i + 2, len(beads)):
            if {i, j} == captured:
                continue  # the two end beads face each other inside the link
            note("bead-bead", _dist(p, beads[j]) - BEAD_DIA)
    for i in range(len(beads) - 1):
        a, b = beads[i], beads[i + 1]
        for k in range(1, 8):
            q = _add(a, _scale(_sub(b, a), k / 8.0))
            for key, gap in _solid_gap(q, ROD_R).items():
                note(f"rod-{key}", gap)
    for k in range(0, 9):
        q = _add(LINK_ORIGIN, _scale(LINK_AXIS, (k / 8.0 - 0.5) * LINK_LENGTH))
        for key, gap in _solid_gap(q, LINK_OD / 2.0).items():
            note(f"link-{key}", gap)
    return worst


def pitch_errors() -> list[float]:
    return [
        abs(_dist(BEAD_CENTRES[i], BEAD_CENTRES[i + 1]) - PITCH)
        for i in range(BEAD_COUNT - 1)
    ]


def _link_solid(x: float, y: float, z: float) -> bool:
    """Whether local point (x, y, z) is brass: the link's own CSG, axis X."""
    r = math.hypot(y, z)
    ro = LINK_OD / 2.0
    ri = ro - LINK_WALL
    over = abs(x) - LINK_END_BEAD_X
    if over > ro:
        return False
    dome = math.hypot(over, r) if over > 0.0 else r
    if dome > ro or dome < ri:
        return False
    crimp_r = 0.3
    crimp_c = ro + crimp_r - LINK_CRIMP_DEPTH
    if math.hypot(abs(x) - LINK_CRIMP_X, r - crimp_c) < crimp_r:
        return False
    if r < LINK_TIP_HOLE / 2.0:
        return False
    if y <= 0.0:
        return True
    in_mouth = (
        abs(abs(x) - LINK_END_BEAD_X) < LINK_MOUTH_LENGTH / 2.0
        and abs(z) < LINK_MOUTH_WIDTH / 2.0
    )
    return not (in_mouth or abs(z) < LINK_SLOT_WIDTH / 2.0)


def link_volume(steps: int = 72) -> float:
    """The link's volume by midpoint integration of ``_link_solid``."""
    ro = LINK_OD / 2.0
    half = LINK_LENGTH / 2.0
    dx, dr = LINK_LENGTH / (2 * steps), LINK_OD / steps
    total = 0
    for ix in range(2 * steps):
        x = -half + (ix + 0.5) * dx
        for iy in range(steps):
            y = -ro + (iy + 0.5) * dr
            for iz in range(steps):
                if _link_solid(x, y, -ro + (iz + 0.5) * dr):
                    total += 1
    return total * dx * dr * dr


# The purchased-part identification sheets (build_purchased_part_drawing).
# One short line each: the sheet reserves ~0.19 m for the note (the first cut,
# 94 characters, ran 0.204 m and failed drawing:keeper_chain).
CHAIN_DRAWING_NOTES = f"CUT TO {BEAD_COUNT} BEADS ({CHAIN_LENGTH:.0f} MM); CLOSED BY MHA-150."
LINK_DRAWING_NOTES = "JOINS THE MHA-149 ENDS: ONE BEAD PER DOME."

# The chain part's own frame: machine axes, origin on its first bead (the
# ring-side end bead, inside the link). Its seed bead then needs no
# reference plane, and the part's origin sits on its body. The drive train
# places it at the crank frame plus CHAIN_PART_ORIGIN.
CHAIN_PART_ORIGIN: Vec = BEAD_CENTRES[0]
CHAIN_PART_BEADS: tuple[Vec, ...] = tuple(_sub(p, CHAIN_PART_ORIGIN) for p in BEAD_CENTRES)
