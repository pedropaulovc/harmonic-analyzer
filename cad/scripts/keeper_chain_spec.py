r"""Crank-pin keeper chain (MHA-149) and its splicing links (MHA-150), pure data.

The ch11 p.14 photographs show the brass eye on the crank arm and the brass
ring on the taper pin's head; the chain that tied the removable pin to the arm
is lost. It is reconstructed with purchased McMaster-Carr bead chain:

* 3606T118 -- unfinished brass bead chain, trade size 3, 3/32 in beads,
  20 lbf, cut to BEAD_COUNT beads.
* 3606T813 -- brass splicing links for trade-size-3 chain, two per chain. Each
  chain end passes through the eye (or the ring), and its end bead snaps into
  one end of a link. The running chain threads the link's cross-hole.

McMaster publishes neither CAD nor dimensions for either item (read
2026-09-29). The bead diameter is the catalogue's. The pitch is the trade-size
3 average of 94 beads per foot (Ball Chain Mfg. and Frank Winne size charts).
The rod and link dimensions are assumptions, named below; each one only
decides clearances the functions here prove.

Frame ("crank frame"): machine axes, origin on the crank axis at the arm's
front (outboard) face, machine z -183. The arm fills z 0..ARM_THICKNESS and
the hub barrel ARM_THICKNESS..HUB_LENGTH. The chain part is authored in this
frame, and the drive train places it with an identity rotation at that
machine point. Splice links are authored with their axis on +X and their
cross-hole on +Y, and placed with an identity rotation at ``SPLICE_ORIGINS``.

Geometry, rest pose (arm hanging down, gravity -Y):

* eye end, plane z = EYE_LOOP_Z: the chain passes through the eye along X, and
  its rod bears on the inside of the loop's bottom wire with a bead either
  side. Both strands drop to a splice link below, the end bead in the link's
  -X cup and the running bead in its cross-hole.
* ring end, plane z = RING_PLANE_Z: the same wrap on the ring's return leg,
  bottom, ~9.5 below the pin, where the hub-side bead clears the barrel.
* the run leaves each link's cross-hole straight down, then drapes round the
  arm's -X edge: forward of the arm face at the eye end, beside the edge, and
  behind the arm up to the ring. Its low point is solved so the run closes on
  a whole number of pitches.

``BEAD_COUNT`` is the length to cut. It is chosen so the taper pin can be
drawn fully out of the hub (PIN_WITHDRAWAL) with the chain still attached.
"""

from __future__ import annotations

import math

from crank_arm_spec import ANCHOR_SCREW_X, ANCHOR_SCREW_Y, ARM_THICKNESS, HALF_WIDTH
from crank_hub_geometry import HUB_BARREL_DIA, HUB_LENGTH, SERVICE_PIN_STATION
from crank_pin_eye_spec import ANCHOR_AIR, LOOP_INNER_R, LOOP_R
from crank_pin_eye_spec import TAIL_LEN as EYE_TAIL_LEN
from crank_pin_eye_spec import WIRE_DIA as EYE_WIRE_DIA
from crank_pin_ring_spec import HUB_CLEARANCE, MEAN_R, RING_BOTTOM_X, RING_CENTRE_X
from crank_pin_ring_spec import WIRE_DIA as RING_WIRE_DIA
from crank_pin_spec import BIG_END_DIA, PIN_LENGTH, RING_HOLE_X, SMALL_END_DIA
from fillister_screw_spec import HEAD_DIA as SCREW_HEAD_DIA
from fillister_screw_spec import HEAD_H as SCREW_HEAD_H
from fillister_screw_spec import SHANK_DIA as SCREW_SHANK_DIA

Vec = tuple[float, float, float]

MM_PER_IN = 25.4

# --- purchased-part nominals --------------------------------------------------
CHAIN_SKU = "3606T118"
SPLICE_SKU = "3606T813"
BEAD_DIA = 3.0 / 32.0 * MM_PER_IN  # 2.38125, the catalogue bead diameter
BEAD_R = BEAD_DIA / 2.0
PITCH = 12.0 * MM_PER_IN / 94.0  # 3.2426, trade size 3 average
# Assumption: the connecting rod. It is hidden inside the beads except for
# the ~0.9 mm between them.
ROD_DIA = 0.5
ROD_R = ROD_DIA / 2.0
# Assumption: the splicing-link envelope. It is a tube whose bore takes a bead
# at each end, cross-drilled at mid-length for the running chain.
SPLICE_OD = 3.1
SPLICE_BORE = 2.5
SPLICE_LENGTH = 8.4
SPLICE_CROSS_HOLE = 1.2  # passes the rod; the running bead sits in the bore
SPLICE_END_BEAD_X = 2.9  # end-bead centre from the link centre, in the -X cup

AIR = 0.02  # minimum air the solve leaves between parts that must not touch

# --- pose inputs from the part specs (crank frame) ----------------------------
HUB_R = HUB_BARREL_DIA / 2.0
ARM_Z = (0.0, ARM_THICKNESS)
HUB_Z = (ARM_THICKNESS, HUB_LENGTH)
PIN_Z = SERVICE_PIN_STATION
PIN_PROUD = RING_HOLE_X + RING_WIRE_DIA / 2.0 + HUB_CLEARANCE
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

# The run drapes outboard of the arm's -X edge at this x.
RUN_SIDE_X = -(HALF_WIDTH + BEAD_R + 1.6)


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


def _solve_splice(wire_x: float, rod_y: float) -> tuple[float, float]:
    """Link centre (x, y) below a wrap whose rod crosses x=wire_x at rod_y.

    The link hangs outboard (-X) of the wire. The wrap beads sit half a pitch
    either side of the wire. The end bead sits in the link's +X cup, and its
    neighbour leaves the cup along +X to meet the +X wrap bead one pitch away.
    The running bead's upper neighbour, one pitch above the link centre, meets
    the -X wrap bead one pitch away. That is two circles, and the solution
    below the wrap is taken.
    """
    s = PITCH / 2.0
    # a = x_link - wire_x, b = y_link - rod_y.
    # (a + END + P - s)^2 + b^2 = P^2 ; (a + s)^2 + (b + P)^2 = P^2
    c1 = (-(SPLICE_END_BEAD_X + PITCH - s), 0.0)
    c2 = (-s, -PITCH)
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy)
    if d > 2.0 * PITCH or d == 0.0:
        raise AssertionError("splice-link wrap has no closing geometry")
    h = math.sqrt(PITCH**2 - (d / 2.0) ** 2)
    mx, my = c1[0] + dx / 2.0, c1[1] + dy / 2.0
    candidates = (
        (mx + h * dy / d, my - h * dx / d),
        (mx - h * dy / d, my + h * dx / d),
    )
    a, b = min(candidates, key=lambda ab: ab[1])
    return wire_x + a, rod_y + b


def _end_loop(wire_x: float, rod_y: float, z: float) -> tuple[list[Vec], Vec]:
    """Beads from the end bead to the running bead, and the link centre."""
    s = PITCH / 2.0
    lx, ly = _solve_splice(wire_x, rod_y)
    link = (lx, ly, z)
    end = (lx + SPLICE_END_BEAD_X, ly, z)
    beads = [
        end,
        (end[0] + PITCH, ly, z),
        (wire_x + s, rod_y, z),
        (wire_x - s, rod_y, z),
        (lx, ly + PITCH, z),
        link,
    ]
    return beads, link


EYE_ROD_Y = EYE_LOOP_CENTRE[1] - LOOP_INNER_R + ROD_R + AIR
RING_ROD_Y = -RING_BOTTOM_X + RING_WIRE_DIA / 2.0 + ROD_R + AIR
EYE_LOOP, EYE_LINK = _end_loop(EYE_ROOT[0], EYE_ROD_Y, EYE_LOOP_Z)
RING_LOOP, RING_LINK = _end_loop(RING_X, RING_ROD_Y, RING_PLANE_Z)
SPLICE_ORIGINS: tuple[Vec, Vec] = (EYE_LINK, RING_LINK)


# --- the run -------------------------------------------------------------------
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


def _run_curve(low_y: float) -> list[Vec]:
    start = _sub(EYE_LINK, (0.0, PITCH, 0.0))
    end = _sub(RING_LINK, (0.0, PITCH, 0.0))
    return _catmull_rom(
        [
            EYE_LINK,
            start,
            (RUN_SIDE_X, low_y, EYE_LOOP_Z),
            (RUN_SIDE_X, low_y, RING_PLANE_Z),
            end,
            RING_LINK,
        ]
    )


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


def _run_beads(links: int) -> tuple[list[Vec], float]:
    """Run beads from below the eye link to below the ring link, inclusive.

    ``links`` pitches separate them. The low point is bisected until the
    last chord closes exactly on the bead below the ring link.
    """
    end = _sub(RING_LINK, (0.0, PITCH, 0.0))

    def residual(low_y: float) -> float:
        beads = _chord_walk(_run_curve(low_y), links - 1)
        if len(beads) < links:
            return -PITCH  # curve too short: the walk ran off its end
        return _dist(beads[-1], end) - PITCH

    lo, hi = EYE_LINK[1] - 80.0, EYE_LINK[1] - PITCH - 1.0
    if residual(lo) <= 0.0 or residual(hi) >= 0.0:
        raise AssertionError(f"keeper-chain run of {links} pitches does not close")
    for _ in range(56):  # 80 mm / 2**56: far below any COM tolerance
        mid = (lo + hi) / 2.0
        if residual(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    low_y = (lo + hi) / 2.0
    beads = _chord_walk(_run_curve(low_y), links - 1) + [end]
    return beads, low_y


def _withdrawal_reach() -> float:
    """Shortest run from below the eye link to below the withdrawn ring link.

    It is a straight line to the arm's front -X corner, then a straight line
    to the ring link after the pin's withdrawal, minimised over the height
    where it rounds the corner.
    """
    start = _sub(EYE_LINK, (0.0, PITCH, 0.0))
    end = _add(_sub(RING_LINK, (0.0, PITCH, 0.0)), (-PIN_WITHDRAWAL, 0.0, 0.0))
    corner_x = -(HALF_WIDTH + BEAD_R)
    corner_z = -BEAD_R
    return min(
        _dist(start, (corner_x, y, corner_z)) + _dist((corner_x, y, corner_z), end)
        for y in (start[1] + 0.25 * k for k in range(-200, 200))
    )


WITHDRAWAL_REACH = _withdrawal_reach()
# Enough pitches to reach the withdrawn ring with a few in hand, so the pin
# can be set down beside the machine without dragging on the chain.
RUN_SLACK_PITCHES = 3
RUN_LINKS = math.ceil(WITHDRAWAL_REACH / PITCH) + RUN_SLACK_PITCHES
RUN_BEADS, RUN_LOW_Y = _run_beads(RUN_LINKS)

# Chain order: eye end bead ... eye link bead, run, ring link bead ... ring end
# bead. The two link beads are the ends of the run.
BEAD_CENTRES: tuple[Vec, ...] = tuple(EYE_LOOP + RUN_BEADS + RING_LOOP[::-1])
BEAD_COUNT = len(BEAD_CENTRES)
CHAIN_LENGTH = (BEAD_COUNT - 1) * PITCH


# --- clearance proof -----------------------------------------------------------
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


def _splice_axis(origin: Vec) -> tuple[Vec, Vec]:
    return (
        (origin[0] - SPLICE_LENGTH / 2.0, origin[1], origin[2]),
        (origin[0] + SPLICE_LENGTH / 2.0, origin[1], origin[2]),
    )


def _splice_gap(p: Vec, link: Vec) -> float:
    """Distance from p to the outside of a link's flat-ended tube."""
    axial = max(0.0, abs(p[0] - link[0]) - SPLICE_LENGTH / 2.0)
    radial = max(0.0, math.hypot(p[1] - link[1], p[2] - link[2]) - SPLICE_OD / 2.0)
    if axial == 0.0 and radial == 0.0:
        return 0.0
    return math.hypot(axial, radial)


def clearance_report() -> dict[str, float]:
    """Smallest air (mm) per contact class; every value must be >= 0.

    A captured bead inside a link is proved against the bore, and every other
    bead against the link's outside.
    """
    beads = BEAD_CENTRES
    worst: dict[str, float] = {}

    def note(key: str, value: float) -> None:
        worst[key] = min(worst.get(key, math.inf), value)

    captured = {0: EYE_LINK, len(EYE_LOOP) - 1: EYE_LINK, BEAD_COUNT - 1: RING_LINK}
    captured[BEAD_COUNT - len(RING_LOOP)] = RING_LINK
    for i, p in enumerate(beads):
        for key, gap in _solid_gap(p, BEAD_R).items():
            note(f"bead-{key}", gap)
        for link in SPLICE_ORIGINS:
            a, b = _splice_axis(link)
            if captured.get(i) == link:
                radial = math.hypot(p[1] - link[1], p[2] - link[2])
                note("bead-in-bore", SPLICE_BORE / 2.0 - radial - BEAD_R)
                continue
            note("bead-splice", _splice_gap(p, link) - BEAD_R)
        for j in range(i + 2, len(beads)):
            note("bead-bead", _dist(p, beads[j]) - BEAD_DIA)
    for i in range(len(beads) - 1):
        a, b = beads[i], beads[i + 1]
        for k in range(1, 8):
            q = _add(a, _scale(_sub(b, a), k / 8.0))
            for key, gap in _solid_gap(q, ROD_R).items():
                note(f"rod-{key}", gap)
    for link in SPLICE_ORIGINS:
        a, b = _splice_axis(link)
        for k in range(0, 9):
            q = _add(a, _scale(_sub(b, a), k / 8.0))
            for key, gap in _solid_gap(q, SPLICE_OD / 2.0).items():
                note(f"splice-{key}", gap)
    return worst


def pitch_errors() -> list[float]:
    return [
        abs(_dist(BEAD_CENTRES[i], BEAD_CENTRES[i + 1]) - PITCH)
        for i in range(BEAD_COUNT - 1)
    ]


def splice_volume() -> float:
    """Link tube volume less the cross-hole's two wall plugs (numeric)."""
    a, b, rh = SPLICE_OD / 2.0, SPLICE_BORE / 2.0, SPLICE_CROSS_HOLE / 2.0
    tube = math.pi * (a * a - b * b) * SPLICE_LENGTH
    n = 400
    plugs = 0.0
    for i in range(n):  # midpoint rule over the hole disk, strips along x
        z = -rh + (i + 0.5) * 2.0 * rh / n
        chord = 2.0 * math.sqrt(rh * rh - z * z)
        wall = 2.0 * (math.sqrt(a * a - z * z) - math.sqrt(max(0.0, b * b - z * z)))
        plugs += chord * wall * (2.0 * rh / n)
    return tube - plugs
