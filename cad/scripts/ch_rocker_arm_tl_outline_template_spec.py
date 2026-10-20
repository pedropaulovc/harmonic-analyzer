r"""Pure-data contract for the rocker arm's outline template (MHA-CH-06-TL-13).

Shop gauge, not a machine part (cad/docs/subsystem-identities.md). An annealed
O1 plate carrying the rocker arm's finished outline: the R800 top and R816
bottom arcs about the pivot, the radial tip lands and the tapered ends, plus a
locating hole for a pin gauge in the arm's reamed pivot bore and a radial slot
for a second pin gauge in its rod-pin hole, which clocks it. The arm is
scribed from it (S5) and its outline is checked against it (S7: top-edge
height, radii, arc lengths, tip lands).

Every edge derives from the rocker's own CAD source (``ch_rocker_arm_spec``),
never from a render. The one deliberate offset: every edge aims at the middle
of the rocker's 0.5 surface-profile zone (``ch_rocker_arm_spec.TOP_EDGE_BAND``,
outside on the top arc, inside on the lower outline), leaving the zone's whole
width to the filing that follows. The arc system sits 0.25 higher, on the
trammel's own radii; the tip lands and tapered ends are offset 0.25 along
their own normals, since a +Y shift would carry the near-vertical lands out
of the lower zone.

Frame: origin on the pivot-hole axis in the face laid on the arm, +Y toward
the arcs' common centre (the mirror line is the Y axis), +X toward the
rocker's connecting-rod end, the plate Z0..THICK.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_spec as rocker
from _hole_spec import blind_cut_dia_mm
from _printed_tolerance import printed_band_mm, printed_deviations

R_TOP = rocker.R_TOP
R_BOTTOM = rocker.R_BOTTOM
_ROCKER_ZONE = rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]

# The aim: the middle of the rocker's one-sided top-edge band.
_ROCKER_TOP_LOW = rocker.TOP_EDGE_ABOVE_PIVOT + rocker.TOP_EDGE_BAND[1]
_ROCKER_TOP_HIGH = rocker.TOP_EDGE_ABOVE_PIVOT + rocker.TOP_EDGE_BAND[0]
TOP_ABOVE_PIVOT = round((_ROCKER_TOP_LOW + _ROCKER_TOP_HIGH) / 2.0, 2)  # 8.25
CENTER_Y = TOP_ABOVE_PIVOT + R_TOP  # 808.25
BOTTOM_BELOW_PIVOT = round(R_BOTTOM - CENTER_Y, 2)  # 7.75
# The rocker's bottom arc rides the same concentric zone: its nominal sits
# ARM_DEPTH under the top arc, and the band moves both arcs together.
_ROCKER_BOTTOM_BELOW = rocker.ARM_DEPTH - rocker.TOP_EDGE_ABOVE_PIVOT  # 8.0
_ROCKER_BOTTOM_LOW = _ROCKER_BOTTOM_BELOW - rocker.TOP_EDGE_BAND[0]
_ROCKER_BOTTOM_HIGH = _ROCKER_BOTTOM_BELOW - rocker.TOP_EDGE_BAND[1]
if abs(R_BOTTOM - R_TOP - rocker.ARM_DEPTH) > 1e-9:
    raise AssertionError("rocker arcs are no longer ARM_DEPTH apart")
if abs(TOP_ABOVE_PIVOT + BOTTOM_BELOW_PIVOT - rocker.ARM_DEPTH) > 1e-9:
    raise AssertionError(
        "template arcs are no longer ARM_DEPTH apart on the mirror line"
    )
if (
    abs(
        rocker.CENTER_Y
        - rocker.PIVOT_MID_Y
        + (TOP_ABOVE_PIVOT - rocker.TOP_EDGE_ABOVE_PIVOT)
        - CENTER_Y
    )
    > 1e-9
):
    raise AssertionError(
        "template arc centre is not the rocker's, raised by the aim offset"
    )

# Shop acceptance (inventory gauges.arm-outline-template, Pedro 2026-10-11):
# DTI stations within +/-0.03 of nominal, taken about the pivot hole and the
# rod slot (below) with pins in both.
DTI_ACCEPTANCE = 0.03
# The sheet fixes each arc by its low point on the mirror line, measured from
# the pin gauge in the hole, and prints its radius at the title block's .XX
# band. The centre sits on the pivot centreline, so the low point and the
# radius pin the whole arc; the end stations below check that the radius
# band, carried out to the arc ends, stays inside DTI_ACCEPTANCE.
LOW_POINT_BAND = (0.02, -0.02)
APEX_PLACES = 2
RADIUS_PLACES = 2
for _low, _high, _nominal in (
    (_ROCKER_TOP_LOW, _ROCKER_TOP_HIGH, TOP_ABOVE_PIVOT),
    (_ROCKER_BOTTOM_LOW, _ROCKER_BOTTOM_HIGH, BOTTOM_BELOW_PIVOT),
):
    if not _low < _nominal + LOW_POINT_BAND[1] < _nominal + LOW_POINT_BAND[0] < _high:
        raise AssertionError("template low-point band leaves the rocker's arc zone")
    # The gauge spends at most a quarter of the zone it sets.
    if LOW_POINT_BAND[0] - LOW_POINT_BAND[1] > 0.25 * (_high - _low) + 1e-9:
        raise AssertionError(
            "template low-point band spends more than a quarter of the rocker zone"
        )

# The rocker's lower outline (the R816 arc, both tapers and both tip lands,
# between J and K) is one 0.5 Ⓤ0 surface profile: the zone lies wholly inside
# the material, so its middle is half the zone in from the BASIC outline along
# each segment's own normal. A rigid +Y shift is mid-zone on the arcs only: it
# put each tip land 0.0453 OUTSIDE that zone (#1544). So the straight edges are
# offset along their own normals instead, through the three printed stations:
# the top-arc end, the tip-land length and the bottom-arc end. The arcs stay
# on the trammel's R800/R816 about CENTER_Y (MHA-CH-06-TL-14..19 scribe them).
_MID_ZONE = _ROCKER_ZONE / 2.0  # 0.25 into the material on the lower outline
END_PLACES = 3
_ROCKER_CENTRE = (0.0, rocker.CENTER_Y - rocker.PIVOT_MID_Y)
_ROCKER_MIDDLE = (0.0, _ROCKER_CENTRE[1] - (R_TOP + R_BOTTOM) / 2.0)


def _inward(
    start: tuple[float, float], end: tuple[float, float]
) -> tuple[float, float]:
    """Unit normal of start -> end toward the arm's material."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    normal = (-dy / length, dx / length)
    side = (_ROCKER_MIDDLE[0] - start[0]) * normal[0] + (
        _ROCKER_MIDDLE[1] - start[1]
    ) * normal[1]
    return normal if side > 0.0 else (-normal[0], -normal[1])


def _offset(
    points: tuple[tuple[float, float], ...], by: float
) -> tuple[tuple[float, float], ...]:
    normal = _inward(points[0], points[-1])
    return tuple((x + by * normal[0], y + by * normal[1]) for x, y in points)


def _crossing(
    p: tuple[float, float],
    d: tuple[float, float],
    q: tuple[float, float],
    e: tuple[float, float],
) -> tuple[float, float]:
    s = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / (d[0] * e[1] - d[1] * e[0])
    return (p[0] + s * d[0], p[1] + s * d[1])


# The rocker's BASIC +X land (radial from its top-arc end) and taper, pivot frame.
_ROCKER_TOP_END = (
    R_TOP * math.sin(rocker._ALPHA_TOP),
    _ROCKER_CENTRE[1] - R_TOP * math.cos(rocker._ALPHA_TOP),
)
_ROCKER_TIP = (
    _ROCKER_TOP_END[0] + rocker.TIP_FACE * math.sin(rocker._ALPHA_TOP),
    _ROCKER_TOP_END[1] - rocker.TIP_FACE * math.cos(rocker._ALPHA_TOP),
)
_ROCKER_BOT_END = (
    rocker.BOT_END_X,
    _ROCKER_CENTRE[1] - math.sqrt(R_BOTTOM**2 - rocker.BOT_END_X**2),
)
ROCKER_LAND = (_ROCKER_TOP_END, _ROCKER_TIP)
ROCKER_TAPER = (_ROCKER_TIP, _ROCKER_BOT_END)
_LAND_AIM = _offset(ROCKER_LAND, _MID_ZONE)
_TAPER_AIM = _offset(ROCKER_TAPER, _MID_ZONE)
_TAPER_DIRECTION = (
    _TAPER_AIM[1][0] - _TAPER_AIM[0][0],
    _TAPER_AIM[1][1] - _TAPER_AIM[0][1],
)
# The land stays radial to CENTER_Y (the sketch's relation), aimed through its
# mid-zone line's middle; the half-angles are re-derived from the rounded
# stations so the sketch closes exactly.
_LAND_AIM_MIDDLE = tuple((a + b) / 2.0 for a, b in zip(*_LAND_AIM, strict=True))
TOP_END_X = round(
    R_TOP
    * _LAND_AIM_MIDDLE[0]
    / math.hypot(_LAND_AIM_MIDDLE[0], _LAND_AIM_MIDDLE[1] - CENTER_Y),
    END_PLACES,
)  # 144.951
ALPHA_TOP = math.asin(TOP_END_X / R_TOP)
TOP_END_Y = CENTER_Y - R_TOP * math.cos(ALPHA_TOP)  # 21.491
_LAND_DIRECTION = (math.sin(ALPHA_TOP), -math.cos(ALPHA_TOP))
# Each tip land runs radially outward from the top arc's end to the mid-zone
# taper; the tapered end runs from its foot to the bottom arc's end.
TIP_FACE = round(
    math.dist(
        (TOP_END_X, TOP_END_Y),
        _crossing(
            (TOP_END_X, TOP_END_Y), _LAND_DIRECTION, _TAPER_AIM[0], _TAPER_DIRECTION
        ),
    ),
    END_PLACES,
)  # 5.699
TIP_X = TOP_END_X + TIP_FACE * _LAND_DIRECTION[0]  # 145.984
TIP_Y = TOP_END_Y + TIP_FACE * _LAND_DIRECTION[1]  # 15.887


def _taper_meets_bottom_arc() -> float:
    """X where the mid-zone taper line meets the template's bottom arc."""
    length = math.hypot(*_TAPER_DIRECTION)
    ex, ey = _TAPER_DIRECTION[0] / length, _TAPER_DIRECTION[1] / length
    fx, fy = _TAPER_AIM[0][0], _TAPER_AIM[0][1] - CENTER_Y
    b = fx * ex + fy * ey
    along = -b + math.sqrt(b * b - (fx * fx + fy * fy - R_BOTTOM**2))
    return _TAPER_AIM[0][0] + along * ex


BOT_END_X = round(_taper_meets_bottom_arc(), END_PLACES)  # 132.636
ALPHA_BOT = math.asin(BOT_END_X / R_BOTTOM)
BOT_END_Y = CENTER_Y - R_BOTTOM * math.cos(ALPHA_BOT)  # 3.102
# With the centre on the pivot centreline and the low point held, a radius
# error dR moves the edge at station x by dR x^2 / (2 R^2): at the end
# stations that drift plus the low-point band stays inside the DTI acceptance.
END_STATION_DRIFT: dict[str, float] = {}
for _name, _radius, _station in (
    ("top", R_TOP, TOP_END_X),
    ("bottom", R_BOTTOM, BOT_END_X),
):
    _lower, _upper = printed_deviations(_radius, RADIUS_PLACES)
    END_STATION_DRIFT[_name] = (
        max(-_lower, _upper) * _station**2 / (2.0 * _radius**2)
    )  # top 0.0084, bottom 0.0067
    if END_STATION_DRIFT[_name] + LOW_POINT_BAND[0] > DTI_ACCEPTANCE + 1e-9:
        raise AssertionError(
            f"title-block {_name} radius band carries the arc end outside the DTI acceptance"
        )


# The arcs' one residual: R800/R816 about CENTER_Y are _MID_ZONE toward the
# centre from the rocker's arcs on the mirror line only; at angle phi off it
# they fall short of mid-zone by about _MID_ZONE (1 - cos phi), most at the arc
# ends. Exactly: a template-arc point's distance from the rocker's centre,
# less the rocker radius, plus _MID_ZONE (both arcs' mid-zone lies centreward).
def arc_mid_zone_residual(radius: float, x: float) -> float:
    """Template arc ``radius`` at station ``x``: its edge's offset from mid-zone."""
    y = CENTER_Y - math.sqrt(radius**2 - x**2)
    return math.hypot(x, y - _ROCKER_CENTRE[1]) - radius + _MID_ZONE


ARC_MID_ZONE_RESIDUAL = {
    "top": arc_mid_zone_residual(R_TOP, TOP_END_X),  # 0.0041
    "bottom": arc_mid_zone_residual(R_BOTTOM, BOT_END_X),  # 0.0033
}
for _name, _residual in ARC_MID_ZONE_RESIDUAL.items():
    if not 0.0 <= _residual <= END_STATION_DRIFT[_name] + 1e-9:
        raise AssertionError(
            f"the {_name} arc's mid-zone residual exceeds its budgeted end drift"
        )
# The end stations print at three places: their band is about a quarter of
# the rocker's own two-place band on the same ends.
if printed_band_mm(END_PLACES) > 0.26 * printed_band_mm(2):
    raise AssertionError(
        "template end-station band spends more than a quarter of the rocker's"
    )

# Pivot locating hole: the rocker's Ø6.5 bore, reamed to H7 (+0.015/0) so
# one bought 0.2558 in Class X minus pin gauge (inventory
# gauges.vermont-class-x-2558-minus: 0.25576-0.25580 in, 6.4963-6.4973)
# locates it in the arm's bore. The shop's 0.001 in Class ZZ set stops at
# 0.2550, whose play alone is 0.0505; auto-selected 2026-10-15 after review
# timeout, Pedro may revisit.
PIVOT_HOLE_DIA = rocker.PIVOT_HOLE_DIA
PIVOT_HOLE_BAND = (0.015, 0.0)
PIVOT_PLACES = 3
PIN_GAUGE_IN = 0.2558
PIN_GAUGE_CLASS_X_IN = 0.00004  # Class X tolerance, minus direction
PIN_GAUGE_MIN = (PIN_GAUGE_IN - PIN_GAUGE_CLASS_X_IN) * 25.4  # 6.4963
PIN_GAUGE_MAX = PIN_GAUGE_IN * 25.4  # 6.4973
# The fit and its mate are named on the bore's own callout.
PIVOT_CALLOUT = f"REAM, SLIP FIT ON PIN GAUGE\n{PIN_GAUGE_IN:.4f} IN, CLASS X MINUS"
# Both arcs' shared centre lies on the pivot bore's vertical centreline,
# CENTER_Y above the bore: off any sheet, so the radius callouts say so.
ARC_CENTER_CALLOUT = "CENTER ON PIVOT CL"
_ROCKER_BORE_LOW = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1]
_ROCKER_BORE_HIGH = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0]
if PIN_GAUGE_MAX >= PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[1]:
    raise AssertionError("pin gauge does not enter the template hole")
if PIN_GAUGE_MAX >= _ROCKER_BORE_LOW:
    raise AssertionError("pin gauge does not enter the rocker's pivot bore")
# Two budgets. The low-point band holds the template's own edges about its
# hole (the DTI record checks them against DTI_ACCEPTANCE). Laid on the arm,
# the pin's worst-case play in both bores (each at its largest, the pin at its
# smallest) moves the edges further: low-point band plus that registration
# stays inside the quarter of the rocker's arc zone the gauge may spend,
# centred on the aim (0.02 + 0.0262 = 0.0462 <= 0.0625).
LOCATOR_REGISTRATION_MAX = (
    math.ceil(
        1e4
        * (
            (PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0] - PIN_GAUGE_MIN) / 2.0
            + (_ROCKER_BORE_HIGH - PIN_GAUGE_MIN) / 2.0
        )
    )
    / 1e4
)  # 0.0262 = 0.0094 template + 0.0169 rocker, rounded up
# The aim spends a quarter of the zone (_ROCKER_ZONE, above) at most.
if LOW_POINT_BAND[0] + LOCATOR_REGISTRATION_MAX > 0.25 * _ROCKER_ZONE / 2.0 + 1e-9:
    raise AssertionError(
        "pin-gauge play in both bores plus the low-point band spends more than a"
        " quarter of the rocker zone"
    )

# Rod-pin slot: the template's clocking. The rocker's datum C is its #47
# rod-pin hole (MHA-CH-06, Ø0.20 position to A|B). The pivot pin alone
# leaves the template free to turn about the pivot; a fixed pin gauge in the
# arm's rod-pin hole, through a slot here at that hole's BASIC station,
# clocks it. The slot runs radially from the pivot, so the hole's radial
# position error and the pin's play only slide the pin along it: the slot's
# width alone sets the clocking. The station prints BASIC, as on the rocker,
# and the template's profile acceptance (DTI_ACCEPTANCE) is taken about the
# pivot hole and this slot with pins in both.
ROD_SLOT_PLACES = 3
ROD_SLOT_X = round(rocker.ROD_HOLE_X, ROD_SLOT_PLACES)  # 133.067 BASIC
ROD_SLOT_Y = round(rocker.ROD_HOLE_Y - rocker.PIVOT_MID_Y, ROD_SLOT_PLACES)  # 8.456
ROD_SLOT_LEVER = math.hypot(ROD_SLOT_X, ROD_SLOT_Y)  # 133.335
ROD_SLOT_AXIS = (ROD_SLOT_X / ROD_SLOT_LEVER, ROD_SLOT_Y / ROD_SLOT_LEVER)
_ROD_SLOT_TANGENT = (-ROD_SLOT_AXIS[1], ROD_SLOT_AXIS[0])
# The pin: the largest of the shop's 0.001 in Class ZZ minus set
# (gauges.pin-gauges; ASME B89.1.5 Class ZZ is 0.0002 in at this size) that
# enters the #47 hole at its drilled minimum.
ROD_PIN_GAUGE_IN = 0.0780
ROD_PIN_CLASS_ZZ_IN = 0.0002
ROD_PIN_MAX = ROD_PIN_GAUGE_IN * 25.4  # 1.98120
ROD_PIN_MIN = (ROD_PIN_GAUGE_IN - ROD_PIN_CLASS_ZZ_IN) * 25.4  # 1.97612
# The rocker's #47 hole at the title block's drilled-hole band (native specs
# read the band directly: _printed_limits is drawing/feature-only).
_DRILLED = _config.title_block("drilled_hole")
_ROD_HOLE_DIA = blind_cut_dia_mm(rocker.ROD_HOLE_SPEC)
_ROD_HOLE_LOW = _ROD_HOLE_DIA - float(_DRILLED["minus_mm"])  # 1.994
_ROD_HOLE_HIGH = _ROD_HOLE_DIA + float(_DRILLED["plus_mm"])  # 2.094
if not ROD_PIN_MAX < _ROD_HOLE_LOW <= (ROD_PIN_GAUGE_IN + 0.001) * 25.4:
    raise AssertionError("the rod-hole pin is no longer the set's largest that enters")
# The slot is an H7 width on that pin (ISO 286, 1-3 mm: +0.010/0), printed as
# a matched fit: its reference width and the clearance on the pin.
ROD_SLOT_WIDTH = 1.983
ROD_SLOT_WIDTH_BAND = (0.010, 0.0)  # (upper, lower)
ROD_SLOT_WIDTH_MAX = ROD_SLOT_WIDTH + ROD_SLOT_WIDTH_BAND[0]
ROD_SLOT_CLEARANCE = (
    math.floor((ROD_SLOT_WIDTH - ROD_PIN_MAX) * 1e3 + 1e-9) / 1e3,
    math.ceil((ROD_SLOT_WIDTH_MAX - ROD_PIN_MIN) * 1e3 - 1e-9) / 1e3,
)  # 0.001-0.017: the true limits 0.0018-0.0169, rounded outward
if ROD_SLOT_CLEARANCE[0] <= 0.0:
    raise AssertionError("the rod-hole pin does not enter the smallest slot")
ROD_SLOT_CALLOUT = (
    f"{ROD_SLOT_CLEARANCE[0]:.3f}-{ROD_SLOT_CLEARANCE[1]:.3f} DIAMETRAL\n"
    f"CLEARANCE ON PIN GAUGE\n{ROD_PIN_GAUGE_IN:.4f} IN (CLASS ZZ MINUS)"
)
# The flat (end-centre run) lets the pin in wherever the rocker puts its hole
# radially (half its Ø0.20 position zone), plus the pin's play in that hole,
# plus a three-place title-block band for where the slot itself lands along
# its radial (its station is BASIC, so the print sets no band there: the
# pin entering on a good arm is the functional check). The run is printed at
# three places, so its minimum is what must reach.
ROD_HOLE_RADIAL = float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"]) / 2.0
ROD_HOLE_PLAY = (_ROD_HOLE_HIGH - ROD_PIN_MIN) / 2.0  # 0.0589
ROD_SLOT_PLAY = (ROD_SLOT_WIDTH_MAX - ROD_PIN_MIN) / 2.0  # 0.0084
ROD_SLOT_FLAT = 0.75
if (ROD_SLOT_FLAT - printed_band_mm(ROD_SLOT_PLACES)) / 2.0 < (
    ROD_HOLE_RADIAL + ROD_HOLE_PLAY + printed_band_mm(ROD_SLOT_PLACES)
):
    raise AssertionError("the rod slot's run no longer lets the pin in")
# Clocking budget. A template laid on the arm moves rigidly: the pivot pin
# lets it shift by up to LOCATOR_REGISTRATION_MAX, and the rod pin lets the
# slot's centre move across the slot by up to ROD_CLOCKING_PLAY (its play in
# the rocker's hole and in the slot, plus the BASIC station's rounding off
# the rocker's hole). For an edge point p with unit normal n, the rotation
# that the slot allows is (e - d.t)/lever, where d is the pivot shift, e the
# cross-slot shift and t the slot's cross direction, so the edge moves
#     d.(n - g t) + g e,  g = (z x p).n / lever,
# at most |n - g t| LOCATOR_REGISTRATION_MAX + |g| ROD_CLOCKING_PLAY, plus the
# template's own DTI_ACCEPTANCE. The lever arm g reaches 1.10 at the tail end,
# whose top end is the worst station (top ends -X 0.159, +X 0.108; bottom
# ends 0.148 / 0.099; tapers 0.134 / 0.106; tip lands 0.062 / 0.062; apex 0.057).
_ROD_SLOT_ROUNDING = abs(
    (ROD_SLOT_X - rocker.ROD_HOLE_X) * _ROD_SLOT_TANGENT[0]
    + (ROD_SLOT_Y - (rocker.ROD_HOLE_Y - rocker.PIVOT_MID_Y)) * _ROD_SLOT_TANGENT[1]
)
ROD_CLOCKING_PLAY = ROD_HOLE_PLAY + ROD_SLOT_PLAY + _ROD_SLOT_ROUNDING  # 0.0674
# The template's share of the rocker's half-zone (0.25 either side of the
# aim): a template-gauge allocation, not a part tolerance. The other 0.09 is
# left to filing to the scribed line (#1545, approved 2026-10-15).
END_STATION_SHARE = 0.16


def clocking_error(
    point: tuple[float, float], normal: tuple[float, float], play: float | None = None
) -> float:
    """Worst normal error of an outline point laid on the arm (unit ``normal``):
    the template's own acceptance plus the rigid motion the two pins allow.
    ``play`` overrides the cross-slot play (a round hole's, in the tests)."""
    cross = ROD_CLOCKING_PLAY if play is None else play
    gain = (point[0] * normal[1] - point[1] * normal[0]) / ROD_SLOT_LEVER
    pivot = math.hypot(
        normal[0] - gain * _ROD_SLOT_TANGENT[0], normal[1] - gain * _ROD_SLOT_TANGENT[1]
    )
    return DTI_ACCEPTANCE + pivot * LOCATOR_REGISTRATION_MAX + abs(gain) * cross


# Plate: O1 ground flat stock, 1/8 in, thickness as supplied.
THICK = 3.175
THICK_PLACES = 3
THICK_CALLOUT = "GROUND FLAT STOCK"
# drawing-guidelines.md rule 17 (walls and webs): the thinnest web, between the hole and the bottom arc.
WEB_MIN = round(
    BOTTOM_BELOW_PIVOT
    + LOW_POINT_BAND[1]
    - (PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0]) / 2.0,
    4,
)
if min(WEB_MIN, THICK - printed_band_mm(THICK_PLACES)) < 1.5 - 1e-9:
    raise AssertionError(
        "outline template falls under the drawing-guidelines.md rule 17 (walls and webs) floor"
    )


def outline_points(n: int = 200) -> list[tuple[float, float]]:
    """The closed outline, bottom arc rod->tail, tail tip, top arc tail->rod, rod tip."""
    points: list[tuple[float, float]] = []
    for i in range(n + 1):
        a = ALPHA_BOT - 2.0 * ALPHA_BOT * i / n
        points.append((R_BOTTOM * math.sin(a), CENTER_Y - R_BOTTOM * math.cos(a)))
    points.append((-TIP_X, TIP_Y))
    for i in range(n + 1):
        a = -ALPHA_TOP + 2.0 * ALPHA_TOP * i / n
        points.append((R_TOP * math.sin(a), CENTER_Y - R_TOP * math.cos(a)))
    points.append((TIP_X, TIP_Y))
    return points


def outline_area() -> float:
    """Shoelace area of the outline (no hole), exact enough for the volume gate."""
    points = outline_points()
    area = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def rod_slot_points(
    width: float = ROD_SLOT_WIDTH, flat: float = ROD_SLOT_FLAT
) -> tuple[tuple[float, float], ...]:
    """The rod slot's stadium, counter-clockwise (the ``add_arc`` sense).

    ``(p1, p2, p3, p4, outer_centre, inner_centre)``: side a runs p1 -> p2 on
    the slot's clockwise side, the outer end arcs about outer_centre from p2
    to p3, side b runs p3 -> p4 and the inner end arcs about inner_centre from
    p4 back to p1 (build_fr_top_frame.slot_stadium_points, turned radial).
    """

    def at(along: float, across: float) -> tuple[float, float]:
        return (
            ROD_SLOT_X + along * ROD_SLOT_AXIS[0] + across * _ROD_SLOT_TANGENT[0],
            ROD_SLOT_Y + along * ROD_SLOT_AXIS[1] + across * _ROD_SLOT_TANGENT[1],
        )

    half_flat, half_width = flat / 2.0, width / 2.0
    return (
        at(-half_flat, -half_width),
        at(half_flat, -half_width),
        at(half_flat, half_width),
        at(-half_flat, half_width),
        at(half_flat, 0.0),
        at(-half_flat, 0.0),
    )


def _segment_distance(
    point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    along = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (
        dx * dx + dy * dy
    )
    along = min(1.0, max(0.0, along))
    return math.dist(point, (start[0] + along * dx, start[1] + along * dy))


def outline_clocking_errors(play: float | None = None) -> list[float]:
    """``clocking_error`` at both ends of every sampled outline segment, each
    with that segment's normal: arcs, tip lands and tapered ends alike."""
    points = outline_points()
    errors: list[float] = []
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        length = math.dist(a, b)
        normal = ((a[1] - b[1]) / length, (b[0] - a[0]) / length)
        errors += [clocking_error(a, normal, play), clocking_error(b, normal, play)]
    return errors


if END_STATION_SHARE >= _ROCKER_ZONE / 2.0:
    raise AssertionError("the template's clocking share leaves nothing for filing")
ROD_CLOCKING_WORST = max(outline_clocking_errors())  # 0.1586, the tail's top end
if ROD_CLOCKING_WORST > END_STATION_SHARE + 1e-9:
    raise AssertionError(
        "pivot and rod-pin play carry an outline edge outside the template's share"
    )


def _rod_slot_web() -> float:
    """drawing-guidelines.md rule 17 (walls and webs): the web between the rod
    slot, at its widest and longest, and the outline at its low-point band.
    The slot's core segment never crosses an outline segment, so their
    distance is the least of the four end-to-segment distances."""
    outer, inner = rod_slot_points(
        ROD_SLOT_WIDTH_MAX, ROD_SLOT_FLAT + printed_band_mm(ROD_SLOT_PLACES)
    )[4:]
    points = outline_points()
    core = min(
        min(
            _segment_distance(outer, a, b),
            _segment_distance(inner, a, b),
            _segment_distance(a, inner, outer),
            _segment_distance(b, inner, outer),
        )
        for a, b in zip(points, points[1:] + points[:1], strict=True)
    )
    return core - ROD_SLOT_WIDTH_MAX / 2.0 - max(-LOW_POINT_BAND[1], LOW_POINT_BAND[0])


ROD_SLOT_WEB_MIN = round(_rod_slot_web(), 4)
if ROD_SLOT_WEB_MIN < 1.5 - 1e-9:
    raise AssertionError(
        "the rod slot falls under the drawing-guidelines.md rule 17 (walls and webs) floor"
    )

ROD_SLOT_AREA = math.pi * (ROD_SLOT_WIDTH / 2.0) ** 2 + ROD_SLOT_FLAT * ROD_SLOT_WIDTH
PLATE_VOLUME = (
    outline_area() - math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 - ROD_SLOT_AREA
) * THICK

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OutlineProfile": {
        "TopRadius",
        "BottomRadius",
        "TopTailX",
        "TopRodX",
        "BottomTailX",
        "BottomRodX",
        "RodTipLen",
        "TailTipLen",
    },
    "ApexReference": {"TopAbovePivot", "BottomBelowPivot"},
    "PivotHoleProfile": {"PivotDia"},
    "Plate": {"Thick"},
    "RodSlotProfile": {"RodSlotWidth", "RodSlotFlat"},
    "RodSlotReference": {"RodSlotX", "RodSlotY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OutlineProfile": {
        "TopRadius": RADIUS_PLACES,
        "BottomRadius": RADIUS_PLACES,
        "TopTailX": END_PLACES,
        "TopRodX": END_PLACES,
        "BottomTailX": END_PLACES,
        "BottomRodX": END_PLACES,
        "RodTipLen": END_PLACES,
        "TailTipLen": END_PLACES,
    },
    "ApexReference": {"TopAbovePivot": APEX_PLACES, "BottomBelowPivot": APEX_PLACES},
    "PivotHoleProfile": {"PivotDia": PIVOT_PLACES},
    "Plate": {"Thick": THICK_PLACES},
    "RodSlotProfile": {
        "RodSlotWidth": ROD_SLOT_PLACES,
        "RodSlotFlat": ROD_SLOT_PLACES,
    },
    "RodSlotReference": {
        "RodSlotX": ROD_SLOT_PLACES,
        "RodSlotY": ROD_SLOT_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError(
        "every marked outline-template dimension needs authored places"
    )
# Bands other than the title block's, keyed (feature, dimension).
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("ApexReference", "TopAbovePivot"): LOW_POINT_BAND,
    ("ApexReference", "BottomBelowPivot"): LOW_POINT_BAND,
    ("PivotHoleProfile", "PivotDia"): PIVOT_HOLE_BAND,
}
# The rod slot's station is BASIC (the rocker's datum C, at its BASIC
# station); its width is the reference nominal of a matched fit on its pin.
BASIC_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("RodSlotReference", "RodSlotX"),
    ("RodSlotReference", "RodSlotY"),
)
REFERENCE_DIMENSIONS = frozenset({"RodSlotWidth"})
# The slot runs radially from the pivot: its station callout says so.
ROD_SLOT_STATION_CALLOUT = "ROD SLOT, RADIAL TO PIVOT"
DETAIL_SCALE = (5, 1)

# The scribing edges' SHARP requirement rides the radius and tip-land
# callouts of the edges it applies to, not a general note.
DRAWING_NOTES = "LAYOUT AND PROFILE GAUGE FOR THE ROCKER ARM."
SHARP_EDGE_CALLOUT = "SHARP EDGE"
# The outline stations and tip lands are the rocker arm's own profile
# stations: the flag names that function at each three-place callout.  The
# stations also name the rocker's drawing; the tip lands sit between the
# sheet border and the station extension lines, with room for the short flag
# only.
PROFILE_CALLOUT = "ROCKER PROFILE"
ROCKER_NUMBER = "MHA-CH-06"
STATION_CALLOUT = f"{PROFILE_CALLOUT}, {ROCKER_NUMBER}"
# The run's function (its three-place minimum is what must reach), no method.
ROD_SLOT_FLAT_CALLOUT = f"PIN REACH TO ROD-PIN\nHOLE, {ROCKER_NUMBER}"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:4"

# The #1413 placeholder provenance every solid carries: ``by`` is
# _process_plans.PLACEHOLDER_BY verbatim (test_process_shop pins the spelling)
# and bind_shop refuses a solid without a measured status (#1462).
_MEASURED = {
    "status": "measured",
    "by": "placeholder (realistic, remeasure: #1413)",
    "date": "2026-10-12",
    "instrument": (
        "digital calipers, height gauge and indicator; physical component sizes/fit only"
    ),
}
# prechips models a fixture as boxes and cylinders only, so the bound shop
# inventory carries the plate's envelope (its outline's extents by the plate
# thickness) with the pivot hole and the rod slot's pin seat as voids, in
# this module's frame.
PRECHIPS_SOLIDS: list[dict[str, object]] = [
    {
        "name": "plate",
        "supply": "made",
        "shape": "box",
        "at_mm": [round(-TIP_X, 3), round(-BOTTOM_BELOW_PIVOT, 3), 0.0],
        "size_mm": [
            round(2.0 * TIP_X, 3),
            round(TOP_END_Y + BOTTOM_BELOW_PIVOT, 3),
            THICK,
        ],
        "note": "outline envelope; the arcs, tip lands and tapered ends are inside it",
        "measured": dict(_MEASURED),
    },
    {
        "name": "pivot-hole",
        "shape": "cylinder",
        "void": True,
        "at_mm": [0.0, 0.0, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": PIVOT_HOLE_DIA,
        "length_mm": THICK,
        "locates": "pin gauge in the rocker's pivot bore",
        "measured": dict(_MEASURED),
    },
    {
        "name": "rod-slot",
        "shape": "cylinder",
        "void": True,
        "at_mm": [ROD_SLOT_X, ROD_SLOT_Y, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": ROD_SLOT_WIDTH,
        "length_mm": THICK,
        "locates": "pin gauge in the rocker's rod-pin hole (datum C); the radial slot's run is not modelled",
        "measured": dict(_MEASURED),
    },
]
