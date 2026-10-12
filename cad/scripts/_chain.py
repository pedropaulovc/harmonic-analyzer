"""Inherited drive-chain VISUAL guide geometry (book ch. 23/30).

The ANSI #25 roller chain loops the two CHAIN-WRAPPED removable sprockets
selected for the crank and knob shafts in ``pd_transgear_removable_spec``
(ch. 23: swapping the removables changes the platen ratio). Every chain-side
ch30 plate (p002/p005/p006) shows it: a taut run on the pinion-bar side and a
visibly drooping slack run on the other.

Pure math only. The native connected-linkage visual follows three circular
arcs and a straight run; its integer component count and continuous arc
length do not prove a physical, standard-pitch roller-chain cycle. The
independent ``paper_drive_chain_fit`` solver checks discrete pinned links,
free sprocket phase, gravity slack and the actual ANSI tooth boundaries.

Local frame: knob wrap centre at the origin, machine xy pre-mirror. Centres
come from cone_line and paper_drive_geom; mounted tooth counts, standard
pitch and the FIXED installed count come from pd_transgear_removable_spec.
The continuous guide's slack arc is solved inside its internal-tangency
domain. This preserves the inherited native representation without silently
selecting a different physical chain or stretching its pitch.
"""

from __future__ import annotations

import math

import pd_transgear_removable_spec as _removable
from paper_drive_chain_fit import source_nominal_chain_centres_mm


# Chain-wheel centres, machine xy pre-mirror.

_KNOB_SOURCE, _CRANK_SOURCE = source_nominal_chain_centres_mm()
KNOB_CENTRE = (-_KNOB_SOURCE[0], _KNOB_SOURCE[1])
# Canonical physical lower axis evaluated at the actual wheel Z; same source
# as the discrete nominal solver. The inherited guide remains VISUAL only.
CRANK_CENTRE = (-_CRANK_SOURCE[0], _CRANK_SOURCE[1])
# The selected physical count stays fixed; only the visual guide's droop changes.

# Mounted removables (ANSI #25, pd_transgear_removable_spec): tip r = OD / 2.
KNOB_TIP_R = _removable.outside_dia(_removable.KNOB_TEETH) / 2.0
CRANK_TIP_R = _removable.outside_dia(_removable.CRANK_TEETH) / 2.0
# Pitch r = p / (2 sin(180/N)) -- the chain pin centreline rides here.
KNOB_PITCH_R = _removable.pitch_dia(_removable.KNOB_TEETH) / 2.0
CRANK_PITCH_R = _removable.pitch_dia(_removable.CRANK_TEETH) / 2.0
# The inherited native chain VISUAL follows the pitch-circle arcs. Its arc
# length is not a discrete-pitch seating or closure certificate: that proof
# belongs to paper_drive_chain_fit. The visual and its intentional-contact
# classification remain unchanged; physical qualification never uses them.
WRAP_R_A = KNOB_PITCH_R
WRAP_R_B = CRANK_PITCH_R
# The continuous guide is a visual representation, not a suspended chain.

# --- centreline geometry (A = knob = origin, B = crank) ----------------------
BX = CRANK_CENTRE[0] - KNOB_CENTRE[0]
BY = CRANK_CENTRE[1] - KNOB_CENTRE[1]
D = math.hypot(BX, BY)
UX, UY = BX / D, BY / D
NX, NY = -UY, UX  # taut-side normal (local upper-right)

# Common external tangents of the unequal wrap circles: unit normal
# m = u * (rA - rB) / D +- n * k touches A at A + rA*m and B at B + rB*m.
_DR = (WRAP_R_A - WRAP_R_B) / D
_K = math.sqrt(1.0 - _DR * _DR)
# taut side (+n):
TNX = UX * _DR + NX * _K
TNY = UY * _DR + NY * _K
TAUT_LEN = D * _K
# slack side (-n) straight tangent, the droop reference line:
_SNX = UX * _DR - NX * _K
_SNY = UY * _DR - NY * _K
_SC0 = WRAP_R_A  # line constant: (A + rA*m) . m with A at the origin


def _unit(px: float, py: float) -> tuple[float, float]:
    n = math.hypot(px, py)
    return px / n, py / n


def _slack_centre(rs: float) -> tuple[float, float]:
    """Centre of the slack arc, internally tangent to both wraps, +n side."""
    p = (D * D + (WRAP_R_B - WRAP_R_A) * (2.0 * rs - WRAP_R_A - WRAP_R_B)) / (
        2.0 * D
    )
    q2 = (rs - WRAP_R_A) ** 2 - p * p
    if q2 < -1e-8:
        raise ValueError(f"slack radius {rs} too small")
    q = math.sqrt(max(0.0, q2))
    return UX * p + NX * q, UY * p + NY * q


def _droop(rs: float) -> float:
    """Bulge of the slack arc beyond the straight -n tangent line."""
    cx, cy = _slack_centre(rs)
    return cx * _SNX + cy * _SNY + rs - _SC0


def _ccw(a_from: float, a_to: float) -> float:
    return (a_to - a_from) % (2.0 * math.pi)


def _solve_slack_radius(sag: float) -> float:
    """Visual arc radius within the finite internal-tangency droop domain."""
    lo = (D + WRAP_R_A + WRAP_R_B) / 2.0
    maximum = _droop(lo)
    if not math.isfinite(sag) or not 0.0 < sag <= maximum:
        raise ValueError(f"visual droop {sag} outside 0..{maximum:.6f}")
    hi = 2.0 * lo
    for _ in range(64):
        if _droop(hi) <= sag:
            break
        hi *= 2.0
    else:
        raise ValueError("cannot bracket the visual slack radius")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if _droop(mid) > sag:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _loop_length(sag: float) -> float:
    """Continuous VISUAL guide length, not the sum of physical link chords."""
    if sag == 0.0:
        dr = WRAP_R_A - WRAP_R_B
        return (
            2.0 * TAUT_LEN
            + math.pi * (WRAP_R_A + WRAP_R_B)
            + 2.0 * dr * math.asin(dr / D)
        )
    rs = _solve_slack_radius(sag)
    cx, cy = _slack_centre(rs)
    gax, gay = _unit(-cx, -cy)
    gbx, gby = _unit(BX - cx, BY - cy)
    ang_n = math.atan2(TNY, TNX)
    ang_ga = math.atan2(gay, gax)
    ang_gb = math.atan2(gby, gbx)
    span_a = _ccw(ang_n, ang_ga)
    span_slack = _ccw(ang_ga, ang_gb)
    span_b = _ccw(ang_gb, ang_n)
    return WRAP_R_A * span_a + WRAP_R_B * span_b + rs * span_slack + TAUT_LEN


# --- selected-count visual guide ---------------------------------------------
LINK_PITCH = _removable.CHAIN_PITCH
LINK_COUNT = _removable.CHAIN_LINK_COUNT
if type(LINK_COUNT) is not int or LINK_COUNT <= 0 or LINK_COUNT % 2:
    raise ValueError("the selected ANSI #25 chain count must be a positive even integer")
CENTRELINE_LEN = LINK_COUNT * LINK_PITCH
VISUAL_TAUT_LENGTH = _loop_length(0.0)
VISUAL_MAX_SAG = _droop((D + WRAP_R_A + WRAP_R_B) / 2.0)
VISUAL_MAX_LENGTH = _loop_length(VISUAL_MAX_SAG)
if not VISUAL_TAUT_LENGTH < CENTRELINE_LEN < VISUAL_MAX_LENGTH:
    raise ValueError(
        f"selected {LINK_COUNT}-link visual guide cannot fit centres "
        f"{KNOB_CENTRE}, {CRANK_CENTRE}: target {CENTRELINE_LEN:.6f}, "
        f"continuous guide domain {VISUAL_TAUT_LENGTH:.6f}..{VISUAL_MAX_LENGTH:.6f}; "
        "this is not a discrete-chain feasibility verdict"
    )
_LO_SAG, _HI_SAG = 0.0, VISUAL_MAX_SAG
for _ in range(80):
    _MID = 0.5 * (_LO_SAG + _HI_SAG)
    if _loop_length(_MID) < CENTRELINE_LEN:
        _LO_SAG = _MID
    else:
        _HI_SAG = _MID
SAG = 0.5 * (_LO_SAG + _HI_SAG)
assert abs(_loop_length(SAG) - CENTRELINE_LEN) < 1e-6

SLACK_R = _solve_slack_radius(SAG)
CX, CY = _slack_centre(SLACK_R)

GAX, GAY = _unit(-CX, -CY)  # C -> A radial (slack tangent at knob)
GBX, GBY = _unit(BX - CX, BY - CY)  # C -> B radial (slack tangent at crank)

# Loop traversal is CCW throughout (add_arc draws CCW start -> end):
# wrap A from the taut normal to gA, slack arc from gA to gB about C,
# wrap B from gB to the taut normal, taut line back. The three arc spans
# must close the full turn.
_ANG_N = math.atan2(TNY, TNX)
_ANG_GA = math.atan2(GAY, GAX)
_ANG_GB = math.atan2(GBY, GBX)

SPAN_A = _ccw(_ANG_N, _ANG_GA)
SPAN_SLACK = _ccw(_ANG_GA, _ANG_GB)
SPAN_B = _ccw(_ANG_GB, _ANG_N)
assert abs(SPAN_A + SPAN_SLACK + SPAN_B - 2.0 * math.pi) < 1e-9
assert abs(
    WRAP_R_A * SPAN_A + WRAP_R_B * SPAN_B + SLACK_R * SPAN_SLACK + TAUT_LEN
    - CENTRELINE_LEN
) < 1e-6

# --- roller chain ------------------------------------------------------------
# A real ANSI #25 roller chain (pitch 1/4 in EXACT, roller Ø3.30 from
# pd_transgear_removable_spec; see LINK_PITCH/LINK_COUNT above): alternating
# INNER links (2 inner plates + 2 rollers) and OUTER links (2 outer plates + 2
# pins), filled along the centreline loop by the connected-linkage chain
# pattern (build_pd_paper_drive_assembly._insert_roller_chain). The in-plane
# envelope stays +-2.4 (the retired #13 ball chain's 4.8 bead).

# Every clearance is >= 0.25 mm and nothing relies on exact tangency: the
# M6.x interference checker flags ~0.00 mm^3 slivers, so the links FLOAT as a
# multibody (disconnected bodies in a part are allowed). The z stack is sized
# so the chain STRADDLES the removable sprocket's plate (ch23 p.58-59: chain
# wider than the wheel): sprocket faces +-PLATE/2 about the chain plane,
# inner-plate INNER faces SPROCKET_CLEAR outside them, so the tooth tips pass
# BETWEEN the plates instead of through them.
PLATE_HEIGHT = 4.8  # obround plate height (in-plane envelope, unchanged)
PLATE_HALF_H = PLATE_HEIGHT / 2.0  # 2.4, the obround end-arc radius
PLATE_THICK = 0.8  # side-plate thickness (z)
SPROCKET_CLEAR = 0.25  # sprocket face -> inner-plate inner face, per side
PLATE_GAP = 0.3  # inner-plate outer face -> outer-plate inner face
FLOAT = 0.3  # radial float of a round body in its plate hole

ROLLER_DIA = _removable.ROLLER_DIA  # 3.30, the #25 roller/bushing OD
ROLLER_R = ROLLER_DIA / 2.0  # 1.65
BUSH_BORE_R = 1.0  # bushing through-bore; pin floats inside (0.35 clearance)
INNER_PLATE_HOLE_R = ROLLER_R + FLOAT  # 1.95: bushing OD floats inside; web 0.45

PIN_DIA = 1.3  # outer-link pin (floats in the bushing bore and plate holes)
PIN_R = PIN_DIA / 2.0  # 0.65
OUTER_PLATE_HOLE_R = PIN_R + FLOAT  # 0.95: pin floats inside; web 1.45

# z stack (pin axis), symmetric about the chain mid-plane:
INNER_PLATE_INNER_Z = _removable.PLATE / 2.0 + SPROCKET_CLEAR  # 1.65
BUSH_HALF_LEN = INNER_PLATE_INNER_Z  # bushing spans between the inner plates
INNER_PLATE_Z = INNER_PLATE_INNER_Z + PLATE_THICK / 2.0  # 2.05 (faces 1.65..2.45)
OUTER_PLATE_Z = INNER_PLATE_Z + PLATE_THICK + PLATE_GAP  # 3.15 (faces 2.75..3.55)
PIN_HALF_LEN = OUTER_PLATE_Z + PLATE_THICK / 2.0  # 3.55, flush with the outer plates
if PLATE_HALF_H - INNER_PLATE_HOLE_R < SPROCKET_CLEAR:
    raise AssertionError("inner-plate hole leaves no web around the #25 roller")


def loop_point_tangent(
    s: float, dx: float = 0.0, dy: float = 0.0, mirror_x: bool = False
) -> tuple[float, float, float]:
    """Point (x, y) and CCW tangent angle (rad) at arc length ``s`` along the
    loop, in the same (dx, dy, mirror_x) frame as :func:`loop_segments`.

    ``s`` is taken mod CENTRELINE_LEN. The tangent points in the direction of
    increasing ``s`` (the CCW traversal: knob wrap from the taut normal, slack
    arc, crank wrap, taut line). Used to seat the chain-pattern seeds tangent
    to the path at their stations.
    """
    s %= CENTRELINE_LEN
    base = 0.0
    for cx, cy, r, ang0, span in (
        (0.0, 0.0, WRAP_R_A, _ANG_N, SPAN_A),
        (CX, CY, SLACK_R, _ANG_GA, SPAN_SLACK),
        (BX, BY, WRAP_R_B, _ANG_GB, SPAN_B),
    ):
        arc_len = r * span
        if s <= base + arc_len:
            ang = ang0 + (s - base) / r
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
            theta = ang + math.pi / 2.0  # CCW tangent
            return _frame_point_tangent(x, y, theta, dx, dy, mirror_x)
        base += arc_len
    # taut line, from crank tangent point back to knob tangent point
    x1, y1 = BX + WRAP_R_B * TNX, BY + WRAP_R_B * TNY
    x2, y2 = WRAP_R_A * TNX, WRAP_R_A * TNY
    t = (s - base) / TAUT_LEN
    x, y = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
    theta = math.atan2(y2 - y1, x2 - x1)
    return _frame_point_tangent(x, y, theta, dx, dy, mirror_x)


def _frame_point_tangent(
    x: float, y: float, theta: float, dx: float, dy: float, mirror_x: bool
) -> tuple[float, float, float]:
    x, y = x + dx, y + dy
    if not mirror_x:
        return x, y, theta
    # reflect about machine x = 0: (x, y) -> (-x, y); a direction angle theta
    # -> pi - theta (cos flips sign, sin keeps it).
    return -x, y, math.pi - theta


def loop_segments(
    dx: float = 0.0, dy: float = 0.0, mirror_x: bool = False
) -> tuple[
    tuple[float, ...], tuple[float, ...], tuple[float, ...], tuple[float, ...]
]:
    """The centreline loop as add_arc/add_line coordinate tuples.

    Returns (knob_arc, slack_arc, crank_arc, taut_line): arcs as
    (cx, cy, sx, sy, ex, ey), the line as (x1, y1, x2, y2), translated by
    (dx, dy) and then optionally reflected about machine x = 0 (the M6.8
    YZ mirror -- an assembly path sketch has no part-local mirror shim to
    lean on, so it is authored in final post-mirror coordinates). The
    local loop is CCW; a mirror reverses that, so mirrored arcs come back
    with start/end SWAPPED (add_arc draws CCW start -> end) and all four
    junctions still merge exactly.
    """
    ra, rb, rs = WRAP_R_A, WRAP_R_B, SLACK_R
    knob = (0.0, 0.0, ra * TNX, ra * TNY, ra * GAX, ra * GAY)
    slack = (CX, CY, CX + rs * GAX, CY + rs * GAY, CX + rs * GBX, CY + rs * GBY)
    crank = (BX, BY, BX + rb * GBX, BY + rb * GBY, BX + rb * TNX, BY + rb * TNY)
    taut = (BX + rb * TNX, BY + rb * TNY, ra * TNX, ra * TNY)

    def _xy(x: float, y: float) -> tuple[float, float]:
        x, y = x + dx, y + dy
        return (-x, y) if mirror_x else (x, y)

    def _arc(a: tuple[float, ...]) -> tuple[float, ...]:
        centre = _xy(a[0], a[1])
        start, end = _xy(a[2], a[3]), _xy(a[4], a[5])
        if mirror_x:
            start, end = end, start
        return (*centre, *start, *end)

    line = (*_xy(taut[0], taut[1]), *_xy(taut[2], taut[3]))
    return _arc(knob), _arc(slack), _arc(crank), line


def loop_parameter(
    x: float, y: float, dx: float = 0.0, dy: float = 0.0, mirror_x: bool = False
) -> float:
    """Arc-length position s in [0, CENTRELINE_LEN) of the loop point nearest
    (x, y), in the same (dx, dy, mirror_x) frame as :func:`loop_segments`.

    s runs along the CCW traversal (knob wrap from the taut normal, slack,
    crank wrap, taut line). Meant for points already gated ON the loop by
    :func:`centreline_distance` -- link spacing/closure checks."""
    if mirror_x:
        x = -x
    x, y = x - dx, y - dy
    two_pi = 2.0 * math.pi
    candidates: list[tuple[float, float]] = []  # (distance to segment, s)
    base = 0.0
    for cx, cy, r, ang0, span in (
        (0.0, 0.0, WRAP_R_A, _ANG_N, SPAN_A),
        (CX, CY, SLACK_R, _ANG_GA, SPAN_SLACK),
        (BX, BY, WRAP_R_B, _ANG_GB, SPAN_B),
    ):
        wedge = (math.atan2(y - cy, x - cx) - ang0) % two_pi
        if wedge <= span:
            candidates.append(
                (abs(math.hypot(x - cx, y - cy) - r), base + r * wedge)
            )
        base += r * span
    x1, y1 = BX + WRAP_R_B * TNX, BY + WRAP_R_B * TNY
    x2, y2 = WRAP_R_A * TNX, WRAP_R_A * TNY
    t = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / (TAUT_LEN * TAUT_LEN)
    t = max(0.0, min(1.0, t))
    dist = math.hypot(x - (x1 + t * (x2 - x1)), y - (y1 + t * (y2 - y1)))
    candidates.append((dist, base + t * TAUT_LEN))
    return min(candidates)[1] % CENTRELINE_LEN


def centreline_distance(
    x: float, y: float, dx: float = 0.0, dy: float = 0.0, mirror_x: bool = False
) -> float:
    """Distance from a point to the centreline loop, in the same
    (dx, dy, mirror_x) frame as :func:`loop_segments`.

    The wrap/slack arcs are treated as FULL circles -- ample for the
    link-on-path gate: a mirrored, mis-planed or unmirrored loop misses
    by tens of millimetres, while a link pin0 ON the path sits within solver
    tolerance of one of the true sub-arcs.
    """
    if mirror_x:
        x = -x
    x, y = x - dx, y - dy
    candidates = [
        abs(math.hypot(x, y) - WRAP_R_A),
        abs(math.hypot(x - BX, y - BY) - WRAP_R_B),
        abs(math.hypot(x - CX, y - CY) - SLACK_R),
    ]
    x1, y1 = BX + WRAP_R_B * TNX, BY + WRAP_R_B * TNY
    x2, y2 = WRAP_R_A * TNX, WRAP_R_A * TNY
    t = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / (TAUT_LEN * TAUT_LEN)
    t = max(0.0, min(1.0, t))
    candidates.append(math.hypot(x - (x1 + t * (x2 - x1)), y - (y1 + t * (y2 - y1))))
    return min(candidates)
