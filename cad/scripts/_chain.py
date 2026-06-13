"""Drive-chain centreline geometry (book ch. 23/30).

The bead chain loops the two CHAIN-WRAPPED removable gears (crank shaft
T12 -> knob shaft T24; ch. 23: the chain rides the removables' m2 teeth --
swapping them is what changes the platen ratio). Every chain-side ch30
plate (p002/p005/p006) shows it: a taut run on the pinion-bar side and a
visibly drooping slack run on the other.

Pure math only -- shared by the chain-bead part script and the output
assembly's chain-component-pattern path sketch (the chain is a SolidWorks
chain component pattern of chain-bead spheres along that path; the M6.8
rigid-band stand-in part is retired).

Geometry (local frame: knob wrap centre at the origin, machine xy
pre-mirror; crank centre from build_drive_train_assembly X_CRANK / Y_DRIVE
minus build_output_assembly KNOB_SHAFT_XY): two UNEQUAL wrap arcs whose
centreline floats clear OUTSIDE the gear tooth tips (a real chain wraps at
the teeth; rigid model beads there would intersect them), the common
external tangent taut line on the +n side (the pinion-bar side), and a
slack arc sagging SAG below the straight external tangent on the -n side,
tangent-continuous at all four junctions (internal tangency:
|C - A| = R_slack - WRAP_R_A, |C - B| = R_slack - WRAP_R_B; R_slack is
solved numerically for the SAG droop).
"""

from __future__ import annotations

import math

# Chain-wheel centres, machine xy pre-mirror.
KNOB_CENTRE = (65.0, 241.78)  # build_output_assembly KNOB_SHAFT_XY (ch30
# rest state: latch C2C 66.05 from the stud, y clamped under the pinion bar)
CRANK_CENTRE = (118.0, 126.8)  # build_drive_train_assembly X_CRANK, Y_DRIVE

TIP_R_T24 = 26.0  # mounted removables, module 2: tip r = (T + 2) * 2 / 2
TIP_R_T12 = 14.0
TIP_AIR = 0.41  # chain inner reach floats this clear of the tooth tips
REACH = 2.5  # centreline-to-tip budget past TIP_AIR: the retired flat band
# was 5 wide (centreline +- 2.5) and every M6.8/M6.9 checker-arbitrated
# clearance was tuned against that reach; the bead radius (2.4) stays
# inside it, so the tuning transfers with margin
WRAP_R_A = TIP_R_T24 + TIP_AIR + REACH  # 28.91 (knob T24)
WRAP_R_B = TIP_R_T12 + TIP_AIR + REACH  # 16.91 (crank T12)
SAG = 14.0  # slack-run droop below the straight tangent (p006 crop read 18;
# trimmed so the chain's OUTER reach (radius SLACK_R + REACH about C -- it
# dips REACH * R / sqrt(R^2 - dx^2) below the centreline, ~3.7 near the
# window edge, NOT a flat 2.5) clears the cone-pivot-post top (y 135.8,
# rotated-block box to pre-mirror x 77.7) by 0.95: SAG 18 clipped the post
# corner 10.6 mm^3, SAG 15 left a 0.17 sliver the checker reports as 0.00)

# --- centreline geometry (A = knob = origin, B = crank) ----------------------
BX = CRANK_CENTRE[0] - KNOB_CENTRE[0]
BY = CRANK_CENTRE[1] - KNOB_CENTRE[1]
D = math.hypot(BX, BY)  # 126.61
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


# Solve droop(SLACK_R) = SAG (droop decreases monotonically with rs).
_LO = max(WRAP_R_A, WRAP_R_B) + D / 2.0  # safely past the q2 > 0 floor
while _droop(_LO) < SAG:  # pragma: no cover - geometry sanity
    _LO *= 0.9
_HI = 10000.0
assert _droop(_LO) > SAG > _droop(_HI)
for _ in range(80):
    _MID = 0.5 * (_LO + _HI)
    if _droop(_MID) > SAG:
        _LO = _MID
    else:
        _HI = _MID
SLACK_R = 0.5 * (_LO + _HI)
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


def _ccw(a_from: float, a_to: float) -> float:
    return (a_to - a_from) % (2.0 * math.pi)


SPAN_A = _ccw(_ANG_N, _ANG_GA)
SPAN_SLACK = _ccw(_ANG_GA, _ANG_GB)
SPAN_B = _ccw(_ANG_GB, _ANG_N)
assert abs(SPAN_A + SPAN_SLACK + SPAN_B - 2.0 * math.pi) < 1e-9

CENTRELINE_LEN = (
    WRAP_R_A * SPAN_A + WRAP_R_B * SPAN_B + SLACK_R * SPAN_SLACK + TAUT_LEN
)

# --- bead chain ---------------------------------------------------------------
BEAD_DIA = 4.8  # ball-chain trade size #13: ball O0.1875 in (4.76), the
# largest stock size -- matching the chunky beads the ch30 plates show;
# rounded to the model grid and kept under REACH (2.5) so the band-tuned
# clearances hold. The connecting wire is not modeled (flexible element).
BEAD_R = BEAD_DIA / 2.0
BEAD_PITCH_NOMINAL = 6.35  # #13 ball chain pitch (1/4 in)
BEAD_COUNT = round(CENTRELINE_LEN / BEAD_PITCH_NOMINAL)
BEAD_PITCH = CENTRELINE_LEN / BEAD_COUNT  # exact closure: count * pitch = loop


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


def centreline_distance(
    x: float, y: float, dx: float = 0.0, dy: float = 0.0, mirror_x: bool = False
) -> float:
    """Distance from a point to the centreline loop, in the same
    (dx, dy, mirror_x) frame as :func:`loop_segments`.

    The wrap/slack arcs are treated as FULL circles -- ample for the
    bead-on-path gate: a mirrored, mis-planed or unmirrored loop misses
    by tens of millimetres, while a bead ON the path sits within solver
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
