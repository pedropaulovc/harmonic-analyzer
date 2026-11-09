r"""Crank-pin keeper chain (MHA-DT-VN-65), pure data.

The ch11 p.14 photographs show the crank arm's anchor screw and the brass
ring on the taper pin's head; the chain that tied the removable pin to the arm
is lost. Owner ruling 2026-11-08 (#2144 item 9.2) reconstructs it as one open
strand of purchased jack chain:

* McMaster-Carr 3603T354, #18 solid brass single jack chain, cut to
  LINK_COUNT links (``_mcmaster_3603t354``).
* One end: the end link's eye lies flat on the arm's outboard face and the
  MHA-DT-VN-70 #2-56 binding-head screw (``dt_vn_keeper_chain_screw_spec``)
  clamps it through that eye into the arm's tapped hole.
* Other end: the keeper ring (MHA-DT-27) is opened, threaded through the pin's
  cross-hole and the far link's far eye, and closed with pliers.

Link geometry (D1). Each link is a figure-8: two round eyes of inside
diameter EYE_ID, at 90 deg to each other, EYE_CENTRE_SPACING apart, wire
WIRE_DIA. Taut, two interlocked perpendicular eyes sit one inside diameter
apart, so the inside length (the chain's pitch, link centre to link centre)
is EYE_CENTRE_SPACING + EYE_ID. A link is modelled as two tori of mean
radius EYE_MEAN_R joined by a straight Ø WIRE_DIA neck along the link axis.

EYE_ID UNCERTAINTY. McMaster publishes no eye inside diameter. The modelled
.115 in is the Peco Fasteners #18 single-jack sheet's minimum eye; the
published range runs from .110 in (Eastools inside width, EYE_ID_MIN) to
.1535 in (McMaster's reference STEP round eye, EYE_ID_MAX). GAUGE A SAMPLE
before committing the purchase (a 10 ft length is about $7.30): every fit
below is asserted at the limit that governs it, but the head only clamps
eyes up to WASHER_EYE_ID (.134 in); a gauged eye over that needs a #2
washer under the screw head (not modelled).

Frame ("crank frame"): machine axes, origin on the crank axis at the arm's
front (outboard) face, machine z -183. The arm fills z 0..ARM_THICKNESS and
the hub barrel ARM_THICKNESS..HUB_LENGTH; outboard is -z. The chain part is
authored in this frame relative to CHAIN_PART_ORIGIN (link 0's centre) and
placed with an identity rotation.

Rest pose (arm hanging down, gravity -Y):

* Link 0 (D4): its screw eye lies flat on the arm's outboard face round the
  screw axis, wire centre at z = -(WIRE_DIA / 2 + ANCHOR_AIR); its axis points
  -X, and its standing eye hangs in the crank XZ plane past the arm's -X edge.
* The strand (D5) drapes outboard of the arm's -X edge, down, round to the
  pin's plane behind the arm, and up to the ring: the last link hangs plumb
  from the ring's outboard wire, its far eye round that wire.
* The ring keeps owner ruling A1's pose: flat in the pin's axial plane,
  hanging outboard (-X) past the pin's big end.

The strand pulls straight when the taper pin is drawn out of the hub
(PIN_WITHDRAWAL): LINK_COUNT is the fewest links that reach, plus
STRAND_SLACK_PITCHES.
"""

from __future__ import annotations

import functools
import math
from typing import NamedTuple

import _mcmaster_3603t354 as _catalogue
import dt_vn_keeper_chain_screw_spec as screw
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from dt_crank_arm_spec import ANCHOR_EDGE_DIST, ANCHOR_EDGE_DIST_MAX, ANCHOR_EDGE_DIST_MIN
from dt_crank_arm_spec import ANCHOR_SCREW_X, ANCHOR_SCREW_Y, ARM_C2C
from dt_crank_arm_spec import ARM_THICKNESS, HALF_WIDTH
from dt_crank_hub_geometry import (
    ARM_STOCK_THICKNESS_MAX,
    HUB_BARREL_DIA,
    HUB_LENGTH,
    SERVICE_PIN_STATION,
)
from dt_crank_hub_geometry import UNIT as HUB_UNIT
from dt_crank_hub_spec import DRAWING_PRECISION_BY_NAME as HUB_PRECISION
from dt_crank_pin_ring_spec import ARC_SAGITTA, MEAN_R, PIN_BAND, PIN_DIA_AT_HOLE_MAX
from dt_crank_pin_ring_spec import PIN_DIA_AT_HOLE, PIN_PROUD
from dt_crank_pin_ring_spec import RING_CENTRE_X, RING_FAR_X, RING_ID_MAX, RING_ID_MIN
from dt_crank_pin_ring_spec import WIRE_DIA as RING_WIRE_DIA
from dt_crank_pin_spec import BIG_END_DIA, PIN_LENGTH, RING_HOLE_DIA
from dt_crank_pin_spec import RING_HOLE_X, SMALL_END_DIA
from dt_crank_pin_spec import UNIT as PIN_UNIT


Vec = tuple[float, float, float]

MM_PER_IN = 25.4

# --- purchased-part nominals (D1) ----------------------------------------------
CHAIN_SKU = _catalogue.PART_NO
WIRE_DIA = _catalogue.WIRE_DIA
WIRE_R = WIRE_DIA / 2.0
INSIDE_LENGTH = _catalogue.INSIDE_LENGTH
EYE_ID = _catalogue.EYE_ID
EYE_ID_MIN = _catalogue.EYE_ID_MIN
EYE_ID_MAX = _catalogue.EYE_ID_MAX
EYE_CENTRE_SPACING = _catalogue.eye_centre_spacing(EYE_ID)
EYE_MEAN_R = (EYE_ID + WIRE_DIA) / 2.0
# The neck joins the two eyes' wire centrelines along the link axis.
NECK_LEN = EYE_CENTRE_SPACING - 2.0 * EYE_MEAN_R
if NECK_LEN <= 0.0:
    raise AssertionError(f"the modelled link's eyes overlap: neck {NECK_LEN:.3f}")
# The one catalogue size the purchased-part sheet imports: the 2-D PDF's
# wire, on a blanked reference circle in the neck's section (see the builder).
CATALOGUE_WIRE_DIMENSION = "CatalogueWireDiameter"
CATALOGUE_REFERENCE = "CatalogueReference"
DRAWING_DIMENSIONS = {CATALOGUE_REFERENCE: {CATALOGUE_WIRE_DIMENSION}}
DRAWING_REFERENCE_PRECISION = {CATALOGUE_WIRE_DIMENSION: 3}  # .047 in

AIR = 0.02  # minimum air the solve leaves between parts that must not touch
ANCHOR_AIR = 0.02  # end-link wire to arm face, and screw head to wire

# --- pose inputs from the part specs (crank frame) ----------------------------
HUB_R = HUB_BARREL_DIA / 2.0
ARM_Z = (0.0, ARM_THICKNESS)
HUB_Z = (ARM_THICKNESS, HUB_LENGTH)
PIN_Z = SERVICE_PIN_STATION
# The hub prints the pin's station from its faced outboard end, flush with the
# arm's outboard face (ARM_Z[0]), at ServicePinStation's places in the hub
# sheet's unit; its seat length is a fit-up reference turned to suit the arm,
# so the arm's inboard face (ARM_Z[1]) is wherever the stock's thickness puts
# it. At the station band's arm-side limit in the thickest stock the mill
# ships, the pin, and the ring hanging from it, sit that much nearer the arm.
PIN_Z_BAND = printed_band_mm(HUB_PRECISION["ServicePinStation"], unit=HUB_UNIT) + (
    ARM_STOCK_THICKNESS_MAX - ARM_THICKNESS
)
PIN_Z_ARMWARD = PIN_Z - PIN_Z_BAND
PIN_X0 = -HUB_R - PIN_PROUD  # the pin's big end
RING_X = PIN_X0 + RING_HOLE_X  # the ring's through leg and plane

# --- the anchor (D2, D4) --------------------------------------------------------
SCREW_XY = (-ANCHOR_SCREW_Y, -ANCHOR_SCREW_X)
# The arm's -X edge sits ANCHOR_EDGE_DIST from the screw axis (its print's
# nominal); the arm spec owns that distance and its printed band.
if abs(SCREW_XY[0] - ANCHOR_EDGE_DIST - (-HALF_WIDTH)) > 1e-9:
    raise AssertionError("the anchor screw's edge distance disagrees with the arm's width")
_EYE_Z = -(WIRE_R + ANCHOR_AIR)  # the end link's wire centre, flat on the face
# The screw's under-head plane, clamping the end link's wire to the face.
SCREW_HEAD_Z = -(WIRE_DIA + ANCHOR_AIR)
ANCHOR_EYE_CENTRE: Vec = (SCREW_XY[0], SCREW_XY[1], _EYE_Z)

EYE_PASS_AIR = 0.05  # least radial air round a wire threading an eye
# Shank: the screw passes the smallest published eye.
SHANK_AIR_MIN = (EYE_ID_MIN - screw.SHANK_DIA) / 2.0
if SHANK_AIR_MIN < EYE_PASS_AIR:
    raise AssertionError(
        f"the {screw.THREAD} shank (Ø{screw.SHANK_DIA:.3f}) leaves {SHANK_AIR_MIN:.3f} "
        f"radial air in the smallest published eye (Ø{EYE_ID_MIN:.3f}), under {EYE_PASS_AIR}"
    )


def head_cover(eye_id: float) -> float:
    """How far the least head reaches past the eye wire's centreline: >= 0
    clamps the wire, not just its inner edge."""
    return screw.HEAD_DIA_MIN / 2.0 - (eye_id + WIRE_DIA) / 2.0


HEAD_COVER = head_cover(EYE_ID)
HEAD_COVER_MIN_EYE = head_cover(EYE_ID_MIN)
for _eye, _cover in ((EYE_ID, HEAD_COVER), (EYE_ID_MIN, HEAD_COVER_MIN_EYE)):
    if _cover < 0.0:
        raise AssertionError(
            f"the Ø{screw.HEAD_DIA_MIN:.3f} head stops {-_cover:.3f} short of the "
            f"Ø{_eye:.3f} eye's wire centreline: it would not clamp the end link"
        )
# At EYE_ID_MAX the head does not reach the centreline (HEAD_COVER_MAX_EYE < 0):
# the largest published eye needs the #2 washer the docstring names. A gauged
# eye over WASHER_EYE_ID (the listed head's reach) takes it.
HEAD_COVER_MAX_EYE = head_cover(EYE_ID_MAX)
WASHER_EYE_ID = screw.HEAD_DIA - WIRE_DIA

# Ring (D5): its wire threads the far link's eye at the smallest published eye.
RING_EYE_AIR_MIN = (EYE_ID_MIN - RING_WIRE_DIA) / 2.0
if RING_EYE_AIR_MIN < EYE_PASS_AIR:
    raise AssertionError(
        f"the Ø{RING_WIRE_DIA:.3f} ring wire leaves {RING_EYE_AIR_MIN:.3f} radial air "
        f"in the smallest published eye (Ø{EYE_ID_MIN:.3f}), under {EYE_PASS_AIR}"
    )


def standing_eye_edge_air(eye_id: float, edge_dist: float, samples: int = 3600) -> float:
    """Air between the end link's standing eye and the arm, the -X edge
    ``edge_dist`` from the screw axis.

    The screw eye is centred on the screw axis; the standing eye's centre is
    one eye spacing out along -X, its wire centreline (radius (ID + w) / 2) in
    the crank XZ plane at the flat eye's height. The arm, seen in that plane,
    is the quadrant x >= edge, 0 <= z <= ARM_THICKNESS.
    """
    spacing = _catalogue.eye_centre_spacing(eye_id)
    mean_r = (eye_id + WIRE_DIA) / 2.0
    edge = -edge_dist  # screw-relative
    least = math.inf
    for k in range(samples):
        t = 2.0 * math.pi * k / samples
        x = -spacing + mean_r * math.cos(t)
        z = _EYE_Z + mean_r * math.sin(t)
        dx = max(0.0, edge - x)
        dz = max(0.0, ARM_Z[0] - z, z - ARM_Z[1])
        least = min(least, math.hypot(dx, dz))
    return least - WIRE_R


# The standing eye clears the arm at the modelled and the largest published
# eye, with the edge at its farthest printed distance from the screw.
STANDING_EYE_EDGE_AIR = standing_eye_edge_air(EYE_ID, ANCHOR_EDGE_DIST_MAX)
STANDING_EYE_EDGE_AIR_MAX_EYE = standing_eye_edge_air(EYE_ID_MAX, ANCHOR_EDGE_DIST_MAX)
for _eye, _air in ((EYE_ID, STANDING_EYE_EDGE_AIR), (EYE_ID_MAX, STANDING_EYE_EDGE_AIR_MAX_EYE)):
    if _air < 0.0:
        raise AssertionError(
            f"the end link's standing eye (Ø{_eye:.3f}) cuts {-_air:.3f} into the arm "
            f"with the -X edge {ANCHOR_EDGE_DIST_MAX:.3f} from the screw"
        )
# At EYE_ID_MAX the flat screw eye's outside (ID / 2 + w) overhangs the arm's
# -X edge by this much at the edge's nearest printed distance: harmless, the
# head still bears on the wire over the face.
SCREW_EYE_OVERHANG_MAX_EYE = EYE_ID_MAX / 2.0 + WIRE_DIA - ANCHOR_EDGE_DIST_MIN

# The ring swings freely about the cross-hole axis (machine z). Owner ruling
# 2026-10-15 A1: it is modelled flat in the pin's axial plane, hanging
# outboard along RING_HANG past the pin's big end and clear of the arm's -X
# edge; hung toward -Y along the arm (the Ø12 ring, option A) its low arc
# dipped 0.9 into the arm's inboard face. The far link's eye hangs on its
# outboard wire, in the pin axis's z plane. In service the arm is the ring's
# swing stop (RING_STOP_SWING_DEG); what holds at the printed limits is
# asserted with ring_arm_air below.
RING_HANG: Vec = (-1.0, 0.0, 0.0)
RING_CENTRE: Vec = (RING_X - RING_CENTRE_X, 0.0, PIN_Z)
RING_OUT_X = RING_X - RING_FAR_X  # the wire centreline's outboard extreme
RING_PLANE_Z = PIN_Z

# In the A1 plane the wire leaves the cross-hole along the pin's straight top
# and bottom lines, so the hole's edges, not its wall, are the tight points:
# the outboard edge sits inside the arc, the hub-side edge outside it, and the
# crown rides ARC_SAGITTA / 2 hub-side of the axis.
_HOLE_R = RING_HOLE_DIA / 2.0
_PIN_R_AT_HOLE = PIN_DIA_AT_HOLE / 2.0
A1_HOLE_AIR = (
    min(
        MEAN_R - math.hypot(RING_CENTRE_X - _HOLE_R, _PIN_R_AT_HOLE),
        math.hypot(RING_CENTRE_X + _HOLE_R, _PIN_R_AT_HOLE) - MEAN_R,
        _HOLE_R - ARC_SAGITTA / 2.0,
    )
    - RING_WIRE_DIA / 2.0
)
if A1_HOLE_AIR <= 0.0:
    raise AssertionError(
        f"the nominal keeper ring posed in the pin's axial plane leaves "
        f"{A1_HOLE_AIR:.3f} air at the cross-hole's edges"
    )

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


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a: Vec) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Vec) -> Vec:
    return _scale(a, 1.0 / _norm(a))


def _dist(a: Vec, b: Vec) -> float:
    return _norm(_sub(a, b))


def _rotate(v: Vec, axis: Vec, angle: float) -> Vec:
    """``v`` turned ``angle`` about unit ``axis`` (Rodrigues)."""
    c, s = math.cos(angle), math.sin(angle)
    return _add(
        _add(_scale(v, c), _scale(_cross(axis, v), s)),
        _scale(axis, _dot(axis, v) * (1.0 - c)),
    )


# Owner ruling 2026-10-15 A1, at the printed limits: the smallest printed ring
# on the pin's fattest printed section pinches the hole's outboard edge in the
# modelled plane (-0.057 centred in the hole, -0.010 at its best slide), so it
# sits swung about the hole axis, zero air from ~RING_REST_SWING_DEG off the
# plane. Its threading air (dt_crank_pin_ring_spec.HOLE_AIR_WORST) is in the
# hole's own section and holds at every swing.
RING_REST_SWING_DEG = 25.0
RING_ARM_AIR = 0.1  # least air between the modelled (nominal, A1) ring and the arm


def _arm_gap(p: Vec) -> float:
    """Distance from p to the arm: the R HALF_WIDTH stadium from the crank
    axis down to the handle pivot, z 0..ARM_THICKNESS (0 inside)."""
    x, y, z = p
    radial = max(0.0, math.hypot(x, y - min(0.0, max(-ARM_C2C, y))) - HALF_WIDTH)
    axial = max(0.0, ARM_Z[0] - z, z - ARM_Z[1])
    return math.hypot(radial, axial)


def ring_arm_air(
    swing_deg: float,
    mean_r: float,
    crown: float,
    hole_x: float,
    pin_z: float,
    samples: int = 360,
) -> float:
    """Air between a keeper ring's wire and the arm.

    The ring's plane holds the hole axis, swung ``swing_deg`` from RING_HANG
    toward -Y; its wire centreline (radius ``mean_r``) crowns ``crown`` hub-side
    of a hole at machine x ``hole_x`` in a pin whose axis is at machine z
    ``pin_z``.
    """
    a = math.radians(swing_deg)
    hang = (RING_HANG[0] * math.cos(a), -math.sin(a), 0.0)
    centre = _add((hole_x, 0.0, pin_z), _scale(hang, mean_r - crown))
    return (
        min(
            _arm_gap(
                _add(
                    centre,
                    _add(
                        _scale(hang, mean_r * math.cos(2.0 * math.pi * k / samples)),
                        (0.0, 0.0, mean_r * math.sin(2.0 * math.pi * k / samples)),
                    ),
                )
            )
            for k in range(samples)
        )
        - RING_WIRE_DIA / 2.0
    )


# The modelled ring: nominal, in the A1 plane, at the nominal pin station.
RING_ARM_AIR_NOMINAL = ring_arm_air(0.0, MEAN_R, ARC_SAGITTA / 2.0, RING_X, PIN_Z)
if RING_ARM_AIR_NOMINAL < RING_ARM_AIR:
    raise AssertionError(
        f"the modelled keeper ring comes within {RING_ARM_AIR_NOMINAL:.3f} of the "
        f"crank arm, under {RING_ARM_AIR}"
    )

# The arm is the ring's swing stop, not a clearance it keeps. With the arm
# hanging down, the nominal ring swings under its own weight toward -Y until
# its low arc lands on the arm's -X edge, RING_STOP_SWING_DEG off the A1
# plane and short of plumb; as the crank turns it falls onto the arm's other
# side. It touches the arm in service at every printing, so the printed limits
# must keep that contact harmless, not absent:
# * The pin is reamed into the hub, which is pressed and pinned into the arm:
#   the crank carries ring and arm together, only the ring's own swing moves
#   against the arm, and the chain hangs from the ring's far (outboard) wire.
# * Withdrawal: no point of any printed ring reaches x = 0 (RING_REACH_X_MAX,
#   the oversize hole's hub-side wall at its station's hub-side limit). The
#   arm is symmetric about x = 0, so wherever the ring meets it the arm's
#   outward normal points -X or along its face: drawing the pin out (-X) lifts
#   or slides the ring off the arm, never into it.
# * No clamp: at the adverse printed corner every ring the title block accepts
#   has a pose clear of the arm (ring_clear_pose_air), so the arm is a
#   one-sided stop the ring can always leave and the pin seats with the ring
#   held clear. The corner: the pin at ServicePinStation's arm-side limit in
#   the thickest arm stock
#   (PIN_Z_ARMWARD), the hole at its station's hub-side limit, the pin's
#   fattest printed section through it, and the hole drilled to size (the
#   least room to slide in). The arm's hub end cannot grow past the
#   as-supplied bar's half-width. Crowned against the hole's hub-side wall
#   there, the worst crown, the largest .43-ID ring still clears the arm in
#   the A1 plane; slid outboard as far as the hole's edges let it, it clears
#   more.


def _ring_stop_swing() -> float:
    """Swing toward -Y at which the modelled ring meets the arm."""
    clear, plumb = 0.0, 90.0
    for _ in range(30):
        mid = (clear + plumb) / 2.0
        if ring_arm_air(mid, MEAN_R, ARC_SAGITTA / 2.0, RING_X, PIN_Z) > 0.0:
            clear = mid
        else:
            plumb = mid
    return clear


if ring_arm_air(90.0, MEAN_R, ARC_SAGITTA / 2.0, RING_X, PIN_Z) >= 0.0:
    raise AssertionError(
        "the nominal keeper ring hangs plumb clear of the crank arm: the arm is "
        "no longer its rest, so the contact case below no longer covers it"
    )
RING_STOP_SWING_DEG = _ring_stop_swing()

_HOLE_R_MAX = (RING_HOLE_DIA + drilled_oversize_mm(unit=PIN_UNIT)) / 2.0
_HOLE_X_HUBWARD = RING_X + PIN_BAND
RING_REACH_X_MAX = _HOLE_X_HUBWARD + _HOLE_R_MAX
if RING_REACH_X_MAX >= 0.0:
    raise AssertionError(
        f"a printed keeper ring reaches x = {RING_REACH_X_MAX:.3f}, past the arm's "
        "mid-plane: drawing the pin out could drive it into the arm"
    )

_PIN_R_AT_HOLE_MAX = PIN_DIA_AT_HOLE_MAX / 2.0


def a1_crown_min(mean_r: float, pin_r: float) -> float:
    """Least crown at which a ring of wire-centreline radius ``mean_r`` in the
    A1 plane keeps a drilled-to-size hole's outboard edges, on a pin section of
    radius ``pin_r``, a wire radius inside its arc (A1_HOLE_AIR's edge term at
    zero air)."""
    return mean_r - _HOLE_R - math.sqrt((mean_r - RING_WIRE_DIA / 2.0) ** 2 - pin_r**2)


def ring_clear_pose_air(mean_r: float) -> float:
    """Arm air in one pose a printed ring of radius ``mean_r`` can take at the
    adverse corner: a witness, other poses may clear more.

    Where the hole admits the ring in the A1 plane, that plane with its crown
    slid outboard to a1_crown_min. Otherwise (the smallest rings, which pinch
    there) RING_REST_SWING_DEG either way, crowned against the oversize hole's
    hub-side wall, the worst crown.
    """
    crown = a1_crown_min(mean_r, _PIN_R_AT_HOLE_MAX)
    if crown <= _HOLE_R - RING_WIRE_DIA / 2.0:
        return ring_arm_air(0.0, mean_r, crown, _HOLE_X_HUBWARD, PIN_Z_ARMWARD)
    hub_wall = _HOLE_R_MAX - RING_WIRE_DIA / 2.0
    return min(
        ring_arm_air(swing, mean_r, hub_wall, _HOLE_X_HUBWARD, PIN_Z_ARMWARD)
        for swing in (-RING_REST_SWING_DEG, RING_REST_SWING_DEG)
    )


_RING_R_MIN = (RING_ID_MIN + RING_WIRE_DIA) / 2.0
_RING_R_MAX = (RING_ID_MAX + RING_WIRE_DIA) / 2.0
RING_FREE_AIR_WORST = min(
    ring_clear_pose_air(_RING_R_MIN + (_RING_R_MAX - _RING_R_MIN) * k / 32.0)
    for k in range(33)
)
if RING_FREE_AIR_WORST < 0.0:
    raise AssertionError(
        f"a printed keeper ring at the adverse corner finds no pose clear of the "
        f"crank arm ({RING_FREE_AIR_WORST:.3f}): the arm would clamp it"
    )


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
                # Exactly the knot, not its float reconstruction: the walk
                # starts on the standing eye's centre.
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


def _crossing(curve: list[Vec], seg: int, centre: Vec, chord: float) -> tuple[Vec, int] | None:
    """The first point along the polyline, from segment ``seg`` on, ``chord``
    from ``centre``, and its segment; None when the polyline ends first."""
    while seg < len(curve) - 1:
        a, b = curve[seg], curve[seg + 1]
        if _dist(centre, b) >= chord:
            # First crossing of the chord sphere on segment a -> b.
            d = _sub(b, a)
            f = _sub(a, centre)
            qa, qb, qc = _dot(d, d), 2.0 * _dot(f, d), _dot(f, f) - chord**2
            t = (-qb + math.sqrt(max(0.0, qb * qb - 4.0 * qa * qc))) / (2.0 * qa)
            return _add(a, _scale(d, t)), seg
        seg += 1
    return None


# --- the strand's ends ----------------------------------------------------------
_X: Vec = (1.0, 0.0, 0.0)
_Y: Vec = (0.0, 1.0, 0.0)
_Z: Vec = (0.0, 0.0, 1.0)
# Link 0 (D4): screw eye on the screw axis, axis -X, standing eye in XZ.
STANDING_EYE_CENTRE: Vec = _sub(ANCHOR_EYE_CENTRE, _scale(_X, EYE_CENTRE_SPACING))
# The far link's far eye hangs on the ring's outboard wire, which runs along
# z there: the eye's inside edge bears up on the wire with AIR.
RING_WIRE_POINT: Vec = (RING_OUT_X, 0.0, RING_PLANE_Z)
FAR_EYE_CENTRE: Vec = _sub(
    RING_WIRE_POINT, _scale(_Y, EYE_ID / 2.0 - RING_WIRE_DIA / 2.0 - AIR)
)

STRAND_SLACK_PITCHES = 2


def _reach(start: Vec, end: Vec) -> float:
    """Shortest strand from ``start`` to ``end`` once the pin is drawn out.

    Straight to ``end`` moved out with the pin when that line keeps the
    arm's -X edge; otherwise straight to the arm's front -X corner and on,
    minimised over the height where it rounds the corner.
    """
    moved = _add(end, (-PIN_WITHDRAWAL, 0.0, 0.0))
    corner_x = -(HALF_WIDTH + WIRE_R)
    if max(start[0], moved[0]) <= corner_x:
        return _dist(start, moved)  # x is linear along the line: it never meets the arm
    return min(
        _dist(start, (corner_x, y, -WIRE_R)) + _dist((corner_x, y, -WIRE_R), moved)
        for y in (start[1] + 0.25 * k for k in range(-200, 200))
    )


# Interlock (D1). A link's near eye hooks the previous link's far eye. The
# pull on it (its axis) seats its wire on the far eye's wire at the far-eye
# point the pull leans toward; its own plane is square to the far eye's wire
# there and holds the pull, and its wire passes round that wire with AIR. So
# two taut, straight, perpendicular eyes sit one inside diameter (less AIR)
# apart, and each further link adds PITCH.
_HOOK = EYE_MEAN_R - WIRE_DIA - AIR  # near-eye centre back to the contact point
PITCH = EYE_MEAN_R + _HOOK + EYE_CENTRE_SPACING  # INSIDE_LENGTH - AIR

# The strand runs from link 0's standing eye to the far link's far eye.
REACH = _reach(STANDING_EYE_CENTRE, FAR_EYE_CENTRE)
REACH_LINKS = 1 + math.ceil(REACH / PITCH)
LINK_COUNT = REACH_LINKS + STRAND_SLACK_PITCHES
# Withdrawn and pulled straight, the strand's spare length.
STRAND_LENGTH = (LINK_COUNT - 1) * PITCH
SLACK = STRAND_LENGTH - REACH

# The drape: outboard of the arm's -X edge, past the end link's standing eye,
# then round to the pin's plane, then up to the ring.
SIDE_X = -(HALF_WIDTH + 2.0 * (EYE_MEAN_R + WIRE_R) + 2.0)
# The far link arrives from below: its near eye about one eye spacing under
# its far eye.
_LAST_NEAR: Vec = _sub(FAR_EYE_CENTRE, _scale(_Y, EYE_CENTRE_SPACING))


def _curve(low_y: float) -> list[Vec]:
    return _catmull_rom(
        [
            _add(STANDING_EYE_CENTRE, _scale(_X, EYE_ID)),
            STANDING_EYE_CENTRE,
            (SIDE_X, low_y, _EYE_Z),
            (SIDE_X, low_y, RING_PLANE_Z),
            _LAST_NEAR,
            FAR_EYE_CENTRE,
            _add(FAR_EYE_CENTRE, _scale(_Y, EYE_CENTRE_SPACING)),
        ]
    )


class Link(NamedTuple):
    """One link: centre, unit axis (near eye -> far eye), and the unit
    normals of its near and far eyes' planes."""

    centre: Vec
    axis: Vec
    near_normal: Vec
    far_normal: Vec


def near_eye(link: Link) -> Vec:
    return _sub(link.centre, _scale(link.axis, EYE_CENTRE_SPACING / 2.0))


def far_eye(link: Link) -> Vec:
    return _add(link.centre, _scale(link.axis, EYE_CENTRE_SPACING / 2.0))


# Link 0 (D4): screw eye flat round the screw (normal z), axis -X, standing
# eye in the crank XZ plane (normal y).
_LINK_0 = Link(_sub(ANCHOR_EYE_CENTRE, _scale(_X, EYE_CENTRE_SPACING / 2.0)), _scale(_X, -1.0), _Z, _Y)


def _hang(prev: Link, pull: Vec, twist: float) -> Link:
    """The link hooked on ``prev``'s far eye and pulled along unit ``pull``,
    its near eye turned ``twist`` about its axis from square to the far eye's
    wire (the joint's play)."""
    normal = prev.far_normal
    lean = _sub(pull, _scale(normal, _dot(pull, normal)))
    toward = _unit(lean) if _norm(lean) > 1e-9 else prev.axis
    contact = _add(far_eye(prev), _scale(toward, EYE_MEAN_R))
    # The pull is square to the far eye's wire at the contact, so it is the
    # link's axis, and that wire's run is the near eye's normal.
    near_normal = _rotate(_unit(_cross(normal, toward)), pull, twist)
    centre = _add(contact, _scale(pull, _HOOK + EYE_CENTRE_SPACING / 2.0))
    return Link(centre, pull, near_normal, _unit(_cross(pull, near_normal)))


def _basis(d: Vec) -> tuple[Vec, Vec]:
    """Two unit vectors square to unit ``d`` and to each other."""
    seed = _X if abs(d[0]) < 0.9 else _Y
    e1 = _unit(_cross(d, seed))
    return e1, _cross(d, e1)


def _last_link(prev: Link, twist: float) -> Link:
    """The far link, its pull solved (Newton) so its far eye's direction from
    ``prev``'s far eye is FAR_EYE_CENTRE's."""
    start = far_eye(prev)
    want = _unit(_sub(FAR_EYE_CENTRE, start))
    e1, e2 = _basis(want)

    def miss(a: float, b: float) -> tuple[Link, float, float]:
        link = _hang(prev, _unit(_add(want, _add(_scale(e1, a), _scale(e2, b)))), twist)
        got = _unit(_sub(far_eye(link), start))
        return link, _dot(got, e1), _dot(got, e2)

    a = b = 0.0
    step = 1e-7
    for _ in range(30):
        link, fa, fb = miss(a, b)
        if math.hypot(fa, fb) < 1e-13:
            return link
        _, fa_a, fb_a = miss(a + step, b)
        _, fa_b, fb_b = miss(a, b + step)
        j11, j12 = (fa_a - fa) / step, (fa_b - fa) / step
        j21, j22 = (fb_a - fb) / step, (fb_b - fb) / step
        det = j11 * j22 - j12 * j21
        a -= (fa * j22 - fb * j12) / det
        b -= (fb * j11 - fa * j21) / det
    raise AssertionError("keeper chain's far link does not turn onto the ring")


def _strand(low_y: float, twist: float) -> list[Link] | None:
    """Links 0..LINK_COUNT-2 hung along the drape at ``low_y``, each pulled
    toward the drape point one PITCH from the last far eye, then the far link
    aimed at the ring; None when the drape is too short for them."""
    curve = _curve(low_y)
    links = [_LINK_0]
    seg = 0
    for _ in range(1, LINK_COUNT - 1):
        start = far_eye(links[-1])
        found = _crossing(curve, seg, start, PITCH)
        if found is None:
            return None
        point, seg = found
        links.append(_hang(links[-1], _unit(_sub(point, start)), twist))
    links.append(_last_link(links[-1], twist))
    return links


def _solve_drape(twist: float) -> tuple[list[Link], float]:
    """The strand whose far eye lands on FAR_EYE_CENTRE, and the drape's low y.

    The low point is bisected until the far link's far eye closes on it.
    """

    def residual(low_y: float) -> float:
        links = _strand(low_y, twist)
        if links is None:
            return -PITCH  # drape too short: the walk ran off its end
        return _dist(far_eye(links[-2]), FAR_EYE_CENTRE) - _dist(
            far_eye(links[-2]), far_eye(links[-1])
        )

    hi = min(STANDING_EYE_CENTRE[1], _LAST_NEAR[1]) - 1.0
    lo = hi - 120.0
    if residual(lo) <= 0.0 or residual(hi) >= 0.0:
        raise AssertionError("keeper chain's strand does not close on the ring")
    for _ in range(50):
        mid = (lo + hi) / 2.0
        if residual(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    low_y = (lo + hi) / 2.0
    links = _strand(low_y, twist)
    if links is None or _dist(far_eye(links[-1]), FAR_EYE_CENTRE) > 1e-6:
        raise AssertionError("keeper chain's strand closure bisected onto a run-off edge")
    return links, low_y


def _end_twist(links: list[Link]) -> float:
    """Angle about the far link's axis from its far normal to the ring wire's
    run (z made square to the axis), folded into (-90, 90] deg: the far eye
    must lie square to the wire it hangs on."""
    last = links[-1]
    target = _unit(_sub(_Z, _scale(last.axis, _dot(_Z, last.axis))))
    angle = math.atan2(_dot(_cross(last.far_normal, target), last.axis), _dot(last.far_normal, target))
    while angle <= -math.pi / 2.0:
        angle += math.pi
    while angle > math.pi / 2.0:
        angle -= math.pi
    return angle


def _solve_twist() -> tuple[list[Link], float, float]:
    """The even joint twist that turns the far eye square to the ring's wire.

    The eyes interlock loosely, so each joint takes an equal share of the
    twist the strand needs between the flat end link and the ring (secant).
    """
    t0, t1 = 0.0, math.radians(1.0)
    e0 = _end_twist(_solve_drape(t0)[0])
    for _ in range(30):
        links, low_y = _solve_drape(t1)
        e1 = _end_twist(links)
        if abs(e1) < 1e-10:
            return links, low_y, t1
        t0, t1, e0 = t1, t1 - e1 * (t1 - t0) / (e1 - e0), e1
    raise AssertionError("keeper chain's far eye does not turn square to the ring wire")


_LINKS, DRAPE_LOW_Y, JOINT_TWIST = _solve_twist()
JOINT_TWIST_DEG = math.degrees(JOINT_TWIST)
LINKS: tuple[Link, ...] = tuple(_LINKS)


def eye_circle(centre: Vec, normal: Vec, axis: Vec, samples: int = 72) -> list[Vec]:
    """An eye's wire centreline: radius EYE_MEAN_R about ``centre`` in the
    plane of ``axis`` and normal x axis."""
    side = _cross(normal, axis)
    return [
        _add(
            centre,
            _add(
                _scale(axis, EYE_MEAN_R * math.cos(2.0 * math.pi * k / samples)),
                _scale(side, EYE_MEAN_R * math.sin(2.0 * math.pi * k / samples)),
            ),
        )
        for k in range(samples)
    ]


def neck_ends(link: Link) -> tuple[Vec, Vec]:
    """The neck's ends, on the two eyes' wire centrelines."""
    half = NECK_LEN / 2.0
    return _sub(link.centre, _scale(link.axis, half)), _add(link.centre, _scale(link.axis, half))


def _neck_points(link: Link, samples: int = 8) -> list[Vec]:
    a, b = neck_ends(link)
    return [_add(a, _scale(_sub(b, a), k / samples)) for k in range(samples + 1)]


def _link_parts(link: Link) -> dict[str, list[Vec]]:
    return {
        "near": eye_circle(near_eye(link), link.near_normal, link.axis),
        "far": eye_circle(far_eye(link), link.far_normal, link.axis),
        "neck": _neck_points(link),
    }


def _seg_point_dist(p: Vec, a: Vec, b: Vec) -> float:
    d = _sub(b, a)
    t = max(0.0, min(1.0, _dot(_sub(p, a), d) / _dot(d, d)))
    return _dist(p, _add(a, _scale(d, t)))


def _polyline_dist(p: Vec, pts: list[Vec]) -> float:
    return min(_seg_point_dist(p, pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def _ring_circle(mean_r: float, centre: Vec, samples: int = 144) -> list[Vec]:
    """A ring's wire centreline: radius ``mean_r`` about ``centre`` in the
    plane of RING_HANG and machine z."""
    return [
        _add(
            centre,
            (
                RING_HANG[0] * mean_r * math.cos(2.0 * math.pi * k / samples),
                RING_HANG[1] * mean_r * math.cos(2.0 * math.pi * k / samples),
                mean_r * math.sin(2.0 * math.pi * k / samples),
            ),
        )
        for k in range(samples + 1)
    ]


_RING_CENTRELINE = _ring_circle(MEAN_R, RING_CENTRE, samples=720)


def _pin_radius_at(x: float) -> float:
    s = (x - PIN_X0) / PIN_LENGTH
    return (BIG_END_DIA - (BIG_END_DIA - SMALL_END_DIA) * s) / 2.0


def _screw_gaps(p: Vec, r: float) -> tuple[float, float]:
    """Air from a sphere of radius r at p to the anchor screw's head and shank."""
    x, y, z = p
    radial = math.hypot(x - SCREW_XY[0], y - SCREW_XY[1])
    drs = max(0.0, radial - screw.HEAD_DIA / 2.0)
    dzs = max(0.0, SCREW_HEAD_Z - screw.HEAD_H - z, z - SCREW_HEAD_Z)
    head = math.hypot(drs, dzs) - r
    shank_z = (SCREW_HEAD_Z, SCREW_HEAD_Z + screw.SHANK_LEN)
    drk = max(0.0, radial - screw.SHANK_DIA / 2.0)
    dzk = max(0.0, shank_z[0] - z, z - shank_z[1])
    shank = math.hypot(drk, dzk) - r
    return head, shank


def _solid_gap(p: Vec, r: float) -> dict[str, float]:
    """Air from a sphere of radius r at p to each rigid neighbour."""
    x, y, z = p
    gaps: dict[str, float] = {}
    gaps["arm"] = _arm_gap(p) - r
    # Hub barrel.
    dr = max(0.0, math.hypot(x, y) - HUB_R)
    dzh = max(0.0, HUB_Z[0] - z, z - HUB_Z[1])
    gaps["hub"] = math.hypot(dr, dzh) - r if math.hypot(x, y) >= HUB_R or dzh > 0.0 else -r
    # Taper pin (conical; radius sampled at the nearest station).
    xs = max(PIN_X0, min(PIN_X0 + PIN_LENGTH, x))
    dxp = abs(x - xs)
    drp = max(0.0, math.hypot(y, z - PIN_Z) - _pin_radius_at(xs))
    gaps["pin"] = math.hypot(dxp, drp) - r
    gaps["screw"] = min(_screw_gaps(p, r))
    gaps["ring"] = _polyline_dist(p, _RING_CENTRELINE) - RING_WIRE_DIA / 2.0 - r
    return gaps


def thread_air(a: Link, b: Link, samples: int = 180) -> float:
    """Air between ``a``'s far eye and the next link ``b``'s near eye, which
    it threads: the joint's designed contact, left AIR."""
    far = eye_circle(far_eye(a), a.far_normal, a.axis, samples)
    near = eye_circle(near_eye(b), b.near_normal, b.axis, samples)
    return min(_dist(p, q) for p in far for q in near) - WIRE_DIA


@functools.cache
def _clearances() -> tuple[tuple[str, float], ...]:
    worst: dict[str, float] = {}

    def note(key: str, value: float) -> None:
        worst[key] = min(worst.get(key, math.inf), value)

    parts = [_link_parts(link) for link in LINKS]
    last = len(LINKS) - 1
    for i, link_parts in enumerate(parts):
        for name, points in link_parts.items():
            # The screw eye and the neck's root under the head are the clamp.
            clamped = i == 0 and name in ("near", "neck")
            threaded = i == last and name == "far"
            for p in points:
                for key, gap in _solid_gap(p, WIRE_R).items():
                    if key == "screw" and clamped:
                        note("screw-shank", _screw_gaps(p, WIRE_R)[1])
                    elif key == "ring" and threaded:
                        note("ring-thread", gap)
                    else:
                        note(key, gap)
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            for name_i, points_i in parts[i].items():
                for name_j, points_j in parts[j].items():
                    if j == i + 1 and (name_i, name_j) == ("far", "near"):
                        continue  # the joint itself: thread_air
                    for p in points_i:
                        for q in points_j:
                            note("link-link", _dist(p, q) - WIRE_DIA)
    for a, b in zip(LINKS, LINKS[1:]):
        note("link-thread", thread_air(a, b))
    return tuple(worst.items())


def clearance_report() -> dict[str, float]:
    """Smallest air (mm) per contact class; every value must be >= 0.

    Every link's wire against the arm, hub, pin, ring and screw, and against
    every other link. Three designed contacts are proved on their own: the
    end link's screw eye and neck root, clamped by the head, against the
    shank only ("screw-shank"); the far link's far eye against the ring wire
    it hangs on ("ring-thread"); and each joint's two interlocked eyes
    ("link-thread"), all left AIR or more.
    """
    return dict(_clearances())


# The purchased-part identification sheet (build_purchased_part_drawing):
# the cut is the note; it carries no dimension (#290).
CHAIN_DRAWING_NOTES = f"CUT TO {LINK_COUNT} LINKS."

# The chain part's own frame: machine axes, origin on link 0's centre. The
# drive train places it at the crank frame plus CHAIN_PART_ORIGIN.
CHAIN_PART_ORIGIN: Vec = LINKS[0].centre
CHAIN_PART_LINKS: tuple[Link, ...] = tuple(
    link._replace(centre=_sub(link.centre, CHAIN_PART_ORIGIN)) for link in LINKS
)
