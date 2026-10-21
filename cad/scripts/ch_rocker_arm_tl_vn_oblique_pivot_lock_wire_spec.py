"""VN-76: one continuous cut length securing one X pair of cap screws.

Frame: origin at pair midpoint on screw bearing-face plane; X joins the
screws, Z points toward cap top. Install unchanged at each Y row on each cap.
The native centreline is a representative hand-formed route, not an elastic
model or a locking-force calculation. The exterior entry legs flare within
the counterbores, then narrow before the wire channel; their elevation
separates them from the straight drilled legs. This is the 0/180 representative
route, not authority for every received six-hole head clock. Accept the actual
formed route only through real straight holes, pulling toward tightening, with
the installed whole-route clearances; never loosen or over-torque a seated head
to obtain its clock. Tuck cut ends; discard wire on opening the cartridge.
"""
from __future__ import annotations

import math

from ch_rocker_arm_tl_oblique_retention_hardware_spec import (
    WIRE_SKU as SKU, WIRE_SOURCE_URL as SOURCE_URL, WIRE_DIA,
    SCREW_HEAD_DIA_MAX, SCREW_HEAD_ECCENTRICITY_MAX, SCREW_WIRE_HEIGHT,
    SCREW_WIRE_HEIGHT_MIN, SCREW_WIRE_HEIGHT_MAX,
)
from ch_rocker_arm_tl_oblique_retention_spec import CAP_BOLT_X_OFFSETS

QUANTITY = 4
CALLOUT = '.032 STAINLESS SAFETY WIRE'
TWIST_RADIUS = 0.52
BRIDGE_TURNS = 4
OUTER_BEND_RADIUS = (
    SCREW_HEAD_DIA_MAX / 2 + SCREW_HEAD_ECCENTRICITY_MAX + WIRE_DIA / 2 + 0.35
)
ENTRY_SHOULDER_OFFSET = 0.20
ENTRY_SHOULDER_RISE = 1.00
# Leave a real approach length between the larger head loops and the twist.
# Keeping the former fixed 8 mm half-span would put the returning drilled leg
# within one wire diameter of the other strand at its bridge endpoint.
BRIDGE_HALF_LENGTH = min(abs(x) for x in CAP_BOLT_X_OFFSETS) - OUTER_BEND_RADIUS - 1.0
WIRE_AXIS_Z = SCREW_WIRE_HEIGHT


def _line(a, b):
    return (a, tuple((2*x+y)/3 for x,y in zip(a,b)),
            tuple((x+2*y)/3 for x,y in zip(a,b)), b)


def _round_path(points, trim=0.7):
    """Lines and circular-arc cubic bends; bore passages stay straight.

    A degree-elevated quadratic corner can have less centreline radius than
    the wire section. Circular-arc handles and almost-half-edge trims retain
    room for a real tube while preventing adjacent fillets from overlapping.
    """
    result = []
    previous = points[0]
    for a, b, c in zip(points, points[1:], points[2:]):
        incoming = math.dist(a, b)
        outgoing = math.dist(b, c)
        enter = tuple((bi-ai)/incoming for ai,bi in zip(a,b))
        leave = tuple((ci-bi)/outgoing for bi,ci in zip(b,c))
        turn = math.acos(max(-1.0, min(1.0, sum(u*v for u,v in zip(enter,leave)))))
        if turn < 1e-9:
            result.append(_line(previous, b))
            previous = b
            continue
        distance = min(trim, 0.49*incoming, 0.49*outgoing)
        handle = 4*distance*math.tan(turn/4)/(3*math.tan(turn/2))
        p = tuple(bi-u*distance for bi,u in zip(b,enter))
        q = tuple(bi+v*distance for bi,v in zip(b,leave))
        result.append(_line(previous, p))
        result.append((p, tuple(pi+u*handle for pi,u in zip(p,enter)),
                       tuple(qi-v*handle for qi,v in zip(q,leave)), q))
        previous = q
    result.append(_line(previous, points[-1]))
    return result


def _radial(center, radius, angle, z=0.0):
    theta = math.radians(angle)
    return (center + radius*math.cos(theta), radius*math.sin(theta), WIRE_AXIS_Z+z)


def _helix(x0, x1, phase, turns):
    """Hermite cubic helix, twelve spans per turn; no interpolating overshoot."""
    segments = []
    steps = int(turns * 12)
    omega = turns * 2 * math.pi
    for i in range(steps):
        values = []
        for j in (i, i+1):
            t = j / steps
            a = phase + omega*t
            p = (x0 + (x1-x0)*t, TWIST_RADIUS*math.cos(a),
                 WIRE_AXIS_Z + TWIST_RADIUS*math.sin(a))
            d = ((x1-x0)/steps, -TWIST_RADIUS*omega*math.sin(a)/steps,
                 TWIST_RADIUS*omega*math.cos(a)/steps)
            values.append((p,d))
        (p,d),(q,e) = values
        segments.append((p,tuple(v+w/3 for v,w in zip(p,d)),
                         tuple(v-w/3 for v,w in zip(q,e)),q))
    return segments


def _reverse(segments):
    return [tuple(reversed(segment)) for segment in reversed(segments)]


def installed_wire_segments():
    """Continuous wire, two twisted bridge strands, drilled-head loops and tail.

    Both heads use diametrically opposed radial holes 0/180. The exterior
    legs wrap above the left head and below the right head. Clocking is part
    of this representative assembly, not permission to loosen a screw.
    """
    left, right = CAP_BOLT_X_OFFSETS
    r = OUTER_BEND_RADIUS
    bridge_a = _helix(-BRIDGE_HALF_LENGTH, BRIDGE_HALF_LENGTH, 0.0, BRIDGE_TURNS)
    bridge_b = _helix(-BRIDGE_HALF_LENGTH, BRIDGE_HALF_LENGTH, math.pi, BRIDGE_TURNS)
    # A->B: upper exterior wrap, then a straight diametral passage. Bends
    # remain outside the head; there is no fictitious curved drilled hole.
    # Keep the elevated exterior leg away from the axial drilled return.
    # The flared bend's control hull stays in the counterbore; the shoulder
    # brings Y back to the bridge radius before entering the narrow channel.
    left_points = [
        bridge_a[0][0],
        (left+r+ENTRY_SHOULDER_OFFSET,TWIST_RADIUS,WIRE_AXIS_Z+ENTRY_SHOULDER_RISE),
        (left+r-0.1,1.2,WIRE_AXIS_Z+ENTRY_SHOULDER_RISE),
    ]
    left_points.extend(_radial(left,r,angle) for angle in (15,35,60,90,120,150,180))
    left_points.extend([_radial(left,r,0), bridge_b[0][0]])
    left_loop = _round_path(left_points, trim=0.6)
    # Start the outward twist after the drilled leg has cleared the head and
    # separated from its return. The larger head leaves room for a half-turn,
    # not the former full-turn tail compressed into the same access mouth.
    tail_x0 = right + r + 0.6
    tail_x1 = right + 9.0
    tail_a = _helix(tail_x0, tail_x1, math.pi/2, 0.5)
    tail_b = _helix(tail_x0, tail_x1, -math.pi/2, 0.5)
    # A goes straight through the head and socket. B is outside throughout,
    # vertically separated from A before they enter the twisted tail.
    right_a = _round_path([
        bridge_a[-1][-1], _radial(right,r,180),
        _radial(right,SCREW_HEAD_DIA_MAX/2+WIRE_DIA/2+0.3,0), tail_a[0][0],
    ], trim=0.6)
    right_b_points = [
        bridge_b[-1][-1],
        (right-r-ENTRY_SHOULDER_OFFSET,-TWIST_RADIUS,WIRE_AXIS_Z+ENTRY_SHOULDER_RISE),
        (right-r+0.1,-1.2,WIRE_AXIS_Z+ENTRY_SHOULDER_RISE),
    ]
    right_b_points.extend(_radial(right,r,angle,-TWIST_RADIUS)
                          for angle in (195,215,240,270,300,330,345))
    right_b_points.append(tail_b[0][0])
    right_b = _round_path(right_b_points, trim=0.6)
    # Turn both cut ends inward in the full-width outward access mouth.
    hooks = []
    for tail, side in ((tail_a, 1), (tail_b, -1)):
        end = tail[-1][-1]
        hooks.append(_round_path([end, (end[0],side*1.4,end[2]),
                                  (end[0]-1.5,side*1.4,end[2])], trim=0.6))
    path_a = bridge_a + right_a + tail_a + hooks[0]
    path_b = bridge_b + right_b + tail_b + hooks[1]
    return tuple(_reverse(path_a) + left_loop + path_b)


def swept_wire_z_bounds(segments=None, *, hardware_limits=False):
    """Conservative full-tube Z bounds above the actual screw head seat.

    The cubic control hull plus the round section bounds every bend, twist
    and tucked end. Hardware limits add independent NAS head-height and
    from-top hole-location extrema; the installer forms to each actual hole.
    These are not a fictitious wire roof above the screw head.
    """
    if segments is None:
        segments = installed_wire_segments()
    heights = [point[2] for segment in segments for point in segment]
    low = min(heights) - WIRE_DIA / 2
    high = max(heights) + WIRE_DIA / 2
    if hardware_limits:
        low += SCREW_WIRE_HEIGHT_MIN - WIRE_AXIS_Z
        high += SCREW_WIRE_HEIGHT_MAX - WIRE_AXIS_Z
    return low, high


# Nominal native solid bounds and independent purchased-hardware-limit bounds.
WIRE_Z_MIN, WIRE_Z_MAX = swept_wire_z_bounds()
WIRE_Z_WORST_MIN, WIRE_Z_WORST_MAX = swept_wire_z_bounds(hardware_limits=True)
