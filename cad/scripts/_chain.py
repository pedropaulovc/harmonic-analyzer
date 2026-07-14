"""Drive-chain centreline geometry (book ch. 23/30).

The roller chain loops the two CHAIN-WRAPPED removable gears (crank shaft
T12 -> knob shaft T24; ch. 23: the chain rides the removables' m2 teeth --
swapping them is what changes the platen ratio). Every chain-side ch30
plate (p002/p005/p006) shows it: a taut run on the pinion-bar side and a
visibly drooping slack run on the other.

Pure math only -- the roller chain's alternating inner/outer links are
explicitly placed along this centreline loop (build_paper_drive_assembly
._insert_roller_chain); the M6.8 rigid-band stand-in and the #13 bead-chain
stand-in are both retired.

Geometry (local frame: knob wrap centre at the origin, machine xy
pre-mirror; crank centre from build_drive_train_assembly X_CRANK / Y_CRANK
minus build_paper_drive_assembly KNOB_SHAFT_XY): two UNEQUAL wrap arcs whose
centreline rides each gear's PITCH circle (where a real chain seats -- the
rollers rest in the tooth valleys, the plates STRADDLE the 2.4-wide
sprocket, and the tips pass between them; only the roller<->tooth seating
remains as intended contact, whitelisted in
build_paper_drive_assembly.check_no_interference), the common
external tangent taut line on the +n side (the support-bar side), and a
slack arc sagging SAG below the straight external tangent on the -n side,
tangent-continuous at all four junctions (internal tangency:
|C - A| = R_slack - WRAP_R_A, |C - B| = R_slack - WRAP_R_B; R_slack is
solved numerically for the SAG droop).
"""

from __future__ import annotations

import math

# Chain-wheel centres, machine xy pre-mirror.
KNOB_CENTRE = (54.575, 284.1332)  # build_paper_drive_assembly KNOB_SHAFT_XY:
# stud (12, 297.9667) + latch C2C 44.766 at -18 deg (the permanent 12T:120T
# mesh -- paper-drive rework E8; ch30 p002 cross-check knob ~(55-58, 279-287))
# The crank chain-wheel rides the crankshaft, so its centre IS (X_CRANK, Y_CRANK)
# (the ch30 GT crank axis, ABOVE the drive line since the 2026-07-02 re-anchor).
# Hardcoded as a literal (like KNOB_CENTRE above) -- NOT imported from
# build_drive_train_assembly. _chain feeds the leaf chain-link PARTS through
# _chain_link, and a leaf part must not transitively depend on _assembly
# (test_buildgraph / check:graph enforces this); importing the drive-train
# assembly module would drag _assembly into that import chain. Instead,
# build_paper_drive_assembly._assert_chain_layout pins this value to the live
# drive-train (X_CRANK, Y_CRANK) and fails loud on drift, so a stale literal can
# never silently mis-anchor the chain over the relocated 64T/cone. The cleaner
# split (leaf-safe geometry vs assembly-time layout, no literal) is issue #86.
CRANK_CENTRE = (122.8, 143.90354719422464)  # drive-train abs(X_CRANK), Y_CRANK

TIP_R_T24 = 26.0  # mounted removables, module 2: tip r = (T + 2) * 2 / 2
TIP_R_T12 = 14.0
PITCH_R_T24 = 24.0  # module 2 pitch r = T * 2 / 2 -- the chain pin centreline
PITCH_R_T12 = 12.0  # rides here (rollers seat in the tooth valleys)
# The roller chain SEATS on each sprocket: its pin centreline rides the gear
# PITCH circle (the pitch polygon a real chain wraps), so the rollers rest in
# the tooth valleys and the tips poke out past the chain -- "on the base, not
# the teeth". Because the chain and the removables share one z-plane (a
# coplanar single-plane stand-in for a chain that really straddles the
# sprocket), the links necessarily overlap the teeth in that plane; that
# contact is intended mesh, whitelisted in
# build_paper_drive_assembly.check_no_interference (chain-link <->
# transgear-removable), exactly as link<->link contact already is.
WRAP_R_A = PITCH_R_T24  # 24.0 (knob T24 pitch circle)
WRAP_R_B = PITCH_R_T12  # 16.91 -> 12.0 (crank T12 pitch circle)
SAG_NOMINAL = 14.0  # slack-run droop seed (p006 crop read 18; was trimmed
# from 18 to clear the cone-pivot-post top, but the ch30 GT re-anchor retired
# that constraint: the post (now the p1 swing bracket at machine z -113..-87)
# no longer shares a z corridor with the chain plane (z -155). 14 kept
# conservatively -- every M6.8/M6.9 clearance was tuned near this droop.
# The BUILT droop is SAG below: solved off this seed so the loop closes on an
# integer number of standard-pitch links (a real chain's length is quantised;
# the sag is the underdefined member that absorbs the slack).

# --- centreline geometry (A = knob = origin, B = crank) ----------------------
BX = CRANK_CENTRE[0] - KNOB_CENTRE[0]
BY = CRANK_CENTRE[1] - KNOB_CENTRE[1]
D = math.hypot(BX, BY)  # 112.76
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
    if q2 < 0.0:
        raise ValueError(f"slack radius {rs} too small")
    q = math.sqrt(q2)
    return UX * p + NX * q, UY * p + NY * q


def _droop(rs: float) -> float:
    """Bulge of the slack arc beyond the straight -n tangent line."""
    cx, cy = _slack_centre(rs)
    return cx * _SNX + cy * _SNY + rs - _SC0


def _ccw(a_from: float, a_to: float) -> float:
    return (a_to - a_from) % (2.0 * math.pi)


def _solve_slack_radius(sag: float) -> float:
    """Slack-arc radius whose droop equals ``sag`` (droop falls with rs)."""
    lo = max(WRAP_R_A, WRAP_R_B) + D / 2.0  # safely past the q2 > 0 floor
    while _droop(lo) < sag:  # pragma: no cover - geometry sanity
        lo *= 0.9
    hi = 10000.0
    assert _droop(lo) > sag > _droop(hi)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if _droop(mid) > sag:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _loop_length(sag: float) -> float:
    """Total centreline loop length at slack droop ``sag`` (monotonically
    increasing: more droop = a longer slack run)."""
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


# --- integer-link closure -----------------------------------------------------
# A roller chain has a FIXED standard pitch and closes only on an EVEN link
# count (inner/outer must alternate back to the seam), so the loop length is
# QUANTISED: pick the even count nearest the nominal-droop loop, then solve the
# SAG so the centreline lands EXACTLY on count * pitch. The sag -- not the
# pitch -- absorbs the slack, exactly like a real chain (move an axle and the
# droop responds).
LINK_PITCH = 6.35  # ANSI #25 pitch (1/4 in), EXACT: the link parts and the
# chain-pattern spacing carry this standard pitch; closure comes from the sag.
LINK_COUNT = 2 * round(_loop_length(SAG_NOMINAL) / (2.0 * LINK_PITCH))
CENTRELINE_LEN = LINK_COUNT * LINK_PITCH

# Quantisation moves the target length by at most LINK_PITCH / 2 (~3.2 mm), so
# the solved sag stays within a few mm of the seed -- a tight bracket keeps the
# solve inside the internal-tangency feasibility window (very large droops make
# the slack arc infeasible: _slack_centre's q2 < 0).
_LO_SAG, _HI_SAG = SAG_NOMINAL - 8.0, SAG_NOMINAL + 8.0
assert _loop_length(_LO_SAG) < CENTRELINE_LEN < _loop_length(_HI_SAG)
for _ in range(80):
    _MID = 0.5 * (_LO_SAG + _HI_SAG)
    if _loop_length(_MID) < CENTRELINE_LEN:
        _LO_SAG = _MID
    else:
        _HI_SAG = _MID
SAG = 0.5 * (_LO_SAG + _HI_SAG)  # the BUILT droop (solved for LINK_COUNT).
# The count quantisation moves the target length by at most LINK_PITCH / 2
# (~3.2 mm); the slack run's length-vs-droop sensitivity is ~0.85 mm/mm here,
# so the solved sag lands within ~4 mm of the seed -- INSIDE the +-8 bracket
# and under the 14-tuned clearance envelope (a tauter chain sits higher in the
# corridor every M6.8/M6.9 clearance was tuned against; the next-larger count,
# 56 links, would need SAG 26 -- outside both the p006 photo read (18) and the
# tuned envelope, so the tauter side is the right quantisation).
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
# A real ANSI-#25-proportioned roller chain (pitch 1/4 in EXACT, see
# LINK_PITCH/LINK_COUNT above): alternating INNER links (2 inner plates + 2
# rollers) and OUTER links (2 outer plates + 2 pins), filled along the
# centreline loop by the connected-linkage chain pattern
# (build_paper_drive_assembly._insert_roller_chain). Every dimension stays
# inside a +-2.4 in-plane / +-2.1 z envelope (the retired #13 ball chain's 4.8
# bead) so the band-tuned M6.8/M6.9 clearances transfer untouched.

# Every clearance is >= 0.25 mm and nothing relies on exact tangency: the
# M6.x interference checker flags ~0.00 mm^3 slivers, so the links FLOAT as a
# multibody (disconnected bodies in a part are allowed). The z stack is sized
# so the chain STRADDLES the 2.4-wide removable sprockets (ch23 p.58-59:
# chain wider than the wheel -- paper-drive rework E6): sprocket faces +-1.2,
# inner-plate INNER faces at +-1.45 (0.25 clear per side), so the tooth tips
# pass BETWEEN the plates instead of through them.
PLATE_HEIGHT = 4.8  # obround plate height (in-plane envelope, unchanged)
PLATE_HALF_H = PLATE_HEIGHT / 2.0  # 2.4, the obround end-arc radius
PLATE_THICK = 0.8  # side-plate thickness (z)

ROLLER_DIA = 2.5  # roller/bushing outer diameter (~0.52 of plate height, #25)
ROLLER_R = ROLLER_DIA / 2.0  # 1.25
BUSH_BORE_R = 1.0  # bushing through-bore; pin floats inside (0.35 clearance)
BUSH_HALF_LEN = 1.45  # bushing spans the inner plates (z -1.45..1.45)
INNER_PLATE_HOLE_R = 1.55  # bushing OD floats inside (0.30); web 0.85

PIN_DIA = 1.3  # outer-link pin (floats in the bushing bore and plate holes)
PIN_R = PIN_DIA / 2.0  # 0.65
PIN_HALF_LEN = 3.35  # pin reach along the pin axis (flush with the outer plates)
OUTER_PLATE_HOLE_R = 0.95  # pin floats inside (0.30); web 1.45

# z stack (pin axis), symmetric about the chain mid-plane:
INNER_PLATE_Z = 1.85  # inner-plate centre (faces 1.45..2.25, sprocket 0.25 clear)
OUTER_PLATE_Z = 2.95  # outer-plate centre (faces 2.55..3.35, 0.3 gap to inner)


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
